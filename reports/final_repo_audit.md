# Final Repository Audit

Evaluated as a technical interviewer and recruiter for the question:

> Can a recruiter clone this project, understand it, run it, and believe the claims?

**Scope:** audit only. Nothing was implemented, merged, simplified or deleted.

**Repository state at audit time:** commit `9da7f84`, working tree clean, 66 tracked files.

**Note on the referenced commit.** The audit was requested against `68848e7`. The actual
HEAD is `9da7f84`, which contains one additional commit fixing a stale provider
assumption in `tests/test_explainer.py`. All findings below are against `9da7f84`.

**Provider decision assumed locked:** primary Groq / `openai/gpt-oss-20b`; optional
offline Ollama / `ministral-3:3b`. Provider comparison already complete, not rerun.

---

## Summary judgement

The engineering is solid. The deterministic core is clean, well tested, and correctly
separated from the model. The rules are honest about their own limits, and the
project refuses to overclaim in the places that matter most.

The weakness is almost entirely in the documentation layer, and it is the kind that
costs credibility in an interview. The project accumulated seven session documents
that were each accurate when written and were never reconciled after the provider
decision. A recruiter reading `README.md` → `AI_PROVIDER.md` → `PROGRESS.md` will hit
three mutually exclusive statements about which provider is the default, whether an
API key is required, and how many notebooks were audited. Two of the three are wrong.

The second weakness is a single command: the README's flagship usage example does not
run. That is the first thing a reviewer will try.

Neither issue requires touching working code.

**Counts:** 12 MUST FIX, 9 SHOULD SIMPLIFY, 9 OPTIONAL POLISH.

---

# MUST FIX

## 1. The README's headline usage example does not run

**Files:** `README.md` (lines 69–81), `pyproject.toml`, `src/`

**Problem.** The README tells the reader to install dependencies with raw `pip install`
commands, then shows:

```python
from rules import audit_notebook
```

`src/` contains no `__init__.py` and no package directory, so nothing makes `rules`
importable from the repo root. Verified:

```
$ .venv/bin/python -c "from rules import audit_notebook"
ModuleNotFoundError: No module named 'rules'
```

It only works after `pip install -e .`, which the README never mentions. The project
currently relies on `sys.path` manipulation in two places: `pyproject.toml`
(`pythonpath = ["src"]`) and `app/streamlit_app.py` (`sys.path.insert`). Those cover
pytest and the Streamlit app, but not a reader following the README.

**Why it matters.** This is the first command a reviewer runs. A one-line failure at
the front door costs more credibility than the entire RAG layer earns.

**Smallest action.** Add `pip install -e .` to the README install block, or change the
example to run from `src/`. One line either way.

## 2. The `run_explanation` example silently returns `None`

**Files:** `README.md` (lines 110–116), `src/explainer.py` (lines 259–295)

**Problem.** The README presents this as the "one request per audit" example:

```python
result, evidence, explanation = run_explanation("notebook.ipynb", "2026.07")
print(explanation.summary)
```

`run_explanation` only calls the model when `COLABAUDIT_LLM_ENABLED=1`. The README no
longer documents that variable anywhere. Run as written, `explanation` is `None` and
the final line raises `AttributeError`.

**Why it matters.** The README's headline AI claim is undemonstrable as written, which
undercuts the one part of the project that needs the reader to believe it.

**Smallest action.** Either add the `export COLABAUDIT_LLM_ENABLED=1` line above the
example, or drop `run_explanation` from the README (see MUST FIX 9 / SHOULD SIMPLIFY 1).

## 3. README test section contradicts the current test suite

**Files:** `README.md` (lines 149–158)

**Problem.** Three stale statements:

- `pytest -m "not integration"` is described as "no API key needed" — correct.
- Plain `pytest` is described as adding "one live provider call" — **wrong**. The only
  `integration`-marked test is Ollama-only and is gated behind `RUN_OLLAMA_TESTS=1`, so
  plain `pytest` now contacts no provider at all.
