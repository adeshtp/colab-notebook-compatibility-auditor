# Colab Notebook Compatibility Auditor

Status: **Session 2 complete.** The deterministic core works and is tested. The RAG layer and UI are not implemented yet. See `PROGRESS.md`.

> This tool identifies detectable compatibility risks; it does not guarantee that a notebook will execute successfully.

## What it does

Give it an old Colab notebook and a runtime snapshot. It parses the notebook as JSON,
extracts package references, and compares them against the real pre-installed package
set published by Google for that runtime. Findings are deterministic, not guessed. A
local model then explains those findings using official Colab documentation.

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

## Evidence and explanation

After the audit, evidence is retrieved from a small curated corpus of official Colab
sources and one local model call turns it into prose.

```bash
export COLABAUDIT_LLM_ENABLED=1
```

```python
from explainer import run_explanation

result, evidence, explanation = run_explanation("my_old_notebook.ipynb", "2026.07")

print(result.status)          # computed deterministically, never by the model
print(evidence["R001"][0]["url"])   # inspectable before any model call
print(explanation.summary)
```

Retrieval is a direct Python call. The model never decides whether to search, what to
search, or which findings exist. One audit means one model call.

The explanation model cannot alter a finding: `ExplanationResult` has no version,
severity or status field, and `AuditResult` has no explanation field, so the two cannot
merge.

Provider: Groq `openai/gpt-oss-20b` by default, chosen by measured comparison against
local Ollama and Gemini. Needs `GROQ_API_KEY`. Set
`COLABAUDIT_LLM_PROVIDER=ollama` for a fully offline run with no key. See
`AI_PROVIDER.md`.

## Running the tests

```bash
python -m venv .venv
.venv/bin/pip install pydantic pytest
.venv/bin/pip install agno==3.1.1 lancedb sentence-transformers openai groq
.venv/bin/python -m pytest -m "not integration"   # no LLM key needed
.venv/bin/python -m pytest                        # adds one live model call
```

No API key is needed for any deterministic test. The RAG tests build a real local
LanceDB index, so the first run takes about a minute while the embedding model is
downloaded. The single live model call is marked `integration` and skips itself when
the provider is not reachable.

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
.ipynb → parsing → extraction → deterministic rules            [done]
       → retrieval from official Colab docs                     [done]
       → one local Agno explanation call                        [done]
       → Streamlit UI                                           [Session 4]
```

Notebooks are parsed as data and are never executed. The explanation model runs
entirely on your machine.