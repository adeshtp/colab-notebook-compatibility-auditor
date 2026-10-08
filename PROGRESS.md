# PROGRESS.md

Session handoff. Read this first, then the governance documents.

## Current state

**Project complete.** 64 tests pass, 63 of them with no API key at all. The
deterministic audit, evidence retrieval, one-call explanation and Streamlit UI are all
built and verified end to end.

Locked provider decision: **Groq `openai/gpt-oss-20b`**, key from `GROQ_API_KEY`.
Ollama `ministral-3:3b` retained as an offline mode.

```python
from explainer import run_explanation
result, evidence, explanation = run_explanation("notebook.ipynb", "2026.07")
```

## Session 4 — UI and final verification

### Files created

```
app/streamlit_app.py        UI only, no analysis logic
tests/test_app.py           6 tests driving the real app via AppTest
.streamlit/config.toml      local run config, gatherUsageStats off
.streamlit/secrets.example.toml
reports/example_report.md   committed example report
```

### Files changed

- `README.md` — rewritten for a reader who has not seen the project.
- `ARCHITECTURE.md` — final pipeline, UI behaviour, retrieval behaviour.
- `pyproject.toml` — `groq` moved into the `llm` extra, `ollama` into a `local` extra.
- `.gitignore` — `.streamlit/secrets.toml`, local model caches.
- `src/explainer.py` — two docstrings that still claimed Ollama was the default.
- `PROGRESS.md` — this section.

### Measured final facts

**Archive verification, deterministic only, no LLM:**

```
notebooks audited : 83
parse/runtime failures : 0
statuses : 66 ATTENTION, 17 READY
rules   : R002 112, R004 108, R003 59, R001 0, R005 0
```

R001 and R005 fire zero times because none of the archived notebooks pins a version.
That is a property of the corpus, not a defect.

**Case A — `mismatching_pin.ipynb` vs `2026.07`, 1 Groq call:**

```
status HIGH_RISK | findings [('R001','numpy','HIGH')] | deps 2
evidence {'R001': 3} | elapsed 2.31s | unexplained []
versions 1.24.3 and 2.0.2 both preserved in the explanation
```

The model noted the retrieved evidence does not itself state 2026.07's numpy version,
which is faithful: that chunk does not contain it.

**Case B — `unpinned_package.ipynb` vs `2026.07`, 1 Groq call:**

```
status ATTENTION | findings [('R002','opendatasets','ATTENTION'),
                             ('R004','opendatasets','UNKNOWN')]
evidence {'R002': 3, 'R004': 3} | elapsed 2.45s | unexplained []
```

**Archive notebook — `fraud_detection_ad.ipynb` vs `2026.07`, 1 Groq call:**

```
status ATTENTION | 6 findings across R002, R003, R004
evidence {R002: 3, R003: 3, R004: 3} | elapsed 1.73s | unexplained []
```

**Degraded path, no `GROQ_API_KEY`, LLM stage requested:**

```
status HIGH_RISK | findings [('R001','HIGH','numpy')] | deps 2
evidence {'R001': 3} | explanation None
```

The audit stays fully usable with no key.

### Test result

```
63 passed, 1 deselected   # -m "not integration", no API key
64 passed                 # full suite, includes one live Groq call
```

The single live call is marked `integration`. No test requires a key to pass.

### Intermittent Groq failure found during final verification

The first full-suite run failed the integration test with Agno logging
`All parsing attempts failed`. Reproduced investigation: 8 consecutive isolated
integration runs passed, then 3 consecutive full-suite runs passed. Counting every live
Groq call made in this session, that is **1 failure in roughly 14 calls**, followed by
11 consecutive successes.

This is a real reliability characteristic, not a flake to be dismissed. It matches what
`AI_PROVIDER.md` already warned about: Agno reports
`supports_native_structured_outputs = False` for Groq, so the response schema is
advisory rather than enforced server-side.