- "63 tests run with no API key" omits the skip. The real result is 63 passed,
  1 skipped.

The `RUN_OLLAMA_TESTS` opt-in is undocumented anywhere in the repository.

**Why it matters.** Test documentation that is wrong is worse than none. It also hides
a genuinely good property: the suite is now fully hermetic.

**Smallest action.** Rewrite the four lines to state 63 passed / 1 skipped, that plain
`pytest` makes no network or provider call, and document
`RUN_OLLAMA_TESTS=1 python -m pytest -m integration`.

## 4. `PROGRESS.md` still lists a completed session as the next objective

**Files:** `PROGRESS.md` (lines 558–576)

**Problem.** The document says "Project status: complete" at line 388, then later
carries a live heading:

```
## Next session objective

**SESSION 3 — RAG + AGNO.** Deterministic core is done and must not be rewritten.
1. Install the `llm` extra...
2. `src/knowledge.py`: ingest the 5 curated files...
```

Session 3 was completed four commits ago. The RAG layer exists.

**Why it matters.** `PROGRESS.md` is the project's handoff document. A reader opening it
is told the core deliverable is still pending. It makes the finished project look
unfinished.

**Smallest action.** Delete lines 558–576.

## 5. `PROGRESS.md` contradicts itself on archive size

**Files:** `PROGRESS.md` (lines 412, 435, 441 versus line 26)

**Problem.** The Session 4 section states "notebooks audited : 83". Three earlier
sections state the archive holds 86 notebooks (and "86 notebooks reference `/content/`").
The verified figure is 83 `*.ipynb` files; 86 counted directory entries including
non-notebook items.

**Why it matters.** Two different numbers for the same dataset inside one document, both
presented as verified. Directly undermines the "measured, not asserted" framing the
project is built on.

**Smallest action.** Change the three occurrences of 86 to 83, or state "86 entries,
83 notebooks" once.

## 6. `PROGRESS.md` retains pre-decision provider and environment claims

**Files:** `PROGRESS.md` (lines 411, 427, 431)

**Problem.**

- Line 427: "Reference only. **Default provider is local Ollama**" — the default is Groq.
- Line 411: "No LLM API keys present in the environment or `~/.zshrc`" — keys were later
  created and used to run the recorded evaluation.
- Line 431: "Session 3 must use the 3.x forms" — Session 3 is done.

**Why it matters.** `PROGRESS.md` is quoted in the Session 4 commit message as the
verified record. Stale facts inside it are the opposite of its purpose.

**Smallest action.** Correct the three lines. Do not delete the history; the history is
the value.

## 7. `AI_PROVIDER.md` contains a table that flatly contradicts its own conclusion

**Files:** `AI_PROVIDER.md` (lines 130–143 versus lines 184–186)

**Problem.** The "Session 3 verification" table includes:

```
| API key required | **No.** Nothing in the pipeline reads a key. |
| LLM call time | roughly 1-2 minutes per call on CPU |
```

Line 184 states the opposite: "the default provider `groq` **requires `GROQ_API_KEY`**".
A reader encountering line 142 first is told the project needs no credentials, then
line 184 says it does.

**Why it matters.** This is the single most damaging contradiction in the repository,
because it concerns the one operational fact a reviewer must know before running
anything.

**Smallest action.** Mark the table explicitly as historical, for the Ollama-only period
before the provider evaluation, and add a one-line pointer to the current requirement.

## 8. Rejected providers are still documented as selectable

**Files:** `AI_PROVIDER.md` (lines 40, 163, 166, 223–240, 263); `src/explainer.py`
(lines 11, 14, 90–93); `app/streamlit_app.py` (line 31)

**Problem.** The locked decision is Groq plus Ollama-offline. Yet:

- Line 40 still advertises "Optional alternative: OpenRouter free tier, unchanged and
  still opt-in".
- The configuration table lists `gemini` and `openrouter` as valid `COLABAUDIT_LLM_PROVIDER`
  values, with a full setup example for each.
