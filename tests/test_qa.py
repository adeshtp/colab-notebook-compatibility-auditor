"""Tests for the retrieval-augmented question-answering layer.

None of these call a provider. Retrieval runs against the real local index, but
answer generation is either switched off explicitly or replaced with a stub, so the
suite needs no API key, no network and no local model.

What is deliberately not tested here: the exact wording a model produces. Wording
from an LLM is not a stable contract. What is tested is everything the application
actually controls -- what gets retrieved, what enters the prompt, which citations
are allowed, and what happens when the evidence is not there.
"""

import json

import pytest

import qa
from knowledge_base import build_knowledge, ingest, retrieve
from qa import (
    MIN_EVIDENCE_COVERAGE,
    AnswerResult,
    Answered,
    answer_question,
    build_prompt,
    content_terms,
    evidence_coverage,
    format_passages,
    is_sufficient,
    parse_answer,
    unsupported_citations,
)


@pytest.fixture(scope="module")
def knowledge():
    kb = build_knowledge(rebuild=True)
    ingest(kb)
    return kb


def passage(content: str, source_id: str = "src", url: str = "https://example.com") -> dict:
    return {
        "source_id": source_id,
        "source": "Google Colab",
        "title": "T",
        "url": url,
        "content_type": "SOURCE_FACT",
        "runtime_context": "all",
        "content": content,
        "rank": 1,
    }


# ----------------------------------------------------------------- retrieval

def test_a_user_question_retrieves_relevant_passages(knowledge):
    hits = retrieve(knowledge, "Where is Google Drive mounted in Colab?", max_results=4)

    assert hits
    assert hits[0]["source_id"] == "colab-filesystem-conventions"


def test_retrieved_passages_carry_citable_source_metadata(knowledge):
    hits = retrieve(knowledge, "How long are past runtime versions available?", max_results=4)

    assert hits
    for hit in hits:
        assert hit["source_id"]
        assert hit["title"]
        assert hit["source"]
        assert hit["url"].startswith("https://")
        assert hit["content"].strip()
        assert hit["content_type"] == "SOURCE_FACT"


def test_retrieved_passage_content_is_not_truncated(knowledge):
    """A chunk must reach the prompt whole.

    Truncating here previously risked cutting the exact sentence a question asks
    about, such as the runtime component list that carries the version numbers.
    """
    hits = retrieve(knowledge, "What version of PyTorch is in the 2026.04 runtime?", max_results=4)
    joined = " ".join(hit["content"] for hit in hits)

    assert "2.10.0" in joined


def test_retrieval_never_returns_yaml_front_matter(knowledge):
    """Front matter duplicates metadata and must not become retrievable text."""
    for question in (
        "Where is Google Drive mounted in Colab?",
        "How long are past runtime versions available?",
        "How much RAM does Colab give me?",
    ):
        for hit in retrieve(knowledge, question, max_results=4):
            assert "source_id:" not in hit["content"]
            assert not hit["content"].lstrip().startswith("---")


def test_a_question_is_not_a_rule_id(knowledge):
    """QA queries come from the user, not from the rule engine."""
    hits = retrieve(knowledge, "How do I pin a notebook to a past runtime version?", max_results=4)

    assert any(hit["source_id"] == "colab-runtime-version-faq" for hit in hits)


# ------------------------------------------------------------ sufficiency gate

def test_content_terms_drops_stopwords_and_keeps_version_digits():
    assert content_terms("How much RAM does a Colab runtime give me?") == {"ram", "colab", "runtime"}
    assert "2026.07".split(".")[0] in content_terms("What is in the 2026.07 runtime")


def test_a_term_absent_from_every_passage_is_not_counted_as_covered():
    """The gate's core mechanism: an uncovered term costs coverage.

    Two terms, one ubiquitous and one absent. A question whose second term appears
    nowhere cannot reach full coverage however generic the first term is.
    """
    ubiquitous = [
        passage("Colab runtimes are updated often."),
        passage("Colab notebooks run in a browser."),
        passage("More about Colab and notebooks."),
    ]

    uncovered = evidence_coverage("runtime ram", ubiquitous)
    covered = evidence_coverage("runtime ram", ubiquitous + [passage("The runtime has ram.")])

    assert uncovered < 1.0
    assert covered == 1.0


