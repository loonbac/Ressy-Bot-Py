# Tasks: cleanup-scheduler-coverage

**Change ID:** cleanup-scheduler-coverage
**Phase:** Tasks
**Date:** 2026-05-14
**Preceding artifacts:** `proposal.md`, `specs/delta-spec.md`, `design.md`
**Target:** `tests/test_openrouter_ranking_scheduler_coverage.py` (new file, ~280 lines)
**Strict TDD:** Active per `openspec/config.yaml`

---

## Review Workload Forecast

| Field                   | Value                       |
| ----------------------- | --------------------------- |
| Estimated changed lines | ~280 (single new test file) |
| 400-line budget risk    | Low                         |
| Chained PRs recommended | No                          |
| Suggested split         | Single PR                   |
| Delivery strategy       | single-pr                   |
| Chain strategy          | size-exception              |

```text
Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: size-exception
400-line budget risk: Low
```

---

## Summary

One new file: `tests/test_openrouter_ranking_scheduler_coverage.py`. 22 test methods across 6 classes. No source code changes to `scheduler.py`. Strict RED → GREEN for each test class.

**Fixture strategy:** Import `Counter`, `_make_db_model`, `_ok_result`, `_error_result`, and `_make_scheduler` from `tests/test_openrouter_ranking_scheduler.py`. No conftest changes.

**Patch targets (function-local imports):**

- `src.web.routes.activity.push_event`
- `src.bot.plugins.openrouter_prices.discord_embeds.build_weekly_price_embed`
- `src.bot.plugins.openrouter_prices.discord_embeds.build_ranking_embed`
- `src.bot.plugins.openrouter_prices.ranking.compute_ranking_for_phase`

---

## Task 1 — Create file with imports and test class stubs

**File:** `tests/test_openrouter_ranking_scheduler_coverage.py`

**Action:** Create the file with:

- Module docstring referencing change ID
- Imports: `pytest`, `asyncio`, `unittest.mock.{patch, MagicMock, AsyncMock}`
- Fixture imports from `tests.test_openrouter_ranking_scheduler`: `Counter`, `_make_db_model`, `_ok_result`, `_error_result`, `_make_scheduler`
- 6 empty test classes: `TestIsScraping`, `TestTriggerScrape`, `TestTickLoop`, `TestRunJobIfDue`, `TestJobWeeklyReport`, `TestJobRankingEmbed`
- `@pytest.mark.asyncio` on all test methods, `@pytest.mark.timeout(5)` on tick/loop tests

**Verify:** `uv run pytest tests/test_openrouter_ranking_scheduler_coverage.py --collect-only` — 0 collected (all stubs).

**TDD:** N/A (scaffold only).

---

## Task 2 — TestIsScraping (2 tests)

**Lines targeted:** `scheduler.py:105`
**Covers:** `is_scraping()` true/false branches

| #   | Method                           | Setup                               | Assertion                            |
| --- | -------------------------------- | ----------------------------------- | ------------------------------------ |
| 1   | `test_is_scraping_returns_true`  | `sched._active_scrapes.add("bfcl")` | `sched.is_scraping("bfcl") == True`  |
| 2   | `test_is_scraping_returns_false` | Empty `_active_scrapes`             | `sched.is_scraping("bfcl") == False` |

**TDD — RED:**

1. Write both tests.
2. Run `uv run pytest tests/test_openrouter_ranking_scheduler_coverage.py::TestIsScraping -v`.
3. Confirm: 2 passed (tests exercise existing code; RED is verified by confirming assertions fail with wrong setup).

**TDD — GREEN:**

1. Re-run — all pass. No source changes needed.

**Verify:** `uv run pytest tests/test_openrouter_ranking_scheduler_coverage.py::TestIsScraping -v` — 2 passed.

---

## Task 3 — TestTriggerScrape (5 tests)

**Lines targeted:** `scheduler.py:105, 113–141`
**Covers:** Conflict return, bfcl/aa/openrouter dispatch, exception cleanup + push_event

