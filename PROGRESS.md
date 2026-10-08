# PROGRESS.md

Session handoff. Read this first, then the governance documents.

## Current state

Session 2 (Deterministic Core) is complete. 34 tests passing, no LLM key required.

The deterministic stage is one call: `rules.audit_notebook(notebook_path, snapshot)`.

```
.venv/bin/python -c "import sys; sys.path.insert(0,'src'); from rules import audit_notebook; print(audit_notebook('tests/fixtures/mismatching_pin.ipynb','2026.07').status)"
```

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

## Next session objective

**SESSION 2 — DETERMINISTIC CORE.** Must run with no LLM API key.

1. `src/colab_audit/models.py`: Pydantic models — `RuntimeSnapshot`, `Requirement`, `Finding`, `EvidenceItem`, `CompatibilityReport`. Include `origin` on findings to keep RULE / EVIDENCE / EXPLANATION separate.
2. `src/colab_audit/parsing.py`: validate and read `.ipynb` JSON. Never execute. Size limit, schema check, clear errors.
3. `src/colab_audit/extraction.py`: parse `pip install` (including bare `pip install` without `!`), `import`/`from`, standard-library exclusion list, import-to-distribution mapping (`sklearn`→`scikit-learn`, `cv2`→`opencv-python`, `bs4`→`beautifulsoup4`, `PIL`→`pillow`, `langchain_core`→`langchain-core`), cell index tracking.
4. `src/colab_audit/runtime.py`: load vendored snapshots. Handle `name==version`, PEP 440 direct references, and normalisation (`_` vs `-` vs `.`, case).
5. `src/colab_audit/rules.py`: R001-R007 as pure functions plus status aggregation.
6. `tests/fixtures/`: the 10 required notebooks — clean, matching pin, mismatching pin, unpinned, multiple installs, conflicting installs, `/content/` usage, unknown package, malformed install, harmless text mentioning package names.
7. `tests/`: extraction, version parsing, runtime comparison, rules, UNKNOWN handling, report serialisation.

Do not start the RAG or Agno layer in Session 2.