- Line 263 keeps Gemini in the deployment assessment.
- `explainer.build_model` retains working `Gemini` and `OpenRouter` branches with live
  imports.
- `app/streamlit_app.py` `KEY_VARIABLES` carries an unreachable `"gemini"` entry.

Gemini was explicitly rejected on evidence (a 503, plus abstracted-away versions).
OpenRouter was never selected. Keeping them implies an unfinished evaluation.

**Why it matters.** The evaluation narrative says "we tried three providers and chose
one". The code says "we support four". A reviewer who notices the gap will question
the conclusion.

**Smallest action.** Remove the Gemini and OpenRouter branches from `build_model` and
their imports, delete the `"gemini"` key from `KEY_VARIABLES`, and trim
`AI_PROVIDER.md` to keep the Gemini rejection as evidence while dropping it from the
configuration reference. Keep `reports/provider_eval_gemini.json` as the record.

## 9. `ARCHITECTURE.md` describes a code path the app does not use

**Files:** `ARCHITECTURE.md` (lines 72–74, 149–155)

**Problem.** Line 74 states: "`explainer.run_explanation` chains the audit, the retrieval
and the one model call. **The app calls those** and renders the result." The app does
not call `run_explanation`. It calls `rules.audit_notebook`, `collect_evidence` and
`explain` inline, because it needs the `llm_status` detail that `run_explanation`
discards.

The whole "Degradation behaviour" section is likewise written in terms of
`run_explanation`, describing an error-handling path the UI never exercises.

**Why it matters.** This is the architecture document. A statement about which function
calls which is exactly the kind of thing a reviewer spot-checks, and it is false.

**Smallest action.** Correct line 74 to state that the app calls the three functions
directly, and rewrite the two degradation bullets to describe the app's actual
`llm_status` behaviour.

## 10. No LICENSE file

**Files:** repository root

**Problem.** The project vendors Google's `pip-freeze.txt` and `os-info.txt` output
under Apache-2.0 from `googlecolab/backend-info`, alongside code that is clearly the
author's own. There is no `LICENSE`.

**Why it matters.** Public portfolio repositories are expected to carry one. Its absence
is also ambiguous about the vendored Google data, which has its own licence. A recruiter
may read the omission as carelessness.

**Smallest action.** Add an MIT `LICENSE` and a short provenance note in `SOURCES.md`
recording the Apache-2.0 status of the vendored `backend-info` files.

## 11. The app writes uploads to a fixed shared path

**Files:** `app/streamlit_app.py` (lines 120–122)

**Problem.**

```python
upload_path = Path("/tmp") / "colab_audit_upload.ipynb"
upload_path.write_bytes(uploaded.getbuffer())
```

One fixed filename shared by every session. On a multi-user Streamlit deployment two
concurrent analyses overwrite the same file, so one user's notebook can be audited
under another user's session. The file also persists after the request.

**Why it matter.** Notebooks may contain proprietary code or customer data. A
cross-session overwrite on a deployed instance is a genuine confidentiality issue, and
the README invites deployment to Streamlit Community Cloud.

**Smallest action.** Write to a per-session unique path, for example
`tempfile.NamedTemporaryFile(suffix=".ipynb", delete=False)`, and delete it in a
`finally` block.

## 12. `SOURCES.md` documents a source tier that does not exist

**Files:** `SOURCES.md` (lines 36–38)

**Problem.** A "Tier 3 — Official package documentation (used only when relevant)"
section describes retrieving PyPI and upstream docs "when a specific detected package
needs version-history or deprecation context. Recorded per-item in the manifest." There
are zero Tier 3 sources in `data/sources/`. `README.md` correctly states the corpus
"cannot explain a specific third-party package's breaking changes".

**Why it matters.** An aspirational section reads as an implemented capability, and it
contradicts an honest limitation stated elsewhere in the same repository.

**Smallest action.** Replace the Tier 3 section with one line stating it is not
implemented and why, and that such claims currently resolve to `UNKNOWN`.

---

# SHOULD SIMPLIFY