| #   | Method                                       | Setup                                                           | Assertion                                                  |
| --- | -------------------------------------------- | --------------------------------------------------------------- | ---------------------------------------------------------- |
| 1   | `test_trigger_scrape_conflict_returns_false` | Add "bfcl" to `_active_scrapes`                                 | Returns `False`; no scrape call                            |
| 2   | `test_trigger_scrape_bfcl_dispatches`        | `trigger_scrape("bfcl")`, `sleep(0.1)`                          | `bfcl_scraper.scrape` called; `_active_scrapes` cleaned    |
| 3   | `test_trigger_scrape_aa_dispatches`          | `trigger_scrape("aa")`, `sleep(0.1)`                            | `aa_scraper.scrape` called                                 |
| 4   | `test_trigger_scrape_openrouter_dispatches`  | `trigger_scrape("openrouter")`, `sleep(0.1)`                    | `mock_client.fetch_models` called                          |
| 5   | `test_trigger_scrape_exception_pushes_event` | `bfcl_scraper.scrape` raises `RuntimeError`; patch `push_event` | `push_event` called; `_active_scrapes` empty after cleanup |

**Key details:**

- Tests 2–4: `await asyncio.sleep(0.1)` after `trigger_scrape` to let inner task execute.
- Test 5: Patch at `src.web.routes.activity.push_event`. Increase sleep to `0.2`.

**TDD — RED:**

1. Write all 5 tests.
2. Run `uv run pytest tests/test_openrouter_ranking_scheduler_coverage.py::TestTriggerScrape -v`.
3. Confirm all 5 execute (may pass immediately since they test existing code).

**TDD — GREEN:**

1. Re-run — all pass.

**Verify:** `uv run pytest tests/test_openrouter_ranking_scheduler_coverage.py::TestTriggerScrape -v` — 5 passed.

---

## Task 4 — TestTickLoop (3 tests)

**Lines targeted:** `scheduler.py:149–161`
**Covers:** Error survival, stop-event break, timeout continue

| #   | Method                                          | Setup                                                                                                                   | Assertion                   |
| --- | ----------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- | --------------------------- |
| 1   | `test_tick_loop_continues_after_exception`      | Patch `_tick` to raise on first call then succeed; patch `asyncio.wait_for` to raise `TimeoutError` then set stop_event | `_tick` called ≥1; no crash |
| 2   | `test_tick_loop_breaks_on_stop_event`           | Patch `asyncio.wait_for` to return immediately (simulates stop)                                                         | Loop exits; `_tick` called  |
| 3   | `test_tick_loop_timeout_continues_to_next_tick` | Patch `asyncio.wait_for`: first call `TimeoutError`, second returns; `_tick = AsyncMock()`                              | `_tick.call_count >= 2`     |

**Key details:**

- All 3 tests patch `asyncio.wait_for` with a call-counting async mock to avoid 60s real timeout.
- `sched._stop_event` is set by the mock after N iterations to prevent infinite loops.
- `@pytest.mark.timeout(5)` safety net on all tests.

**TDD — RED:**

1. Write all 3 tests.
2. Run `uv run pytest tests/test_openrouter_ranking_scheduler_coverage.py::TestTickLoop -v`.
3. Confirm execution and assertions.

**TDD — GREEN:**

1. Re-run — all pass.

**Verify:** `uv run pytest tests/test_openrouter_ranking_scheduler_coverage.py::TestTickLoop -v` — 3 passed.

---

## Task 5 — TestRunJobIfDue (4 tests, 2 parametrized)

**Lines targeted:** `scheduler.py:208, 219, 221`
**Covers:** Disabled skip, within-interval skip, past-interval execution, metadata persistence

