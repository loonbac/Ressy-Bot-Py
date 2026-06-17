# sdd-apply — `ai-web-search` PR 2 output

- Date: 2026-06-16
- Phase: **apply**
- Change: `ai-web-search`
- Slice: **PR 2 — Dashboard exposure + live tests + frontend** (Phases 7–9)
- Delivery: chained PRs (stacked-to-main), auto-chain resolved by orchestrator.
- Status: **PR 2 done; ready for `sdd-verify` PR 2 → `sdd-archive` whole change**.

## Executive summary

PR 2 (Phases 7–9) is implemented end-to-end:

- **Phase 7 — API/model typed exposure + PUT validation**: `api.py::_typed_config`
  exposes the 3 `search_*` keys as `bool` / `bool` / `int`; `api.py::update_config`
  rejects `search_max_per_hour` outside 1..100 with `HTTPException(422,
  detail="search_max_per_hour debe estar entre 1 y 100.")` BEFORE any persist;
  `models.py::ConfigPayload` adds the 3 Optional fields.
- **Phase 8 — Opt-in live tests**: `tests/test_ai_chat_web_search_live.py` with 2
  tests, both `@pytest.mark.live` (excluded by default via `addopts = "-m 'not live'"`).
  The fetch test forces `browser_fallback=False` to honor the project-wide
  "never launch a browser from agent/test tooling" constraint.
- **Phase 9 — Frontend dashboard**: `AIChatConfig` interface gains the 3 keys;
  `AIChatConfig.tsx` `DEFAULT_CONFIG` initialized to `true / true / 10`; new
  `WebSearchCard.tsx` + `WebSearchCard.css` (light + dark, modular, with
  `animate-ai-chat-card-enter` animation, no `glass-panel`) renders in the card
  stack next to `PlaygroundCard`; the `handleSaveConfig` payload includes the
  3 new keys so the dashboard persists them via PUT.

TDD cycle (Phase 7) observed RED → GREEN: 12 of 13 new tests failed RED with
`KeyError: 'search_enabled'/'search_safe'/'search_max_per_hour'` (and 422 not
raised for out-of-bounds), then all 13 passed after the implementation.

## Status (structured envelope)

```json
{
  "schemaName": "gentle-pi.sdd-status",
  "schemaVersion": 1,
  "changeName": "ai-web-search",
  "artifactStore": "openspec",
  "planningHome": {
    "root": "/home/loonbac/Proyectos/Ressy-Bot-Py",
    "changesDir": "/home/loonbac/Proyectos/Ressy-Bot-Py/openspec/changes"
  },
  "changeRoot": "/home/loonbac/Proyectos/Ressy-Bot-Py/openspec/changes/ai-web-search",
  "artifactPaths": {
    "proposal": ["/home/loonbac/Proyectos/Ressy-Bot-Py/openspec/changes/ai-web-search/proposal.md"],
    "specs": ["/home/loonbac/Proyectos/Ressy-Bot-Py/openspec/changes/ai-web-search/specs/ai-chat/spec.md"],
    "design": ["/home/loonbac/Proyectos/Ressy-Bot-Py/openspec/changes/ai-web-search/design.md"],
    "tasks": ["/home/loonbac/Proyectos/Ressy-Bot-Py/openspec/changes/ai-web-search/tasks.md"],
    "applyProgress": ["/home/loonbac/Proyectos/Ressy-Bot-Py/openspec/changes/ai-web-search/apply-progress.md"],
    "verifyReport": ["/home/loonbac/Proyectos/Ressy-Bot-Py/openspec/changes/ai-web-search/verify-report.md"]
  },
  "artifacts": {
    "proposal": "present",
    "specs": "present",
    "design": "present",
    "tasks": "present",
    "applyProgress": "present",
    "verifyReport": "present (PR 1 PASS)",
    "syncReport": "missing"
  },
  "taskProgress": {
    "total": 25,
    "complete": 25,
    "remaining": 0,
    "unchecked": []
  },
  "applyState": "PR 2 done; ready for sdd-verify PR 2",
  "dependencies": {
    "apply": "satisfied",
    "verify": "ready",
    "sync": "pending",
    "archive": "pending"
  },
  "actionContext": {
    "mode": "workspace-authoritative",
    "workspaceRoot": "/home/loonbac/Proyectos/Ressy-Bot-Py",
    "allowedEditRoots": [
      "/home/loonbac/Proyectos/Ressy-Bot-Py/src",
      "/home/loonbac/Proyectos/Ressy-Bot-Py/tests",
      "/home/loonbac/Proyectos/Ressy-Bot-Py/frontend",
      "/home/loonbac/Proyectos/Ressy-Bot-Py/openspec/changes/ai-web-search"
    ],
    "warnings": []
  }
}
```

