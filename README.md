# Colab Notebook Compatibility Auditor

An old Google Colab notebook, checked against a real Colab runtime snapshot.

> **This tool identifies detectable compatibility risks. It does not guarantee that a
> notebook will execute successfully.**

## Problem

Google Colab runtimes are updated frequently. A notebook written a year ago may pin a
package version that no longer matches the runtime, install packages without pins,
depend on packages that are not present, or assume Colab-specific filesystem paths.
When someone reuses that notebook, the failures are cryptic.

## Solution

Parse the notebook as JSON, extract its package references, compare them against the
real pre-installed package set that Google publishes for a chosen runtime, and report
the differences. Then retrieve official Colay documentation about those differences and
generate a short grounded explanation.

## The AI does not decide anything

This is the most important design point.

```
.ipynb
  ↓  notebook_parser      read as JSON. Never executed.
  ↓  runtime_checker      package metadata from googlecolab/backend-info
  ↓  rules                R001–R006 decide what is a risk        ← authoritative
  ↓  knowledge_base       retrieve official evidence            ← deterministic
  ↓  explainer            ONE model call, prose only            ← cannot decide
```

The rule engine owns `rule`, `package`, `severity`, `status`, `message` and `cell`.
The model receives those as fixed input and may only write explanatory prose.

This is enforced structurally, not by convention: `ExplanationResult` has no version,
severity or status field, and `AuditResult` has no explanation field, so the two cannot
merge even by accident. The model never decides whether to search, what to search, or
which findings exist.

## The six rules

| Rule | What it detects | Severity |
|---|---|---|
| R001 | Notebook pins a version that differs from the runtime snapshot | `HIGH` |
| R002 | A pip install with no exact version pin | `ATTENTION` |
| R003 | `/content/` Colab path assumptions | `ATTENTION` |
| R004 | A package absent from the snapshot | `UNKNOWN` |
| R005 | The same package installed twice with different requirements | `HIGH` |
| R006 | Insufficient evidence to conclude | `UNKNOWN` |

`READY` means **no obvious risk was detected by the implemented checks**. It does not
mean the notebook will run. Status aggregates worst-first: `HIGH` → `HIGH_RISK`, then
`ATTENTION`, then `UNKNOWN`, otherwise `READY`.

## Evidence comes from official sources

Five curated documents from Google Colab documentation and the `googlecolab` GitHub
organisation. No blogs, no Stack Overflow, no SEO content. Provenance for each is
recorded in `data/sources/manifest.json`.

Runtime package data is vendored from `googlecolab/backend-info` at pinned commits for
five snapshots (`2025.07` → `2026.07`), so analyses are reproducible offline.

## Usage

```bash
python -m venv .venv
.venv/bin/pip install pydantic pytest streamlit
.venv/bin/pip install agno==3.1.1 lancedb sentence-transformers openai groq
```

```python
from rules import audit_notebook

result = audit_notebook("my_old_notebook.ipynb", "2026.07")

print(result.status)   # READY | ATTENTION | HIGH_RISK | UNKNOWN
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

### Streamlit UI

```bash
export GROQ_API_KEY=...      # optional; the audit works without it
.venv/bin/streamlit run app/streamlit_app.py
```

Upload a notebook, pick a runtime snapshot, press Analyze. The report shows the
deterministic findings first, then the retrieved evidence with source links, then the
AI explanation under a clearly separated heading. There is no chat interface.

### One request per audit

Findings are deduplicated by rule before retrieval, so a notebook with 40 findings
still costs **one** model call.

```python
from explainer import run_explanation

