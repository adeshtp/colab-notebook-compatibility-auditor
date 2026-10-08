# Colab Notebook Compatibility Auditor

Status: **Session 2 complete.** The deterministic core works and is tested. The RAG layer and UI are not implemented yet. See `PROGRESS.md`.

> This tool identifies detectable compatibility risks; it does not guarantee that a notebook will execute successfully.

## What it does

Give it an old Colab notebook and a runtime snapshot. It parses the notebook as JSON,
extracts package references, and compares them against the real pre-installed package
set published by Google for that runtime. Findings are deterministic, not guessed.

```python
from rules import audit_notebook

result = audit_notebook("my_old_notebook.ipynb", "2026.07")

print(result.status)          # READY | ATTENTION | HIGH_RISK | UNKNOWN
for finding in result.findings:
    print(finding.rule, finding.package, finding.message)
```

```json
{
  "rule": "R001",
  "package": "numpy",
  "severity": "HIGH",
  "status": "RISK",
  "message": "Notebook pins numpy==1.24.3 but the selected runtime contains 2.0.2.",
  "cell": 0
}
```

## Rules

| Rule | What it detects |
|---|---|
| R001 | Notebook pins a version that differs from the runtime snapshot |
| R002 | A pip install with no exact version pin |
| R003 | `/content/` Colab path assumptions |
| R004 | A package absent from the snapshot, reported as `UNKNOWN` |
| R005 | The same package installed twice with different requirements |
| R006 | Insufficient evidence, reported as `UNKNOWN` |

`READY` means "no obvious risk detected by the implemented checks". It is not a
guarantee that the notebook runs.

## Running the tests

```bash
python -m venv .venv
.venv/bin/pip install pydantic pytest
.venv/bin/python -m pytest
```

No API key is needed. Nothing in the deterministic core imports a model provider.

## Governance documents

Read these before doing any work. They are the project contract.

| Document | Purpose |
|---|---|
| `AGENTS.md` | Permanent operating rules. |
| `PROJECT_SPEC.md` | Scope, inputs, outputs, report states. |
| `RULES.md` | R001–R007 deterministic rules with severities and limitations. |
| `ARCHITECTURE.md` | Module layout and the deterministic / RAG responsibility boundary. |
| `AI_PROVIDER.md` | LLM provider decision, configuration, key policy. |
| `SOURCES.md` | Knowledge base provenance and pinned runtime snapshot commits. |
| `PROGRESS.md` | Session handoff. Current objective lives here. |

## Runtime snapshots

Pinned Colab runtime package data lives in `data/runtimes/`. Each snapshot is vendored from `googlecolab/backend-info` at a fixed commit so results are reproducible offline.

## Planned workflow

```
.ipynb → safe JSON parsing → dependency extraction → deterministic rules   [done]
       → RAG over official Colab docs → Agno structured report → Streamlit UI   [later]
```

Notebooks are parsed as data and are never executed.