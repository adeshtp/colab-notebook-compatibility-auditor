"""Retrieval-augmented question answering over the curated Colab corpus.

This is the primary mode of the application. A user asks a question in plain
language, the question is embedded with the same local model the auditor already
uses, a few passages are retrieved from the same LanceDB index, and the configured
provider writes an answer grounded in exactly those passages.

Three deliberate design points:

1. One retrieval per question, one model call per question. No query rewriting, no
   agent loop, no second model call to decide whether the first answer was good.

2. Evidence sufficiency is decided by deterministic code, not by the model. A vector
   search always returns something, so "the top hits were returned" is not evidence
   that the corpus covers the question. See evidence_coverage().

3. Every citation the model emits is checked against the passages actually
   retrieved. A source id that was not retrieved is reported as unsupported rather
   than displayed as a real reference.
"""

import json
import math
import re
from dataclasses import dataclass, field

from agno.agent import Agent
from pydantic import BaseModel, Field

from explainer import (
    DEFAULT_MODEL,
    DEFAULT_PROVIDER,
    ProviderError,
    build_model,
)
from knowledge_base import retrieve

# A question answered from four passages should not be answered from one lucky
# keyword match. Three is enough to show corroboration and small enough that every
# passage still fits comfortably in the prompt.
DEFAULT_TOP_K = 4

# The corpus is five small official documents. Retrieval returns the nearest
# passages whether or not they are about the question, so a threshold is needed to
# separate "the documentation covers this" from "the nearest paragraphs happen to
# share a common word".
#
# Calibrated by hand, not learned. Over the 12 answerable and 6 out-of-domain
# questions in tests/retrieval_eval.json, measured coverage runs 0.52-1.00 for the
# answerable questions and 0.07-0.42 for the rest, so 0.5 separates them with roughly
# a 0.1 margin on each side. The margin is narrow and the measure is lexical, so this
# is a heuristic rather than a classifier: it is deliberately visible, documented and
# tunable here instead of being buried in a prompt. tests/test_qa.py pins both sides
# of the split so a corpus or chunking change cannot silently break it.
MIN_EVIDENCE_COVERAGE = 0.5

# Words that carry no retrieval signal. Kept small and explicit: an aggressive
# stopword list would throw away the domain terms that make a Colab question
# answerable, such as "runtime", "version" or "install".
STOPWORDS = {
    "a", "about", "am", "an", "and", "any", "are", "as", "at", "be", "been", "but",
    "by", "can", "could", "did", "do", "does", "for", "from", "get", "give", "gives",
    "had", "has", "have", "how", "i", "if", "in", "into", "is", "it", "its", "know",
    "many", "may", "me", "much", "my", "need", "of", "on", "or", "our", "should",
    "so", "some", "such", "than", "that", "the", "their", "then", "there", "these",
    "they", "this", "to", "too", "use", "used", "using", "very", "was", "we", "were",
    "what", "when", "where", "which", "who", "why", "will", "with", "would", "you",
    "your",
}

TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def content_terms(text: str) -> set[str]:
    """Lowercase content-bearing words in a question or passage.

    Single characters and stopwords are dropped; numbers are kept, because a
    question about "2026.07" or "1 year" is answerable and those digits are the
    strongest retrieval signal it has.
    """
    tokens = {t for t in TOKEN_PATTERN.findall(text.lower()) if len(t) > 1}
    return tokens - STOPWORDS


def evidence_coverage(question: str, passages: list[dict]) -> float:
    """How much of the question's discriminative weight the best single passage covers.

    Plain term weighting in the spirit of IDF, computed over the retrieved passages
    themselves:

        weight = log(1 + N / containing)

    where N is the number of retrieved passages and containing is how many of them
    contain the term. A term in every passage is weighted least, one in none is
    weighted most: "colab" appears in all of them, "ram" appears in no Colab source.

    This exact form was chosen by measurement, not taste. An alternative that drove
    ubiquitous terms closer to zero, log((N+1)/(containing+0.5)), was tried and made
    things worse: it compressed the answerable questions down onto the out-of-domain
    ones. Re-run scripts/run_retrieval_eval.py after any change here; it reports both
    ranges and whether the threshold still separates them.

    Coverage is measured against the single best passage rather than the union of all
    of them. An answer has to be supported by something specific, and pooling unrelated
    paragraphs would let a question pass on generic overlap alone. For "How do I use
    Kaggle notebooks instead of Colab?", "colab" matches everywhere and "notebooks"
    happens to match one unrelated passage, which would look like support under a
    union; measured per passage, no single text is about Kaggle.

    Returned value is between 0.0 and 1.0:

        "where is Google Drive mounted"  -> one passage covers it      -> high
        "how much RAM does Colab give"   -> no passage contains "ram"  -> low
    """
    question_terms = content_terms(question)
    if not question_terms or not passages:
        return 0.0

    total = len(passages)
    documents = [content_terms(passage.get("content", "")) for passage in passages]

    weights = {}
    for term in question_terms:
        containing = sum(1 for document in documents if term in document)
        if containing == 0:
            # Nothing in the retrieved text contains it, so it is the most
            # discriminative term in the question and carries the full weight.
            weights[term] = math.log(1 + total)
        else:
            weights[term] = math.log(1 + total / containing)

    total_weight = sum(weights.values())
    if total_weight == 0:
        return 0.0

    best = 0.0
    for document in documents:
        covered = sum(weight for term, weight in weights.items() if term in document)
        best = max(best, covered / total_weight)

    return best