def test_padding_with_repeated_generic_passages_does_not_manufacture_coverage():
    """Adding more on-topic-looking but irrelevant text must never help.

    A term absent from every passage gets weightier as the retrieved set grows, so
    padding with duplicates pushes coverage down rather than up. That is the
    intended direction: more irrelevant context is worse evidence, not better.
    """
    question = "How much RAM does a Colab runtime give me?"
    sparse = [passage("This is the Colab runtime documentation, from Google Colab.")]

    assert evidence_coverage(question, sparse * 8) < evidence_coverage(question, sparse)


def test_coverage_rises_only_when_the_discriminative_term_appears():
    """The same question, with a passage that actually mentions RAM."""
    question = "How much RAM does a Colab runtime give me?"
    without = [
        passage("This is the Colab runtime documentation, from Google Colab."),
        passage("Colab releases are announced in a separate announcement post."),
        passage("Another Colab paragraph about mounting files in the browser."),
    ]
    with_ram = without + [passage("The Colab runtime reports 12.7 GB of RAM.")]

    assert evidence_coverage(question, with_ram) > evidence_coverage(question, without)


def test_evidence_is_high_when_a_passage_actually_answers():
    question = "Where is Google Drive mounted?"
    passages = [passage("Mount Google Drive on the VM, default: /content/drive.")]

    assert evidence_coverage(question, passages) >= MIN_EVIDENCE_COVERAGE


def test_coverage_is_scored_per_passage_not_pooled_across_them():
    """Unrelated paragraphs must not combine into apparent support.

    'Kaggle' appears in no Colab source. Under a pooled measure the generic 'colab'
    plus an incidental 'notebooks' match would look like coverage; per passage it
    does not.
    """
    question = "How do I use Kaggle notebooks instead of Colab?"
    passages = [
        passage("This document is about Colab notebooks in general."),
        passage("An unrelated paragraph that happens to mention the word Colab."),
    ]

    assert evidence_coverage(question, passages) < MIN_EVIDENCE_COVERAGE


def test_no_passages_means_no_coverage():
    assert evidence_coverage("Where is Drive mounted?", []) == 0.0
    assert not is_sufficient("Where is Drive mounted?", [])


def test_corpus_questions_pass_the_gate_and_ram_does_not(knowledge):
    answerable = "Where is Google Drive mounted in a Colab runtime?"
    unanswerable = "How much RAM does a free Colab runtime give me?"

    assert is_sufficient(answerable, retrieve(knowledge, answerable, max_results=4))
    assert not is_sufficient(unanswerable, retrieve(knowledge, unanswerable, max_results=4))


# ------------------------------------------------------------ prompt assembly

def test_prompt_contains_the_question_and_every_retrieved_passage():
    passages = [passage("First fact about runtimes.", "a"), passage("Second fact.", "b")]
    prompt = build_prompt("What changed in runtimes?", passages)

    assert "What changed in runtimes?" in prompt
    assert "First fact about runtimes." in prompt
    assert "Second fact." in prompt
    assert "[1]" in prompt and "[2]" in prompt


def test_prompt_lists_the_citable_source_ids():
    prompt = build_prompt("q", [passage("text", "src-one"), passage("text", "src-two")])

    assert "src-one, src-two" in prompt


def test_format_passages_numbers_from_one_and_keeps_urls():
    passages = [passage("body one", "s1", "https://a.example"), passage("body two", "s2", "https://b.example")]
    formatted = format_passages(passages)

    assert formatted.index("[1]") < formatted.index("[2]")
    assert "https://a.example" in formatted
    assert "https://b.example" in formatted


def test_system_prompt_forbids_outside_knowledge_and_citation_invention():
    prompt = qa.QA_SYSTEM_PROMPT

    assert "Answer only from the passages" in prompt
    assert "Never use outside knowledge" in prompt
    assert "Only cite passage numbers that were actually given to you" in prompt
    assert "If the passages do not answer the question" in prompt


# ------------------------------------------------------------ citation control

def test_citations_are_checked_against_retrieved_sources():
    passages = [passage("text", "src-real")]
    answer = AnswerResult(answer="a", used_sources=["src-real"], follow_ups=[], caveats=[])

    assert unsupported_citations(answer, passages) == []


