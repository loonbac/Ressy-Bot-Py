# Explore — `ai-web-search`

- Date: 2026-06-15
- Phase: explore (read-only investigation)
- Owner: el Gentleman orchestrator (inline, corroborated against `sdd-explore` subagent mapping)
- next_recommended: **proposal**

---

## Executive Summary

The `ai_chat` plugin **already ships a full web-tool subsystem** (`src/bot/plugins/ai_chat/web.py`) with SSRF protection, httpx + Playwright fallback, HTML→text extraction, and a dedicated dispatch path (`dispatch_web_tool`) plus config keys (`web_enabled`, `web_max_chars`, `web_timeout_seconds`). The single gap is that the only web tool today is `fetch_webpage`, which **requires a URL**. There is no `web_search(query)` tool, so when the LLM lacks a link (e.g. "busca info sobre malware en AUR") it correctly reports it cannot search the web from zero.

**Adding real web search = add ONE new tool (`web_search`) + its dispatch + a search backend + config/keys + a tool hint in the cog.** No architectural change required; the extension points already exist.

---

## Current Behavior Mapping

| File | Role | Relevant to this change |
|------|------|:---:|
| `src/bot/plugins/ai_chat/web.py` | Web tools: `fetch_webpage`, `dispatch_web_tool`, SSRF guard, httpx+Playwright fetch, `html_to_text`, `_TextExtractor` | ✅ primary — add `web_search` here |
| `src/bot/plugins/ai_chat/tools.py` | `TOOLS` (Discord) + `run_tool_loop()` tool-calling loop; routes web names via `WEB_TOOL_NAMES` | ✅ minor — loop already routes any name in `WEB_TOOL_NAMES` |
| `src/bot/plugins/ai_chat/cog.py` | `AIChatCog.ask_full()` — assembles tool schemas + hints, calls `run_tool_loop` | ✅ minor — add a `web_search` hint when `web_on` |
| `src/bot/plugins/ai_chat/database.py` | `DEFAULTS` dict + `ai_chat_config` table (key/value) | ✅ minor — add `search_*` config keys |
| `src/bot/plugins/ai_chat/api.py` | FastAPI router, `_typed_config()`, `ConfigPayload` | ✅ minor — expose new config keys to dashboard |
| `src/bot/plugins/ai_chat/models.py` | Pydantic models (`ConfigPayload`) | ✅ minor — add fields if exposed |
| `src/bot/plugins/ai_chat/client.py` | MiniMax OpenAI-compatible client; `chat_completion` returns `tool_calls` | ⚪ no change — tool-calling protocol already supports multiple tools |
| `src/bot/plugins/ai_chat/__init__.py` | `setup(bot, cm, app)` | ⚪ no change |
| `src/bot/plugins/blackboard/scraper.py` | Playwright login+scrape | ⚪ reference only (Playwright patterns) |
| `src/bot/plugins/openrouter_prices/scrapers/` | HTTP scraping primitives | ⚪ reference only |
| `pyproject.toml` | `httpx>=0.27`, `playwright>=1.40` already declared | ✅ reuse, no new dep for backend-less options |

---

## Tool System Architecture

- **Schema format**: OpenAI-compatible function tools (`{"type":"function","function":{name,description,parameters}}`) in `TOOLS` (Discord, `tools.py`) and `WEB_TOOLS` (`web.py`).
- **Protocol** (`run_tool_loop` in `tools.py`):
  1. Send messages + tool schemas to MiniMax with `tool_choice="auto"`.
  2. If response carries `tool_calls`, append the assistant message, then for each call:
     - parse `function.arguments` JSON;
     - **route by name**: if `name in WEB_TOOL_NAMES` → `dispatch_web_tool`; elif executor present → `DiscordTools.dispatch`; else error dict.
     - append `{"role":"tool","tool_call_id":...,"content":json(result)}`.
  3. Loop up to `max_iters=5`; on exhaustion force a final completion with no tools.
- **Key insight**: adding a tool is **purely additive**. Put its schema in `WEB_TOOLS`, add its name to `WEB_TOOL_NAMES`, implement it, handle it in `dispatch_web_tool`. The loop, routing, and tool-calling protocol need no change.

---

## Current Web/Fetch Tool (confirmed: URL-only, no search)

`fetch_webpage(url, max_chars, timeout, ...)` in `web.py`:
- Requires a full URL (auto-prefixes `https://` if missing).
- SSRF guard: rejects non-http(s), resolves host, blocks private/loopback/link-local/reserved IPs; manually follows redirects re-validating each hop; Playwright route handler aborts internal IPs.
- Fetch path: httpx with browser headers → if empty (JS render) or blocked status (403/429/5xx) → Playwright/Chromium headless fallback.
- Returns `{url, final_url, status, title, description, content, length, truncated, fetched_with}` or `{error}`.
- `dispatch_web_tool` only knows `fetch_webpage` → `WEB_TOOL_NAMES = {"fetch_webpage"}`.

**Confirmed: no query→search capability exists.** This is exactly why the bot told the user it can only open a provided link.

---

## LLM Provider & Config

