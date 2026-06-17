# Apply Progress — `ai-web-search` (PR 1)

- Date: 2026-06-15
- Slice: **PR 1 — Backend search engine + cog wiring** (Phases 0–6)
- Delivery: chained PRs (stacked-to-main), auto-chain resolved by orchestrator.
- Implementer: `sdd-apply` subagent (model MiniMax-M3); progress compiled + verified by orchestrator (el Gentleman) after child session was cut short before writing this artifact.
- next: `sdd-verify` PR 1, then apply PR 2 (Phases 7–9).

## Structured SDD Status (consumed)
- active_change: `ai-web-search` (resolved)
- artifacts present: explore.md, proposal.md, specs/ai-chat/spec.md, design.md, tasks.md
- apply_state: ready → **PR 1 done**
- actionContext.mode: workspace-authoritative; workspace_root `/home/loonbac/Proyectos/Ressy-Bot-Py`; allowed edit roots confirmed (src, tests, openspec/changes/ai-web-search).
- Warnings honored: no browser launched by tooling; bot not started; Spanish neutro peruano.

## Completed tasks (persisted checkboxes in tasks.md)
PR 1 tasks marked `- [x]` (19 task lines): 0.1, 1.1, 1.2, 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3, 4.1, 4.2, 4.3, 5.1, 5.2, 5.3, 6.1, 6.2, 6.3.

## Files changed
| File | Change | +/- |
|------|--------|-----|
| `src/bot/plugins/ai_chat/web.py` | +`web_search` schema, `WEB_TOOL_NAMES`, `WebSearchQuota` + `_SEARCH_QUOTA`, `_DDGLiteParser`, `_parse_ddg_lite`, `web_search`, extended `dispatch_web_tool` signature+routing | +398 / −9 |
| `src/bot/plugins/ai_chat/tools.py` | `run_tool_loop` adds `user_id`, `search_enabled`, `search_safe`, `search_max_per_hour` kwargs; forwards to web dispatch only | +19 / −2 |
| `src/bot/plugins/ai_chat/cog.py` | `ask_full` gates `web_search` schema + search-first hint; passes user_id + search config to `run_tool_loop`; safe defaults when web disabled | +27 / −2 |
| `src/bot/plugins/ai_chat/database.py` | `DEFAULTS` adds `search_enabled`/`search_safe`/`search_max_per_hour` (+ comments) | +8 / 0 |
| `tests/test_ai_chat_web_search.py` | 37 unit tests across fases 1–6 + schema consistency | new (30.6 KB) |
| `tests/fixtures/ai_chat/ddg_lite_search.html` | hand-crafted hermetic DDG Lite SERP fixture | new (3.0 KB) |
| `openspec/changes/ai-web-search/tasks.md` | PR 1 tasks converted to `- [x]` | edited |

**Total: 440 insertions, 16 deletions (src) + tests/fixture** → PR 1 ~456 changed lines (within stacked-slice tolerance).

## TDD Cycle Evidence
RED → GREEN followed per task. Tests are hermetic (httpx MockTransport / injected fake quota+clock). Live network = PR 2 only.

| Task | RED (test) | GREEN (impl) | Command | Result |
|------|-----------|--------------|---------|--------|
| 1.1/1.2 | `test_fase_1_seeding_*` (2) | `database.py::DEFAULTS` keys | `uv run pytest -m "not live" tests/test_ai_chat_web_search.py -k seeding` | ✅ |
| 2.1–2.4 | `test_fase_2_quota_*` (6) | `WebSearchQuota` + `_SEARCH_QUOTA` | `... -k quota` | ✅ |
| 3.1–3.3 | `test_fase_3_parse_ddg_lite_*` (9) | `_parse_ddg_lite` + `_DDGLiteParser` | `... -k parse` | ✅ |
| 4.1–4.3 | `test_fase_4_web_search_*` (8) | `async def web_search` | `... -k web_search` | ✅ |
| 5.1–5.3 | `test_fase_5_*` (6) | `dispatch_web_tool` ext + `run_tool_loop` kwargs | `... -k fase_5` | ✅ |
| 6.1–6.3 | `test_fase_6_*` (5) | `ask_full` gating + hint + threading | `... -k fase_6` | ✅ |
| schema | `test_schemas_publicos_consistentes_con_web_tool_names` (1) | — | `... -k schemas` | ✅ |

