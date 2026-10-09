#!/usr/bin/env python3
"""Report retrieval quality and sufficiency separation over tests/retrieval_eval.json.

    python scripts/run_retrieval_eval.py

Prints, for each question, which sources were retrieved and the measured evidence
coverage, then two honest summaries:

  * recall@k and top-1 accuracy over the answerable questions
  * the coverage range for answerable versus out-of-domain questions, and whether the
    threshold in src/qa.py separates them

This is a sanity check, not a benchmark. Eighteen hand-written questions cannot
support an accuracy claim, and none is made. It exists so that a change to the
corpus, the chunking or the embedding model can be seen immediately instead of
silently degrading retrieval.

Runs offline with no API key. It builds the LanceDB index, which downloads the
embedding model the first time.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from knowledge_base import build_knowledge, ingest, retrieve  # noqa: E402
from qa import MIN_EVIDENCE_COVERAGE, evidence_coverage  # noqa: E402

EVAL_PATH = ROOT / "tests" / "retrieval_eval.json"


def main() -> int:
    cases = json.loads(EVAL_PATH.read_text(encoding="utf-8"))
    top_k = cases.get("top_k", 4)

    print("Building the local index from the committed curated sources...")
    knowledge = build_knowledge(rebuild=True)
    ingest(knowledge)
    print()

    answerable_hits = 0
    answerable_top1 = 0
    answerable_coverage = []

    print("ANSWERABLE QUESTIONS")
    print("-" * 78)
    for case in cases["answerable"]:
        question = case["question"]
        expected = set(case["expected_sources"])
        passages = retrieve(knowledge, question, max_results=top_k)
        retrieved = [p["source_id"] for p in passages]
        coverage = evidence_coverage(question, passages)
        answerable_coverage.append(coverage)

        hit = expected & set(retrieved)
        top1 = retrieved[0] in expected if retrieved else False
        answerable_hits += bool(hit)
        answerable_top1 += top1

        mark = "ok " if hit else "MISS"
        print(f"[{mark}] coverage={coverage:.2f}  {question}")
        print(f"        expected {sorted(expected)}")
        print(f"        retrieved {retrieved}")
    print()

    out_coverage = []
    print("OUT-OF-DOMAIN QUESTIONS (the corpus should not claim to cover these)")
    print("-" * 78)
    for case in cases["out_of_domain"]:
        question = case["question"]
        passages = retrieve(knowledge, question, max_results=top_k)
        coverage = evidence_coverage(question, passages)
        out_coverage.append(coverage)
        print(f"     coverage={coverage:.2f}  {question}")
    print()

    total = len(cases["answerable"])
    print("SUMMARY")
    print("-" * 78)
    print(f"  answerable questions            : {total}")
    print(f"  expected source in top-{top_k}      : {answerable_hits}/{total}")
    print(f"  expected source ranked first    : {answerable_top1}/{total}")
    print()
    print(f"  answerable coverage range       : {min(answerable_coverage):.2f}"
          f"-{max(answerable_coverage):.2f}")
    print(f"  out-of-domain coverage range    : {min(out_coverage):.2f}"
          f"-{max(out_coverage):.2f}")
    print(f"  threshold in src/qa.py          : {MIN_EVIDENCE_COVERAGE:.2f}")

    separated = min(answerable_coverage) >= MIN_EVIDENCE_COVERAGE > max(out_coverage)
    print(f"  threshold separates the two sets: {'yes' if separated else 'NO'}")
    print()
    print("  These counts describe this hand-written set only. They are not an accuracy")
    print("  figure for the system and must not be quoted as one.")
    return 0 if separated else 1


if __name__ == "__main__":
    raise SystemExit(main())