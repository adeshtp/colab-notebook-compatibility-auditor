# ARCHITECTURE.md

## Workflow

```
USER
  ↓
Streamlit
  ↓
Notebook Parser          (deterministic, JSON only)
  ↓
Dependency Extraction    (deterministic, regex/AST-free text parsing)
  ↓
Runtime Metadata Loader  (deterministic, local snapshot files)
  ↓
Deterministic Risk Rules (deterministic, pure functions)
  ↓
RAG Evidence Retrieval   (embeddings + LanceDB, local curated docs)
  ↓
Agno Agent               (one LLM call, structured output)
  ↓
Pydantic Structured Report
  ↓
UI
```

## Responsibility boundary

### Deterministic code owns

- Notebook parsing and validation
- Dependency and import extraction
- Version parsing and normalisation
- Runtime snapshot lookup
- Rule evaluation and finding creation
- Machine-readable findings and status aggregation
- Report schema definition and serialisation

### RAG / LLM owns

- Retrieving relevant official documentation for the detected findings
- Presenting evidence with source, title, URL, and runtime context
- Explaining detected findings in plain language
- Producing the human-readable explanation and recommended checks

### The LLM must not

- Invent package versions or compatibility facts
- Override a deterministic finding
- Change the report status
- Assert that a notebook will or will not run

The report status is computed deterministically. The model writes prose into `explanation` only.

## Modules

| Module | Responsibility |
|---|---|
| `colab_audit/parsing.py` | Validate and read `.ipynb` JSON. Extract cell sources. Never execute code. |
| `colab_audit/extraction.py` | Parse `pip install` lines and `import` statements into normalised requirements. |
| `colab_audit/runtime.py` | Load a curated runtime snapshot (packages + OS/python info) from `data/runtimes/`. |
| `colab_audit/rules.py` | R001–R007 evaluation. Pure functions over parsed inputs. |
| `colab_audit/models.py` | Pydantic models: `CompatibilityReport`, `Finding`, `EvidenceItem`, `RuntimeSnapshot`. |
| `colab_audit/knowledge/` | Curated source ingestion, SentenceTransformer embeddings, LanceDB vector store. |
| `colab_audit/llm.py` | Provider construction isolated from application logic. One Agno call. |
| `colab_audit/pipeline.py` | Orchestration. Deterministic stage always runs; RAG/LLM stage degrades gracefully. |
| `app/streamlit_app.py` | Streamlit UI only. No analysis logic. |

## Evidence separation

`Finding` objects carry `origin`:

- `RULE` — produced by deterministic code, with `rule_id`
- `EVIDENCE` — retrieved document snippet with `source`, `title`, `url`, `runtime_context`
- `EXPLANATION` — model-generated prose, marked as such and never merged into `deterministic_findings`

The three origins are stored in separate report fields so the model cannot blur them.

## Degradation behaviour

- No LLM key configured → deterministic report is produced, `explanation` is empty, and a clear note is recorded. No error.
- RAG retrieval returns nothing → `evidence` is empty and status becomes `UNKNOWN` per R006 where the conclusion depended on retrieval.
- Provider error or rate limit → the failure is recorded in the report and surfaced in the UI. The architecture is not changed and no paid fallback is triggered.
- No runtime snapshot selected → deterministic findings limited to notebook-local rules; anything version-dependent becomes `UNKNOWN`.