def is_sufficient(question: str, passages: list[dict]) -> bool:
    """Whether the retrieved passages are on-topic enough to answer from."""
    return evidence_coverage(question, passages) >= MIN_EVIDENCE_COVERAGE


QA_SYSTEM_PROMPT = """You answer questions about Google Colab runtimes, package
compatibility and environment changes, using only the official documentation excerpts
you are given.

You are given a user question and a numbered set of retrieved passages. The passages
are the only material you may use. They come from a small curated corpus of official
Google Colab documentation.

Rules you must follow:
- Answer only from the passages. Never use outside knowledge, and never fill a gap
  with what you happen to know about Colab.
- Cite inline by passage number, like [1] or [2], immediately after the claim it supports.
  Only cite passage numbers that were actually given to you.
- In 'used_sources', list the source_id values of the passages you used, copied
  character for character from the passage headers, for example
  "colab-runtime-version-faq". Do not put passage numbers such as 1 or 2 in this
  field; those belong in the inline [n] citations only.
- If the passages do not answer the question, say so plainly in the first sentence of
  'answer'. Do not substitute a related answer, do not speculate, and do not pad the
  answer with general Colab advice that the passages do not support.
- Quote exact values from the passages as written: version strings, file paths,
  numbers and quoted sentences. Never round them, and never invent a version number.
- Note when the passages themselves describe an uncertainty, such as published
  package data lagging a live runtime.
- Answer for a data-science learner who is reusing an old notebook. Be direct and
  brief. No preamble, no closing pleasantries."""


class AnswerResult(BaseModel):
    """Model prose for one question. No findings, no severities, no statuses.

    The three list fields default to empty because they are supplementary. Agno's
    structured output against Groq does not always return every declared field, and
    losing a whole usable answer because the model skipped 'follow_ups' would be a
    poor trade. A missing list is reported as empty, which is the honest rendering of
    "the model did not say".
    """

    answer: str = Field(
        description=(
            "The answer, grounded in the passages and citing them as [1], [2]. If the "
            "passages do not cover the question, the first sentence must say the "
            "documentation provided does not answer it."
        )
    )
    used_sources: list[str] = Field(
        default_factory=list,
        description=(
            "source_id values of the passages actually used, copied exactly from the "
            "passage headers, e.g. 'colab-runtime-version-faq'. Never passage numbers. "
            "Empty if the passages were not sufficient."
        )
    )
    follow_ups: list[str] = Field(
        default_factory=list,
        description="At most two related questions this corpus could plausibly answer.",
    )
    caveats: list[str] = Field(
        default_factory=list,
        description=(
            "At most three short sentences on limits of the retrieved evidence itself, "
            "for example that published package data can lag a live runtime."
        )
    )


@dataclass
class Answered:
    """The full outcome of one question, including the failure states.

    A status is a first-class result rather than an exception, because 'the corpus
    does not cover this' is a normal answer, not a crash.
    """

    question: str
    status: str
    coverage: float = 0.0
    passages: list[dict] = field(default_factory=list)
    answer: AnswerResult | None = None
    used_sources: list[str] = field(default_factory=list)
    unsupported_citations: list[str] = field(default_factory=list)
    detail: str = ""


def format_passages(passages: list[dict]) -> str:
    """Render retrieved passages as a numbered, citable block for the prompt."""
    blocks = []

    for index, passage in enumerate(passages, start=1):
        blocks.append(
            f"[{index}]\n"
            f"source_id: {passage['source_id']}\n"
            f"title: {passage['title']}\n"
            f"source: {passage['source']}\n"
            f"url: {passage['url']}\n"
            f"content: {passage['content'].strip()}"
        )

    return "\n\n".join(blocks)


def build_prompt(question: str, passages: list[dict]) -> str:
    """Assemble the single grounded-answering prompt."""
    source_ids = ", ".join(sorted({p["source_id"] for p in passages}))

    return f"""QUESTION
{question.strip()}

RETRIEVED PASSAGES ({len(passages)})
{format_passages(passages)}

Available source ids: {source_ids}

Answer the question using only the passages above, citing them as [1], [2] and so on.
If the passages do not answer it, say so in the first sentence of 'answer' and leave
'used_sources' empty."""