The product consequence is bounded and was verified: a parse failure raises inside
`explain()`, the app catches it, sets `llm_status = "failed"`, and shows "AI explanation
unavailable. Deterministic audit completed successfully." The audit and the evidence are
untouched. That is the degradation path doing its job.

It is also why the deterministic core never depends on this call.

### Streamlit verification

`streamlit run app/streamlit_app.py` serves HTTP 200 with no app-side exceptions.
The full flow is covered by `tests/test_app.py` using Streamlit's own `AppTest`,
including the no-key path rendering `HIGH_RISK` and `R001`.

A first attempt at these tests loaded the app module via an AST filter so it could be
tested without a server. That was fragile and was replaced with `AppTest`, which drives
the real app.

### Files and counts for the record

| Session 2 tests | 34 |
| Session 3 tests | 19 |
| Provider evaluation tests | 4 |
| Session 4 tests | 6 |
| **Total** | **63 without a key, 64 with the integration call** |

| Fact | Value |
|---|---|
| Deterministic rules | R001–R006 active, R007 defined but inactive |
| Agno | `3.1.1` |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` |
| Vector store | local LanceDB, rebuilt from 5 committed sources |
| Curated sources | 5, all official, all `SOURCE_FACT` |
| Runtime snapshots | 5, pinned commits |
| Provider | Groq `openai/gpt-oss-20b` |
| Offline provider | Ollama `ministral-3:3b` |
| Gemini | evaluated, rejected: one 503 of two requests, versions abstracted away |
| LLM calls per audit | 1 |

### Honest limits of everything measured

1. The provider comparison was two cases per provider. It is an engineering selection.
   **No accuracy percentage, win rate or statistical claim is made anywhere.**
2. Groq's structured output failed 1 call in roughly 14 observed, and the schema is not
   server-enforced. See the section above.
3. Ollama coverage varied between runs on the same case. Local model output is not
   deterministic.
4. Latency was measured on one machine with a warm embedding cache.
5. `READY` is not a guarantee. Nothing in this project has executed any notebook.
6. Streamlit Community Cloud readiness is an assessment. Nothing has been deployed.
7. The example report uses a committed test fixture rather than a private notebook, so
   no private content is published.

### Known limitations of the project

1. Regex parsing, not `ast`: an `import` in a comment is read as a dependency.
2. Six-entry import-to-distribution map; unmapped mismatches give a false `UNKNOWN`.
3. Snapshot data can lag a live runtime by one to two days, per Google's own README.
4. `git+` references carry no version and are treated as absent.
5. Retrieval relevance is not scored numerically.
6. Five small documents cannot explain third-party breaking changes.
7. Groq is a hosted dependency; the offline mode is slower and less complete.

### Security check performed

Searched the repository for `gsk_`, `sk-`, `sk-or-v1`, `AQ.Ab` and key assignments:
**no credential values are tracked.** Secret names appear only as variable references in
docs and `src/explainer.py`. `.gitignore` covers `.env`, `.streamlit/secrets.toml`,
`data/lancedb/`, `inbox/` and local model caches. The key is read at runtime from the
environment or Streamlit secrets and is never displayed.

## Provider evaluation session (2026-10-08)

Purpose: pick the best-fit provider, measured rather than assumed. Baseline problems
were 53 s per call, a hot machine, and a 3B model that left R004 unexplained.

### Method

`scripts/compare_providers.py`. Same two fixtures, same findings, same retrieved
evidence, same system prompt, same `ExplanationResult` schema. Only the model changed.
**Two requests per provider, four in total.** Raw records committed under
`reports/provider_eval_*.json`.

Case A = `mismatching_pin.ipynb` vs `2026.07` (R001, numpy, 1.24.3 vs 2.0.2).
Case B = `unpinned_package.ipynb` vs `2026.07` (R002 + R004), the case the local model
had already failed.

### Measured results

| Dimension | Ollama `ministral-3:3b` | **Groq `openai/gpt-oss-20b`** | Gemini `gemini-3.8-flash` |
|---|---|---|---|
| Case A latency | 52.97 s | **1.67 s** | 15.51 s |
| Case B latency | 52.32 s | **1.44 s** | failed, 3.92 s |
| Requests succeeded | 2 / 2 | **2 / 2** | 1 / 2 |
| Structured output valid | yes | **yes** | yes on the one success |
| Case B R002 + R004 coverage | **R004 missing** | **both explained** | not measured |
| Versions reproduced exactly | yes | **yes** | **no, all three omitted** |
| Rule ids reproduced exactly | yes | **yes** | yes |
| Signalled uncertainty | yes | **yes** | no |
| Overreach phrases | none | **none** | none |
| Speculative snapshot mentions | none | **none** | none |
| Agno native structured output | `True` | `False` | `True` |
| Local hardware | sustained CPU | none | none |
| API key needed | no | yes | yes |

**Decision: Groq.** It was fastest by roughly 30x, and the only provider to explain
every supplied rule on the case the local model had been failing. Gemini lost on a
`503 high demand` failure and on abstracting away every concrete version. Full
reasoning, caveats and the deployment assessment are in `AI_PROVIDER.md`.

### This does not claim statistical superiority

Two cases per provider is an engineering selection, not a benchmark. No accuracy
percentage, win rate or significance claim is made anywhere.

### Defects found and fixed while evaluating

1. **Gemini `503` surfaced as a `ValidationError`.** A provider outage arrives as an
   error document in the response body, and it was being fed to
   `ExplanationResult.model_validate`. Added `explainer.ProviderError` and
   `parse_explanation` so the real reason is reported. Found during this evaluation, not
   theoretical.
2. **Two bugs in the measurement harness itself.** Runtime versions were read only from
   `dependencies`, so legitimate quotes of `2.0.2` were scored as invented; and the
   overreach pattern flagged "not guaranteed", which is correct hedging. Both fixed and
   the harness self-tested against known inputs.

### Infrastructure notes found

- Groq returns Cloudflare `error code: 1010` to a bare Python `urllib` request.
  Agno's client sends a normal User-Agent and is unaffected. Anyone testing with
  `curl` or `urllib` directly will hit this.
- Agno's `Gemini` class reads only `GOOGLE_API_KEY` and logs a false
  `GOOGLE_API_KEY not set` error when only `GEMINI_API_KEY` is set, even though the
  underlying SDK falls back and the call succeeds.

### Files changed this session

```
src/explainer.py            groq + gemini branches, ProviderError, parse_explanation,
                            default provider switched to groq
