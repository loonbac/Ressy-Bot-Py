# Tasks — `ai-web-search`

Implementation tasks for the additive `web_search` capability in the `ai_chat`
plugin. Strict TDD (RED → GREEN → TRIANGULATE → REFACTOR). Default test command
throughout: `uv run pytest` (live marker excluded by default via
`addopts = "-m 'not live'"` in `pyproject.toml`; `asyncio_mode = "auto"`).

Grounding (read before starting):
- `src/bot/plugins/ai_chat/web.py` — `WEB_TOOLS`, `WEB_TOOL_NAMES`,
  `_TextExtractor`, `_collapse_inline`, `_BROWSER_HEADERS`, `dispatch_web_tool`,
  `fetch_webpage`, SSRF helpers (UNCHANGEABLE).
- `src/bot/plugins/ai_chat/tools.py` — `run_tool_loop` (late-imports
  `WEB_TOOL_NAMES`/`dispatch_web_tool` at call time).
- `src/bot/plugins/ai_chat/cog.py` — `AIChatCog.ask_full` (builds `tool_schemas`
  + `tool_hints`, calls `run_tool_loop`).
- `src/bot/plugins/ai_chat/database.py` — `DEFAULTS` + `INSERT OR IGNORE` seeding
  in `connect()`.
- `src/bot/plugins/ai_chat/api.py` — `_typed_config`, `update_config` clamps.
- `src/bot/plugins/ai_chat/models.py` — `ConfigPayload`.
- `tests/test_ai_chat_web.py`, `tests/test_ai_chat.py` — mirror style/layout.

HARD CONSTRAINT (human): No task may launch a browser from agent/test tooling.
Live tests against DuckDuckGo MUST be `@pytest.mark.live` and MUST use **httpx
only**. Do NOT add new Playwright usage in tasks. The Playwright fallback in
`fetch_webpage` stays untouched.

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~730 (impl+frontend ~330, tests+fixture ~400) |
| 400-line budget risk | Medium (PR 1 sits at/near 400; PR 2 comfortably under) |
| Chained PRs recommended | Yes |
| Suggested split | PR 1: backend engine + cog wiring → PR 2: API exposure + live tests + frontend |
| Delivery strategy | ask-on-risk |
| Chain strategy | stacked-to-main |

Forecast rationale: design LOC estimates sum to ~245 backend impl + ~330 tests +
fixture bytes, plus ~80 frontend. Total comfortably exceeds 400. Splitting along
the functional seam (engine works through the cog/tool-loop after PR 1; dashboard
exposure + live + frontend after PR 2) gives each PR a clean start/finish/
verification/rollback boundary. PR 1 alone is ~480 changed lines (engine impl +
its unit tests) — it sits at/just over the 400 budget, hence `ask-on-risk`: the
human decides at apply time whether to accept PR 1 as-is or further split the
parser+web_search body into its own PR. PR 2 is ~290 lines.

Work-unit boundaries:
- **PR 1 — "Backend search engine + cog wiring"** (Phases 0–6). After merge,
  `web_search` is fully functional through the Discord `/ia` + mention path; the
  feature is toggled via raw DB config (`search_enabled`). Verification:
  `uv run pytest -m "not live"` green. Rollback: set `search_enabled=false` and
  restart.
- **PR 2 — "Dashboard exposure + live + frontend"** (Phases 7–9). Adds typed API
  exposure, PUT validation, opt-in live smoke tests, and the dashboard card.
  Verification: `uv run pytest -m "not live"` + `cd frontend && pnpm exec tsc
  --noEmit && pnpm exec vite build`. Rollback: revert additive frontend + API
  surface; engine still runs via PR 1 defaults.

```text
Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: Medium
```

---

## PR 1 — Backend search engine + cog wiring

### Phase 0 — DDG Lite HTML fixture (hermetic parser input)

- [x] **Task 0.1** — `tests/fixtures/ddg_lite_search.html` (new).
- What: Commit a minimal hand-crafted fixture that mirrors the real DuckDuckGo
  Lite SERP structure: at least two result rows whose anchors are wrapped as
  `https://duckduckgo.com/l/?uddg=<URL-ENCODED>&rut=<token>` (and one relative
  `/l/?uddg=...` variant), plus a sibling snippet text node. The human will
  optionally provide captured bytes; if not available, hand-craft the minimal
  structure. Do NOT fetch this from a browser in any task.
