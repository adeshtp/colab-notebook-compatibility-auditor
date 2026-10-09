#!/usr/bin/env python3
"""Regenerate reports/example_qa.md, showing the question-answering path end to end.

    export GROQ_API_KEY=...
    python scripts/generate_example_qa.py

Runs the same functions the Streamlit question tab calls, against the committed
curated corpus. It deliberately includes one question the corpus cannot answer, so
the committed report shows the refusal path and not only the happy path.

Without a key the retrieval, the coverage scores and the refusal still appear; the
answer sections are replaced by a note.
"""

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import qa  # noqa: E402
from explainer import DEFAULT_MODEL, DEFAULT_PROVIDER  # noqa: E402
from knowledge_base import build_knowledge, ingest  # noqa: E402

OUTPUT = ROOT / "reports" / "example_qa.md"

# Two the corpus covers, one it does not.
QUESTIONS = [
    (
        "How do I pin a notebook to a past Colab runtime version?",
        "Answerable. colab-runtime-version-faq describes the Runtime -> Change "
        "runtime type dialog.",
    ),
    (
        "Where is Google Drive mounted in a Colab runtime?",
        "Answerable. google-colab-cli documents the /content/drive default mount.",
    ),
    (
        "How much RAM does a free Colab runtime give me?",
        "NOT answerable. No curated source states a RAM figure, so the assistant "
        "must refuse rather than guess.",
    ),
]


def render(knowledge) -> str:
    lines = []
    add = lines.append

    add("# Example: question answering\n")
    add(
        "Regenerate with `python scripts/generate_example_qa.py`. Produced by the "
        "same `qa.answer_question` the Streamlit question tab calls, against the "
        "committed curated corpus. No private data and no API key are included.\n"
    )
    add(f"- Provider: `{DEFAULT_PROVIDER}` / `{DEFAULT_MODEL}`")
    add("- At most one model call per question")
    add(f"- Evidence threshold: {qa.MIN_EVIDENCE_COVERAGE:.2f}")
    add(f"- Generated: {date.today().isoformat()}\n")

    import os

    configured = bool(os.getenv("GROQ_API_KEY")) or DEFAULT_PROVIDER == "ollama"

    for question, note in QUESTIONS:
        result = qa.answer_question(
            knowledge,
            question,
            use_ai=configured,
        )

        add(f"## {question}\n")
        add(f"*Why this question was chosen:* {note}\n")
        add(f"- Status: `{result.status}`")
        add(f"- Passages retrieved: {len(result.passages)}")
        add(f"- Evidence coverage: **{result.coverage:.2f}** "
            f"(threshold {qa.MIN_EVIDENCE_COVERAGE:.2f})\n")

        if result.status == "insufficient_evidence":
            add("### Refused\n")
            add(result.detail)
            add("")
            add(
                "The passages below are shown anyway so the refusal is inspectable, "
                "but no answer was generated and the model was not called at all.\n"
            )
        elif result.status == "disabled":
            add("### Answer not generated\n")
            add(
                "No provider key was configured, so only retrieval and the evidence "
                "check ran.\n"
            )
        elif result.status == "ok":
            answer = result.answer
            add("### Answer\n")
            add(answer.answer)
            add("")
            if result.unsupported_citations:
                add(
                    f"> The model cited a source outside the retrieved set, which is "
                    f"withheld from the reference list: "
                    f"{', '.join(result.unsupported_citations)}\n"
                )
            add("### Sources used\n")
            seen = set()
            for passage in result.passages:
                if passage["source_id"] in result.used_sources and passage["source_id"] not in seen:
                    seen.add(passage["source_id"])
                    add(f"- [{passage['title']}]({passage['url']}) — {passage['source']}")
            add("")
            if answer.caveats:
                add("### Limits of the retrieved evidence\n")
                for item in answer.caveats:
                    add(f"- {item}")
                add("")
        else:
            add(f"### Outcome\n\n`{result.status}`: {result.detail}\n")

        add("### Retrieved passages\n")
        for index, passage in enumerate(result.passages, start=1):
            add(f"**[{index}] {passage['source_id']}** — {passage['title']}  ")
            add(f"<{passage['url']}>")
            add("```text")
            add(passage["content"].strip())
            add("```")
            add("")

    add("## How to read this report\n")
    add(
        "- Every answer above is built only from the passages printed under it. The "
        "prompt contains the question and those passages and nothing else.\n"
        "- Coverage is computed by deterministic code before the model is called. The "
        "third question never reaches the model.\n"
        "- A citation to a source outside the retrieved set would be withheld from the "
        "reference list rather than rendered as a real link.\n"
        "- Retrieval, embeddings and the vector database run locally. Only answer "
        "generation calls a provider."
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    knowledge = build_knowledge(rebuild=True)
    ingest(knowledge)
    OUTPUT.write_text(render(knowledge), encoding="utf-8")
    print(f"wrote {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())