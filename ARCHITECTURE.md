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

Session 2 simplified these to four plain modules under `src/`. There are no classes
beyond the Pydantic models, no factories, and no interfaces.

| Module | Responsibility |
|---|---|
| `src/models.py` | Pydantic models: `Requirement`, `Finding`, `RuntimeInfo`, `AuditResult`. |
| `src/notebook_parser.py` | Read `.ipynb` as JSON, extract pip installs and imports. Never execute. |
| `src/runtime_checker.py` | Load a vendored snapshot from `data/runtimes/`, look up package versions. |
| `src/rules.py` | R001–R006 and status aggregation, plus the `audit_notebook` entry point. |
| `src/knowledge/` (Session 3) | Curated source ingestion, embeddings, LanceDB vector store. |
| `src/llm.py` (Session 3) | Provider construction isolated from application logic. One Agno call. |
| `app/streamlit_app.py` (Session 4) | Streamlit UI only. No analysis logic. |

`rules.audit_notebook(notebook_path, snapshot)` is the whole deterministic stage: one
function, plain data in, plain data out.

## Active rules

R001, R002, R003, R004, R005 and R006 are implemented.

R007 (malformed install command) is defined but **inactive**. Its trigger condition
overlaps with R006 and with the parser's existing behaviour of skipping tokens it
cannot interpret, so a separate finding would duplicate information already reported.
Reconsider it only if a distinct user-facing need appears.

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
- No runtime snapshot selected → `audit_notebook` returns `UNKNOWN` with an R006 finding and the notebook-local dependency list. Nothing is guessed.