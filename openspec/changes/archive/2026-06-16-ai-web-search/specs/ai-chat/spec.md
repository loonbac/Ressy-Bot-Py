# ai-chat Specification

## Purpose

Add an additive `web_search` capability to the existing `ai_chat` plugin so the LLM can discover relevant public web pages from a plain-language query, then continue using the already-shipped `fetch_webpage` flow to read result URLs safely. This spec covers the new search behavior only; existing `fetch_webpage` behavior and its SSRF guard are referenced as preconditions, not redefined here.

## Requirements

### Requirement: REQ-SEARCH-01 — Tool registration and schema gating

The system MUST register `web_search` in `WEB_TOOLS` and add its name to `WEB_TOOL_NAMES`. The existing `run_tool_loop`/`dispatch_web_tool` path MUST route `web_search` through the shared web-tool dispatch flow without a special-case loop rewrite. Tool schemas MUST include `web_search` only when web tools are enabled and search is enabled.

- **GIVEN** `web_enabled=true` and `search_enabled=true`
- **WHEN** `ask_full` assembles tool schemas
- **THEN** `web_search` appears in the exposed tool schemas and can be routed by the shared web-tool dispatch path

- **GIVEN** `web_enabled=false` or `search_enabled=false`
- **WHEN** `ask_full` assembles tool schemas
- **THEN** `web_search` is absent from the exposed tool schemas

### Requirement: REQ-SEARCH-02 — Keyless DuckDuckGo HTML query execution

The system MUST perform search using a keyless DuckDuckGo HTML endpoint with only the query parameter. It MUST NOT send an `Authorization` header or any API key to the search endpoint.

- **GIVEN** a query such as `linux kernel 6.8`
- **WHEN** `web_search` executes
- **THEN** the outbound request targets the DuckDuckGo HTML endpoint with the query parameter and no auth/API-key header is present

### Requirement: REQ-SEARCH-03 — Structured result payload

`web_search` MUST return a structured payload to the LLM containing `query`, safe-search mode, and a bounded list of results. Each result MUST include `title`, `url`, and `snippet`. The LLM MUST NOT receive raw SERP HTML.

- **GIVEN** parsed search results
- **WHEN** `dispatch_web_tool` handles `web_search`
- **THEN** it returns a dict with the documented keys and each result has `title`, `url`, and `snippet`

- **GIVEN** a SERP with many hits
- **WHEN** results are returned
- **THEN** the list is truncated to the tool's bounded maximum and no raw HTML is included in the payload

### Requirement: REQ-SEARCH-04 — SSRF carry-over for result URLs

Any result URL later opened through the existing `fetch_webpage` flow MUST remain subject to the existing SSRF guard unchanged. `web_search` MUST NOT bypass or weaken that guard.

- **GIVEN** a search result URL that resolves to a private IP
- **WHEN** `fetch_webpage` is later called for that URL
- **THEN** it is rejected exactly as the current SSRF guard would reject it today

### Requirement: REQ-SEARCH-05 — Safe search default and admin-only control

`search_safe` MUST default to `true`. Safe-search MUST be governed only by admin config; end-user requests, prompt instructions, or tool arguments MUST NOT override or bypass it.

- **GIVEN** fresh config
- **WHEN** `ai_chat` config is read
- **THEN** `search_safe=true`

- **GIVEN** an end user asks to disable safe search
- **WHEN** the request is processed
- **THEN** the stored admin config remains unchanged and safe search stays enabled

### Requirement: REQ-SEARCH-06 — Per-user rolling-hour quota

The system MUST enforce a per-user rolling-hour cap (`search_max_per_hour`, default `10`) before any outbound network work begins. When the cap is exhausted, the tool MUST return a clear Spanish error payload and MUST NOT perform HTTP or Playwright work.

- **GIVEN** a user is under quota
- **WHEN** `web_search` executes
- **THEN** the search proceeds normally

- **GIVEN** a user is at or over quota
- **WHEN** `web_search` executes
- **THEN** it returns an error dict in Spanish and no outbound request is made

### Requirement: REQ-SEARCH-07 — Caller identity threading

The dispatch path MUST receive the invoking user's identity so quota checks can be applied per user. The exact mechanism is unspecified, but the `user_id` MUST flow from `AIChatCog.ask_full` into `web_search` dispatch and quota evaluation.

- **GIVEN** `ask_full` is invoked by a Discord user
- **WHEN** a `web_search` tool call is dispatched
- **THEN** the invoking user's id is available to the quota check

### Requirement: REQ-SEARCH-08 — Graceful failure

`web_search` MUST never raise out of the tool loop. Network failures, timeouts, parse failures, quota failures, or search blocking MUST return `{"error": "..."}` dicts and allow the loop to continue.

- **GIVEN** DuckDuckGo returns `503` or invalid HTML
- **WHEN** `web_search` executes
- **THEN** it returns an error dict and the tool loop continues

### Requirement: REQ-SEARCH-09 — Config seeding and idempotence

The new config keys `search_enabled`, `search_safe`, and `search_max_per_hour` MUST be seeded in `database.py::DEFAULTS` via `INSERT OR IGNORE` with defaults `true`, `true`, and `10` respectively. Repeated setup MUST NOT overwrite customized values.

- **GIVEN** a fresh `ai_chat` config DB
- **WHEN** `connect()`/setup runs
- **THEN** those keys are inserted with their defaults

- **GIVEN** `search_safe=false` was customized manually
- **WHEN** `connect()`/setup runs again
- **THEN** `search_safe` remains `false`

### Requirement: REQ-SEARCH-10 — API/model exposure

The `ai_chat` config MUST expose `search_enabled`, `search_safe`, and `search_max_per_hour` through the existing `GET/PUT /api/plugins/ai-chat/config` endpoint and the typed config path (`_typed_config()` + `ConfigPayload`). `PUT` MUST validate that `search_max_per_hour >= 1`.

- **GIVEN** a `GET` request against a configured plugin
- **WHEN** `/config` is called
- **THEN** the response includes the `search_*` keys with typed values

- **GIVEN** `PUT` includes `search_max_per_hour=0`
- **WHEN** `/config` is called
- **THEN** the request is rejected with a Spanish validation error

### Requirement: REQ-SEARCH-11 — Search-first tool hint

When search is enabled, `ask_full` MUST inject a tool hint that instructs the LLM to search first when no URL is provided and then fetch relevant result URLs using the existing `fetch_webpage` flow. When search is disabled, that hint MUST be absent.

- **GIVEN** `search_enabled=true` and the user request does not include a URL
- **WHEN** `ask_full` builds the message list
- **THEN** the messages include a search-first hint

- **GIVEN** `search_enabled=false`
- **WHEN** `ask_full` builds the message list
- **THEN** no search hint is included

### Requirement: REQ-SEARCH-12 — Timeout bound

`web_search` MUST honor the existing `web_timeout_seconds` bound. When a search exceeds that timeout, it MUST return a timeout error dict and MUST NOT hang the tool loop.

- **GIVEN** `web_timeout_seconds` is set to `5`
- **WHEN** `web_search` does not finish within `5` seconds
- **THEN** it returns a timeout error dict and the loop resumes
