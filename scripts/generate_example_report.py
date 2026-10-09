#!/usr/bin/env python3
"""Regenerate reports/example_report.md from a committed fixture.

Runs the same three steps the Streamlit app runs, so the committed report is
reproducible rather than a one-off capture.

    export GROQ_API_KEY=...
    python scripts/generate_example_report.py

The notebook used is a committed test fixture, so no private content is involved.
Without a key the report is still written, with the explanation section replaced by a
note that the provider was not configured.
"""

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import rules  # noqa: E402
from explainer import (  # noqa: E402
    DEFAULT_MODEL,
    DEFAULT_PROVIDER,
    collect_evidence,
    explain,
    unexplained_rules,
)
from knowledge_base import build_knowledge, ingest  # noqa: E402

FIXTURE = "tests/fixtures/unpinned_package.ipynb"
SNAPSHOT = "2026.07"
OUTPUT = ROOT / "reports" / "example_report.md"


def build_markdown(result, evidence, explanation, status) -> str:
    lines = []
    add = lines.append

    add("# Example report\n")
    add(
        "Regenerate with `python scripts/generate_example_report.py`. This report is "
        "produced by the same three functions the Streamlit app calls "
        "(`rules.audit_notebook`, `explainer.collect_evidence`, `explainer.explain`), "
        "run against a committed test fixture. No private notebook content or API key "
        "is included.\n"
    )
    add(f"- Notebook: `{FIXTURE}` (committed test fixture)")
    add(f"- Runtime snapshot: `{SNAPSHOT}`")
    add(f"- Provider: `{DEFAULT_PROVIDER}` / `{DEFAULT_MODEL}`")
    add(f"- LLM calls: 1")
    add(f"- Generated: {date.today().isoformat()}\n")

    add("## Notebook summary\n")
    add(f"- Detected dependencies: {len(result.dependencies)}")
    add(f"- Findings: {len(result.findings)}")
    add(f"- **Overall status: {result.status}**")
    if result.runtime:
        add(
            f"- Runtime: {result.runtime.os_version}, Python "
            f"{result.runtime.python_version}, commit `{result.runtime.source_commit}`"
        )
    add("")

    add("## Deterministic findings\n")
    add("Produced by `src/rules.py`. Authoritative, and unchanged by the model.\n")
    add("| rule | package | severity | status | cell | message |")
    add("|---|---|---|---|---|---|")
    for finding in result.findings:
        cell = finding.cell if finding.cell is not None else "-"
        add(
            f"| {finding.rule} | {finding.package or '-'} | {finding.severity} | "
            f"{finding.status} | {cell} | {finding.message} |"
        )
    add("")

    add("## Retrieved evidence\n")
    add("Official Colab sources, grouped per rule. Retrieval is deterministic.\n")
    seen = set()
    for rule, hits in evidence.items():
        add(f"### {rule}\n")
        for hit in hits:
            key = (rule, hit["source_id"], hit["rank"])
            if key in seen:
                continue
            seen.add(key)
            add(f"**{hit['title']}** — {hit['source']}  ")
            add(f"<{hit['url']}>  ")
            add("```text")
            add(hit["content"].strip())
            add("```")
            add("")

    add("## AI-generated explanation\n")
    add("Model prose only. It cannot change any field in the table above.\n")
    if explanation is None:
        add(f"Provider status: `{status}`. No explanation was generated.\n")
    else:
        add("**Summary**\n")
        add(f"{explanation.summary}\n")
        add("**Explanations**\n")
        for item in explanation.explanations:
            add(f"- {item}")
        add("")
        add("**Recommended manual checks**\n")
        for item in explanation.recommendations:
            add(f"- {item}")
        add("")
        missing = unexplained_rules(result, explanation)
        add(
            f"Rules not explained by the model: {', '.join(missing) if missing else 'none'}\n"
        )

    add("## Limitations\n")
    add("- The notebook is analysed, never executed.")
    add("- `READY` means no issue was detected by the supported checks, not that the notebook runs.")
    add("- Runtime snapshots are published CI data and can lag the live runtime.")
    add("- The AI explanation is secondary and can be wrong; the deterministic findings stand alone.")
    add("")
    return "\n".join(lines)


def main() -> int:
    knowledge = build_knowledge()
    ingest(knowledge)

    result = rules.audit_notebook(str(ROOT / FIXTURE), SNAPSHOT)
    evidence = collect_evidence(knowledge, result)

    explanation = None
    status = "not attempted"
    try:
        explanation = explain(result, evidence)
        status = "one model call completed"
    except Exception as exc:
        status = f"{type(exc).__name__}"

    OUTPUT.write_text(
        build_markdown(result, evidence, explanation, status), encoding="utf-8"
    )
    print(f"wrote {OUTPUT.relative_to(ROOT)} (provider status: {status})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())