- Why: keeps `_parse_ddg_lite` tests hermetic and offline. Fixture content is
  characterized by the parser RED test (Task 3.1).
- Verification: file exists; `uv run pytest -m "not live"` (fixture is read by
  Task 3.1; no standalone assertion here).
- Rollback: delete the fixture + parser test together.

### Phase 1 — Config seeding (DEFAULTS only)

- [x] **Task 1.1** (RED) — `tests/test_ai_chat_web_search.py` (new) config-seeding block.
- RED assertion: fresh `AIChatDatabase(str(tmp_path/"ai_chat.db")).connect()`
  yields `search_enabled=="true"`, `search_safe=="true"`,
  `search_max_per_hour=="10"`; and after manually setting `search_safe="false"`
  + reconnect, `search_safe` stays `"false"` (idempotence — REQ-SEARCH-09).
  (Mirror the idempotence style in `test_ai_chat.py::test_ai_chat_drops_legacy_model_key_and_preserves_dashboard_selection`.)
- Run: `uv run pytest -m "not live" tests/test_ai_chat_web_search.py -k seeding`
  → RED (keys absent today; `get_config` omits them).

- [x] **Task 1.2** (GREEN) — `src/bot/plugins/ai_chat/database.py`.
- Add to `DEFAULTS` (string values, preserving existing `INSERT OR IGNORE`
  seeding):
  ```python
  "search_enabled": "true",
  "search_safe": "true",
  "search_max_per_hour": "10",
  ```
- GREEN target: Task 1.1 RED tests now pass. No migration table needed.
- Verification: `uv run pytest -m "not live" tests/test_ai_chat_web_search.py -k seeding`.
- Rollback: additive keys; safe to remove.

### Phase 2 — WebSearchQuota (in-memory rolling-hour)

- [x] **Task 2.1** (RED) — `tests/test_ai_chat_web_search.py` quota block.
- RED assertions against `WebSearchQuota` with an injected fake clock
  (`clock=lambda: t`):
  - `check_and_consume("u1", 2)` allows twice and returns
    `(True, remaining_after_consume)`.
  - Third call on `"u1"` returns `(False, retry_after_seconds)` (retry > 0).
  - Advance fake clock past `3600s` → old timestamps pruned, next call allowed.
  - `"u2"` has an independent deque (separate users, separate counters).
- Run → RED (`WebSearchQuota` not importable yet).

- [x] **Task 2.2** (GREEN) — `src/bot/plugins/ai_chat/web.py`.
- Add `import time`, `from collections import defaultdict, deque`, `from math import ceil`,
  `from typing import Callable`.
- Add `class WebSearchQuota` per design §3 (Pruning rule: pop left while
  `events[0] <= cutoff`; deny when `len(events) >= max_per_hour` returning
  `ceil(events[0] + window_seconds - now)`; else append `now`, return
  `(True, max_per_hour - len(events))`). Constructor:
  `window_seconds=3600`, `clock=time.monotonic`.
- Add module-level `_SEARCH_QUOTA = WebSearchQuota()`.
- GREEN target: Task 2.1 passes.

- [x] **Task 2.3** (TRIANGULATE) — add a case: `max_per_hour=1` denies on the 2nd call
  immediately; boundary `events[0] == cutoff` is pruned (use `<=`). Confirm green.

- [x] **Task 2.4** (REFACTOR) — keep the prune loop O(1) amortized; no behavior change.

### Phase 3 — `_parse_ddg_lite` parser (stdlib only)

- [x] **Task 3.1** (RED) — `tests/test_ai_chat_web_search.py` parser block reading
  `tests/fixtures/ddg_lite_search.html`.
- RED assertions:
  - `_parse_ddg_lite(html)` returns a non-empty list.
  - Every result has exactly `title`, `url`, `snippet` keys; `title`/`url` non-empty.
  - A wrapped `https://duckduckgo.com/l/?uddg=<encoded>&rut=...` is decoded to
    the real destination URL via `urllib.parse` (no DDG wrapper leaked as `url`).
  - A relative `/l/?uddg=...` variant is also decoded.
  - No raw HTML substring and no `duckduckgo.com/l/?uddg=` appears in any `url`.
- Run → RED (`_parse_ddg_lite` absent).