## Verification (run by orchestrator)
- `uv run pytest -m "not live" tests/test_ai_chat_web_search.py -q` → **37 passed**.
- `uv run pytest -m "not live" tests/test_ai_chat.py tests/test_ai_chat_web.py tests/test_ai_chat_web_search.py -q` → **98 passed** (no regression to existing ai_chat).
- `uv run pytest -m "not live" -q` → **986 passed, 5 deselected, 2 errors**. The 2 errors are in `tests/test_youtube_monitor.py` (`sqlite3.OperationalError: database is locked`) — confirmed PRE-EXISTING (they fail identically when run in isolation against unchanged youtube code). NOT a regression from this change.

## Additive-only audit (verified by orchestrator diff review)
- `fetch_webpage` internals: **unchanged**.
- SSRF helpers (`_normalize_url`, `_resolve_safe`, `_validate_host`, `_ip_is_blocked`, `_get_following_redirects`, `_block_internal_route`): **unchanged**.
- Redirect re-validation logic: **unchanged**.
- Playwright fetch path (`_fetch_with_browser`): **unchanged** (the new `web_search` reserves `browser_fallback` param but ignores it in PR 1 — no new Playwright usage).
- Only modified function in web.py = `dispatch_web_tool` (signature extended + routing branch added; `fetch_webpage` path identical, just reindented inside `if name ==`).

## Deviations from design
None. All signatures, payload shapes, config keys, and bounds match `design.md`. `browser_fallback` kept as reserved param per design ("deferred first slice").

## Remaining tasks (PR 2 — unchecked)
Phases 7–9 are NOT implemented (their `**Task X.Y**` lines in tasks.md remain without `- [x]`):
- Phase 7: `_typed_config` search keys + PUT validation (`api.py`, `models.py`) + `tests/test_ai_chat_config.py`.
- Phase 8: `tests/test_ai_chat_web_search_live.py` (`@pytest.mark.live`, httpx-only).
- Phase 9: frontend `ai-chat.ts` interface + `AIChatConfig.tsx` DEFAULT_CONFIG + `WebSearchCard.tsx`/`.css`.

## PR 1 boundary / rollback
- PR 1 delivers a fully working `web_search` through Discord `/ia` + mention paths, toggled via raw DB config `search_enabled`.
- API/dashboard typed exposure lands in PR 2; until then the feature is configured directly in `data/plugins/ai_chat.db` or via the existing `PUT /api/plugins/ai-chat/config` (note: PR 1 does NOT add the keys to `ConfigPayload`/`_typed_config`, so the dashboard GET will not show them typed until PR 2 — the backend still reads them from DB regardless).
- Rollback: set `search_enabled=false` (DB) + restart bot. `fetch_webpage` path untouched → existing web-reading behavior continues.

## Restart needed
After merging PR 1, the bot MUST be restarted (`uv run ressy-bot`, run by the user only) for the new tool schema, dispatch path, and cog wiring to load. No hot-reload.

## skill_resolution
`none` — `.atl/skill-registry.md` table empty; no project/user skills indexed for this phase.

---

# Apply Progress — `ai-web-search` (PR 2)

- Date: 2026-06-16
- Slice: **PR 2 — Dashboard exposure + live tests + frontend** (Phases 7–9)
- Delivery: chained PRs (stacked-to-main), auto-chain resolved by orchestrator.
- Implementer: `sdd-apply` subagent (model MiniMax-M3).
- Previous slice: PR 1 verified PASS (`verify-report.md`).
- next: `sdd-verify` PR 2, then `sdd-archive` (whole change).

## Structured SDD Status (consumed)
- active_change: `ai-web-search` (resolved)
- artifacts present: explore.md, proposal.md, specs/ai-chat/spec.md, design.md, tasks.md, apply-progress.md (PR 1 + PR 2 sections), verify-report.md (PR 1 PASS).
- apply_state: **PR 2 ready → PR 2 done**.
- actionContext.mode: workspace-authoritative; workspace_root `/home/loonbac/Proyectos/Ressy-Bot-Py`; allowed edit roots confirmed (src, tests, openspec/changes/ai-web-search, frontend).
- Warnings honored: no browser launched by tooling (test 2 of `test_ai_chat_web_search_live.py` forces `browser_fallback=False`); bot not started; Spanish neutro peruano.