def resolve_used_sources(answer: AnswerResult, passages: list[dict]) -> tuple[list[str], list[str]]:
    """Split the model's cited sources into (resolved ids, unsupported ids).

    Models are unreliable bookkeepers. Asked for source ids they often reply with the
    passage numbers they cited inline, such as "1, 2", which are not ids at all and
    would otherwise be reported as invented citations. Both forms are resolved here:

      * an exact source id is kept as-is
      * a passage number is mapped back to that passage's source id

    Anything left over really was not retrieved, and is reported so the caller can
    refuse to render it as a reference.
    """
    by_id = {p["source_id"] for p in passages}
    by_number = {
        str(index): passage["source_id"]
        for index, passage in enumerate(passages, start=1)
    }

    resolved: list[str] = []
    unsupported: list[str] = []

    for entry in answer.used_sources:
        candidate = str(entry).strip()
        if candidate in by_id:
            resolved.append(candidate)
        elif candidate in by_number:
            resolved.append(by_number[candidate])
        else:
            unsupported.append(candidate)

    # Preserve order while removing duplicates.
    return list(dict.fromkeys(resolved)), list(dict.fromkeys(unsupported))


def unsupported_citations(answer: AnswerResult, passages: list[dict]) -> list[str]:
    """Source ids the model cited that were not actually retrieved.

    A citation to a document the user was never shown is worse than no citation, so
    it is surfaced instead of being rendered as a reference link.
    """
    return resolve_used_sources(answer, passages)[1]


def parse_answer(content, provider: str = DEFAULT_PROVIDER) -> AnswerResult:
    """Turn an agent response into an AnswerResult.

    A provider outage can arrive as an error document in the body rather than as an
    exception, so that case is raised as ProviderError to match the audit path.
    """
    if isinstance(content, AnswerResult):
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

    return AnswerResult.model_validate(payload)


def answer_question(
    knowledge,
    question: str,
    provider: str = DEFAULT_PROVIDER,
    model: str = DEFAULT_MODEL,
    top_k: int = DEFAULT_TOP_K,
    use_ai: bool = True,
) -> Answered:
    """Answer one question: retrieve, check the evidence, then generate once.

    Retrieval and the sufficiency check always happen, so the retrieved passages can
    be shown even when no provider is configured or the evidence is too thin to
    answer from. The model call happens only when the evidence passes the gate.
    """
    question = question.strip()
    if not question:
        return Answered(question=question, status="empty_question")

    passages = retrieve(knowledge, question, max_results=top_k)

    if not passages:
        return Answered(
            question=question,
            status="no_passages",
            passages=passages,
            detail="Retrieval returned nothing from the curated corpus.",
        )

    coverage = evidence_coverage(question, passages)

    if not is_sufficient(question, passages):
        return Answered(
            question=question,
            status="insufficient_evidence",
            coverage=coverage,
            passages=passages,
            detail=(
                "The nearest passages in the curated corpus do not cover enough of "
                f"the question to answer it (coverage {coverage:.2f}, threshold "
                f"{MIN_EVIDENCE_COVERAGE:.2f}). Showing them anyway, unverified."
            ),
        )

    if not use_ai:
        return Answered(
            question=question,
            status="disabled",
            coverage=coverage,
            passages=passages,
            detail="An answer was not requested. The retrieved passages are shown below.",
        )

    agent = Agent(
        model=build_model(provider, model),
        description="You answer Colab runtime questions from retrieved documentation.",
        instructions=[QA_SYSTEM_PROMPT],
        output_schema=AnswerResult,
        telemetry=False,
    )

    try:
        response = agent.run(build_prompt(question, passages))
        answer = parse_answer(response.content, provider)
    except ProviderError as exc:
        return Answered(
            question=question,
            status="failed",
            coverage=coverage,
            passages=passages,
            detail=str(exc),
        )
    except Exception as exc:
        return Answered(
            question=question,
            status="failed",
            coverage=coverage,
            passages=passages,
            detail=f"{type(exc).__name__}: {exc}"[:300],
        )

    used, unsupported = resolve_used_sources(answer, passages)

    return Answered(
        question=question,
        status="ok",
        coverage=coverage,
        passages=passages,
        answer=answer,
        used_sources=used,
        unsupported_citations=unsupported,
    )


__all__ = [
    "AnswerResult",
    "Answered",
    "DEFAULT_TOP_K",
    "MIN_EVIDENCE_COVERAGE",
    "QA_SYSTEM_PROMPT",
    "answer_question",
    "build_prompt",
    "content_terms",
    "evidence_coverage",
    "format_passages",
    "is_sufficient",
    "parse_answer",
    "resolve_used_sources",
    "unsupported_citations",
]