- [x] **Task 3.2** (GREEN) — `src/bot/plugins/ai_chat/web.py`.
- Add pure function `def _parse_ddg_lite(html: str) -> list[dict[str, str]]`
  using stdlib only (`HTMLParser` subclass `_DDGLiteParser(HTMLParser)` +
  `urlsplit`/`parse_qs`/`unquote`). Decode `uddg` query param; accept direct
  `http(s)://` hrefs; ignore non-result/internal DDG links and non-http(s) URLs.
  Reuse `_collapse_inline` for titles/snippets; bound snippet to first 500 chars.
- GREEN target: Task 3.1 passes.

- [x] **Task 3.3** (TRIANGULATE) — add a second mini-fixture fragment (inline string)
  with only relative `/l/?uddg=` links to confirm decoding path independently;
  add an empty/garbage HTML input asserting `_parse_ddg_lite("") == []`.
- Verification: `uv run pytest -m "not live" tests/test_ai_chat_web_search.py -k parse`.

### Phase 4 — `web_search` function (DDG Lite via httpx)

- [x] **Task 4.1** (RED) — `tests/test_ai_chat_web_search.py` web_search block.
- RED assertions using `httpx.MockTransport` handler + injected `WebSearchQuota`
  (mirror `test_ai_chat_web.py` mocking style):
  - Empty/whitespace `query` → `{"error": ...}`, no HTTP call.
  - Quota exhausted for `user_id="u1"` (pre-consume via the same fake quota) →
    `{"error": ...}` in Spanish AND injected client NOT called (assert handler
    never invoked) — REQ-SEARCH-06.
  - `user_id=None` → fail-closed `{"error": ...}`, no HTTP (REQ-SEARCH-07).
  - DDG timeout (`httpx.TimeoutException`) → `{"error": ...}`, no raise (REQ-SEARCH-12).
  - Happy path: handler returns the fixture HTML (or a minimal SERP) → payload
    has `query`, `safe` (bool), `results` (list of `{title,url,snippet}`),
    `count`, `source="duckduckgo_lite"`, `fetched_with="http"`; no raw HTML
    (REQ-SEARCH-02, REQ-SEARCH-03, REQ-SEARCH-08).
  - Outbound request uses `https://lite.duckduckgo.com/lite/`, sends `q` param,
    `kp=1` when `safe=True` / `kp=-1` when `safe=False`, and NO `Authorization`
    header (REQ-SEARCH-02). Assert via the handler's `request`.
- Run → RED (`web_search` absent).

- [x] **Task 4.2** (GREEN) — `src/bot/plugins/ai_chat/web.py`.
- Add `async def web_search(query, *, max_results=5, safe=True, timeout=20.0,
  user_id=None, max_per_hour=10, quota=None, client=None, browser_fallback=False)
  -> dict[str, Any]` per design §3 contract:
  - Clamp `max_results` to `1..10`; trim/validate `query`.
  - Fail closed on missing `user_id`.
  - Quota check via `quota or _SEARCH_QUOTA.check_and_consume(user_id, max_per_hour)`
    BEFORE constructing/using the httpx client.
  - `GET https://lite.duckduckgo.com/lite/` with params `q`, admin `kp`; use
    `_BROWSER_HEADERS`; `httpx.AsyncClient(timeout=timeout)` when no client
    injected; `client.aclose()` only if owned.
  - Block/error statuses (`403/429/5xx`) → error dict. Parse via
    `_parse_ddg_lite`; build structured payload (bounded to `max_results`).
  - Catch `httpx.TimeoutException`, `httpx.HTTPError`, parser failures, and
    generic `Exception` into `{"error": "..."}`. Never raise.
  - Do NOT add Playwright usage (`browser_fallback` reserved/ignored this slice).
- GREEN target: Task 4.1 passes.

- [x] **Task 4.3** (TRIANGULATE) — add: blocking `503` status → error dict (REQ-SEARCH-08);
  `safe=False` sends `kp=-1`; `max_results=20` is clamped to ≤10 in the payload.
- Verification: `uv run pytest -m "not live" tests/test_ai_chat_web_search.py -k web_search`.

### Phase 5 — `dispatch_web_tool` routing + signature threading