tests/test_explainer.py     provider construction, default assertion, error handling
scripts/compare_providers.py new evaluation harness
reports/provider_eval_*.json measured results, now tracked as evidence
AI_PROVIDER.md              evaluation table, decision, caveats, deployment fit
README.md                   provider line and install instructions
PROGRESS.md                 this section
.gitignore                  keep provider_eval_*.json, ignore other report output
```

No new rules, no new knowledge sources, no RAG changes, no Session 2 or 3 behaviour
changes. `knowledge_base.py`, `models.py`, `notebook_parser.py`, `runtime_checker.py`
and `rules.py` are untouched.

### Known limitations of this evaluation

1. Two cases per provider. Groq's structured output was observed on 2 calls, not
   measured over many, and Agno reports `supports_native_structured_outputs = False`
   for Groq.
2. Ollama results varied between runs: one run covered R004, two did not. Local model
   output is not deterministic.
3. Latency was measured on one developer machine with a warm model cache.
4. No cost figure is given for Groq's paid tier. The project targets the free tier.
5. Streamlit Community Cloud suitability is assessed, not deployed.

## Session 3 — what was built

### Files created

```
src/knowledge_base.py    build_knowledge, load_sources, ingest, retrieve
src/explainer.py         build_model, build_query_for, distinct_findings,
                         collect_evidence, build_prompt, explain,
                         unexplained_rules, is_llm_enabled, run_explanation
