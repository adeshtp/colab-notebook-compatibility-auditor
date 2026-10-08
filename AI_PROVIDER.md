# AI_PROVIDER.md

## Purpose

Isolate LLM provider selection from application logic. Only `explainer.py` may import a
provider SDK or read an API key. `models.py`, `notebook_parser.py`,
`runtime_checker.py`, `rules.py` and `knowledge_base.py` must never do so.

## Verified environment facts (checked 2026-10-08)

| Fact | Evidence |
|---|---|
| Local Python is 3.14.3 (Homebrew, macOS arm64) | `python3 -V` |
| `agno` latest is 3.1.1, pure-python wheel `py3-none-any`, classifiers list Python 3.11–3.13 | PyPI JSON API |
| `agno` 3.x uses `output_schema` for structured output; `response_model` is **not** a parameter | source: `libs/agno/agno/agent/agent.py` |
| `agno` 3.x Knowledge content is added via `knowledge.insert(path=..., url=..., text_content=...)`; the 2.x `Knowledge(content=[...])` form is gone | source: `libs/agno/agno/knowledge/knowledge.py`, docs.agno.com/knowledge/quickstart |
| `agno` has `models/ollama`, `models/openrouter`, `knowledge/embedder/sentence_transformer.py`, `vectordb/lancedb` | repo tree listing |
| Ollama is running locally with `ministral-3:3b` and `qwen3.5:4b` | `POST localhost:11434/api/tags` |
| `ministral-3:3b` returns valid schema-constrained JSON when given a Pydantic-shaped schema | live call, verified |
| `qwen3.5:4b` returns an **empty** content string under the same schema because it spends the token budget in a `thinking` field | live call, verified |
| OpenRouter currently exposes 20 zero-price models; several advertise `structured_outputs`, including `openrouter/free`, `nvidia/nemotron-3-super-120b-a12b:free`, `apodex/apodex-1.1-mini:free`, `liquid/lfm-2.5-2.6b:free` | `GET openrouter.ai/api/v1/models` |

## Selected provider

**Default: Groq.** `COLABAUDIT_LLM_PROVIDER=groq`, `COLABAUDIT_LLM_MODEL=openai/gpt-oss-20b`.

Chosen by measured comparison, not preference. See "Provider evaluation" below.

- Fastest by an order of magnitude: 1.4–1.7 s per call against 53 s locally.
- The only provider that explained **every** supplied rule, including the R002 + R004
  pair the local 3B model repeatedly failed.
- Reproduced all supplied versions and rule ids exactly.
- Free tier is ample for this project: 30 RPM, 1,000 requests/day, 200K tokens/day.
- No local hardware impact, and it deploys to Streamlit Community Cloud as an HTTP
  call plus one environment secret.

**Optional local mode: Ollama** with `ministral-3:3b`, for fully offline use with no
key at all. Slower and less complete, see the measured results.

Gemini and OpenRouter were evaluated or considered and are not supported. See "Why not
Gemini" below. Raw records are kept in `reports/provider_eval_*.json`; there is no code
path for either.

## Provider evaluation (2026-10-08)

Method: `scripts/compare_providers.py`. Same two fixtures, same deterministic
findings, same retrieved evidence, same system prompt, same `ExplanationResult`
schema. Only the model changed. **Two requests per provider, four in total.** Raw
records in `reports/provider_eval_<provider>.json`.

| Dimension | Ollama `ministral-3:3b` | **Groq `openai/gpt-oss-20b`** | Gemini `gemini-3.8-flash` |
|---|---|---|---|
| Case A latency | 52.97 s | **1.67 s** | 15.51 s |
| Case B latency | 52.32 s | **1.44 s** | failed, 3.92 s |
| Requests succeeded | 2 / 2 | **2 / 2** | 1 / 2 |
| Structured output valid | yes | **yes** | yes on the one success |
| Case A rule coverage | complete | **complete** | complete |
| Case B R002 + R004 coverage | **R004 missing** | **both explained** | not measured |
| Versions reproduced exactly | yes | **yes** | **no, all three omitted** |
| Rule ids reproduced exactly | yes | **yes** | yes |
| Signalled uncertainty | yes | **yes** | no |
| Overreach phrases | none | **none** | none |
| Speculative snapshot mentions | none | **none** | none |
| Agno native structured output | `True` | `False` | `True` |
| Free tier | unlimited, local | 30 RPM, 1K RPD, 200K TPD | free tier, capacity-limited |
| Free-tier data use | none, runs locally | not stated | **used to improve Google's products** |
| Local hardware | sustained CPU load | none | none |
| API key needed | no | yes | yes |

