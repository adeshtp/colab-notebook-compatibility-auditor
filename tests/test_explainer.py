"""Tests for the explanation layer.

Nothing here calls a provider by default. The single live test is opt-in via
RUN_OLLAMA_TESTS=1 and names its provider explicitly. The explanation layer must
never be able to alter a deterministic field, and that is checked structurally rather
than on exact model wording.
"""

import os

import pytest

import explainer
import rules
from explainer import (
    ExplanationResult,
    build_prompt,
    build_query_for,
    collect_evidence,
    distinct_findings,
    is_llm_enabled,
    unexplained_rules,
)
from models import AuditResult, Finding

SNAPSHOT = "2026.07"


def audit(fixture: str) -> AuditResult:
    return rules.audit_notebook(f"tests/fixtures/{fixture}.ipynb", SNAPSHOT)


def test_distinct_findings_collapses_repeated_rules():
    result = audit("unpinned_package")
    unique = distinct_findings(result)

    assert [f.rule for f in unique] == ["R002", "R004"]


def test_one_search_per_distinct_rule_not_per_finding():
    result = AuditResult(
        notebook_name="many.ipynb",
        findings=[Finding(rule="R002", package="a", severity="ATTENTION", status="RISK", message="m")]
        * 12,
        status="ATTENTION",
    )
    assert len(distinct_findings(result)) == 1


def test_query_is_built_from_the_deterministic_finding():
    finding = Finding(
        rule="R001",
        package="numpy",
        severity="HIGH",
        status="RISK",
        message="Notebook pins numpy==1.24.3 but the selected runtime contains 2.0.2.",
    )
    query = build_query_for(finding)

    assert "R001" in query
    assert "numpy" in query
    assert "1.24.3" in query


def test_prompt_carries_findings_and_evidence_and_the_constraints():
    result = audit("mismatching_pin")
    evidence = {"R001": [{"title": "T", "source": "S", "url": "u", "content": "c", "content_type": "SOURCE_FACT", "source_id": "s", "runtime_context": "all", "rank": 1}]}
    prompt = build_prompt(result, evidence)

    assert "R001" in prompt
    assert "HIGH" in prompt
    assert "2.0.2" in prompt
    assert "SOURCE_FACT" not in prompt  # content_type is metadata, not prompt text
    assert "notebook" in prompt.lower()


def test_prompt_states_the_exact_number_of_explanations_required():
    result = audit("unpinned_package")

    assert "Write exactly 2 explanation(s)" in build_prompt(result, {})


def test_llm_stage_is_off_by_default(monkeypatch):
    monkeypatch.delenv("COLABAUDIT_LLM_ENABLED", raising=False)
    assert is_llm_enabled() is False

    monkeypatch.setenv("COLABAUDIT_LLM_ENABLED", "1")
    assert is_llm_enabled() is True


def test_unknown_provider_is_rejected():
    with pytest.raises(ValueError):
        explainer.build_model(provider="openai")


def test_every_documented_provider_builds_without_calling_it():
    """Construction only. No request, so no key is needed."""
    from agno.models.google import Gemini
    from agno.models.groq import Groq
    from agno.models.ollama import Ollama

    assert isinstance(explainer.build_model("ollama", "ministral-3:3b"), Ollama)
    assert isinstance(explainer.build_model("groq", "openai/gpt-oss-20b"), Groq)
    assert isinstance(explainer.build_model("gemini", "gemini-3.8-flash"), Gemini)


def test_groq_is_the_selected_default():
    assert explainer.DEFAULT_PROVIDER == "groq"
    assert explainer.DEFAULT_MODEL == "openai/gpt-oss-20b"


def test_provider_error_document_is_surfaced_as_provider_error():
    """A provider outage must not be reported as a confusing schema failure."""
    payload = '{"error": {"code": 503, "message": "high demand", "status": "UNAVAILABLE"}}'

    with pytest.raises(explainer.ProviderError, match="UNAVAILABLE"):
        explainer.parse_explanation(payload, provider="gemini")


def test_non_error_payload_is_still_validated():
    payload = '{"summary": "ok", "explanations": ["R001: x"], "recommendations": [], "limitations": []}'

    result = explainer.parse_explanation(payload, provider="groq")

    assert result.summary == "ok"


def test_already_parsed_content_passes_through():
    explanation = ExplanationResult(
        summary="s", explanations=["R001: x"], recommendations=[], limitations=[]
    )

    assert explainer.parse_explanation(explanation) is explanation


def test_explanation_schema_carries_no_version_or_severity_fields():
    fields = set(ExplanationResult.model_fields)

    assert fields == {"summary", "explanations", "recommendations", "limitations"}


def test_coverage_gap_is_reported_deterministically():
    result = audit("unpinned_package")
    partial = ExplanationResult(
        summary="s",
        explanations=["R002: only this one was explained"],
        recommendations=[],
        limitations=[],
    )

    assert unexplained_rules(result, partial) == ["R004"]


def test_explanation_cannot_alter_deterministic_findings():
    result = audit("mismatching_pin")
    before = result.model_dump()

    explanation = ExplanationResult(
        summary="This notebook definitely will not run.",
        explanations=["R001: numpy version mismatch."],
        recommendations=["Downgrade numpy."],
        limitations=["Static analysis cannot guarantee execution."],
    )

    # The explanation lives in its own model. There is no field on AuditResult the
    # model can write back into, so findings are structurally unchanged.
    assert result.model_dump() == before
    assert explanation.summary  # held separately, never merged
    assert not hasattr(result, "summary")


@pytest.mark.integration
def test_ollama_produces_a_structurally_valid_explanation(monkeypatch):
    """Live local model call against Ollama.

    Opt-in via RUN_OLLAMA_TESTS=1, because the normal suite must not call any
    provider. The provider and model are passed explicitly rather than taken from
    the application default, which is Groq and needs an API key.
    """
    import urllib.error
    import urllib.request

    if os.getenv("RUN_OLLAMA_TESTS") != "1":
        pytest.skip("set RUN_OLLAMA_TESTS=1 to run the live Ollama test")

    host = explainer.DEFAULT_HOST
    try:
        urllib.request.urlopen(f"{host}/api/tags", timeout=3).read()
    except (urllib.error.URLError, TimeoutError):
        pytest.skip(f"local Ollama not reachable at {host}")

    result = audit("mismatching_pin")
    from knowledge_base import build_knowledge, ingest

    knowledge = build_knowledge()
    ingest(knowledge)
    evidence = collect_evidence(knowledge, result)

    explanation = explainer.explain(
        result, evidence, provider="ollama", model="ministral-3:3b"
    )

    # Structural validity only. Exact wording from a 3B model is not asserted.
    assert explanation.summary
    assert isinstance(explanation.explanations, list)
    assert isinstance(explanation.recommendations, list)
    assert isinstance(explanation.limitations, list)
    assert result.findings[0].rule == "R001"
    assert result.status == "HIGH_RISK"