tests/test_knowledge_base.py
tests/test_explainer.py
```

### Files changed

- `ARCHITECTURE.md` — real pipeline, request budget, evidence separation, degradation.
- `AI_PROVIDER.md` — Session 3 verification table and the four defects found while running it.
- `README.md` — evidence and explanation section, install and test instructions.
- `pyproject.toml` — registered the `integration` marker.
- `PROGRESS.md` — this section.

**No Session 2 file was modified.** `models.py`, `notebook_parser.py`,
`runtime_checker.py`, `rules.py` and their three test files are untouched. Verified with
`git diff --stat HEAD~1` showing no changes to those paths.

### Dependencies added

```
agno==3.1.1
lancedb==0.40.0
sentence-transformers==6.1.0
torch==2.14.1            (pulled in by sentence-transformers)
transformers==5.19.0
ollama==0.6.3
openai==3.26.1           (required transitively by agno.models.ollama, no key used)
```

### Versions actually used

| Component | Version / model |
|---|---|
| Agno | `3.1.1` |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` |
| Vector store | local LanceDB at `data/lancedb/` |
| LLM | Ollama `ministral-3:3b` |
| API key required | **No** |

### Defects found and fixed while verifying

1. **Agno `Document` API drift.** `Document` has `meta_data`, not `metadata`, and
   exposes no `score` field in 3.1.1. Retrieval now carries `rank` instead of inventing
   a similarity number.
2. **Chunking swallowed the body text.** Default chunk size treated each 2-3 KB source
   as one chunk, so retrieved content was mostly YAML front matter. Fixed with
   `MarkdownReader(chunk_size=600)`.
3. **`agno.models.ollama` imports `agno.models.openai`.** The `openai` package must be
   installed even though no OpenAI account, key or request is involved.
4. **Uncapped generation produced invalid JSON.** The 3B model ran past 300 and then
   past 800 tokens and returned truncated, unparseable JSON both times. Fixed with
   `options={"num_predict": 700}` plus explicit brevity instructions in the schema field
   descriptions.

### Local model result

The local model works. It returns valid structured output grounded in the retrieved
evidence, quotes the rule ids correctly, and marks unverified points as unverified. It
also produced one overreach: in the first run it claimed evidence "confirms 2026.07's
runtime explicitly lists numpy 2.0.2", which the retrieved chunk did not say. The prompt
now instructs the model to mention only snapshots present in the evidence.

### Test result

```
53 passed in 107s          # full suite
52 passed, 1 deselected   # -m "not integration", no LLM, no Ollama needed
```

Deterministic tests still pass with no key and no model. The one live model call is
marked `integration` and skips itself when Ollama is not reachable.

### End-to-end demo

`tests/fixtures/mismatching_pin.ipynb` against snapshot `2026.07`, **1 LLM call**:

- Deterministic: `HIGH_RISK`, R001, HIGH, numpy, cell 0, unchanged after the call.
- Evidence: 3 chunks, all from `colab-runtime-version-faq`, URLs preserved, inspectable
  before the call.
- Query built deterministically: `"R001 numpy Notebook pins numpy==1.24.3 but the
  selected runtime contains 2.0.2."`
- Model output: summary plus an explanation of R001 quoting the rule id and both
  versions exactly as given, one recommendation, one limitation.
- `unexplained_rules` returned `[]`.

### Known limitations

1. **The 3B model does not reliably explain every rule.** On a two-rule notebook
   (R002 + R004) it explained R002 and moved the R004 discussion into `limitations`,
   even after the field descriptions were tightened. `explainer.unexplained_rules`
   reports this gap deterministically rather than hiding it. A stronger local model
   would fix it; that is a model-quality limit, not a pipeline one.
2. **One LLM call takes 1-2 minutes on CPU.** Acceptable for a portfolio demo, too slow
   for a tight loop.
3. **Retrieval relevance is not scored numerically.** Agno 3.1.1 does not expose the
   similarity score, so results are only ordered, and no retrieval metric is claimed.
4. **The corpus is 5 small documents.** It answers questions about Colab runtime
   versioning and `/content/` paths. It cannot explain a specific third-party package's
   breaking changes; those need a Tier 3 source that this project has not added.
