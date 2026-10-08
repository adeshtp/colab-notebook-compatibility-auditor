"""One Agno call turns deterministic findings plus retrieved evidence into prose.

The model explains. It never decides. Rule, package, severity, status, message and
cell all come from the deterministic stage and are passed through untouched.
"""

import json
import os

from agno.agent import Agent
from agno.models.groq import Groq
from agno.models.ollama import Ollama
from pydantic import BaseModel, Field

from knowledge_base import retrieve
from models import AuditResult, Finding

# One audit, one explanation call. No teams, no tool loops, no per-finding calls.
# Chosen by measured comparison, see AI_PROVIDER.md. Groq was fastest and the only
# provider to explain every supplied rule. Ollama is the offline mode.
DEFAULT_PROVIDER = os.getenv("COLABAUDIT_LLM_PROVIDER", "groq")
DEFAULT_MODEL = os.getenv("COLABAUDIT_LLM_MODEL", "openai/gpt-oss-20b")
DEFAULT_HOST = os.getenv("COLABAUDIT_OLLAMA_HOST", "http://localhost:11434")

# Applies to the local Ollama mode only. A 3B model on CPU will otherwise ramble past
# the token limit and return unparseable JSON. The hosted Groq path is not capped;
# see AI_PROVIDER.md for the observed consequence of that.
MAX_TOKENS = 700


class ProviderError(Exception):
    """A provider returned an error document instead of an explanation."""


SYSTEM_PROMPT = """You explain compatibility risks in an old Google Colab notebook.

You are given deterministic findings produced by a rule engine, and official
documentation retrieved from a curated knowledge base. Both are authoritative facts.

Rules you must follow:
- Explain the findings. Never decide, re-evaluate or second-guess whether a finding is
  valid. A finding is a fact you were given, not a claim to be checked.
- Never call a deterministic finding "unverified", "unconfirmed" or "not proven" because
  the retrieved documents do not restate it. The finding already carries the verified
  facts, including the exact package versions.
- Quote exact values from the findings and evidence as given. Reproduce version strings
  character for character. Never substitute another version, and never invent one.
- Never invent compatibility claims beyond the supplied evidence, and never speculate
  about runtime snapshots that are not in the evidence.
- Never state or imply that a notebook was executed, or that it will definitely fail.
- Never change a rule id, severity or status.
- State the real limitation in 'limitations': that this is static analysis and execution
  was not tested. That limitation is about execution, not about whether findings hold.

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

    Plain configuration-driven selection, no factory or registry. Groq is the default
    and reads GROQ_API_KEY from the environment. Ollama is the offline local mode and
    needs no key. Only the two evaluated-and-retained providers are supported; see
    AI_PROVIDER.md for the comparison that selected them.
    """
    if provider == "groq":
        return Groq(id=model)
    if provider == "ollama":
        return Ollama(id=model, host=DEFAULT_HOST, options={"num_predict": MAX_TOKENS})
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
    """Render retrieved chunks in full.

    Do not truncate these. The corpus is five small documents and the whole prompt is
    only a few thousand characters, while a truncated chunk can cut off the exact fact
    a finding is about, such as a snapshot's package version list.
    """
    blocks = []

    for rule, hits in evidence.items():
        if not hits:
            blocks.append(f"[{rule}]\n(no evidence retrieved)")
            continue

        lines = [f"[{rule}]"]
        for hit in hits:
            lines.append(f"- {hit['title']} | {hit['source']} | {hit['url']}")
            lines.append(f"  {hit['content']}")
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
starting with its rule id. Restate the finding's own facts, including the exact package
and version numbers, so the reader can see the mismatch without cross-checking. Keep
'limitations' for what the tool cannot know, and do not put rule explanations there.

The findings above are already verified. Do not describe them as unverified or
unconfirmed, and do not ask the evidence to prove them. Ground your wording in the
evidence, but where the evidence is silent, just explain the finding rather than
doubting it."""


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

    A model may not cover every rule it was given, so coverage is checked
    deterministically and the gap is reported rather than hidden.
    """
    explained = " ".join(explanation.explanations).upper()

    return [f.rule for f in distinct_findings(result) if f.rule not in explained]