## 1. Two overlapping pipeline entry points, and a third control nobody uses

**Files:** `src/explainer.py` (lines 259–295)

**Problem.** `run_explanation()`, `is_llm_enabled()` and `COLABAUDIT_LLM_ENABLED` form a
convenience entry point that **no code calls** — not the app, not any test, not either
script. It is documented in four places as the project's primary API. Meanwhile the app
implements the same three steps inline, because it needs the `llm_status` detail that
`run_explanation` throws away.

The two paths also disagree: `run_explanation` swallows all errors and returns `None`;
the app reports `failed` plus a reason.

**Why it matters.** Untested code presented as the main API, plus a second untested
implementation of the same pipeline. Whichever one a reviewer reads is the one they
judge.

**Smallest action.** Pick one. Either delete `run_explanation`, `is_llm_enabled` and
`COLABAUDIT_LLM_ENABLED` and update the four docs to show the three-function sequence
the app actually uses, or make the app call `run_explanation` and have it return the
status. Deleting is the smaller change.

## 2. `MAX_TOKENS` is documented as a global cap but only applies to Ollama

**Files:** `ARCHITECTURE.md` (lines 90–91), `src/explainer.py` (lines 27–30)

**Problem.** `ARCHITECTURE.md` lists under "Request budget": "Generation is capped at
700 tokens. A 3B model on CPU will otherwise ramble past the token limit and return
unparseable JSON." The cap is passed only on the Ollama branch
(`Ollama(..., options={"num_predict": MAX_TOKENS})`). The default Groq path is uncapped.

**Why it matters.** Understates a real risk for the default provider. The measured
Groq parse failure is in fact a truncation-shaped problem, and the doc implies Groq is
protected when it is not.

**Smallest action.** State that the cap applies to the local Ollama mode only, and note
that the hosted path is not capped.

## 3. The 700-token cap has no test

**Files:** `src/explainer.py`, `tests/test_explainer.py`

**Problem.** `MAX_TOKENS` was introduced to stop a 3B model returning unparseable JSON.
It is applied to the Ollama branch only and is asserted by no test. A future edit could
drop it silently.

**Why it matters.** It is a deliberate workaround for an observed failure, documented in
`AI_PROVIDER.md`, with no regression guard.

**Smallest action.** One assertion on the constructed Ollama model's `options`.

## 4. `unexplained_rules` is framed around the rejected default

**Files:** `src/explainer.py` (lines 248–256)

**Problem.** The docstring reads "A 3B model does not reliably cover every rule, so
coverage is checked deterministically". The default provider is now Groq, which did
cover every rule in testing. The function and its test are both still valid; the
justification is stale.

**Why it matters.** Minor, but it is a comment asserting a weakness of a model the
project no longer uses.

**Smallest action.** Reword to "a model may fail to explain every rule", which is the
actual invariant the function defends.

## 5. README typo in the solution statement

**Files:** `README.md` (line 19)

**Problem.** "retrieve official **Colay** documentation".

**Why it matters.** It is in the second paragraph of the README, and the project is
about a Google product.

**Smallest action.** Fix the spelling.

## 6. No pinned dependency set

**Files:** `README.md` (lines 69–73), `pyproject.toml`

**Problem.** The README pins only `agno==3.1.1`. `lancedb`, `sentence-transformers`,
`openai`, `groq` and `streamlit` float. There is no `requirements.txt`. The previous
project in this portfolio shipped one.

**Why it matters.** The project makes strong reproducibility claims: vendored snapshots
at pinned commits, offline retrieval, "reproducible". Unpinned dependencies undercut
that, and the pinned Agno version is the one with known 2.x→3.x API drift.

**Smallest action.** Add a `requirements.txt` with the exact versions currently
verified, and have the README reference it.

## 7. `pyproject.toml` declares packaging that does not exist

**Files:** `pyproject.toml` (lines 20–21)

**Problem.**

```toml
[tool.setuptools.packages.find]
where = ["src"]
```