5. **The 83-notebook archive was not run through the LLM.** By design. Only
   deterministic verification was repeated on it.
6. **Session 2 limitations still stand** and are unchanged: regex rather than `ast`
   parsing, six-entry import-to-distribution map, `git+` references in `pip-freeze.txt`
   treated as absent.

## Project status: complete

All four sessions are finished and verified. No further development session is planned.

Optional future work, none of it started and none of it required:

- Add third-party package documentation as a Tier 3 source if explaining breaking
  changes ever becomes a goal.
- Replace regex parsing with `ast`, which would remove the comment false positive.
- Widen the import-to-distribution map.
- Add a larger hand-labelled rule evaluation set and report measured precision and
  recall. Not done deliberately: with one labelled set and 83 unlabelled notebooks,
  any accuracy figure would be an invention.

Do not add new rules, new knowledge sources, or new providers without updating
`PROJECT_SPEC.md` and `RULES.md` first.

## Verified environment

- macOS, Python 3.14.3, `python3` at `/opt/homebrew/bin/python3`
- Project venv at `.venv` (created this session). Verified: `pydantic 2.14.0`, `pytest 9.1.1`
- Git repository initialised in `/Users/adeshtp/Desktop/colab_rag` (was not a repo before)
- Ollama running locally on port 11434 with `ministral-3:3b` and `qwen3.5:4b`
- No LLM API keys present in the environment or `~/.zshrc`
- Raw notebook archive lives outside the repo at `/Users/adeshtp/colab-audit-sanitized/inbox` (86 notebooks). Read-only. Not copied, not modified.

## What was verified this session

### Reference notebook inspection (`inbox/AgnoAi_ad.ipynb`)

29 cells, nbformat 4.0. Contents are unrelated demos: generic agent, DuckDuckGo research team, finance team with yfinance, SQLite memory, Hacker News team, recipe RAG, structured Pydantic output, vision, custom tool.

Reusable mechanism extracted:

| Mechanism | Cell | Reuse decision |
|---|---|---|
| `PDFReader` + `Knowledge` + `LanceDb` + `SentenceTransformerEmbedder` | 19-20 | Reuse the pattern, not the recipe PDF |
| `Agent(knowledge=..., search_knowledge=True)` | 21-22 | Reuse, collapsed to one agent |
| Pydantic `output_schema=` structured output | 24 | Reuse |
| `OpenRouter` free model ids | 0-2, 8 | Reference only. Default provider is local Ollama |

Not carried forward: multi-agent teams, DuckDuckGo, yfinance, Hacker News, SQLite memory, vision, custom tools.

**Important API drift found:** the reference notebook uses the Agno 2.x API. Verified against Agno 3.1.1 source: `Knowledge` no longer accepts `content=[...]`; content is added via `knowledge.insert(path=/url=/text_content=)`. `response_model` does not exist; the parameter is `output_schema`. `LanceDb(uri=, table_name=, embedder=)`. `Ollama` declares `supports_native_structured_outputs = True`. Session 3 must use the 3.x forms.

Also found: cell 0 of the notebook contains what looks like a hardcoded key that was already redacted upstream. **The raw archive must never be copied into this repo.**

### Corpus survey (86 notebooks, read-only scan)

- 76 `!pip install` lines across the corpus. All unpinned — **zero** explicit version pins.
- Most common install: `!pip install opendatasets` (about 50 notebooks).
- Also seen: `emoji`, `wikipedia`, `nltk`, `gensim`, `reverse_geocode`, `crewai crewai-tools litellm`, `langchain ...`, `agno[pdf] lancedb sentence-transformers openai pypdf`.
- Malformed/edge forms present: `pip install nltk` without the `!` prefix.
- 86 notebooks reference `/content/` paths.
- 49 distinct top-level import names. Notable import-vs-distribution mismatches: `sklearn`→`scikit-learn`, `cv2`→`opencv-python`, `bs4`→`beautifulsoup4`, `langchain_core`→`langchain-core`.
- Non-package imports present: `re`, `os`, `string`, `random`, `warnings`, `shutil`, `datetime`, `typing`. These need a standard-library exclusion list.

