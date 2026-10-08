# Colab Notebook Compatibility Auditor

Status: **Session 1 complete.** Deterministic core, RAG layer, and UI are not implemented yet. See `PROGRESS.md`.

> This tool identifies detectable compatibility risks; it does not guarantee that a notebook will execute successfully.

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
.ipynb → safe JSON parsing → dependency extraction → deterministic rules
       → RAG over official Colab docs → Agno structured report → Streamlit UI
```

Notebooks are parsed as data and are never executed.