`find_packages(where="src")` returns `[]` because `src/` has no `__init__.py` and no
package directory. `pip install -e .` still works, but only because setuptools' editable
mode adds `src/` to `sys.path` regardless. The declaration describes an intent the code
does not realise.

**Why it matters.** It is confusing to a reader and it is the root cause of MUST FIX 1.
Either the modules should be a package, or the packaging block should be honest about
being a flat script layout.

**Smallest action.** Add `src/__init__.py` and move the modules under a package, or drop
the `packages.find` block and document the flat layout explicitly.

## 8. README repository layout omits two directories

**Files:** `README.md` (lines 192–208)

**Problem.** The layout table lists `src/`, `app/`, `data/`, `reports/` and the
governance documents. It omits `scripts/` and `tests/`, both of which a reviewer will
look for.

**Why it matters.** Small, but the table is presented as the map of the repository.

**Smallest action.** Add two rows.

## 9. `SOURCES.md` and `PROGRESS.md` report different package counts for the same files

**Files:** `SOURCES.md` (lines 17, 21); `PROGRESS.md` (lines 60–65)

**Problem.** `SOURCES.md` reports 2026.07 as 648 packages and 2025.07 as 641.
`PROGRESS.md` reports 643 and 636. Both are correct counts of the same files, measured
differently: `SOURCES.md` counts all lines, `PROGRESS.md` counts non-comment,
non-blank lines. Neither column says which.

**Why it matters.** Same pattern as MUST FIX 5: two verified-looking numbers for one
dataset. Here it is defensible but unexplained, which is worse than either number alone.

**Smallest action.** Label the `SOURCES.md` column "lines in pip-freeze.txt" and note in
`PROGRESS.md` that counts exclude comment headers.

---

# OPTIONAL POLISH

## 1. Empty `docs/` directory kept alive by a tracked `.gitkeep`

**Files:** `docs/.gitkeep`

**Problem.** `docs/` contains only a `.gitkeep`. Governance content lives in the
repository root.

**Smallest action.** Delete `docs/` and its `.gitkeep`.

## 2. Five redundant `.gitkeep` files in directories that now have content

**Files:** `app/.gitkeep`, `tests/.gitkeep`, `tests/fixtures/.gitkeep`, `reports/.gitkeep`

**Problem.** All four directories contain tracked files. The `.gitkeep` files are
leftovers from the Session 1 skeleton.

**Smallest action.** Delete them.

## 3. Three of six UI tests assert on source text rather than behaviour

**Files:** `tests/test_app.py` (lines 68–87)

**Problem.** `test_locked_provider_models_match_the_decision`,
`test_app_source_contains_no_secret_values` and `test_app_never_executes_the_notebook`
read the app file as text and grep it. `test_app_never_executes_the_notebook` looks for
`"exec("`, `"eval("`, `"subprocess"`, `"os.system"`, `"runpy"`.

**Why it matters.** These break on harmless refactors and prove little. The real
no-execution guarantee is behavioural and already covered: `test_notebook_parser.py`
proves the parser only reads JSON. Renaming the `PROVIDER_MODELS` dict would fail a test
while nothing regressed.

**Smallest action.** Keep the secret-value grep, which is a genuine security control.
Replace the other two with assertions on the imported `PROVIDER_MODELS` constant, or drop
them as already covered elsewhere.

## 4. Each UI test rebuilds the knowledge base

**Files:** `tests/test_app.py`

**Problem.** Two tests each construct a fresh `AppTest`, and `st.cache_resource` does
not persist across them, so the LanceDB index is built twice. That is most of the
suite's runtime.

**Smallest action.** If the two tests are kept, share one module-scoped `AppTest` and
reuse it, as `test_app_loads_without_crashing` already does.

## 5. Session-number language leaks into portfolio-facing documents

**Files:** `ARCHITECTURE.md` (line 61), `AI_PROVIDER.md` (line 130, line 204)