## Artifacts (paths + changed files)

- Apply-progress updated: `openspec/changes/ai-web-search/apply-progress.md`
  (PR 1 section preserved + PR 2 section appended cumulatively).
- Tasks marked complete: `openspec/changes/ai-web-search/tasks.md`
  (Phases 7/8/9 tasks 7.1, 7.2, 8.1, 9.1, 9.2, 9.3 converted to `- [x]`).

| File | Kind | Status |
|------|------|--------|
| `src/bot/plugins/ai_chat/api.py` | edited | +11/−1 (typed exposure + reject branch) |
| `src/bot/plugins/ai_chat/models.py` | edited | +5 (3 Optional fields on `ConfigPayload`) |
| `tests/test_ai_chat_config.py` | new | 13 tests (Phase 7) |
| `tests/test_ai_chat_web_search_live.py` | new | 2 live tests (Phase 8) |
| `frontend/src/api/ai-chat.ts` | edited | +7 (3 fields on `AIChatConfig`) |
| `frontend/src/components/AIChatConfig.tsx` | edited | +20/−2 (DEFAULT_CONFIG, render card, persist patch) |
| `frontend/src/components/ai_chat/WebSearchCard.tsx` | new | full card with 3 controls |
| `frontend/src/components/ai_chat/WebSearchCard.css` | new | light + dark, no `glass-panel` |
| `openspec/changes/ai-web-search/tasks.md` | edited | 6 PR 2 task lines → `- [x]` |
| `openspec/changes/ai-web-search/apply-progress.md` | edited | PR 2 section appended |

**No git commit was made (per orchestrator constraint).**

## Verification gates (run by this session)

| Gate | Command | Result |
|------|---------|--------|
| 1. PR 2 config tests | `uv run pytest -m "not live" tests/test_ai_chat_config.py -q` | **13 passed** in 0.28s |
| 2. PR 1 + PR 2 ai_chat no-regression | `uv run pytest -m "not live" tests/test_ai_chat.py tests/test_ai_chat_web.py tests/test_ai_chat_web_search.py tests/test_ai_chat_config.py -q` | **111 passed** in 2.99s (98 PR 1 + 13 new) |
| 3. Live tests excluded by default | `uv run pytest -m "not live" tests/test_ai_chat_web_search_live.py -q` | **2 deselected** (correctly excluded) |
| 4. Live tests opt-in collection | `uv run pytest --co -q -m live tests/test_ai_chat_web_search_live.py` | **2 tests collected** |
| 5. Full suite (no `-m live`) | `uv run pytest -m "not live" -q` | **1000 passed, 9 deselected, 1 error** — the 1 error is `tests/test_youtube_monitor.py::TestYouTubePluginIntegration::test_config_returns_200` (`sqlite3.OperationalError: database is locked`); pre-existing, unrelated to `ai-web-search` (the test does not touch any ai_chat/web module) |
| 6. tsc check (PR 2 files) | `cd frontend && pnpm exec tsc --noEmit` filtered to PR 2 files | **0 errors** in PR 2 files (8 pre-existing errors in `src/__tests__/ConfigPanel.test.tsx`, `src/components/LatencyChart.tsx`, `src/components/openrouter/AliasesDrawer.tsx` are unrelated and unchanged) |
| 7. vite build | `cd frontend && pnpm exec vite build` | **✓ built in 433ms**, output to `src/web/static/` |

