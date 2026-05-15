# Proposal: cleanup-scheduler-coverage

## Intent

Raise `src/bot/plugins/openrouter_prices/scheduler.py` test coverage from **66%** to **≥80%** by adding a new focused test file (`tests/test_openrouter_ranking_scheduler_coverage.py`) with ~22 tests that exercise the five uncovered code areas identified during exploration. Strict TDD (RED → GREEN → TRIANGULATE → REFACTOR) is active per `openspec/config.yaml`.

## Scope

### In scope

- **One new test file**: `tests/test_openrouter_ranking_scheduler_coverage.py` (~280 lines, 22 tests)
- Coverage of 6 gap areas in `scheduler.py`:
  1. `is_scraping()` — true/false branches (2 tests)
  2. `trigger_scrape()` inner `_run()` — dispatch, conflict, exception cleanup (5 tests)
  3. `_tick_loop()` — error survival, `TimeoutError` break, stop-event exit (3 tests)
  4. `_run_job_if_due()` — disabled skip, within-interval skip, past-interval run (3 tests)
  5. `_job_weekly_report()` — no channel, disabled, invalid count, success/failure publish (5 tests)
  6. `_job_ranking_embed()` — disabled, JSON decode fallback, empty phases fallback, publish failure (4 tests)
- All fixtures reused from `tests/test_openrouter_ranking_scheduler.py` (no conftest changes)

### Out of scope (non-goals)

- No changes to `scheduler.py` source code (unless a bug is found during RED phase, which would be a separate discovery)
- No changes to existing test files or fixtures
- No frontend, API, or integration work requiring a live bot
- No coverage of already-covered lines (no redundant tests)

## Affected Areas

| File                                                  | Change                                      |
| ----------------------------------------------------- | ------------------------------------------- |
| `tests/test_openrouter_ranking_scheduler_coverage.py` | **New** — 22 tests across 6 test classes    |
| `src/bot/plugins/openrouter_prices/scheduler.py`      | Read-only reference (no edits planned)      |
| `tests/test_openrouter_ranking_scheduler.py`          | Read-only (fixtures imported, not modified) |
| `tests/conftest.py`                                   | No changes needed                           |

## Risks

| Risk                                                                                    | Level | Mitigation                                                                                           |
| --------------------------------------------------------------------------------------- | ----- | ---------------------------------------------------------------------------------------------------- |
| `_tick_loop` mock complexity — `asyncio.wait_for` must be replaced to avoid 60s timeout | LOW   | Stateful mock with explicit call counter; 3 focused tests with deterministic ordering                |
| `_job_weekly_report` DB seed — `upsert_models` must produce correct columns             | LOW   | Verified: `_make_db_model` helper format matches `upsert_models` expectations; uses real DB, no mock |
| Function-local import patching — `build_ranking_embed` is imported inside the job body  | LOW   | Patch at source module (`discord_embeds.build_ranking_embed`), not at scheduler namespace            |
| `push_event` fire-and-forget — lazy `ActivityLog` singleton creation                    | NONE  | `get_log()` never crashes in tests; assertions optional (main checks are on `embed_publisher`)       |
| Existing test breakage                                                                  | NONE  | New file is isolated; no shared state mutation beyond existing fixtures                              |

**Review workload**: ~280 lines in a single new file. Well within safe review limits.

## Rollback

Trivial: delete `tests/test_openrouter_ranking_scheduler_coverage.py`. No source files are modified, no database migrations, no config changes. Existing 20 tests in `test_openrouter_ranking_scheduler.py` remain unaffected.

## Success Criteria

1. **Coverage threshold**: `scheduler.py` coverage ≥80% (projected ~96% based on exploration analysis of ~51 statements and ~23 branches newly exercised)
2. **All tests pass**: `uv run pytest tests/test_openrouter_ranking_scheduler_coverage.py` — 22 tests, 0 failures
3. **No regressions**: `uv run pytest tests/test_openrouter_ranking_scheduler.py` — 20 existing tests still pass
4. **Strict TDD followed**: Each test written RED first, then GREEN implementation, with triangulation where applicable
5. **No scheduler.py edits**: Source file remains unchanged (unless a genuine bug is discovered during RED phase, which triggers a separate decision point)

## Coverage Projection

| Gap Area                        | Lines Targeted         | New Tests | Est. Contribution           |
| ------------------------------- | ---------------------- | --------- | --------------------------- |
| `is_scraping`                   | 105                    | 2         | +1 stmt, +1 branch          |
| `trigger_scrape` inner `_run()` | 113–141                | 5         | +12 stmts, +5 branches      |
| `_tick_loop`                    | 149–161                | 3         | +8 stmts, +3 branches       |
| `_run_job_if_due`               | 208, 219, 221          | 3         | +4 stmts, +2 branches       |
| `_job_weekly_report`            | 294–334                | 5         | +20 stmts, +8 branches      |
| `_job_ranking_embed` gaps       | 350, 363–364, 368, 412 | 4         | +6 stmts, +4 branches       |
| **Total**                       | —                      | **22**    | **~51 stmts, ~23 branches** |

Baseline: 110/167 statements (66%). Projected: ~161/167 (~96%).