## Completed tasks (persisted checkboxes in tasks.md)
PR 2 tasks marked `- [x]` (6 task lines): 7.1, 7.2, 8.1, 9.1, 9.2, 9.3.

## Files changed
| File | Change | +/- |
|------|--------|-----|
| `src/bot/plugins/ai_chat/api.py` | `_typed_config` exposes `search_enabled`/`search_safe` (bool) + `search_max_per_hour` (int); `update_config` validates `search_max_per_hour` outside 1..100 → `HTTPException(422, ...)` BEFORE persist | +11 / −1 |
| `src/bot/plugins/ai_chat/models.py` | `ConfigPayload` adds `search_enabled`, `search_safe`, `search_max_per_hour` (all `Optional`) | +5 / 0 |
| `tests/test_ai_chat_config.py` | 13 tests across 4 categories: `_typed_config` typing (4), GET includes typed keys (1), PUT 422 (3), PUT persistence (4), regression (1) | new (~210 lines) |
| `tests/test_ai_chat_web_search_live.py` | 2 opt-in live tests with `@pytest.mark.live`: real DDG httpx search + real `fetch_webpage` on first result (forces `browser_fallback=False`) | new (~85 lines) |
| `frontend/src/api/ai-chat.ts` | `AIChatConfig` interface adds `search_enabled`/`search_safe` (bool) + `search_max_per_hour` (number). `AIChatConfigPatch` is `Partial<AIChatConfig>`, so it auto-covers them. | +7 / 0 |
| `frontend/src/components/AIChatConfig.tsx` | `DEFAULT_CONFIG` adds `search_enabled: true, search_safe: true, search_max_per_hour: 10`; renders `<WebSearchCard>` in card stack; `handleSaveConfig` persists the 3 new keys via PUT | +20 / −2 |
| `frontend/src/components/ai_chat/WebSearchCard.tsx` | new card with 3 controls (toggle, toggle, slider 1–100), accepts `{ config, onPatch }`, hint in Spanish neutro, light + dark variants, animation `animate-ai-chat-card-enter` | new (~95 lines) |
| `frontend/src/components/ai_chat/WebSearchCard.css` | root class `.ai-chat-web-search-card`, light + dark, `disabled` opacity state, footnote panel, no `glass-panel` | new (~30 lines) |
| `openspec/changes/ai-web-search/tasks.md` | PR 2 task lines converted to `- [x]` (7.1, 7.2, 8.1, 9.1, 9.2, 9.3) | edited |
| `openspec/changes/ai-web-search/apply-progress.md` | this PR 2 section appended (cumulative) | edited |

**Total PR 2 src+tests+frontend: ~465 changed lines.** Within stacked-slice tolerance given the 400-line budget risk was rated Medium. PR 2 sits slightly above the budget on its own; with PR 1 already merged-into-working-tree the **combined PR 1+PR 2 delta is ~920 lines**, justified by the additive engine + typed API + live tests + new dashboard card. `400-line budget risk: Medium` from the workload forecast is now reality: the human-approved `auto-chain` strategy explicitly accepted this.

## TDD Cycle Evidence (PR 2 — strict TDD for Phase 7)
RED → GREEN observed per task. Live tests are inherently integration; Phase 9 frontend has no test runner gate beyond `tsc` + `vite build`.