- [x] **Task 5.1** (RED) — `tests/test_ai_chat_web_search.py` dispatch block.
- RED assertions (monkeypatch `web.web_search` to a recording fake, mirroring
  `test_run_tool_loop_routes_web_tool`):
  - `dispatch_web_tool("web_search", {"query":"linux"}, user_id="u1",
    search_enabled=True, search_safe=True, search_max_per_hour=10)` routes to
    `web_search` and forwards `query`, `user_id`, `safe`, `max_per_hour`.
  - `search_enabled=False` → returns `{"error": ...}`, does NOT call `web_search`
    (REQ-SEARCH-01, defense-in-depth).
  - Existing `dispatch_web_tool("fetch_webpage", ...)` path still works
    unchanged (run existing `tests/test_ai_chat_web.py` dispatch tests).
  - `run_tool_loop(...)` now accepts `user_id`, `search_enabled`, `search_safe`,
    `search_max_per_hour` and forwards them only to the web dispatch branch
    (assert via a fake `web_search` capturing kwargs; Discord tools are
    unaffected). Reuse the `FakeClient` pattern from
    `test_ai_chat_web.py::test_run_tool_loop_routes_web_tool`.
- Run → RED (new kwargs absent; `web_search` not dispatched).

- [x] **Task 5.2** (GREEN) — `src/bot/plugins/ai_chat/web.py` + `src/bot/plugins/ai_chat/tools.py`.
- `web.py`:
  - Extend `WEB_TOOLS` with the `web_search` schema (name, description in
    Spanish neutro; required `["query"]`, optional `max_results` only; NO `safe`,
    provider, or key arg — REQ-SEARCH-05).
  - `WEB_TOOL_NAMES = {"fetch_webpage", "web_search"}`.
  - `dispatch_web_tool(name, args, *, timeout=20.0, user_id=None,
    search_enabled=True, search_safe=True, search_max_per_hour=10)`:
    - `name == "fetch_webpage"` → existing path unchanged.
    - `name == "web_search"` → if not `search_enabled`, return error; else call
      `web_search(str(args.get("query") or ""), max_results=int(args.get(
      "max_results") or 5), safe=search_safe, timeout=timeout, user_id=user_id,
      max_per_hour=search_max_per_hour)`; wrap in `try/except` → error dict.
    - unknown name → existing `{"error": ...}`.
- `tools.py`: extend `run_tool_loop(...)` signature with keyword-only
  `user_id: str | None = None`, `search_enabled: bool = True`,
  `search_safe: bool = True`, `search_max_per_hour: int = 10`; in the
  `name in WEB_TOOL_NAMES` branch forward all four to `dispatch_web_tool`. All
  new params have defaults → existing callers/tests unaffected.
- GREEN target: Task 5.1 passes + full `test_ai_chat_web.py` still green.

- [x] **Task 5.3** (TRIANGULATE) — assert `search_enabled=False` is honored at dispatch
  even when a model emits an unexpected `web_search` call (no network). Confirm
  existing `test_run_tool_loop_routes_web_tool` still asserts `calls["url"]`.

### Phase 6 — `ask_full` tool gating + search-first hint + caller threading

- [x] **Task 6.1** (RED) — `tests/test_ai_chat_web_search.py` cog gating block.
- RED assertions against `AIChatCog` (reuse the `ai_cog` fixture pattern from
  `tests/test_ai_chat.py`, with a fake `chat_completion` capturing the `tools`
  arg + the inserted system message):
  - With `web_enabled=true`, `search_enabled=true`: exposed tool schemas include
    both `fetch_webpage` AND `web_search`; a system message contains the
    search-first hint text; `run_tool_loop` is called with
    `user_id=str(<caller>)`, `search_enabled=True`, and the configured
    `search_safe`/`search_max_per_hour` (REQ-SEARCH-01, REQ-SEARCH-07,
    REQ-SEARCH-11).
  - With `search_enabled=false` (set via `update_config`): only `fetch_webpage`
    is exposed; NO search-first hint text in the inserted message.
  - With `web_enabled=false`: neither web schema exposed.
  - Do NOT hit the network (fake client returns content with no tool_calls).
- Run → RED (`ask_full` does not yet gate/search-hint/thread `user_id`).

- [x] **Task 6.2** (GREEN) — `src/bot/plugins/ai_chat/cog.py` (`AIChatCog.ask_full`).
- Read `search_on`, `search_safe`, `search_max_per_hour` (clamped `1..100`) from
  `cfg`.
- In the `if web_on:` block: keep adding `fetch_webpage`; add `web_search`
  schema only when `search_on`; append the search-first hint (Spanish neutro
  per CLAUDE.md) only when `search_on` (e.g. instructs: search first when no URL
  is provided, then `fetch_webpage` only the necessary results, cite title/URL,
  never invent results).
- Pass `user_id=str(user_id)`, `search_enabled=search_on`,
  `search_safe=search_safe`, `search_max_per_hour=search_max_per_hour` into the
  `run_tool_loop(...)` call. (`ask_full` already receives `user_id`.)