### Why Groq won

1. **Coverage on the failing case.** The one quality defect that motivated this
   evaluation was the local model dropping R004. Groq explained both rules in the
   same prompt, same schema, first try.
2. **Latency.** 1.4–1.7 s against 53 s. A Streamlit UI feels broken at 53 s.
3. **No abstraction drift.** Gemini's successful answer described "a specific package
   version that differs from the version in the runtime" without naming `1.24.3` or
   `2.0.2`. For a tool whose entire job is explaining a *specific* mismatch, that is
   a substantive loss even though it parsed cleanly.
4. **Proper hedging.** Groq kept the caveats, including "its presence in the live
   runtime cannot be confirmed from the snapshot alone", which is exactly the R004
   limitation from `RULES.md`.
5. **Deployment fit.** Pure HTTP plus one environment secret. No GPU, no model
   download, no long cold start on Streamlit Community Cloud.

### Honest caveats about Groq

- **Structured output is not schema-enforced.** Agno reports
  `supports_native_structured_outputs = False` for Groq, so the schema is advisory. Across
  roughly 14 live calls during the provider evaluation and final verification, **one call
  failed** with Agno logging `All parsing attempts failed`, meaning the response could not
  be parsed into `ExplanationResult`. The following 11 consecutive calls succeeded. So
  treat this as roughly one failure in a dozen calls, not as a reliable guarantee.
  This is the single strongest argument for the degradation path: a parse failure costs
  the prose layer and nothing else.
- Free-tier limits are per organisation, not per key.
- A raw HTTP request to Groq with a default Python `urllib` User-Agent is blocked by
  Cloudflare with `error code: 1010`. Agno's client sends a normal User-Agent and is
  unaffected, but this will bite anyone testing with `curl`/`urllib` directly.
- `gpt-oss-20b` is a reasoning model. It emitted no stray reasoning into the structured
  output in these runs, but that is a behaviour worth re-checking if output quality
  regresses.
- Free-tier latency measured 1.4–2.5 s per call. No claim is made about paid-tier
  behaviour or about behaviour under load.

### Why not Gemini

One of two requests failed with `503 UNAVAILABLE, high demand`. A provider that can
fail half your calls on a free tier is not a good default for a demo, whatever its
benchmarks say. Separately, its successful answer omitted every concrete version and
did not signal uncertainty. Both are disqualifying here.

There is also a setup trap: Agno's `Gemini` class reads only `GOOGLE_API_KEY` and logs
`GOOGLE_API_KEY not set` when only `GEMINI_API_KEY` is present, even though the
underlying `google-genai` SDK falls back to `GEMINI_API_KEY` and the call then succeeds.
The logged error is misleading.

### Why Ollama is kept

It is the only option with no key, no quota, no data leaving the machine, and no
per-request cost. That is worth keeping for offline use and for anyone who does not want
to configure a credential. It is no longer the default because it is ~30x slower, it
leaves R004 unexplained, and it pins the developer machine at 100% CPU for a minute.

### What this evaluation does not establish

Two cases per provider is an engineering selection, not a benchmark. No accuracy
figure, win rate or statistical claim is made. Groq's structured-output reliability was
observed on roughly 14 live calls and failed once, which is noted above rather than
smoothed over.

## Integration verification (historical)

Confirmed by running the pipeline during initial build-out, while local Ollama was the
only provider. Recorded because the findings drove real code decisions. **This is not
the current configuration**: see "Selected provider" above for the key requirement.