def test_a_citation_to_a_source_that_was_not_retrieved_is_reported():
    passages = [passage("text", "src-real")]
    answer = AnswerResult(
        answer="a",
        used_sources=["src-real", "src-invented"],
        follow_ups=[],
        caveats=[],
    )

    assert unsupported_citations(answer, passages) == ["src-invented"]


def test_passage_numbers_are_mapped_back_to_their_source_id():
    """A model that answers with [1], [2] instead of ids must not be called a liar.

    Found by reading the first real screenshot: the model cited inline as [1] and
    [2], repeated those numbers in used_sources, and every citation was reported as
    invented. That is a formatting habit, not a hallucination, and flagging it hid
    the sources that were genuinely used.
    """
    passages = [
        passage("first", "src-one"),
        passage("second", "src-two"),
    ]
    answer = AnswerResult(answer="a", used_sources=["1", "2"], follow_ups=[], caveats=[])

    used, unsupported = qa.resolve_used_sources(answer, passages)

    assert used == ["src-one", "src-two"]
    assert unsupported == []


def test_ids_and_passage_numbers_can_be_mixed():
    passages = [passage("first", "src-one"), passage("second", "src-two")]
    answer = AnswerResult(
        answer="a", used_sources=["src-one", "2"], follow_ups=[], caveats=[]
    )

    used, unsupported = qa.resolve_used_sources(answer, passages)

    assert used == ["src-one", "src-two"]
    assert unsupported == []


def test_a_genuinely_invented_citation_is_still_caught_among_valid_ones():
    """Mapping must not become a loophole that accepts anything."""
    passages = [passage("first", "src-one"), passage("second", "src-two")]
    answer = AnswerResult(
        answer="a", used_sources=["1", "colab-release-notes"], follow_ups=[], caveats=[]
    )

    used, unsupported = qa.resolve_used_sources(answer, passages)

    assert used == ["src-one"]
    assert unsupported == ["colab-release-notes"]


def test_duplicate_citations_are_collapsed():
    passages = [passage("first", "src-one"), passage("second", "src-one")]
    answer = AnswerResult(answer="a", used_sources=["1", "2"], follow_ups=[], caveats=[])

    used, _ = qa.resolve_used_sources(answer, passages)

    assert used == ["src-one"]


def test_answer_schema_carries_no_finding_or_severity_fields():
    fields = set(AnswerResult.model_fields)

    assert fields == {"answer", "used_sources", "follow_ups", "caveats"}


def test_qa_never_defines_or_rewrites_a_rule():
    """The question-answering layer must not acquire rule semantics."""
    source = open("src/qa.py").read()

    for rule in ("R001", "R002", "R003", "R004", "R005", "R006"):
        assert rule not in source


# ------------------------------------------------------------- answer parsing

def test_provider_error_document_is_surfaced_as_provider_error():
    payload = '{"error": {"code": 503, "message": "high demand", "status": "UNAVAILABLE"}}'

    with pytest.raises(qa.ProviderError, match="UNAVAILABLE"):
        parse_answer(payload, provider="groq")


def test_valid_payload_is_parsed():
    payload = json.dumps(
        {
            "answer": "Drive is mounted at /content/drive [1].",
            "used_sources": ["colab-filesystem-conventions"],
            "follow_ups": [],
            "caveats": [],
        }
    )

    result = parse_answer(payload)

    assert result.used_sources == ["colab-filesystem-conventions"]
    assert "/content/drive" in result.answer


def test_already_parsed_content_passes_through():
    answer = AnswerResult(answer="a", used_sources=[], follow_ups=[], caveats=[])

    assert parse_answer(answer) is answer


# ------------------------------------------------------------- end to end

def test_insufficient_evidence_never_reaches_a_provider(knowledge, monkeypatch):
    """The gate must short-circuit before any model call.

    If the corpus does not cover the question, the honest outcome is refusal with
    the passages shown, not a model asked to improvise.
    """

    def explode(*args, **kwargs):
        raise AssertionError("the provider must not be called without evidence")

    monkeypatch.setattr(qa, "build_model", explode)

    result = answer_question(knowledge, "How much RAM does a free Colab runtime give me?", use_ai=True)

    assert result.status == "insufficient_evidence"
    assert result.answer is None
    assert result.passages  # shown anyway, so the user can judge