- GREEN target: Task 6.1 passes; `tests/test_ai_chat.py` mention/command + API
  chat tests still green.

- [x] **Task 6.3** (REFACTOR) — extract the per-key config reads behind a small local
  helper if it clarifies; behavior unchanged. Ensure `web_on=false` path never
  reads search config in a way that crashes.

- **PR 1 verification gate:** `uv run pytest -m "not live"` fully green (no
  new live tests yet). `cd frontend && pnpm exec tsc --noEmit` unaffected
  (frontend untouched in PR 1). Rollback: set `search_enabled=false` and restart
  the bot — `web_search` schema/hint vanish and dispatch rejects before network.

---

## PR 2 — Dashboard exposure + live tests + frontend

### Phase 7 — API/model typed exposure + PUT validation

- [x] **Task 7.1** (RED) — `tests/test_ai_chat_config.py` (new) or extend
  `tests/test_ai_chat.py`.
- RED assertions:
  - `_typed_config({...})` returns `search_enabled` (bool), `search_safe` (bool),
    `search_max_per_hour` (int) with correct types (REQ-SEARCH-10).
  - `GET /api/plugins/ai-chat/config` includes the three `search_*` keys typed.
  - `PUT /api/plugins/ai-chat/config` with `search_max_per_hour=0` → HTTP `422`
    with Spanish detail (e.g. contains "search_max_per_hour"). (Mirror the ASGI
    client pattern in `tests/test_ai_chat.py`.)
  - `PUT ... search_max_per_hour=25` persists and `GET` returns integer `25`.
  - `PUT ... search_max_per_hour=101` → `422` (upper bound).
