# AI_PROVIDER.md

## Purpose

Isolate LLM provider selection from application logic. Nothing in `parsing.py`, `extraction.py`, `runtime.py`, `rules.py`, or `models.py` may import a provider SDK or read an API key.

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
- One `Agent` instance reused across a session. No teams, no sub-agents, no tool loops.
- Prompt is compact: notebook summary, runtime snapshot id, deterministic findings, and the top retrieved evidence snippets only. Full notebook source is never sent.
- No retry loop beyond Agno's default. On rate limit or provider error, the failure is recorded in the report and the deterministic report is returned unchanged.

## Provider metadata in output

Every report records `llm_provider` and `llm_model`, plus `llm_status`, one of `not_configured`, `ok`, or `failed` with the error message. Run metadata is written next to the report.

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