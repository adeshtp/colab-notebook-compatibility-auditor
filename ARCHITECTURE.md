# ARCHITECTURE.md

Two workflows, sharing one knowledge base and one provider. Neither feeds the other.

## Workflow 1 — ask a question (primary)

```
user question
  ↓
knowledge_base.retrieve                deterministic, top-k passages, local LanceDB
  ↓
qa.evidence_coverage                   deterministic, decides sufficiency
  ↓ (below threshold)  refuse, show the near-miss passages, no model call
  ↓ (above threshold)
qa.build_prompt                        question + passages only
  ↓
qa.answer_question                     ONE agent call, structured output
  ↓
qa.resolve_used_sources                deterministic, verifies every citation
  ↓
Answered(answer, used_sources, unsupported_citations)
  ↓
app/streamlit_app.py                   answer, source links, retrieved passages
```

## Workflow 2 — audit a notebook (secondary)

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
explainer.explain                      ONE agent call, structured output
  ↓
ExplanationResult                      prose only, held separately
  ↓
app/streamlit_app.py                   renders all three in order
```

Optional: `COLABAUDIT_LLM_PROVIDER=ollama` gives a fully offline generation step with
no API key, in both workflows.

Retrieval is a direct Python call. There is no agentic search: the model never decides
whether to search, what to search, or which findings exist.

## Why the evidence gate exists

A vector search always returns its nearest neighbours. "How much RAM does a free Colab
runtime give me?" returns a blog post about reproducibility and a runtime component
list — nothing about RAM. Generation from that would be improvisation.

`qa.evidence_coverage` therefore decides sufficiency before generation, in plain Python:

- Each content-bearing question term is weighted `log(1 + N / containing)`, where N is
  the number of retrieved passages and `containing` is how many hold that term.
- Coverage is the share of that weight covered by the single best passage, not the pool.
- Below `qa.MIN_EVIDENCE_COVERAGE` (0.50) the model is not called at all.

The measure is lexical by choice: no model call means it is exhaustively testable
without an API key, and it cannot be talked into agreeing with itself. The separation is
narrow — 0.52 answerable against 0.42 out-of-domain on the hand-written set — so it is
a calibrated heuristic, kept as one visible constant rather than hidden in a prompt.
`scripts/run_retrieval_eval.py` reports both ranges and whether the threshold still
separates them.

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

- Answering a user's question in prose, grounded in the retrieved passages
- Citing passages inline as `[n]`, and reporting the limits of the retrieved evidence
- Explaining detected findings in plain language
- Producing recommended manual checks

### The LLM must not

- Answer from anything other than the passages it was given
- Invent package versions, compatibility facts or citations
- Override a deterministic finding
- Change the audit report status
- Assert that a notebook will or will not run

The audit status is computed deterministically, and the QA sufficiency decision is
computed deterministically before the model is called. The model writes prose only.

## Modules

Six plain modules. There are no classes beyond the Pydantic models, no factories, and
no interfaces.

| Module | Responsibility |
|---|---|
| `src/qa.py` | Question answering: the evidence gate, the grounded prompt, citation verification. |
| `src/models.py` | Pydantic models: `Requirement`, `Finding`, `RuntimeInfo`, `AuditResult`. |
| `src/notebook_parser.py` | Read `.ipynb` as JSON, extract pip installs and imports. Never execute. |
| `src/runtime_checker.py` | Load a vendored snapshot from `data/runtimes/`, look up package versions. |
| `src/rules.py` | R001–R006 and status aggregation, plus the `audit_notebook` entry point. |
| `src/knowledge_base.py` | Ingest the curated sources, embed with SentenceTransformer, store in local LanceDB, retrieve. |
| `src/explainer.py` | Build the audit evidence prompt and make the single Agno call. Provider construction lives here. |
| `app/streamlit_app.py` | Streamlit UI. Presentation only, no analysis logic. |

`qa.answer_question(knowledge, question)` is the whole question-answering stage, and
`rules.audit_notebook(notebook_path, snapshot)` is the whole deterministic audit stage.
Each is a plain function. The Streamlit app is the only caller of either.

`rules.audit_notebook(notebook_path, snapshot)` is the whole deterministic stage: one
function, plain data in, plain data out. The three-step sequence above
(`audit_notebook` → `collect_evidence` → `explain`) is the single orchestration path.
The Streamlit app is the only caller; it renders the result of each step.

Nothing under `src/` is a class except the Pydantic models. No factories, no
dependency injection, no service layer, no plugin registry. Provider selection is a
plain `if` in `explainer.build_model`.

## Request budget

**One question produces at most one LLM call. One audit produces exactly one.**

### Question answering

- One `knowledge.search` for the question.
- The evidence gate runs in plain Python and may end the request with no model call at
  all. A refused question costs zero tokens.
- The prompt carries the question and the retrieved passages, and nothing else.
- One `Agent.run`.

### Auditing

- `explainer.distinct_findings` collapses repeated rules, so a notebook with 40 R002
  findings needs one search and one explanation slot, not 40.
- `collect_evidence` issues one `knowledge.search` per distinct rule, capped at 3
  chunks each.
- The prompt carries findings, evidence and limitations. Full notebook source is never
  sent.
- Generation is capped at 700 tokens **in the offline Ollama mode only**. A 3B model on
  CPU will otherwise ramble past the limit and return unparseable JSON. The hosted Groq
  path is not capped, which is the observed cause of its occasional parse failure; see
  `AI_PROVIDER.md`.

## Active rules

R001, R002, R003, R004, R005 and R006 are implemented.

R007 (malformed install command) is defined but **inactive**. Its trigger condition
overlaps with R006 and with the parser's existing behaviour of skipping tokens it
cannot interpret, so a separate finding would duplicate information already reported.
Reconsider it only if a distinct user-facing need appears.

## Evidence separation

Four kinds of content, four separate types, none of which can be written by a model:

- `AnswerResult` (`qa.py`) — question-answering prose. Its fields are `answer`,
  `used_sources`, `follow_ups`, `caveats`. It has no finding, version, severity or
  status field, so it **structurally cannot** influence an audit.
- `Finding` (`models.py`) — produced by `rules.py`. Holds `rule`, `package`, `severity`,
  `status`, `message`, `cell`. **Read-only to the model.**
- Evidence (`knowledge_base.retrieve` returns plain dicts) — retrieved chunk with
  `source_id`, `source`, `title`, `url`, `content_type`, `runtime_context`, `content`,
  `rank`. Inspectable before any model call, in either workflow.
- `ExplanationResult` (`explainer.py`) — audit explanation prose. Fields `summary`,
  `explanations`, `recommendations`, `limitations`. No version, severity or status
  field.

`AuditResult` has no `summary` or explanation field. The types cannot merge even by
accident.

Question retrieval and audit evidence retrieval both call the same
`knowledge_base.retrieve`, but the queries are built differently and for different
purposes: a question is the user's own text, while audit queries are synthesised from a
deterministic finding. They are not interchangeable, and the question path never
consults the rule engine.

## Retrieval behaviour

- Chunk size 600 with `MarkdownReader`, so a retrieved chunk is the relevant section
  rather than a whole document.
- YAML front matter is stripped before ingest. Its title and URL are already stored as
  metadata on every chunk, and leaving it in the indexed text meant a chunk of nothing
  but `source_id: …` could be embedded and ranked — it was the top hit for out-of-domain
  questions.
- `Knowledge.insert(text_content=..., skip_if_exists=True)`;
  `build_knowledge(rebuild=True)` clears a half-finished ingest from an interrupted run.
- Retrieved content is returned **whole**. The chunker already bounds chunk length, and a
  character cap in `retrieve` could cut the sentence a question asks about. This matches
  the decision already taken in `explainer._format_evidence`.
- Agno 3.1.1 does not expose the raw similarity score on the returned `Document`, so
  results carry `rank` rather than a fabricated score. The one numeric score in this
  project, `evidence_coverage`, is computed in `qa.py` from real term statistics.
- The Streamlit app calls `build_knowledge(rebuild=True)` once inside
  `st.cache_resource`, so the index is not rebuilt on every rerun and is always
  recreated from the five committed curated sources. A Streamlit Community Cloud
  filesystem is not durable, so the index is treated as rebuildable, never as
  persistent state.

## UI behaviour

Two tabs.

**Ask a question** (primary) — a text input, a passage-count slider and an answer
toggle, then:

1. The measured coverage, shown as a caption, so a refusal is inspectable.
2. Either the answer with inline `[n]` citations, the sources actually used as links,
   the limits the model reported, and every retrieved passage — or the refusal, with
   the near-miss passages and no answer.
3. `Sources used` is de-duplicated by source id, because several passages routinely
   come from one document.
4. A citation outside the retrieved set is withheld from the reference list and warned
   about. Passage numbers are mapped back to their source id first, because models
   often repeat `[1]`, `[2]` in the id field and that is a formatting habit, not a
   fabrication.

**Audit a notebook** (secondary) — renders three visually separated sections in
pipeline order:

1. **Detected by auditor** — dependencies and findings from `rules.py`. Authoritative.
2. **Retrieved evidence** — source title, URL and chunk text, shown before any AI text.
3. **AI-generated explanation** — `ExplanationResult`, labelled with provider, model
   and status.

Both tabs share the sidebar provider selection. The question tab does not reference the
rule engine at all, which a test asserts.

`llm_status` is one of `ok`, `disabled`, `not_configured` or `failed`. A raw exception
is reduced to its type name for display; the underlying `ProviderError` text is kept
in a caption for debugging.

## Degradation behaviour

Every failure is a returned value, not an exception. Both workflows report it the same
way.

Question answering, as `qa.Answered.status`:

- `empty_question` → nothing was asked; nothing is retrieved.
- `no_passages` → retrieval returned nothing from the corpus.
- `insufficient_evidence` → coverage below the threshold. **The model is not called.**
  The near-miss passages are still shown so the refusal can be judged.
- `disabled` → the caller passed `use_ai=False`, or no key is configured. Passages render.
- `failed` → `ProviderError`, rate limit or an unparseable response. The reason is kept
  in `detail`; the passages render. No provider switching, no paid fallback.
- `ok` → the structured response validated and every citation resolved.

Auditing, as the app's `llm_status`:

- Caller does not request an explanation → `disabled`.
- No key for the configured provider → `not_configured`. The audit and the evidence
  still render.
- `ProviderError`, rate limit, or an unparseable response → `failed`, with the reason
  kept in a caption. The deterministic report is untouched.
- `ok` when the structured response validates.

Separately, and independent of any provider:

- RAG retrieval returns nothing for a rule → that rule's evidence list is empty and the
  prompt records it as `(no evidence retrieved)`. The deterministic status is unchanged,
  because retrieval never drives a finding.
- No runtime snapshot selected → `audit_notebook` returns `UNKNOWN` with an R006
  finding. Nothing is guessed.
- The model does not explain every rule → `explainer.unexplained_rules` reports the gap
  deterministically instead of hiding it.
- `AnswerResult`'s supplementary lists default to empty, so a model response missing
  `follow_ups` still yields its answer rather than failing the whole request.