| #   | Method                                                          | Setup                                                         | Assertion                                        |
| --- | --------------------------------------------------------------- | ------------------------------------------------------------- | ------------------------------------------------ |
| 1   | `test_disabled_returns_immediately`                             | `enabled=False`                                               | `job_fn` not called                              |
| 2   | `test_interval_elapsed[param]` (4 params: 1h/24h/7d/14d)        | `metadata={}`, `now = interval + 1`                           | `job_fn` called once                             |
| 3   | `test_within_interval_skipped[param]` (4 params: 1h/24h/7d/14d) | `metadata={"last_<key>_at": str(recent)}`, advance < interval | `job_fn` not called                              |
| 4   | `test_metadata_persisted_after_success`                         | `job_fn` succeeds on scheduler with real `db`                 | `db.get_metadata()["last_<key>_at"] == str(now)` |

**Key details:**

- Tests 2–3 use `@pytest.mark.parametrize("label,interval_seconds,advance", [...], ids=[...])`.
- Tests call `sched._run_job_if_due()` directly with controlled `metadata` dict and `now` values.
- Test 4 uses `Counter(start=5_000_000)` and verifies DB-side metadata via `await db.get_metadata()`.

**TDD — RED:**

1. Write all 4 test methods (2 parametrized = 10 runtime cases).
2. Run `uv run pytest tests/test_openrouter_ranking_scheduler_coverage.py::TestRunJobIfDue -v`.
3. Confirm execution.

**TDD — GREEN:**

1. Re-run — all pass.

**Verify:** `uv run pytest tests/test_openrouter_ranking_scheduler_coverage.py::TestRunJobIfDue -v` — 10 passed.

---

## Task 6 — TestJobWeeklyReport (5 tests)

**Lines targeted:** `scheduler.py:288–334`
**Covers:** No channel, disabled, invalid count, success, failure

| #   | Method                                     | Setup                                                     | Assertion                                                               |
| --- | ------------------------------------------ | --------------------------------------------------------- | ----------------------------------------------------------------------- |
| 1   | `test_no_channel_configured_pushes_event`  | `channel_id=""`, `enabled="true"`                         | `push_event` with "Sin canal configurado"; `embed_publisher` not called |
| 2   | `test_disabled_returns_early`              | `enabled="false"`, channel set                            | `embed_publisher` not called                                            |
| 3   | `test_invalid_count_defaults_to_10`        | `count="abc"`, seeded DB                                  | `list_models` called (implicitly limit=10)                              |
| 4   | `test_successful_publish_pushes_event`     | Valid config, seeded DB, `embed_publisher` returns `True` | `embed_publisher` called; `push_event` title contains "enviado"         |
| 5   | `test_failed_publish_pushes_failure_event` | `embed_publisher` returns `False`                         | `push_event` title contains "fallo"                                     |

**Key details:**

- All tests patch `src.web.routes.activity.push_event`.
- Tests 3–5 also patch `src.bot.plugins.openrouter_prices.discord_embeds.build_weekly_price_embed`.
- Tests 4–5 seed DB with `_make_db_model` via `db.upsert_models()`.

**TDD — RED:**

1. Write all 5 tests.
2. Run `uv run pytest tests/test_openrouter_ranking_scheduler_coverage.py::TestJobWeeklyReport -v`.
3. Confirm execution and assertions.

**TDD — GREEN:**

1. Re-run — all pass.

**Verify:** `uv run pytest tests/test_openrouter_ranking_scheduler_coverage.py::TestJobWeeklyReport -v` — 5 passed.

---

## Task 7 — TestJobRankingEmbed (4 tests)

**Lines targeted:** `scheduler.py:350, 363–364, 368, 412`
**Covers:** Disabled, empty phases fallback, JSON decode fallback, publish failure

| #   | Method                                        | Setup                                                         | Assertion                                                      |
| --- | --------------------------------------------- | ------------------------------------------------------------- | -------------------------------------------------------------- |
| 1   | `test_disabled_returns_early`                 | `ranking_embed_enabled="false"`                               | `embed_publisher` not called                                   |
| 2   | `test_empty_phases_fallback_to_ranking_phase` | `phases_enabled=""`, `ranking_phase="custom_phase"`           | `compute_ranking_for_phase` called with `phase="custom_phase"` |
| 3   | `test_json_decode_error_fallback`             | `phases_enabled="{invalid"`                                   | Falls back to `[config.get("ranking_phase", "orchestrator")]`  |
| 4   | `test_publish_failure_pushes_event`           | `embed_publisher` returns `False`, valid phase with 5+ models | `push_event` title contains "fallo"                            |

