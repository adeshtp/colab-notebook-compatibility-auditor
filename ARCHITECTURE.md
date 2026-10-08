# ARCHITECTURE.md

## Workflow as built

```
.ipynb
  ↓
notebook_parser.extract_dependencies   deterministic, JSON only, never executed
  ↓
runtime_checker.load_snapshot          deterministic, vendored data/runtimes/
  ↓
rules.audit_notebook → AuditResult     deterministic R001–R006, plain functions
  ↓
knowledge_base.retrieve                deterministic, one search per distinct rule
  ↓
explainer.explain                      ONE Groq call, structured output
  ↓
ExplanationResult                      prose only, held separately
  ↓
app/streamlit_app.py                   renders all three in order
```

Optional: `COLABAUDIT_LLM_PROVIDER=ollama` gives a fully offline explanation step with
no API key.

Retrieval is a direct Python call. There is no agentic search: the model never decides
whether to search, what to search, or which findings exist.

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
| `src/knowledge_base.py` | Ingest the curated sources, embed with SentenceTransformer, store in local LanceDB, retrieve. |
| `src/explainer.py` | Build the evidence prompt and make the single Agno call. Provider construction lives here. |
| `app/streamlit_app.py` | Streamlit UI. Presentation only, no analysis logic. |

`rules.audit_notebook(notebook_path, snapshot)` is the whole deterministic stage: one
function, plain data in, plain data out. `explainer.run_explanation` chains the audit,
the retrieval and the one model call. The app calls those and renders the result.

Nothing under `src/` is a class except the Pydantic models. No factories, no
dependency injection, no service layer, no plugin registry. Provider selection is a
plain `if` in `explainer.build_model`.

## Request budget

One audit produces **one** LLM call. Retrieval happens before it.

- `explainer.distinct_findings` collapses repeated rules, so a notebook with 40 R002
  findings needs one search and one explanation slot, not 40.
- `collect_evidence` issues one `knowledge.search` per distinct rule, capped at 3
  chunks each.
- The prompt carries findings, evidence and limitations. Full notebook source is never
  sent.
- Generation is capped at 700 tokens. A 3B model on CPU will otherwise ramble past the
  token limit and return unparseable JSON.

## Active rules

R001, R002, R003, R004, R005 and R006 are implemented.

R007 (malformed install command) is defined but **inactive**. Its trigger condition
overlaps with R006 and with the parser's existing behaviour of skipping tokens it
cannot interpret, so a separate finding would duplicate information already reported.
Reconsider it only if a distinct user-facing need appears.

## Evidence separation

Three kinds of content, three separate types:

- `Finding` (`models.py`) — produced by `rules.py`. Holds `rule`, `package`, `severity`,
  `status`, `message`, `cell`. **Read-only to the model.**
- Evidence (`knowledge_base.retrieve` returns plain dicts) — retrieved chunk with
  `source_id`, `source`, `title`, `url`, `content_type`, `runtime_context`, `content`,
  `rank`. Inspectable before any model call.
- `ExplanationResult` (`explainer.py`) — model prose only. Its fields are `summary`,
  `explanations`, `recommendations`, `limitations`. It has no version, severity or
  status field, so the model **structurally cannot** write back into a finding.

`AuditResult` has no `summary` or explanation field. The two types cannot merge even by
accident.

## Retrieval behaviour

- Chunk size 600 with `MarkdownReader`, so a retrieved chunk is the relevant section
  rather than a whole document.
- `Knowledge.insert(path=..., skip_if_exists=True)`; `build_knowledge(rebuild=True)`
  clears a half-finished ingest from an interrupted run.
- Agno 3.1.1 does not expose the raw similarity score on the returned `Document`, so
  results carry `rank` rather than a fabricated score.
- Retrieval relevance is not scored numerically anywhere in this project.
- The Streamlit app calls `build_knowledge(rebuild=True)` once inside
  `st.cache_resource`, so the index is not rebuilt on every rerun and is always
  recreated from the five committed curated sources. A Streamlit Community Cloud
  filesystem is not durable, so the index is treated as rebuildable, never as
  persistent state.

## UI behaviour

The app renders three visually separated sections in pipeline order:

1. **Detected by auditor** — dependencies and findings from `rules.py`. Authoritative.
2. **Retrieved evidence** — source title, URL and chunk text, shown before any AI text.
3. **AI-generated explanation** — `ExplanationResult`, labelled with provider, model
   and status.

There is no chat interface and no free-text input. The user uploads a file and selects
a runtime; the app never accepts questions.

`llm_status` is one of `ok`, `disabled`, `not_configured` or `failed`. A raw exception
is reduced to its type name for display; the underlying `ProviderError` text is kept
in a caption for debugging.

## Degradation behaviour

- `COLABAUDIT_LLM_ENABLED` unset or `0` → `run_explanation` returns the audit and the
  evidence with `None` for the explanation. The deterministic pipeline is the default.
- Provider error or rate limit → `run_explanation` catches it and returns
  `(result, evidence, None)`. The deterministic report is untouched. No provider
  switching, no paid fallback, no architecture change.
- RAG retrieval returns nothing for a rule → that rule's evidence list is empty and the
  prompt records it as `(no evidence retrieved)`. The deterministic status is unchanged,
  because retrieval never drives a finding.
- No runtime snapshot selected → `audit_notebook` returns `UNKNOWN` with an R006
  finding. Nothing is guessed.
- The local model fails to explain every rule → `explainer.unexplained_rules` reports
  the gap deterministically instead of hiding it.