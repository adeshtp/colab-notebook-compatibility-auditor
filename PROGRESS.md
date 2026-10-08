# PROGRESS.md

Session handoff. Read this first, then the governance documents.

## Current state

Session 1 (Baseline + Specification) is complete. **No application code has been written yet.**

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

## Files changed / created this session

```
.gitignore
AGENTS.md
AI_PROVIDER.md
ARCHITECTURE.md
PROJECT_SPEC.md
PROGRESS.md
README.md
RULES.md
SOURCES.md
pyproject.toml
scripts/fetch_runtimes.py
data/runtimes/{2025.07,2025.10,2026.01,2026.04,2026.07}/{pip-freeze.txt,os-info.txt,manifest.json}
data/sources/manifest.json
data/sources/colab_runtime_version_faq.md
data/sources/colab_backend_info_transparency.md
data/sources/colab_backend_info_readme.md
data/sources/colab_filesystem_conventions.md
data/sources/colab_pip_install_behaviour.md
Directory skeleton: src/colab_audit/, src/colab_audit/knowledge/, app/, tests/, tests/fixtures/, reports/, docs/
```

Nothing under `/Users/adeshtp/colab-audit-sanitized` was modified.

## Tests / results

No tests exist yet. Session 1 scope excluded application code. Verified by inspection: venv imports `pydantic` and `pytest`; snapshot files downloaded and hash-recorded; governance documents written and cross-referenced.

## Known problems

1. Corpus rarely pins versions, so R001 will fire rarely. Report this honestly in evaluation rather than widening rules to manufacture hits.
2. `pip-freeze.txt` uses PEP 440 direct-reference form for some packages. Parser must handle it.
3. Runtime snapshot data can lag a live runtime by 1-2 days per Google's own caveat. Must appear in every report's `limitations`.
4. `qwen3.5:4b` emits thinking tokens that consume the response budget under schema constraints. Do not use it as default.
5. The reference notebook's raw archive contains a pre-existing redacted key-like string. Never copy raw notebooks into the repo.

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