**Key details:**

- All tests patch `src.web.routes.activity.push_event`.
- Tests 2–4 also patch `compute_ranking_for_phase` and `build_ranking_embed`.
- `compute_ranking_for_phase` mock returns list of 5+ model dicts for non-fallback assertions.
- Discord channel IDs as strings (snowflake safety).

**TDD — RED:**

1. Write all 4 tests.
2. Run `uv run pytest tests/test_openrouter_ranking_scheduler_coverage.py::TestJobRankingEmbed -v`.
3. Confirm execution and assertions.

**TDD — GREEN:**

1. Re-run — all pass.

**Verify:** `uv run pytest tests/test_openrouter_ranking_scheduler_coverage.py::TestJobRankingEmbed -v` — 4 passed.

---

## Task 8 — Full suite pass + coverage ≥80%

**Action:**

1. Run full new test file: `uv run pytest tests/test_openrouter_ranking_scheduler_coverage.py -v`
2. Confirm 22 test methods pass (parametrized = more runtime cases).
3. Run coverage: `uv run pytest --cov=src/bot/plugins/openrouter_prices/scheduler --cov-report=term-missing tests/test_openrouter_ranking_scheduler_coverage.py`
4. Verify: coverage ≥ 80%.

**Acceptance:**

- All 22 test methods pass.
- `scheduler.py` line coverage ≥ 80%.
- No import errors, no fixture conflicts.

---

## Task 9 — No regression on existing tests

**Action:**

1. Run existing test file: `uv run pytest tests/test_openrouter_ranking_scheduler.py -v`
2. Confirm all 20 existing tests still pass.
3. Run combined: `uv run pytest tests/test_openrouter_ranking_scheduler.py tests/test_openrouter_ranking_scheduler_coverage.py -v`
4. Confirm 42+ tests pass with 0 failures.

**Acceptance:**

- 0 failures on existing tests.
- 0 failures on new tests.
- No shared state contamination.

---

## Dependency Graph

```
Task 1 (scaffold)
  ├── Task 2 (TestIsScraping)
  ├── Task 3 (TestTriggerScrape)
  ├── Task 4 (TestTickLoop)
  ├── Task 5 (TestRunJobIfDue)
  ├── Task 6 (TestJobWeeklyReport)
  └── Task 7 (TestJobRankingEmbed)
Tasks 2–7 can run in any order after Task 1
Task 8 depends on all of 2–7
Task 9 depends on Task 8
```

---

## Teardown Contract

- Tests that call `sched.start()` must include `try: ... finally: await sched.stop()`.
- Tests calling `_tick()`, `_run_job_if_due()`, `_job_weekly_report()`, `_job_ranking_embed()` directly do NOT need start/stop.
- `trigger_scrape` tests use `asyncio.sleep(0.1)` to let inner tasks complete.
- All `_tick_loop` tests include `@pytest.mark.timeout(5)`.

---

## Risk Assessment

| Risk                                               | Level | Mitigation                                                  |
| -------------------------------------------------- | ----- | ----------------------------------------------------------- |
| `asyncio.wait_for` mock complexity in `_tick_loop` | LOW   | Deterministic call-counting mock; `@pytest.mark.timeout(5)` |
| `trigger_scrape` inner task timing                 | LOW   | `asyncio.sleep(0.1)`; increase to `0.2` if flaky            |
| Function-local import patch paths                  | LOW   | Verified: patch at source module, not scheduler namespace   |
| `_job_weekly_report` DB seeding                    | LOW   | Use `db.upsert_models()` with `_make_db_model`              |
| Parametrized tests obscuring failures              | LOW   | Use explicit `ids` in `@pytest.mark.parametrize`            |