- **Provider**: MiniMax (`api.minimax.io/v1`), OpenAI-compatible chat completions. Default model `MiniMax-M3`.
- **API key resolution** (`client.py::_resolve_api_key`): `config_manager.get("minimax_api_key")` → constructor arg → `MINIMAX_API_KEY` env.
- **Model name**: stored in DB config (`chat_model`, `analysis_model`), chosen via dashboard `PUT /api/plugins/ai-chat/config`.
- **MiniMax has NO native web-search tool** (unlike Perplexity/Gemini). So search must be implemented on our side via a search backend.

---

## Plugin Setup & Available Dependencies

- `setup(bot, config_manager, app)` builds `AIChatDatabase`, `AIChatClient(config_manager=resolved_cm)`, `AIChatCog`, registers router at `/api/plugins/ai-chat`, stashes in `app.state.ai_chat_*`.
- Already-declared deps usable for search: **`httpx>=0.27`** (async HTTP) and **`playwright>=1.40`**. No `beautifulsoup`/`lxml` — HTML parsing is done with the stdlib `HTMLParser` (`_TextExtractor`).
- A **backend-less** search (DuckDuckGo HTML scrape) needs **zero new dependencies**. A **dedicated search API** (Brave/Tavily/Serper/SerpAPI) also needs only httpx + a key.

---

## Reusable Scraping/HTTP Patterns in Repo

- `_TextExtractor` (stdlib `HTMLParser`) in `web.py` → reusable to parse search-result HTML.
- `_normalize_url`, `_resolve_safe`, `_validate_host`, SSRF redirect re-validation → reusable for any URL a search backend returns.
- Playwright fallback pattern (`_fetch_with_browser`) → reusable if a search engine blocks bare httpx.
- `httpx.AsyncClient` with browser headers (`_BROWSER_HEADERS`) → reusable for scraping a search engine.

---

## Config / Secret Surface (project conventions)

Following the existing pattern (mirrors `minimax_api_key` + `web_*` keys):
- New keys live in `database.py::DEFAULTS` (seeded with `INSERT OR IGNORE`, never overwriting user values).
- Stored in `ai_chat_config` table; read via `cfg.get(...)`.
- Secrets (search API key) resolved the same way MiniMax key is: `config_manager.get("<provider>_api_key")` → env fallback.
- Exposed to dashboard via `_typed_config()` in `api.py` + `ConfigPayload` in `models.py`.
- Suggested keys (to be finalized in spec): `search_enabled`, `search_provider`, `search_api_key`, `search_max_results`, `search_safe`.

---

## Frontend Config Surface

- The `ai-chat` plugin already exposes `GET/PUT /api/plugins/ai-chat/config`. A "web search" toggle + provider/key fields would extend the existing `ConfigPayload` and the dashboard AI-Chat config card (locate in `frontend/src/components/` during design phase). No new route pattern required.

---

## Suggested Change Directions (no decision yet)

| Option | Needs key? | Cost | Reliability | ToS risk | Notes |
|---|:---:|---|---|---|---|
| **A. DuckDuckGo HTML scrape (lite.duckduckgo.com)** | no | free | medium (HTML changes) | gray | zero config, reuses `_TextExtractor`+httpx; Playwright fallback if blocked |
| **B. DuckDuckGo Instant Answer API** | no | free | low (abstracts, not real SERP) | ok | good for definitions, poor for "malware AUR news" |
| **C. Brave Search API** | yes | free tier 2000/mo | high | ok | clean JSON, generous free tier |
| **D. Tavily** | yes | free tier 1000/mo | high | ok | LLM-tuned summaries |
| **E. Serper.dev / SerpAPI** | yes | paid (small free) | high | ok | Google results via API |
| **F. Self-hosted SearXNG** | no | free (infra) | high | ok | requires running an instance |

**Recommended to evaluate in proposal**: a **provider-agnostic backend** with a sensible **keyless default (DuckDuckGo HTML scrape)** so the feature works out-of-the-box, plus optional support for a key-based provider (Brave/Tavily) for reliability. Decision deferred to the proposal/product question round.

---

## Risks

- **Abuse / cost**: a web-search tool the LLM can invoke auto means any user can trigger external API calls. Need rate limiting (reuse per-user `rate_limit_seconds`) and a hard per-call cap.
- **Key management**: storing a third-party search key — must follow the same secret hygiene as `minimax_api_key` (config DB / env, never logged, never serialized to the LLM).
- **Latency**: search + fetch + summarize can exceed Discord's interaction window; the mention path already uses `message.reply` (non-deferred) — need to keep within tool-loop `web_timeout`.
- **Reliability of scraping**: DuckDuckGo HTML can change; needs graceful `{"error": ...}` return (already the project convention) and optional Playwright fallback.
- **ToS / legal**: scraping a search engine is a gray area; a key-based API is clean. Surface this to the user as a product decision.
- **Content safety / hallucination**: the LLM summarizes fetched pages — must cite source URLs (the `fetch_webpage` result already carries `url`/`title`).
- **SSRF carry-over**: any URL returned by a search backend and then fetched via `fetch_webpage` is already covered by the existing SSRF guard — no regression.

---

## skill_resolution

`none` — `.atl/skill-registry.md` exists but its skills table is empty; no project/user skills matched this phase. SDD executor skill `sdd-explore` was used as the phase contract.