- Run → RED (`_typed_config` lacks keys; PUT doesn't validate).
- RED observed in PR 2: 12 tests fail with `KeyError: 'search_enabled'/'search_safe'/'search_max_per_hour'` (4 pure `_typed_config` + 8 API round-trip) + the `0/101/-3` 422 cases (HTTPException never raised in current code).

- [x] **Task 7.2** (GREEN) — `src/bot/plugins/ai_chat/api.py` + `models.py`.
- `api.py::_typed_config`: add `search_enabled`/`search_safe` (bool from string),
  `search_max_per_hour` (int).
- `api.py::update_config`: add validation branch — reject `search_max_per_hour`
  `<1` or `>100` with `HTTPException(422, detail="search_max_per_hour debe estar
  entre 1 y 100.")` BEFORE clamping (REQ-SEARCH-10 requires rejection, not
  silent clamp). Then no clamp needed for valid values.
- `models.py::ConfigPayload`: add
  `search_enabled: bool | None = None`, `search_safe: bool | None = None`,
  `search_max_per_hour: int | None = None`.
- GREEN target: Task 7.1 passes; existing config PUT tests still green.
- Verification: `uv run pytest -m "not live" tests/test_ai_chat_config.py`.
- GREEN observed in PR 2: all 13 tests in `tests/test_ai_chat_config.py` pass; regression on `test_ai_chat.py`+`test_ai_chat_web.py`+`test_ai_chat_web_search.py`+`test_ai_chat_config.py` = **111 passed** (98 PR 1 + 13 new). Reject branch returns 422 with detail `"search_max_per_hour debe estar entre 1 y 100."` for 0/101/-3; boundary 1/100 accepted; =25 persists as int.

### Phase 8 — Opt-in live tests (httpx only, `@pytest.mark.live`)

- [x] **Task 8.1** — `tests/test_ai_chat_web_search_live.py` (new).
- What: Two tests, each decorated `@pytest.mark.live` (excluded by default via
  `addopts = "-m 'not live'"`):
  1. Real DDG httpx search: `await web_search("linux kernel 6.8",
     user_id="live-user", max_per_hour=100, safe=True, timeout=10)`. Assert
     EITHER non-empty structured `results` OR a graceful `{"error": ...}` if DDG
     blocks the environment (do not hard-fail on provider blocking).
  2. Real fetch of the first result URL via the EXISTING `fetch_webpage`
     (unchanged SSRF guard path): `await fetch_webpage(result["url"],
     timeout=10)`. Assert structured payload or graceful error (REQ-SEARCH-04
     smoke). If no results, skip (`pytest.skip`).
- Constraint: httpx only; NO Playwright, NO browser. The `browser_fallback`
  param of `fetch_webpage` may be left default (runtime choice), but no new
  browser usage is introduced by these tests.
- Verification: `uv run pytest -m live tests/test_ai_chat_web_search_live.py`
  (manual/opt-in only); default `uv run pytest` skips them.
- Rollback: delete the live file; engine unaffected.
- PR 2 confirmed: live tests collected only with `-m live` (2 tests); default
  `uv run pytest -m "not live"` deselects them. Test 2 forces
  `browser_fallback=False` on `fetch_webpage` to respect the hard
  project-wide constraint ("never launch a browser from agent/test tooling").

### Phase 9 — Frontend dashboard toggle

- [x] **Task 9.1** — `frontend/src/api/ai-chat.ts`.
- Extend `AIChatConfig` interface with `search_enabled: boolean`,
  `search_safe: boolean`, `search_max_per_hour: number`. (Note: the existing
  `web_*` backend keys are NOT in the interface today — out of scope to add;
  only add the `search_*` keys.) `AIChatConfigPatch` already covers
  `Partial<AIChatConfig>` automatically.

- [x] **Task 9.2** — `frontend/src/components/AIChatConfig.tsx`.
- Add the three `search_*` keys to `DEFAULT_CONFIG` (`search_enabled: true,
  search_safe: true, search_max_per_hour: 10`) so the draft initializes cleanly
  before fetch.
- Render a new `WebSearchCard` in the card stack (mirrors how `BehaviorCard` is
  composed).

- [x] **Task 9.3** — `frontend/src/components/ai_chat/WebSearchCard.tsx` (new) +
  `frontend/src/components/ai_chat/WebSearchCard.css` (new).
- Per project conventions (modular TSX + CSS pair, root class
  `.ai-chat-web-search-card`, light + dark variants in CSS, no `glass-panel`,
  at least one animation from `styles/animations.css`).
- Fields: toggle `search_enabled`; toggle `search_safe`; slider/number for
  `search_max_per_hour` (1–100). Accepts `{ config, onPatch }` props like
  `BehaviorCard`. Hint text in Spanish neutro peruano (no Rioplatense).
- GREEN target: `cd frontend && pnpm exec tsc --noEmit` clean;
  `cd frontend && pnpm exec vite build` succeeds (output to
  `src/web/static/`).
- Rollback: revert the additive card + interface fields; backend still runs via
  PR 1 defaults.
- PR 2 confirmed: `tsc --noEmit` produces **0 errors in PR 2 files**
  (8 pre-existing errors in `ConfigPanel.test.tsx`, `LatencyChart.tsx`,
  `openrouter/AliasesDrawer.tsx` are unrelated and unchanged by this change).
  `vite build` succeeds in 412 ms; output to `src/web/static/`.

---

## Cross-cutting reminders
- Spanish neutro peruano everywhere (UI strings, error messages, hints). No
  Rioplatense imperatives.
- Every new error path returns `{"error": "mensaje claro"}`; never raise out of
  the tool loop.
- Discord snowflake handling unchanged (search uses `user_id` as opaque string).
- Do not edit `fetch_webpage`, SSRF helpers, redirect logic, or the Playwright
  fetch path.
- After code/config changes, the bot needs a restart to take effect (no
  hot-reload) — flag restart need, do NOT start the bot.

## Requirement → Task coverage
- REQ-SEARCH-01 → 5.2 (WEB_TOOLS/NAMES), 6.2 (gating).
- REQ-SEARCH-02 → 4.1/4.2 (keyless DDG GET, `q`+`kp`, no auth header).
- REQ-SEARCH-03 → 3.1/3.2, 4.1/4.2 (structured payload, no raw HTML).
- REQ-SEARCH-04 → 8.1 (live fetch via existing SSRF guard).
- REQ-SEARCH-05 → 5.2 (no `safe` arg), 1.2 (default true).
- REQ-SEARCH-06 → 2.x, 4.1/4.2 (quota before network, Spanish error).
- REQ-SEARCH-07 → 5.1/5.2, 6.1/6.2 (`user_id` threading).
- REQ-SEARCH-08 → 4.1/4.2/4.3 (graceful failures).
- REQ-SEARCH-09 → 1.1/1.2 (idempotent seeding).
- REQ-SEARCH-10 → 7.1/7.2 (typed config + PUT validation).
- REQ-SEARCH-11 → 6.1/6.2 (search-first hint gated).
- REQ-SEARCH-12 → 4.1/4.2 (timeout → error dict).