| Fact | Result |
|---|---|
| Agno version installed | `3.1.1` |
| Ollama client | `ollama 0.6.3`, host `http://localhost:11434` |
| `Ollama` native structured output | `supports_native_structured_outputs = True`, confirmed on the installed class |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2`, downloaded from the HF Hub on first run, cached after that |
| Vector store | local LanceDB at `data/lancedb/`, no cloud, no key |
| LLM call time in that local-only setup | roughly 1-2 minutes per call on CPU |
| Generation cap | 700 tokens, needed because a 3B model otherwise runs past the limit and returns unparseable JSON |

The 700-token cap is applied to the local Ollama mode only. The hosted Groq path is not
capped; see the parse-failure caveat above.

### Defects found and fixed during that verification

1. `Document` in Agno 3.1.1 has `meta_data`, not `metadata`, and exposes no `score`
   field. Retrieved results carry `rank` instead of a fabricated similarity number.
2. Default chunking put each whole 2-3 KB source in one chunk, so front matter crowded
   out the body text. `MarkdownReader(chunk_size=600)` fixes this.
3. `agno.models.ollama` imports `agno.models.openai`, so the `openai` package must be
   installed even when no OpenAI account or key is used. This is a transitive import in
   Agno, not a second provider.

## Configuration

All configuration is by environment variable. No key is ever read from, or written to, tracked files.

| Variable | Default | Meaning |
|---|---|---|
| `COLABAUDIT_LLM_PROVIDER` | `groq` | `groq` or `ollama`. Any other value is rejected. |
| `COLABAUDIT_LLM_MODEL` | `openai/gpt-oss-20b` | Provider-specific model id. |
| `GROQ_API_KEY` | unset | Required when provider is `groq`, the default. |
| `COLABAUDIT_OLLAMA_HOST` | `http://localhost:11434` | Ollama base URL, offline mode only. |

The deterministic audit never reads any of these. Keys are read only by
`explainer.build_model`, and by the Streamlit app when copying a Streamlit secret into
the environment.

Whether the AI step runs is chosen by the caller: a checkbox in the UI, or simply
whether you call `explainer.explain`. There is no separate feature flag.

## API key policy

The default provider requires `GROQ_API_KEY`. No key is ever read from, or written to, a
tracked file, and the value is never displayed or logged.

- If the key is absent, the deterministic audit and evidence retrieval still run and the
  UI reports the AI step as unavailable. It does not crash.
- Credentials are never invented, guessed, or substituted for another provider.
- No silent fallback to a paid model.

## Request budget

- One LLM call per analysis. Retrieval happens deterministically before the call.
- One `Agent` instance per call, no teams, no sub-agents, no tool loops.
- Findings are deduplicated by rule before retrieval, so 40 R002 findings cost one
  search and one explanation slot.
- Prompt is compact: snapshot id, deterministic findings, and up to 3 evidence chunks
  per distinct rule. Full notebook source is never sent.
- No retry loop. On provider error the failure is recorded and the deterministic report
  is returned unchanged.

## Provider metadata in output

`explainer.DEFAULT_PROVIDER` and `explainer.DEFAULT_MODEL` record which provider and
model are configured. The Streamlit app reports the outcome per analysis as one of
`ok`, `disabled`, `not_configured` or `failed`, and shows it next to the explanation
section.

## Configuration examples

Default, Groq:

```bash
export GROQ_API_KEY=gsk_...        # never committed
```

Offline, no key:

```bash
export COLABAUDIT_LLM_PROVIDER=ollama
export COLABAUDIT_LLM_MODEL=ministral-3:3b
```

## Runtime degradation

A free tier may become unavailable or rate-limited. In that case:

- Catch the error, record it in `llm_status`, show it in the UI.
- Keep the deterministic report.
- Do not restructure the architecture and do not switch to a paid model.

`explainer.ProviderError` is raised when a provider returns an error document in the
response body rather than an exception. This was added because a Gemini `503` was
otherwise surfaced to the caller as a confusing `ValidationError`. The Streamlit app
catches it, reports `failed` and keeps the deterministic report unchanged.

## Streamlit Community Cloud suitability

The intended deployment is: upload notebook, deterministic audit, local retrieval,
hosted LLM API, structured explanation, report.

- **Groq** suits this. One HTTPS request per analysis and one environment secret. No
  GPU, no model download, no cold start. LanceDB and the SentenceTransformer index stay
  local to the container.
- **Ollama does not suit it.** Streamlit Community Cloud has no GPU and a modest CPU
  allowance, so a local 3B model would be slower still than on a developer machine.

None of this has been deployed. It is a fit assessment, not a deployment claim.