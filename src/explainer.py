"""One local Agno call turns deterministic findings plus retrieved evidence into prose.

The model explains. It never decides. Rule, package, severity, status, message and
cell all come from the deterministic stage and are passed through untouched.
"""

import json
import os

from agno.agent import Agent
from agno.models.google import Gemini
from agno.models.groq import Groq
from agno.models.ollama import Ollama
from agno.models.openrouter import OpenRouter
from pydantic import BaseModel, Field

from models import AuditResult, Finding

# One audit, one explanation call. No teams, no tool loops, no per-finding calls.
# Defaults chosen by measured comparison in scripts/compare_providers.py, see
# AI_PROVIDER.md. Groq was fastest and the only provider to explain every supplied
# rule. Ollama stays available as an offline local mode.
DEFAULT_PROVIDER = os.getenv("COLABAUDIT_LLM_PROVIDER", "groq")
DEFAULT_MODEL = os.getenv("COLABAUDIT_LLM_MODEL", "openai/gpt-oss-20b")
DEFAULT_HOST = os.getenv("COLABAUDIT_OLLAMA_HOST", "http://localhost:11434")

# A 3B model on CPU will happily ramble for thousands of tokens and get cut off
# mid-JSON, which fails schema validation. Capping generation keeps one call short
# and the output parseable.
MAX_TOKENS = 700

class ProviderError(Exception):
    """A provider returned an error document instead of an explanation."""


SYSTEM_PROMPT = """You explain compatibility risks in an old Google Colab notebook.

You are given deterministic findings produced by a rule engine, and official
documentation retrieved from a curated knowledge base. Both are authoritative.

Rules you must follow:
- Explain only. Never decide whether a finding is valid.
- Never repeat or invent package versions other than the ones given to you.
- Never invent compatibility claims not supported by the supplied evidence.
- Never state or imply that a notebook was executed, or that it will definitely fail.
- Never change a rule id, severity or status. Quote them exactly as given.
- Where evidence is insufficient, say so plainly instead of filling the gap.

Write plainly for a data-science learner. Be brief: at most two sentences for the
summary, one or two sentences per explanation, and one short sentence per list item.
No preamble, no closing remarks."""


class ExplanationResult(BaseModel):
    """Model prose only. No versions, no severities, no status."""

    summary: str = Field(
        description="At most two sentences describing the overall situation."
    )
    explanations: list[str] = Field(
        description=(
            "Exactly one entry per distinct rule id listed in the prompt, in the same "
            "order, each starting with that rule id. Every rule must be explained here. "
            "No more, no fewer."
        )
    )
    recommendations: list[str] = Field(
        description="At most three concrete manual checks, one short sentence each. No fixes."
    )
    limitations: list[str] = Field(
        description=(
            "At most three short sentences on what static analysis cannot establish. "
            "Do not explain any rule here; rules are explained in 'explanations'."
        )
    )


def build_model(provider: str = DEFAULT_PROVIDER, model: str = DEFAULT_MODEL):
    """Return the configured model.

    Plain configuration-driven selection. Ollama is the local default and needs no
    API key. Groq and Gemini are hosted alternatives that read their key from the
    environment. Unknown provider names are rejected rather than guessed at.
    """
    if provider == "ollama":
        return Ollama(id=model, host=DEFAULT_HOST, options={"num_predict": MAX_TOKENS})
    if provider == "groq":
        return Groq(id=model)
    if provider == "gemini":
        return Gemini(id=model)
    if provider == "openrouter":
        return OpenRouter(id=model)
    raise ValueError(f"Unknown provider: {provider}")


def build_query_for(finding: Finding) -> str:
    """Search query for one finding. Built from deterministic text, not by a model."""
    parts = [finding.rule]

    if finding.package:
        parts.append(finding.package)

    parts.append(finding.message)

    return " ".join(parts)


def distinct_findings(result: AuditResult) -> list[Finding]:
    """Collapse repeated rules so a notebook with 40 R002 findings needs one search.

    The first finding of each rule is kept as the representative example; the
    package list stays in the audit result and in the prompt summary.
    """
    seen = set()
    unique = []

    for finding in result.findings:
        if finding.rule in seen:
            continue
        seen.add(finding.rule)
        unique.append(finding)

    return unique


def collect_evidence(knowledge, result: AuditResult, max_results: int = 3) -> dict[str, list[dict]]:
    """Retrieve evidence per distinct rule. Fully deterministic, no model involved."""
    from knowledge_base import retrieve

    evidence = {}

    for finding in distinct_findings(result):
        query = build_query_for(finding)
        evidence[finding.rule] = retrieve(knowledge, query, max_results=max_results)

    return evidence


