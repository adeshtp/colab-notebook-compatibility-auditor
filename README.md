# Colab Notebook Compatibility Auditor

An old Google Colab notebook, checked against a real Colab runtime snapshot.

> **This tool identifies detectable compatibility risks. It does not guarantee that a
> notebook will execute successfully.**

## Problem

Google Colab runtimes are updated frequently. A notebook written a year ago may pin a
package version that no longer matches the runtime, install packages without pins,
depend on packages that are not present, or assume Colab-specific filesystem paths.
When someone reuses that notebook, the failures are cryptic.

The audience is a data-science learner or developer trying to reuse an old notebook.

## Solution

Parse the notebook as JSON, extract its package references, compare them against the
real pre-installed package set that Google publishes for a chosen runtime, and report
the differences. Then retrieve official Colab documentation about those differences and
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

## Report states

| State | Meaning |
|---|---|
| `READY` | No obvious risk detected by the implemented checks. |
| `ATTENTION` | One or more detectable risks or assumptions worth reviewing. |
| `HIGH_RISK` | One or more deterministic high-severity rule violations. |
| `UNKNOWN` | Insufficient evidence to conclude; manual verification required. |

Worst-first aggregation: `HIGH` → `HIGH_RISK`, then `ATTENTION`, then `UNKNOWN`,
otherwise `READY`.

`READY` means **no obvious risk was detected by the implemented checks**. It does not
mean the notebook will run.

## The six rules

| Rule | What it detects | Severity |
|---|---|---|
| R001 | Notebook pins a version that differs from the runtime snapshot | `HIGH` |
| R002 | A pip install with no exact version pin | `ATTENTION` |
| R003 | `/content/` Colab path assumptions | `ATTENTION` |
| R004 | A package absent from the snapshot | `UNKNOWN` |
| R005 | The same package installed twice with different requirements | `HIGH` |
| R006 | Insufficient evidence to conclude | `UNKNOWN` |

Full definitions, detection logic and per-rule limitations are in `RULES.md`.

## Evidence comes from official sources

Five curated documents from Google Colab documentation and the `googlecolab` GitHub
organisation. No blogs, no Stack Overflow, no SEO content. Provenance for each is
recorded in `data/sources/manifest.json` and explained in `SOURCES.md`.

Runtime package data is vendored from `googlecolab/backend-info` at pinned commits for
five snapshots (`2025.07` → `2026.07`), so analyses are reproducible offline.

## Installation

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
```

`src/` is a flat script directory rather than an installed package, so put it on the
import path when you use the Python API:

```bash
export PYTHONPATH=src
```

That is what makes `from rules import audit_notebook` work, from any directory. The
Streamlit app sets this up for itself, and pytest is configured with `pythonpath` in
`pyproject.toml`.

For the AI explanation you also need a Groq API key:

```bash
export GROQ_API_KEY=...     # never commit this
```

The deterministic audit and evidence retrieval work with no key at all.

## Usage

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

To include the evidence and the AI explanation, call the same three plain functions the
Streamlit app calls:

```python
from explainer import collect_evidence, explain
from knowledge_base import build_knowledge, ingest

knowledge = build_knowledge()
ingest(knowledge)                       # rebuild the local index from curated sources

result = rules.audit_notebook("my_old_notebook.ipynb", "2026.07")
evidence = collect_evidence(knowledge, result)      # deterministic, one search per rule
explanation = explain(result, evidence)             # one model call, prose only

print(result.status)                        # never affected by the model
print(evidence["R001"][0]["url"])           # inspectable before any model call
print(explanation.summary)
```

Findings are deduplicated by rule before retrieval, so a notebook with 40 findings
still costs **one** model call. If the provider fails, catch `ProviderError` and keep the
deterministic result; the Streamlit app shows this path.

### Streamlit UI

```bash
.venv/bin/streamlit run app/streamlit_app.py
```

Upload a notebook, pick a runtime snapshot, press Analyze. The report shows the
deterministic findings first, then the retrieved evidence grouped by source with links,
then the AI explanation under a clearly separated heading. There is no chat interface.

## Providers

| Provider | Model | Key | Role |
|---|---|---|---|
| **Groq** | `openai/gpt-oss-20b` | `GROQ_API_KEY` | Default |
| Ollama | `ministral-3:3b` | none | Optional fully offline mode |

Set `COLABAUDIT_LLM_PROVIDER=ollama` and `COLABAUDIT_LLM_MODEL=ministral-3:3b` for the
offline mode. Configuration and the measured selection are in `AI_PROVIDER.md`.

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
.venv/bin/python -m pytest
```

**63 passed, 1 skipped.** The suite makes no network request, needs no API key and runs
no local model inference. The single skipped test is a live Ollama call, opt-in:

```bash
RUN_OLLAMA_TESTS=1 .venv/bin/python -m pytest -m integration
```

The UI tests drive the real app through Streamlit's `AppTest`, including the no-key
degraded path.

## What was verified

Measured on the development machine, not estimated:

- **83 archived Colab notebooks** audited with zero parse or runtime failures.
  Distribution: 66 `ATTENTION`, 17 `READY`. Findings: R002 × 112, R004 × 108,
  R003 × 59.
- R001 and R005 fire zero times on that archive because none of those notebooks pins a
  version. That is a property of the corpus, not a gap in the rules. The test fixtures
  exercise both.
- Groq returns in 1.4–2.5 s per call and explained every supplied rule in testing.

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
- **Runtime snapshots differ in Python version.** `2025.07` ships Python 3.11.13 while
  every later snapshot is 3.12.x, which matters for notebooks written against older
  TensorFlow or Keras releases.
- **Retrieval relevance is not scored numerically.** Agno 3.1.1 does not expose the
  similarity score, so results are ordered and no retrieval metric is claimed.
- **The corpus is five small documents.** It covers Colab runtime versioning and
  `/content/` paths. It cannot explain a specific third-party package's breaking changes;
  no package-documentation source tier is implemented.
- **One model call per audit, not zero.** If the provider is unavailable the audit still
  completes, but the prose layer is missing.
- **The explanation call is not fully reliable.** Agno reports
  `supports_native_structured_outputs = False` for Groq, so the output schema is advisory
  rather than enforced. One call in roughly fourteen observed failed to parse. When that
  happens the UI says the AI step is unavailable and the deterministic report is
  unaffected.
- **No accuracy figure is claimed.** The provider comparison used two cases per provider.
  This is an engineering selection, not a benchmark.

## What this is not

Not a universal debugger, not an autonomous debugging agent, not a package solver, not a
guaranteed compatibility checker, and not an automatic repair system. It never executes
a notebook, installs anything, resolves dependencies, performs full static analysis,
builds a dependency graph, or supports arbitrary Jupyter environments.

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
| `tests/` | pytest suite and notebook fixtures |
| `scripts/` | Fetch runtime snapshots, compare providers |
| `data/runtimes/` | Five vendored Colab runtime snapshots |
| `data/sources/` | Five curated official sources plus manifest |
| `reports/` | Example report, provider evaluation records, repository audit |

Reference documents: `RULES.md` (rule definitions and limitations), `ARCHITECTURE.md`
(pipeline and responsibility boundary), `AI_PROVIDER.md` (provider configuration and
the measured selection), `SOURCES.md` (data provenance).

## Licence

Code is MIT licensed, see `LICENSE`. The vendored files under `data/runtimes/` are
Google's `pip-freeze.txt` and `os-info.txt` output from `googlecolab/backend-info`,
which is Apache-2.0 licensed. See `SOURCES.md`.