result, evidence, explanation = run_explanation("notebook.ipynb", "2026.07")
print(result.status)                    # deterministic, never from the model
print(evidence["R001"][0]["url"])       # inspectable before any model call
```

## Providers

| Provider | Model | Key |
|---|---|---|
| **Groq** (default) | `openai/gpt-oss-20b` | `GROQ_API_KEY` |
| Ollama (offline mode) | `ministral-3:3b` | none |

Selected by measurement, not preference. On the same fixtures, evidence and schema,
Groq returned in 1.4–1.7 s against 53 s locally, and was the only provider to explain
every supplied rule on the multi-rule case the local model failed. Full comparison and
caveats in `AI_PROVIDER.md`; raw records in `reports/provider_eval_*.json`.

**This was a two-case engineering comparison, not a benchmark.** No accuracy
percentage is claimed anywhere in this project.

Without a key the deterministic audit and evidence retrieval still work; the UI says
the AI step is unavailable rather than failing.

## Deployment

Ready for Streamlit Community Cloud. Put the key in Streamlit secrets:

```toml
# .streamlit/secrets.toml — never commit this
GROQ_API_KEY = "..."
```

The LanceDB index is rebuilt from the committed curated sources on each session start,
because a Cloud filesystem is not durable. No claim is made that a generated database
persists there. Nothing has been deployed.

## Tests

```bash
.venv/bin/python -m pytest -m "not integration"   # no API key needed
.venv/bin/python -m pytest                        # adds one live provider call
```

63 tests run with no API key. The live call is marked `integration` and skips itself
when the provider is unreachable. The UI tests drive the real app through Streamlit's
`AppTest`, including the no-key degraded path.

## Known limitations

- **Regex parsing, not `ast`.** An `import` inside a comment or docstring is read as a
  dependency. Verified not to affect the 83-notebook archive, but it is a real false
  positive source.
- **Short import-to-distribution map.** Six known cases (`sklearn`, `cv2`, `bs4`,
  `PIL`, `yaml`, `dotenv`). An unmapped name mismatch is reported as an absent package,
  producing a false `UNKNOWN`.
- **Snapshot data can lag.** Google's own README says published package lists reflect
  the most recent CI submission, not the live runtime, and may be one to two days behind.
- **`git+` references carry no version** in `pip-freeze.txt` and are skipped, so such a
  package looks absent and yields `UNKNOWN`. Conservative and correct, but conservative.
- **Retrieval relevance is not scored numerically.** Agno 3.1.1 does not expose the
  similarity score, so results are ordered and no retrieval metric is claimed.
- **The corpus is five small documents.** It covers Colab runtime versioning and
  `/content/` paths. It cannot explain a specific third-party package's breaking changes.
- **One model call per audit, not zero.** If the provider is unavailable the audit still
  completes, but the prose layer is missing.
- **The explanation call is not fully reliable.** Agno reports
  `supports_native_structured_outputs = False` for Groq, so the output schema is advisory
  rather than enforced. One call in roughly fourteen observed failed to parse. When that
  happens the UI says the AI step is unavailable and the deterministic report is
  unaffected.
- **No accuracy figure is claimed.** The provider comparison used two cases per provider.
  This is an engineering selection.

## What this is not

Not a universal debugger, not an autonomous debugging agent, not a package solver, not
a guaranteed compatibility checker, and not an automatic repair system. It never
executes a notebook, installs anything, or resolves dependencies.

## Repository layout

| Path | Purpose |
|---|---|
| `src/notebook_parser.py` | Read `.ipynb` as JSON, extract installs and imports |
| `src/runtime_checker.py` | Load a vendored runtime snapshot |
| `src/rules.py` | R001–R006 and status aggregation |
| `src/knowledge_base.py` | Curated sources, embeddings, local LanceDB retrieval |
| `src/explainer.py` | The single Agno call and its prompt |
| `src/models.py` | Pydantic data shapes |
| `app/streamlit_app.py` | UI only, no analysis logic |
| `data/runtimes/` | Five vendored Colab runtime snapshots |
| `data/sources/` | Five curated official sources plus manifest |
| `reports/` | Example report and provider evaluation records |

Governance documents `AGENTS.md`, `PROJECT_SPEC.md`, `RULES.md`, `ARCHITECTURE.md`,
`AI_PROVIDER.md`, `SOURCES.md` and `PROGRESS.md` define the project contract.