**Problem.** "Session 2 simplified these to four plain modules", "## Session 3
verification", "Session 4 renders that in the UI". This is development scaffolding.
`PROGRESS.md` legitimately contains session history; the other two are reference
documents.

**Smallest action.** In `ARCHITECTURE.md` and `AI_PROVIDER.md`, replace with dates or
plain statements. Leave `PROGRESS.md` alone.

## 6. No upload size guard before writing to disk

**Files:** `app/streamlit_app.py` (lines 106–122)

**Problem.** `notebook_parser` enforces a 20 MB limit, but only after
`write_bytes` has already placed the whole upload on disk.

**Smallest action.** Check `uploaded.size` before writing and show the existing error
message early.

## 7. `notebook_name` extraction assumes POSIX paths

**Files:** `src/rules.py` (line 177)

**Problem.** `notebook_path.rsplit("/", 1)[-1]` leaves the full path in the name on
Windows.

**Smallest action.** `Path(notebook_path).name`.

## 8. Minor style inconsistencies in `explainer.py`

**Files:** `src/explainer.py` (lines 30–32, line 128)

**Problem.** Only one blank line before `class ProviderError` rather than two.
`collect_evidence` imports `knowledge_base.retrieve` inside the function while the rest
of the module uses top-level imports.

**Smallest action.** Two blank lines; hoist the import.

## 9. `.streamlit/secrets.example.toml` contains a placeholder key value

**Files:** `.streamlit/secrets.example.toml`

**Problem.** `GROQ_API_KEY = "replace-me"` is a valid-looking assignment. It is
harmless and gitignored patterns do not exclude the `.example` file, so it is committed
intentionally, but a naive secret scanner will flag it.

**Smallest action.** Add a comment line stating explicitly that the value is a
placeholder, or omit the value.

---

## What is already strong and should not be touched

Worth stating explicitly, because a cleanup pass can damage these:

- **The deterministic core.** `rules.py` is 231 lines of plain functions with no
  abstraction, no classes, and no LLM contact. `audit_notebook` is one readable function.
- **The structural separation.** `ExplanationResult` has no version, severity or status
  field and `AuditResult` has no explanation field, so the model *cannot* write back into
  a finding. This is enforced by the type system, not by prompt discipline. It is the
  strongest single design decision in the project.
- **Fail-closed behaviour.** Unknown inputs produce `UNKNOWN`, never a guess. R004 never
  claims an install will fail.
- **Honest reporting.** The Groq structured-output failure is documented with its actual
  rate. Gemini's rejection is recorded with its 503. No accuracy percentage appears
  anywhere. This is rarer and more valuable than it is given credit for.
- **Retrieval determinism.** One `knowledge.search` per distinct rule, built from
  deterministic text. No agentic search, no model-decided queries.
- **Test isolation.** 63 tests run with no key, no network and no local inference, and
  the single live test is opt-in. That property is better than the README currently
  claims.

## Suggested cleanup order

1. MUST FIX 4, 5, 6, 7, 9 — PROGRESS.md and AI_PROVIDER.md contradictions. Pure text,
   zero risk, highest credibility return.
2. MUST FIX 1, 2, 3 — README correctness. Highest usability return.
3. MUST FIX 11 — the `/tmp` write. Small, real security fix.
4. MUST FIX 8 and SHOULD SIMPLIFY 1 together — they are the same decision: drop the
   rejected providers and the unused entry point. Doing them in one commit keeps
   `AI_PROVIDER.md`, `src/explainer.py` and the app consistent.
5. MUST FIX 10, 12, SHOULD SIMPLIFY 6, 9 — additive files and honest labelling.
6. Everything else.

MUST FIX 9 depends on SHOULD SIMPLIFY 1: once the entry-point duplication is resolved,
the architecture section can be corrected once rather than twice.

---

## Resolution

Applied in a single cleanup commit. The findings above are left unedited as the record of
what was wrong; this section records what was done about each.

**All 12 MUST FIX items applied.**