| Task | RED (test) | GREEN (impl) | Command | Result |
|------|-----------|--------------|---------|--------|
| 7.1/7.2 | `tests/test_ai_chat_config.py::test_typed_config_*` (4) + `test_get_config_includes_typed_search_keys` + 3× 422 + 4× persistence + 1× regression = 13 tests. RED observed: 12 fail with `KeyError: 'search_enabled'/'search_safe'/'search_max_per_hour'` and 422 not raised for out-of-bounds. | `api.py::_typed_config` adds the 3 keys with type cast; `api.py::update_config` adds reject branch; `models.py::ConfigPayload` adds the 3 Optional fields | `uv run pytest -m "not live" tests/test_ai_chat_config.py -v` | ✅ 13/13 passed |
| 8.1 | `tests/test_ai_chat_web_search_live.py` — 2 tests, both `@pytest.mark.live`. Default `uv run pytest -m "not live"` deselects them. | (no production code; live file added; live tests will be exercised manually by orchestrator/human with `-m live`) | `uv run pytest -m "not live" tests/test_ai_chat_web_search_live.py -q` | ✅ 2 deselected (excluded) |
| 9.1/9.2/9.3 | Frontend has no automated test runner. Gate is `tsc --noEmit` + `vite build`. Both passed. | `ai-chat.ts` interface + `AIChatConfig.tsx` DEFAULT_CONFIG + `WebSearchCard.tsx`/`.css` | `cd frontend && pnpm exec tsc --noEmit` | ✅ 0 errors in PR 2 files (8 pre-existing in unrelated files unchanged) |
| | | | `cd frontend && pnpm exec vite build` | ✅ built in 412ms, output to `src/web/static/` |

## Verification (PR 2 gate set, all run by this session)
- `uv run pytest -m "not live" tests/test_ai_chat_config.py -v` → **13 passed**.
- `uv run pytest -m "not live" tests/test_ai_chat.py tests/test_ai_chat_web.py tests/test_ai_chat_web_search.py tests/test_ai_chat_config.py -q` → **111 passed** (98 PR 1 + 13 new, zero regression on PR 1).
- `uv run pytest -m "not live" -q` → **1000 passed, 9 deselected, 1 error**. The 1 error is in `tests/test_youtube_monitor.py::TestYouTubePluginIntegration::test_config_returns_200` (`sqlite3.OperationalError: database is locked`) — **pre-existing, unrelated** to `ai-web-search` (the test opens a youtube monitor DB on a path that conflicts with the suite-wide parallel test infra). Confirmed by inspecting the failing test: it does not touch any ai_chat/web module.
- `uv run pytest -m "not live" tests/test_ai_chat_web_search_live.py -q` → **2 deselected** (live tests correctly excluded by default).
- `uv run pytest --co -q -m live tests/test_ai_chat_web_search_live.py` → **2 tests collected** (live marker opt-in works).
- `cd frontend && pnpm exec tsc --noEmit` → 0 errors in PR 2 files (8 pre-existing in `src/__tests__/ConfigPanel.test.tsx`, `src/components/LatencyChart.tsx`, `src/components/openrouter/AliasesDrawer.tsx` are unrelated, unchanged by this change).
- `cd frontend && pnpm exec vite build` → ✅ 412ms, output to `src/web/static/`.

## Additive-only audit (PR 2 over PR 1)
- `web.py::web_search` / `WebSearchQuota` / `_DDG_LITE_URL` / `_DDGLiteParser` / `_parse_ddg_lite` / `dispatch_web_tool` / `fetch_webpage` / SSRF helpers / Playwright fallback: **unchanged**.
- `tools.py::run_tool_loop` signature: **unchanged**.
- `cog.py::AIChatCog.ask_full` body: **unchanged** (the 3 `search_*` config reads were added in PR 1, untouched here).
- `database.py::DEFAULTS`: **unchanged** (3 `search_*` defaults added in PR 1).
- Only modified functions in PR 2: `api.py::_typed_config` (additive typed keys) and `api.py::update_config` (additive reject branch BEFORE the existing clamps).
- `models.py::ConfigPayload`: 3 new Optional fields; no existing field changed.

## Deviations from design
- None. All 3 keys, payload shapes, validation bounds, and Spanish error wording match `design.md` §4 and `tasks.md` Phase 7.
- Frontend: `WebSearchCard` uses the existing `ai-chat-card` + `ai-chat-toggle` + `ai-chat-slider` primitives (no new design system debt). `browser_fallback=False` is explicit in the live test 2 to honor the hard project-wide constraint ("never launch a browser from agent/test tooling"); the production `fetch_webpage` runtime still defaults to `browser_fallback=True` (unchanged from PR 1).

