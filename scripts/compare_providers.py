#!/usr/bin/env python3
"""Compare LLM providers on the project's real explanation task.

Same notebook, same findings, same evidence, same prompt, same Pydantic schema for
every provider. Only the model changes. Two cases, one request each.

    python scripts/compare_providers.py --provider groq --model openai/gpt-oss-20b
    python scripts/compare_providers.py --provider ollama --model ministral-3:3b

Writes reports/provider_eval_<provider>.json. Nothing here is imported by src/.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

SNAPSHOT = "2026.07"

CASES = {
    "A_mismatching_pin": "tests/fixtures/mismatching_pin.ipynb",
    "B_unpinned_and_absent": "tests/fixtures/unpinned_package.ipynb",
}

# Phrases that would overstate what static analysis can prove. Flagged for human
# review, not auto-failed. "not guaranteed" is the correct hedging phrase and is
# deliberately excluded by the negative lookbehind.
OVERREACH_PATTERNS = [
    r"\bwill (?:definitely |certainly )?fail\b",
    r"(?<!not )\bwill not run\b",
    r"(?<!not )(?<!cannot )\bguarantee[sd]?\b",
    r"(?<!not )\bdefinitely break",
    r"\bcannot run\b",
    r"\bwill crash\b",
]

SNAPSHOT_PATTERN = re.compile(r"\b20\d{2}\.\d{2}\b")
VERSION_PATTERN = re.compile(r"\b\d+\.\d+(?:\.\d+)?\b")


def versions_in(text: str) -> set[str]:
    """Dotted numbers in the text, with snapshot ids removed.

    `2026.07` matches a dotted-number pattern, so it has to be filtered explicitly
    rather than by regex alone.
    """
    found = set(VERSION_PATTERN.findall(text))
    return found - set(SNAPSHOT_PATTERN.findall(text))


def supplied_versions(result) -> set[str]:
    """Versions the model was actually given.

    Notebook pins live on dependencies. Runtime versions only appear inside the
    finding messages, so both have to be collected or the check flags legitimate
    quotes as invented.
    """
    versions = {
        version
        for dependency in result.dependencies
        if (version := dependency.version)
    }
    for finding in result.findings:
        versions.update(versions_in(finding.message))
    return versions


def check_exact_reproduction(result, explanation) -> dict:
    """Did the model copy the supplied rule ids and versions exactly?"""
    text = " ".join(
        [explanation.summary, *explanation.explanations,
         *explanation.recommendations, *explanation.limitations]
    )

    rules = [f.rule for f in result.findings]
    missing_rules = [rule for rule in set(rules) if rule not in text]

    expected = supplied_versions(result)
    missing_versions = [v for v in expected if v not in text]

    # A version in the output that was never supplied is the failure mode that
    # matters most, so it is checked separately from a missing one.
    invented = sorted(versions_in(text) - expected)

    return {
        "rule_ids_reproduced": not missing_rules,
        "missing_rule_ids": missing_rules,
        "supplied_versions": sorted(expected),
        "missing_versions": missing_versions,
        "versions_not_supplied": invented,
    }


def check_evidence_use(evidence, explanation) -> dict:
    """Did the explanation reference the retrieved sources rather than free-associating?"""
    cited = {hit["source_id"] for hits in evidence.values() for hit in hits}
    text = " ".join(
        [explanation.summary, *explanation.explanations, *explanation.limitations]
    ).lower()

    signalled_uncertainty = any(
        word in text for word in ("unverified", "not confirm", "does not confirm",
                                  "cannot confirm", "not proven", "does not establish")
    )

    # Snapshot ids the evidence actually shows, versus ones the model mentioned.
    evidence_snapshots = {s for s in SNAPSHOT_PATTERN.findall(
        " ".join(hit["content"] for hits in evidence.values() for hit in hits)
    )}

    return {
        "sources_available": sorted(cited),
        "mentions_uncertainty": signalled_uncertainty,
        "snapshots_in_evidence": sorted(evidence_snapshots),
        "snapshots_mentioned": sorted(set(SNAPSHOT_PATTERN.findall(text))),
        "speculative_snapshots": sorted(set(SNAPSHOT_PATTERN.findall(text)) - evidence_snapshots - {SNAPSHOT}),
    }


def check_overreach(explanation) -> list[str]:
    text = " ".join(
        [explanation.summary, *explanation.explanations,
         *explanation.recommendations, *explanation.limitations]
    ).lower()

    return [p for p in OVERREACH_PATTERNS if re.search(p, text)]


def run_case(label: str, notebook: str, provider: str, model: str, knowledge) -> dict:
    import explainer
    import rules

    result = rules.audit_notebook(str(ROOT / notebook), SNAPSHOT)
    evidence = explainer.collect_evidence(knowledge, result)

    record = {
        "case": label,
        "notebook": notebook,
        "snapshot": SNAPSHOT,
        "deterministic_status": result.status,
        "findings": [
            {"rule": f.rule, "package": f.package, "severity": f.severity, "cell": f.cell}
            for f in result.findings
        ],
        "distinct_rules": [f.rule for f in explainer.distinct_findings(result)],
        "evidence_hits": {rule: len(hits) for rule, hits in evidence.items()},
        "prompt_chars": len(explainer.build_prompt(result, evidence)),
        "requests": 1,
    }

    started = time.perf_counter()
    try:
        explanation = explainer.explain(result, evidence, provider=provider, model=model)
        record["success"] = True
    except Exception as exc:
        record["success"] = False
        record["error"] = f"{type(exc).__name__}: {exc}"[:400]
        record["latency_seconds"] = round(time.perf_counter() - started, 2)
        return record

    record["latency_seconds"] = round(time.perf_counter() - started, 2)
    record["structured_output_ok"] = True
    record["unexplained_rules"] = explainer.unexplained_rules(result, explanation)
    record["coverage_ok"] = not record["unexplained_rules"]
    record["reproduction"] = check_exact_reproduction(result, explanation)
    record["evidence"] = check_evidence_use(evidence, explanation)
    record["overreach_flags"] = check_overreach(explanation)
    record["n_recommendations"] = len(explanation.recommendations)
    record["n_limitations"] = len(explanation.limitations)
    record["output"] = explanation.model_dump()

    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", required=True)
    parser.add_argument("--model", required=True)
    args = parser.parse_args()

    from knowledge_base import build_knowledge, ingest

    knowledge = build_knowledge()
    ingest(knowledge)

    report = {
        "provider": args.provider,
        "model": args.model,
        "generated_by": "scripts/compare_providers.py",
        "cases": [run_case(label, path, args.provider, args.model, knowledge)
                  for label, path in CASES.items()],
    }

    out = ROOT / "reports" / f"provider_eval_{args.provider}.json"
    out.write_text(json.dumps(report, indent=2) + "\n")

    for case in report["cases"]:
        print(f"{case['case']}: success={case['success']} "
              f"latency={case['latency_seconds']}s coverage_ok={case.get('coverage_ok')} "
              f"unexplained={case.get('unexplained_rules')}")
        if case.get("overreach_flags"):
            print(f"  overreach flags: {case['overreach_flags']}")
        if not case["success"]:
            print(f"  error: {case['error']}")

    print(f"\nwritten to {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())