Implication for Session 2: R001 (explicit version mismatch) will rarely fire on this corpus because nothing is pinned. R002 (unpinned) and R004 (absent from runtime) will carry most of the signal. This must be reported honestly rather than tuned away.

### Runtime snapshot data

Vendored 5 Colab runtime snapshots into `data/runtimes/` from `googlecolab/backend-info` at pinned commits. Fetch script is `scripts/fetch_runtimes.py`; all 10 files verified present with recorded SHA-256.

| Snapshot | Commit | Packages | Ubuntu | Python |
|---|---|---|---|---|
| 2026.07 | `ec53f93f` | 643 | 22.04.5 | 3.12.13 |
| 2026.04 | `77d5dbef` | 668 | 22.04.5 | 3.12.13 |
| 2026.01 | `bd8aaa45` | 662 | 22.04.5 | 3.12.12 |
| 2025.10 | `7a0599e3` | 671 | 22.04.4 | 3.12.12 |
| 2025.07 | `ef1cba03` | 636 | 22.04.4 | 3.11.13 |

Important detail: `2025.07` uses Python 3.11.13 while all later snapshots use 3.12.x. That is a real, checkable compatibility boundary for notebooks pinned to older TensorFlow/Keras versions.

Also noted: some `pip-freeze.txt` lines use URL form, e.g. `torch @ https://download.pytorch.org/whl/cpu/torch-2.10.0%2Bcpu-cp312-cp312-manylinux...whl`. The runtime parser must handle the PEP 440 direct-reference form, not just `name==version`.

### Provider decision

**Local Ollama, model `ministral-3:3b`.** Free, no key, no quota, native structured output support.

Verified by live call: `ministral-3:3b` returns valid schema-constrained JSON for a `status`/`summary` object. `qwen3.5:4b` returns an **empty** content string under the same schema because it exhausts the token budget in a `thinking` field, which is why it is not the default.

OpenRouter free tier recorded as an optional alternative. Verified 20 zero-price models currently exist, several advertising `structured_outputs`. Not the default because it requires a key.

**No API key is needed for this project as currently configured.**

### Knowledge base

Five curated source documents in `data/sources/`, each with YAML front-matter (`source_id`, `source`, `title`, `url`, `retrieved`, `runtime_context`, `content_type`) plus a matching entry in `data/sources/manifest.json`. All are from the official Google Colab documentation or the `googlecolab` GitHub organisation. No blogs, no Stack Overflow, no SEO pages.

## Session 2 — what was built

### Files created

```
src/models.py                 Requirement, Finding, RuntimeInfo, AuditResult
src/notebook_parser.py        read_notebook, extract_dependencies, find_content_paths
src/runtime_checker.py        load_snapshot, version_in_snapshot, versions_match
src/rules.py                  R001-R006, aggregate_status, audit_notebook
tests/test_notebook_parser.py
tests/test_runtime_checker.py
tests/test_rules.py
tests/fixtures/matching_pin.ipynb
tests/fixtures/mismatching_pin.ipynb
tests/fixtures/unpinned_package.ipynb
tests/fixtures/unknown_package.ipynb
tests/fixtures/conflicting_install.ipynb
tests/fixtures/content_paths.ipynb
tests/fixtures/clean_notebook.ipynb
tests/fixtures/malformed_install.ipynb
```

### Files changed

- `ARCHITECTURE.md` — module table rewritten to the four flat modules; recorded that R007 is inactive and why; recorded that no snapshot means `UNKNOWN` rather than partial rules.
- `README.md` — usage, example output, rules table, test instructions.
- `PROGRESS.md` — this section.
- Deleted the unused `src/colab_audit/` package placeholder from Session 1.

Nothing under `/Users/adeshtp/colab-audit-sanitized` was modified.

### Design decisions worth recording