def _format_findings(result: AuditResult) -> str:
    lines = []

    for finding in result.findings:
        package = f" [{finding.package}]" if finding.package else ""
        cell = f" cell={finding.cell}" if finding.cell is not None else ""
        lines.append(
            f"- {finding.rule}{package} severity={finding.severity}{cell}: {finding.message}"
        )

    return "\n".join(lines)


def _format_evidence(evidence: dict[str, list[dict]]) -> str:
    blocks = []

    for rule, hits in evidence.items():
        if not hits:
            blocks.append(f"[{rule}]\n(no evidence retrieved)")
            continue

        lines = [f"[{rule}]"]
        for hit in hits:
            lines.append(f"- {hit['title']} | {hit['source']} | {hit['url']}")
            lines.append(f"  {hit['content'][:300]}")
        blocks.append("\n".join(lines))

    return "\n\n".join(blocks)


def build_prompt(result: AuditResult, evidence: dict[str, list[dict]]) -> str:
    """Assemble the single prompt for the explanation call."""
    runtime = result.runtime.snapshot if result.runtime else "none"
    rules_fired = distinct_findings(result)

    return f"""Notebook: {result.notebook_name}
Selected Colab runtime snapshot: {runtime}
Deterministic status: {result.status}

RULES THAT FIRED, in order: {", ".join(f.rule for f in rules_fired)}
Write exactly {len(rules_fired)} explanation(s), one per rule above, in that order,
each beginning with its rule id.

DETERMINISTIC FINDINGS (authoritative, from the rule engine)
{_format_findings(result)}

RETRIEVED EVIDENCE (authoritative, from official Colab sources)
{_format_evidence(evidence)}

Explain every rule in the 'explanations' list, in order, one sentence each, each
starting with its rule id. Keep 'limitations' for what the tool cannot know, and do
not put rule explanations there.

Ground every claim in the evidence above. Where the evidence does not settle a point,
say it is unverified. Mention only runtime snapshots that appear in the evidence; do
not speculate about other versions."""


def explain(
    result: AuditResult,
    evidence: dict[str, list[dict]],
    provider: str = DEFAULT_PROVIDER,
    model: str = DEFAULT_MODEL,
) -> ExplanationResult:
    """Make exactly one model call to explain an existing audit result.

    A provider outage can reach us as an error document in the response body rather
    than as an exception. That is reported as a ProviderError so the caller records
    a real reason instead of a confusing schema error.
    """
    agent = Agent(
        model=build_model(provider, model),
        description="You explain Colab notebook compatibility findings.",
        instructions=[SYSTEM_PROMPT],
        output_schema=ExplanationResult,
        telemetry=False,
    )

    response = agent.run(build_prompt(result, evidence))

    return parse_explanation(response.content, provider)


def parse_explanation(content, provider: str = DEFAULT_PROVIDER) -> ExplanationResult:
    """Turn an agent response into an ExplanationResult.

    A provider outage can arrive as an error document in the response body rather
    than as an exception. That is raised as ProviderError so the caller records a
    real reason instead of a confusing schema-validation failure.
    """
    if isinstance(content, ExplanationResult):
        return content

    payload = content
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            payload = None

    if isinstance(payload, dict) and "error" in payload:
        raise ProviderError(
            f"{provider} returned an error: {json.dumps(payload['error'])[:300]}"
        )

    return ExplanationResult.model_validate(payload)


def unexplained_rules(result: AuditResult, explanation: ExplanationResult) -> list[str]:
    """Rules the model failed to explain, in order.

    A 3B model does not reliably cover every rule, so coverage is checked
    deterministically and the gap is reported rather than hidden.
    """
    explained = " ".join(explanation.explanations).upper()

    return [f.rule for f in distinct_findings(result) if f.rule not in explained]


def is_llm_enabled() -> bool:
    """The LLM stage is opt-in. Default off keeps the deterministic pipeline the only path."""
    return os.getenv("COLABAUDIT_LLM_ENABLED", "0") == "1"


def run_explanation(
    notebook_path: str,
    snapshot: str | None,
    knowledge=None,
    max_results: int = 3,
) -> tuple[AuditResult, dict, dict | None]:
    """Full pipeline: deterministic audit, evidence retrieval, one explanation call.

    Returns (audit result, evidence, explanation or None). A provider failure yields
    None rather than raising, so the deterministic report survives untouched.
    """
    import rules

    from knowledge_base import build_knowledge, ingest

    result = rules.audit_notebook(notebook_path, snapshot)

    if knowledge is None:
        knowledge = build_knowledge()
        ingest(knowledge)

    evidence = collect_evidence(knowledge, result, max_results=max_results)

    if not is_llm_enabled():
        return result, evidence, None

    try:
        return result, evidence, explain(result, evidence)
    except Exception:
        # Includes ProviderError. Recorded by the caller as llm_status. No provider
        # switching, no architecture change, no paid fallback.
        return result, evidence, None