| # | Resolution |
|---|---|
| 1 | The README now documents `PYTHONPATH=src` and the example was verified to run from an unrelated working directory. `pip install -e .` was tried first and **does not work**: Python 3.14 skips the setuptools `.pth` file because its name begins with `__`, so the install reports success and then `import rules` fails. The reason is recorded in `pyproject.toml` so nobody re-adds the broken step. |
| 2 | Resolved with #SHOULD-1. `run_explanation` is gone, so the example it backed was replaced with the three-function sequence the app actually calls. |
| 3 | Test section rewritten: 63 passed / 1 skipped, no network, `RUN_OLLAMA_TESTS=1` documented. Actual count after this cleanup is 67 passed / 1 skipped. |
| 4 | `PROGRESS.md` deleted. It was a development worklog and its only live section said the next objective was to build the RAG layer, which shipped four commits earlier. Measured facts worth keeping were moved into `README.md`. |
| 5 | Resolved with #4. `README.md` now states 83 notebooks, verified. |
| 6 | Resolved with #4. The "default provider is Ollama" claim is gone. |
| 7 | Table retitled "Integration verification (historical)" with an explicit note that it describes the Ollama-only period and is not the current configuration. |
| 8 | `Gemini` and `OpenRouter` branches and imports removed from `build_model`; `"gemini"` removed from the app's `KEY_VARIABLES`; both dropped from the configuration table and examples in `AI_PROVIDER.md`. The Gemini rejection narrative and `reports/provider_eval_gemini.json` are retained as evidence. |
| 9 | `ARCHITECTURE.md` corrected: the app calls `audit_notebook` → `collect_evidence` → `explain`; the degradation section now describes the app's `llm_status`. |
| 10 | MIT `LICENSE` added; Apache-2.0 status of the vendored `backend-info` files recorded in `SOURCES.md` and `README.md`. |
| 11 | Uploads now go to a `NamedTemporaryFile` and are deleted in a `finally` block, with a size guard before writing. A regression this introduced (the report showed a random temp filename) was caught and fixed, and a test was added. |
| 12 | Tier 3 replaced with an explicit statement that it is not implemented and that such claims resolve to `UNKNOWN`. |

**SHOULD SIMPLIFY applied: 1, 2, 3, 4, 5, 6, 8.** Not applied: 7 and 9 were completed as
part of MUST FIX 1 and MUST FIX 12/5 respectively, and 9 is moot once `PROGRESS.md` is
gone.

- #1: `run_explanation`, `is_llm_enabled` and `COLABAUDIT_LLM_ENABLED` removed. The
  app's inline path became the single orchestration path. The app's path was chosen over
  the preferred "make the app call `run_explanation`" because `run_explanation` discards
  `llm_status` and the error reason, both of which the UI must show, and it swallowed
  `ProviderError`. Tests now assert the flag and entry point are gone.
- #2: `MAX_TOKENS` documented as Ollama-only in both `ARCHITECTURE.md` and the source.
- #3: added `test_generation_cap_is_applied_to_the_offline_mode`.
- #4: `unexplained_rules` docstring reworded to drop the "3B model" framing.
- #5: "Colay" typo fixed.
- #6: `requirements.txt` added with pinned versions.
- #8: layout table now includes `tests/` and `scripts/`.

**OPTIONAL POLISH: not applied**, per instruction. `.gitkeep` files were removed anyway
because `docs/` became an empty directory, which would otherwise have been left tracked.

**Not fixed, deliberately:**

- The `rules.py` POSIX path assumption (OPTIONAL 7) was left alone. It is not a
  correctness bug on the supported platform and `src/rules.py` is frozen.
- Three of six UI tests still assert on source text (OPTIONAL 3). The secret-value grep
  was kept as a genuine security control.

**A deployment blocker found during application, not present in the original audit.**
`src/explainer.py` imports `agno.models.ollama` at module level, and that module imports
the `ollama` package. So `ollama` is a hard requirement even when only Groq is used. The
audit's `requirements.txt` recommendation (#6) would have shipped a broken install.
`requirements.txt` and `pyproject.toml` now include it.