1. **R002 reports pip installs only, not bare imports.** Reporting every unpinned
   import would flood the report. `rules.check_unpinned` documents this.
2. **R004 gives `UNKNOWN`, never a failure claim**, because Google's own README says
   snapshot data can lag a live runtime by one to two days.
3. **Aggregation order is HIGH > ATTENTION > UNKNOWN > READY**, as written in
   `RULES.md`. A notebook that both installs `opendatasets` unpinned and uses a
   `/content/` path reports `ATTENTION`, not `UNKNOWN`.
4. **The `specifier` field was removed from `Requirement`.** It existed only to hold
   text already present in `raw`. Two fewer things to keep in sync.
5. **Only literal versions count as pins.** `numpy==1.24.*`, `pkg==1.0.0,!=1.0.1` and
   `tf==2.9.0 ; python<'3.11'` are not exact pins, so R001 must not fire on them. They
   are skipped rather than guessed at.

## Test result

```
34 passed in 0.12s
```

Run with `.venv/bin/python -m pytest`. No API key, no network.

Verified against the real 83-notebook archive (read-only, not committed): every file
parses without raising. Distribution: 66 ATTENTION, 17 READY. Findings: 112 R002,
108 R004, 59 R003. R001 and R005 fired zero times, as expected — the corpus contains no
version pins, so there is nothing for R001 to mismatch.

## Known problems

1. R001 and R005 never fire on this corpus because nothing is pinned. This is a
   property of the notebooks, not a bug. A pinned-version fixture is needed to
   demonstrate them, which the test fixtures provide.
2. `torch` resolves to `2.11.0` from a PEP 440 direct reference in `pip-freeze.txt`.
   Version is extracted from the wheel filename. A git reference (`pkg @ git+...`)
   carries no version and is skipped, so such a package looks absent and produces an
   R004 `UNKNOWN`. That is conservative and correct.
3. Snapshot data can lag a live runtime by 1-2 days per Google's own caveat. Must
   appear in every report's `limitations`.
4. The parser reads text with regex. It does not use `ast`, so an `import` inside a
   comment or docstring would be picked up. Verified this does not affect the current
   corpus but it is a known false-positive source.
5. `qwen3.5:4b` emits thinking tokens that consume the response budget under schema
   constraints. Do not use it as the Session 3 default.
6. The reference notebook's raw archive contains a pre-existing redacted key-like
   string. Never copy raw notebooks into the repo.
7. The import-to-distribution map covers 6 known cases (`sklearn`, `cv2`, `bs4`,
   `PIL`, `yaml`, `dotenv`). Anything else where import name and distribution name
   differ will be reported as an absent package and yield a false R004.

## Next session objective

**SESSION 3 — RAG + AGNO.** Deterministic core is done and must not be rewritten.

1. Install the `llm` extra: `agno`, `lancedb`, `sentence-transformers`, `ollama`.
2. `src/knowledge.py`: ingest the 5 curated files in `data/sources/` via
   `Knowledge.insert(path=...)`, embed with `SentenceTransformerEmbedder`, store in
   `LanceDb`. **Use the Agno 3.x API** — the reference notebook uses 2.x.
3. Retrieve evidence deterministically before any model call. Query from the
   deterministic findings: snapshot id, Python version, `/content/` assumptions.
4. One `Agent` call with `output_schema` producing the explanation, recommended checks,
   and limitations prose. Never the status, never the version facts.
5. Record `llm_provider`, `llm_model`, and `llm_status` on the output.
6. Graceful degradation: no key or provider failure must leave the deterministic
   report intact. Do not change the architecture or switch to a paid model.
7. Small fixed RAG evaluation set checking retrieval relevance, grounding, and that
   citations are preserved. No invented scores.

Do not start the Streamlit UI in Session 3.

## Archived: Session 2 objective (complete)

Superseded by the Session 2 section above. Session 2 delivered all of it:
`src/models.py`, `src/notebook_parser.py`, `src/runtime_checker.py`, `src/rules.py`,
8 fixtures, and 34 tests.