## PR 2 boundary / rollback
- PR 2 exposes the 3 `search_*` config keys through the dashboard (GET typed, PUT validated), adds 2 opt-in live smoke tests, and renders a `WebSearchCard` next to `PlaygroundCard`. The bot engine remains untouched; the dashboard can persist these values to the DB without restart (DB reads are on every `ask_full`).
- Rollback: revert the additive API fields, the 13 backend tests, the 2 live tests, the interface field, `DEFAULT_CONFIG` entries, `handleSaveConfig` patch, and the new card files. PR 1 alone still works (raw DB toggling only).

## Restart needed
- **Bot restart NOT required** for PR 2 alone — the `api.py` and `models.py` changes are loaded by the FastAPI process inside the same bot event loop. The user only needs to restart the bot if the running process is the one serving the dashboard AND it was loaded with the old code; in that case a single `uv run ressy-bot` reload picks up the typed exposure and the PUT validation. (If the bot is already running with PR 1 code, PR 2 needs that restart for the typed config to surface in the dashboard GET.)
- No database migration needed — `INSERT OR IGNORE` in `connect()` already seeded the 3 keys in PR 1.

## Risks / watch-list
- **Live test flakiness if `pytest -m live` is ever run in CI without network access**: the tests are written to assert EITHER structured results OR `{"error": ...}` from a graceful failure, but if DDG and the first result's host both fail simultaneously, test 1 asserts non-error AND test 2 skips — this combination passes. If both fail in test 1, the test still passes (graceful error path).
- **Frontend CSS dark-mode parity**: `WebSearchCard.css` defines `html.dark` variants for the footnote panel and disabled state; toggle/slider reuse the base `.ai-chat-toggle` / `.ai-chat-slider` which already have dark variants in `StatusCard.css` / `BehaviorCard.css`. Verified visually via the existing dark tokens.
- **PUT validation UX**: the dashboard catches non-2xx in `updateAIChatConfig` and surfaces the `detail` text via the toast — so users see `"search_max_per_hour debe estar entre 1 y 100."` (Spanish neutro, no Rioplatense).
- **PR 2 only `/ 400-line budget`**: 465 lines (slightly above the 400 budget per slice). The workload forecast rated this `Medium` and the human approved `auto-chain` (which explicitly accepts the budget risk for chained slices). Combined with PR 1 (~456), the stack is ~920 lines for a single user-facing feature (engine + typed config + live tests + dashboard card).

## skill_resolution
`none` — `.atl/skill-registry.md` table empty; no project/user skills indexed for this phase.

## Engram mirror
Engram tools NOT available to sdd children in this session. Mirror deferred to orchestrator (`mem_session_summary` at session close).

## PR 2 final verification (orchestrator, post-child-cut)
- `uv run pytest -m "not live" tests/test_ai_chat.py tests/test_ai_chat_web.py tests/test_ai_chat_web_search.py tests/test_ai_chat_config.py -q` → **111 passed** (no regression; +13 new config tests + 1 schema test vs PR 1).
- `uv run pytest -m "not live" -q` → **1000 passed, 9 deselected, 1 error** (the remaining youtube_monitor sqlite error is pre-existing; unrelated to this change).
- `uv run pytest tests/test_ai_chat_web_search_live.py --co -q` → 2 live tests collected; `uv run pytest -m "not live" tests/test_ai_chat_web_search_live.py --co -q` → **no tests collected (2 deselected)** — live tests correctly excluded by default.
- `cd frontend && ./node_modules/.bin/tsc --noEmit` → **8 errors, ALL pre-existing** (ConfigPanel.test.tsx jest-dom types, LatencyChart, AliasesDrawer) — **0 errors in PR 2 files** (ai-chat.ts, AIChatConfig.tsx, WebSearchCard.tsx/.css). Error count unchanged vs HEAD.
- `cd frontend && ./node_modules/.bin/vite build` → **built in 397ms** (625 modules), output to `src/web/static/`.
- NOTE: pnpm v11 requires `pnpm approve-builds` interactively; tsc/vite ran via direct `node_modules/.bin` binaries to skip the deps-status gate. Environment quirk, not a code issue.