def test_insufficient_evidence_explains_itself(knowledge):
    result = answer_question(knowledge, "How do I set up SSH access to a Colab runtime?", use_ai=True)

    assert result.status == "insufficient_evidence"
    assert "coverage" in result.detail


def test_question_is_answered_from_retrieved_evidence_when_generation_is_off(knowledge):
    """use_ai=False still retrieves and still passes the gate; only generation stops."""
    result = answer_question(knowledge, "Where is Google Drive mounted in a Colab runtime?", use_ai=False)

    assert result.status == "disabled"
    assert result.answer is None
    assert result.coverage >= MIN_EVIDENCE_COVERAGE
    assert result.passages[0]["source_id"] == "colab-filesystem-conventions"


def test_no_provider_configured_still_returns_passages(knowledge, monkeypatch):
    """Without a key the app must still show what was retrieved."""
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    result = answer_question(knowledge, "Where is Google Drive mounted in a Colab runtime?", use_ai=False)

    assert result.passages
    assert result.status == "disabled"


def test_blank_question_is_handled_without_retrieval(knowledge):
    result = answer_question(knowledge, "   ", use_ai=False)

    assert result.status == "empty_question"
    assert result.passages == []


def test_generated_answer_is_paired_with_the_passages_it_came_from(knowledge, monkeypatch):
    """A stubbed agent stands in for the provider, so the pairing is verified offline."""

    class StubResponse:
        content = json.dumps(
            {
                "answer": "Drive is mounted at /content/drive [1].",
                "used_sources": ["colab-filesystem-conventions"],
                "follow_ups": [],
                "caveats": [],
            }
        )

    class StubAgent:
        def __init__(self, *args, **kwargs):
            pass

        def run(self, prompt):
            StubAgent.last_prompt = prompt
            return StubResponse()

    monkeypatch.setattr(qa, "Agent", StubAgent)
    monkeypatch.setattr(qa, "build_model", lambda *a, **k: object())

    result = answer_question(knowledge, "Where is Google Drive mounted in a Colab runtime?", use_ai=True)

    assert result.status == "ok"
    assert result.answer.used_sources == ["colab-filesystem-conventions"]
    assert result.unsupported_citations == []
    # The passages shown are the same ones the model was given.
    assert {p["source_id"] for p in result.passages} >= {"colab-filesystem-conventions"}
    assert "/content/drive" in StubAgent.last_prompt


def test_a_model_citation_outside_the_retrieved_set_is_surfaced(knowledge, monkeypatch):
    class StubResponse:
        content = json.dumps(
            {
                "answer": "According to the release notes [1]...",
                "used_sources": ["colab-release-notes"],
                "follow_ups": [],
                "caveats": [],
            }
        )

    class StubAgent:
        def __init__(self, *args, **kwargs):
            pass

        def run(self, prompt):
            return StubResponse()

    monkeypatch.setattr(qa, "Agent", StubAgent)
    monkeypatch.setattr(qa, "build_model", lambda *a, **k: object())

    result = answer_question(knowledge, "Where is Google Drive mounted in a Colab runtime?", use_ai=True)

    assert result.unsupported_citations == ["colab-release-notes"]


def test_provider_failure_is_reported_not_raised(knowledge, monkeypatch):
    class FailingAgent:
        def __init__(self, *args, **kwargs):
            pass

        def run(self, prompt):
            raise RuntimeError("connection reset")

    monkeypatch.setattr(qa, "Agent", FailingAgent)
    monkeypatch.setattr(qa, "build_model", lambda *a, **k: object())

    result = answer_question(knowledge, "Where is Google Drive mounted in a Colab runtime?", use_ai=True)

    assert result.status == "failed"
    assert "connection reset" in result.detail
    assert result.passages


def test_answered_is_a_plain_value_not_an_exception(knowledge):
    """Every outcome, including refusal, is returned as data."""
    result = answer_question(knowledge, "How much RAM does Colab give me?", use_ai=True)

    assert isinstance(result, Answered)
    assert result.answer is None