## RED → GREEN evidence (Phase 7 strict TDD)

- **RED**: 12 of 13 new tests failed with `KeyError: 'search_enabled'` (and
  analogous for `search_safe` / `search_max_per_hour`) and 3 PUT validation
  tests did not raise `HTTPException(422, ...)` because the validation branch
  did not exist in `update_config`. The 13th test (regression: existing
  `context_token_budget` clamp still works) passed even in RED.
- **GREEN**: After implementing the additive typed exposure in `_typed_config`
  and the reject branch in `update_config`, all 13 tests pass.
- Test name index for the 13 new tests:
  1. `test_typed_config_includes_search_enabled_as_bool`
  2. `test_typed_config_includes_search_safe_as_bool`
  3. `test_typed_config_includes_search_max_per_hour_as_int`
  4. `test_typed_config_search_keys_default_when_missing_from_raw`
  5. `test_get_config_includes_typed_search_keys`
  6. `test_put_config_rejects_search_max_per_hour_zero`
  7. `test_put_config_rejects_search_max_per_hour_too_high`
  8. `test_put_config_rejects_search_max_per_hour_negative`
  9. `test_put_config_persists_search_max_per_hour_25`
  10. `test_put_config_persists_search_enabled_false`
  11. `test_put_config_persists_search_safe_false`
  12. `test_put_config_search_boundary_values_accepted`
  13. `test_put_config_other_fields_still_clamped` (regression)

## Next recommended

- `sdd-verify PR 2`: re-run the gate set, then write a fresh
  `verify-report-pr2.md` next to `verify-report.md`. On PASS, the
  orchestrator can proceed to `sdd-sync` and `sdd-archive` the whole
  `ai-web-search` change (PR 1 + PR 2 stacked-to-main).
- **Bot restart needed** for the dashboard to surface the typed config
  (the FastAPI app loads `api.py` at startup). User only; not started by this
  session. PR 1 already required a restart for the engine; a single restart
  after both PRs are merged is enough.

## Risks / watch-list

- **Live test flakiness if `pytest -m live` is run in CI without network**:
  both tests assert EITHER structured results OR a graceful `{"error": ...}`;
  test 2 `pytest.skip`s if test 1 found no results, so even a fully-blocked
  environment passes.
- **Frontend CSS dark-mode parity**: `WebSearchCard.css` defines `html.dark`
  variants for the footnote panel and `--disabled` state; toggle/slider reuse
  the existing `.ai-chat-toggle` / `.ai-chat-slider` primitives which already
  have dark variants in `StatusCard.css` / `BehaviorCard.css`.
- **PUT validation UX**: `updateAIChatConfig` in `frontend/src/api/ai-chat.ts`
  catches non-2xx responses and surfaces the `detail` field via the toast
  (Spanish neutro, no Rioplatense imperatives).
- **PR 2 line budget**: ~465 changed lines (slightly above the 400 budget per
  slice). Workload forecast rated this `Medium` and the human approved
  `auto-chain`, which explicitly accepts the budget risk for chained slices.
  Combined with PR 1 (~456) the stack is ~920 lines, which is justified by
  one user-facing feature (engine + typed config + live tests + new card).
- **Pre-existing `tsc` errors**: 8 errors in unrelated files
  (`ConfigPanel.test.tsx`, `LatencyChart.tsx`, `openrouter/AliasesDrawer.tsx`)
  are not introduced by this change. They were present before PR 2 and remain
  unchanged. PR 2 files typecheck clean.
- **Pre-existing `youtube_monitor` sqlite lock error**: 1 error in
  `test_youtube_monitor.py::TestYouTubePluginIntegration::test_config_returns_200`
  is unrelated to `ai-web-search` and was documented as acceptable in the
  spec.

## skill_resolution

`none` — `.atl/skill-registry.md` table empty; no project/user skills indexed
for this phase.

## Engram mirror

Engram tools NOT available to sdd children in this session. Mirror deferred
to orchestrator (`mem_session_summary` at session close).
