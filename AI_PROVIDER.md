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

**Default: local Ollama.** `COLABAUDIT_LLM_PROVIDER=ollama`, `COLABAUDIT_LLM_MODEL=ministral-3:3b`.

Reasoning:

- Genuinely free. No account, no quota, no billing.
- **No API key required**, so no part of the project is blocked on credential setup.
- Runs on CPU, sufficient for one compact explanation call per analysis.
- `agno` supports it natively and it declares `supports_native_structured_outputs = True`, which the Pydantic report needs.

`ministral-3:3b` is the default rather than `qwen3.5:4b` because the latter produced empty schema-constrained output in verification.

**Optional alternative: OpenRouter free tier.** Enabled only by setting the environment variables below. It requires a key. It is never selected automatically.

## Session 3 verification (2026-10-08)

Confirmed by actually running the pipeline, not by inspection:

| Fact | Result |
|---|---|
| Agno version installed | `3.1.1` |
| Ollama client | `ollama 0.6.3`, host `http://localhost:11434` |
| `Ollama` native structured output | `supports_native_structured_outputs = True`, confirmed on the installed class |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2`, downloaded from the HF Hub on first run, cached after that |
| Vector store | local LanceDB at `data/lancedb/`, no cloud, no key |
| LLM call time | roughly 1-2 minutes per call on CPU for a small explanation |
| API key required | **No.** Nothing in the pipeline reads a key. |
| Generation cap | 700 tokens, needed because a 3B model otherwise runs past the limit and returns unparseable JSON |

### Defects found and fixed during verification

1. `Document` in Agno 3.1.1 has `meta_data`, not `metadata`, and exposes no `score`
   field. Retrieved results carry `rank` instead of a fabricated similarity number.
2. Default chunking put each whole 2-3 KB source in one chunk, so front matter crowded
   out the body text. `MarkdownReader(chunk_size=600)` fixes this.
3. `agno.models.ollama` imports `agno.models.openai`, so the `openai` package must be
   installed even when no OpenAI account or key is used. This is a transitive import in
   Agno, not a second provider.
4. Generation is capped at 700 tokens. Uncapped, the model produced 800+ tokens and
   returned truncated, unparseable JSON.

## Configuration

All configuration is by environment variable. No key is ever read from, or written to, tracked files.

| Variable | Default | Meaning |
|---|---|---|
| `COLABAUDIT_LLM_PROVIDER` | `ollama` | `ollama` or `openrouter`. |
| `COLABAUDIT_LLM_MODEL` | `ministral-3:3b` | Provider-specific model id. |
| `COLABAUDIT_OLLAMA_HOST` | `http://localhost:11434` | Ollama base URL. |
| `OPENROUTER_API_KEY` | unset | Required only when provider is `openrouter`. |
| `COLABAUDIT_LLM_ENABLED` | `0` | Set to `1` to allow the LLM stage. Default `0` keeps the deterministic pipeline the only active path. |

## API key policy

If the configured provider requires a key and no valid key is present:

- Stop only at that point.
- Ask the user exactly: "An API key is required for the selected free provider/model. Do you want to create/configure the key now?"
- Do not generate, invent, or guess credentials.
- Do not silently switch provider or fall back to a paid model.
- Do not block any work that does not need the key.

Current state: **no API key is needed.** The default provider is local Ollama.

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
model are configured, and `run_explanation` returns the audit result, the evidence and
the explanation separately, so the caller records `llm_status` as `not_configured`,
`ok` or `failed` alongside them. Session 4 renders that in the UI.

## Configuration examples

Local, no key:

```bash
export COLABAUDIT_LLM_PROVIDER=ollama
export COLABAUDIT_LLM_MODEL=ministral-3:3b
export COLABAUDIT_LLM_ENABLED=1
```

OpenRouter free tier, if chosen:

```bash
export COLABAUDIT_LLM_PROVIDER=openrouter
export COLABAUDIT_LLM_MODEL=nvidia/nemotron-3-super-120b-a12b:free
export OPENROUTER_API_KEY=...   # never committed
export COLABAUDIT_LLM_ENABLED=1
```

## Runtime degradation

A free model may become unavailable or rate-limited. In that case:

- Catch the error, record it in `llm_status`, show it in the UI.
- Keep the deterministic report.
- Do not restructure the architecture and do not switch to a paid model.