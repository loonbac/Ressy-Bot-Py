# Delta Spec: `cleanup-scheduler-coverage`

**Change ID:** `cleanup-scheduler-coverage`  
**Module:** `src/bot/plugins/openrouter_prices/scheduler.py`  
**Test file:** `tests/test_openrouter_ranking_scheduler_coverage.py`  
**Date:** 2026-05-14  
**Status:** Draft  
**Preceding phase:** Proposal (`openspec/changes/cleanup-scheduler-coverage/proposal.md`)

---

## 1. Scope and Goals

This spec defines 15 tests that MUST be added in a single new file to raise `scheduler.py` line coverage from 66 % to ≥ 80 %. No source file edits are permitted unless a genuine bug is discovered during the RED phase (which triggers a separate decision point).

The tests reuse the existing helper classes (`Counter`, `_make_db_model`, `_ok_result`, `_error_result`) and fixture pattern (`db`, `bfcl_scraper`, `aa_scraper`, `mock_client`, `embed_publisher`, `_make_scheduler`) from `tests/test_openrouter_ranking_scheduler.py`. No conftest changes are needed.

### 1.1. Target Areas

| # | Area | Lines in `scheduler.py` | Tests |
|---|------|-------------------------|-------|
| 1 | Lifecycle: start-twice, stop-before-start, stop-cancels-tick, stop-idempotent | 86–102 | 4 |
| 2 | Job dispatch by interval (parametrized) | 208–228 | 3 |
| 3 | Error handling: failing job doesn't kill loop + logged with source | 149–161, 222–225 | 2 |
| 4 | Multi-phase ranking embed | 342–420 | 4 |
| 5 | Weekly report dispatch by day/hour | 280–335 | 1 |
| 6 | Disabled plugin skips tick | 208–210, 347–348 | 1 |
| **Total** | | | **15** |

---

## 2. Normative Requirements (RFC 2119)

### REQ-01 — Lifecycle

- **REQ-01.1:** Calling `start()` twice without an intervening `stop()` SHALL create a new task. The previous task is not explicitly cancelled by `start()`; the implementation delegates that to caller discipline. The test MUST assert the second `start()` creates a distinct task reference.
- **REQ-01.2:** Calling `stop()` before `start()` MUST NOT raise an exception. The method SHALL be a no-op.
- **REQ-01.3:** Calling `stop()` while `_tick_loop` is waiting for `_TICK_INTERVAL` SHALL cancel the underlying task. The test MUST verify `_task.cancelled() or _task.done()` is `True` after `stop()`.
- **REQ-01.4:** Calling `stop()` a second time after a successful `stop()` MUST NOT raise an exception (idempotent teardown).

### REQ-02 — Job Dispatch by Interval

- **REQ-02.1:** `_run_job_if_due` SHALL invoke `job_fn` when `now - last_run >= interval_seconds`. The test MUST use parametrized intervals (1 h, 24 h, 7 d, 14 d) to verify the boundary condition.
- **REQ-02.2:** `_run_job_if_due` SHALL skip `job_fn` when `now - last_run < interval_seconds`. The test MUST verify zero calls to `job_fn`.
- **REQ-02.3:** After successful `job_fn` execution, `_run_job_if_due` SHALL persist `now` via `db.set_metadata(meta_key, str(now))`.

### REQ-03 — Error Handling

- **REQ-03.1:** If `job_fn` raises an exception inside `_run_job_if_due`, the exception SHALL be caught, logged with `exc_info=True`, and the loop MUST continue. `set_metadata` SHALL NOT be called for failed jobs.
- **REQ-03.2:** If an exception occurs inside `_tick()`, `_tick_loop` SHALL catch it, log it, and continue to the next tick iteration (or break on stop_event). The test MUST verify at least one subsequent tick runs after the failing tick.

### REQ-04 — Multi-Phase Ranking Embed

- **REQ-04.1:** `_job_ranking_embed` SHALL iterate over all phases in `phases_enabled` JSON, calling `compute_ranking_for_phase` for each.
- **REQ-04.2:** If a phase yields fewer than 5 ranked models, `_job_ranking_embed` SHALL skip that phase (no embed published) and log a warning containing the phase name and model count.
- **REQ-04.3:** When `ranking_embed_per_phase` is `"false"`, `_job_ranking_embed` SHALL publish at most one embed using only the first phase in the list.
- **REQ-04.4:** When `phases_enabled` is empty or invalid JSON, `_job_ranking_embed` SHALL fall back to `[config.get("ranking_phase", "orchestrator")]`.

### REQ-05 — Weekly Report

- **REQ-05.1:** `_job_weekly_report` SHALL return early (no embed) when `weekly_report_channel_id` is empty or missing. A `push_event` with detail "Sin canal configurado" SHALL be emitted.

### REQ-06 — Disabled Plugin Skips Tick

- **REQ-06.1:** When a job's `enabled` flag is `False`, `_run_job_if_due` SHALL return immediately without calling `job_fn`.

### REQ-07 — Time Provider Injection

- **REQ-07.1:** `PluginScheduler` SHALL accept an optional `time_provider` callable. When provided, `_run_job_if_due` MUST use its return value as `now` instead of `time.time()`. This is already exercised by existing tests but MUST be explicitly asserted in the new test file for the parametrized interval scenario.

### REQ-08 — Teardown Callback

- **REQ-08.1:** After `stop()` completes, the underlying `_task` SHALL be in a terminal state (`cancelled() or done()`) and `_stop_event` SHALL be set. The test MUST assert both conditions.

---

## 3. Test Fixtures

### FIX-01 — `_FakeTime`

A deterministic time provider (identical in spirit to `Counter` but defined locally for clarity):

```
class _FakeTime:
    def __init__(self, start: int = 1_000_000): self.value = start
    def advance(self, seconds: int): self.value += seconds
    def __call__(self) -> int: return self.value
```

This MUST be used in all new tests instead of the shared `Counter` to keep the new file self-contained while remaining compatible with `_make_scheduler(clock=...)`.

### FIX-02 — Mocked Scraper

`bfcl_scraper` and `aa_scraper` SHALL be `MagicMock` instances with `.scrape = AsyncMock(return_value=_ok_result(source))`. Reuse the same pattern from the existing test file.

### FIX-03 — Mocked `embed_publisher`

An `AsyncMock(return_value=True)` that doubles as a spy for call-count and call-args assertions.

### FIX-04 — Mocked Discord Client

`mock_client` with `.fetch_models = AsyncMock(return_value=[...])` seeded with at least one model via `_make_db_model`.

---

## 4. Test Scenarios

### 4.1 — Lifecycle Tests (`TestLifecycleEdgeCases`)

#### Scenario L1: Start Twice

- **Given** a scheduler with a mocked tick loop (patch `_tick_loop` to hang indefinitely via `asyncio.Event`),
- **When** `start()` is called twice,
- **Then** `sched._task` after the second call SHALL reference a different `asyncio.Task` than after the first call.

```
Given sched._tick_loop patched to await a never-set Event
  And sched.start() has been called once
  And first_task = sched._task
 When sched.start() is called again
 Then sched._task is not first_task
  And sched._task is not None
```

#### Scenario L2: Stop Before Start

- **Given** a newly constructed scheduler (no `start()` called),
- **When** `stop()` is called,
- **Then** no exception SHALL be raised.

```
Given sched = _make_scheduler(...)
 When await sched.stop()
 Then no exception is raised
```

#### Scenario L3: Stop Cancels Tick

- **Given** a running scheduler (`start()` called),
- **When** `stop()` is called,
- **Then** `sched._task.cancelled() or sched._task.done()` SHALL be `True`.

```
Given sched.start() has been called
  And sched._task is not None
  And sched._task.done() is False
 When await sched.stop()
 Then sched._task.cancelled() is True or sched._task.done() is True
```

#### Scenario L4: Stop Idempotent

- **Given** a stopped scheduler (`start()` then `stop()` already called),
- **When** `stop()` is called again,
- **Then** no exception SHALL be raised.

```
Given sched.start() then sched.stop() have been called
 When await sched.stop() is called again
 Then no exception is raised
  And sched._task.done() is still True
```

---

### 4.2 — Job Dispatch by Interval (`TestJobDispatchInterval`)

Parametrized with `interval_label, interval_seconds, advance_by`:

| Label | interval_seconds | advance_by (past first tick) | Expect job_fn called |
|-------|-----------------|------------------------------|---------------------|
| 1h    | 3600            | 3601                         | Yes |
| 24h   | 86400           | 86401                        | Yes |
| 7d    | 604800          | 604801                       | Yes |
| 14d   | 1209600         | 1209601                      | Yes |

#### Scenario D1: Interval Elapsed — Job Fires

- **Given** a scheduler with `_FakeTime`, `_run_job_if_due` called once at `t=0` (records `last_run=0`),
- **When** time is advanced past the interval and `_run_job_if_due` is called again,
- **Then** `job_fn` SHALL be called exactly once.

```
Given fake_time = _FakeTime(start=0)
  And job_fn = AsyncMock()
  And metadata = {}
 When await _run_job_if_due(job_key="test", interval_seconds=<interval>, metadata=metadata, now=fake_time(), job_fn=job_fn, enabled=True)
  And fake_time.advance(<interval> + 1)
  And await _run_job_if_due(job_key="test", interval_seconds=<interval>, metadata=metadata, now=fake_time(), job_fn=job_fn, enabled=True)
 Then job_fn.await_count == 1
```

#### Scenario D2: Within Interval — Job Skipped

- **Given** same setup as D1,
- **When** time is advanced by `interval_seconds - 1` (still within interval),
- **Then** `job_fn` SHALL NOT be called.

```
Given fake_time = _FakeTime(start=0)
  And job_fn = AsyncMock()
  And metadata = {}
 When await _run_job_if_due(job_key="test", interval_seconds=<interval>, metadata=metadata, now=fake_time(), job_fn=job_fn, enabled=True)
  And fake_time.advance(<interval> - 1)
  And await _run_job_if_due(job_key="test", interval_seconds=<interval>, metadata=metadata, now=fake_time(), job_fn=job_fn, enabled=True)
 Then job_fn.await_count == 0
```

#### Scenario D3: Metadata Persisted After Success

- **Given** a successful `job_fn` execution,
- **When** `_run_job_if_due` completes,
- **Then** `db.get_metadata()` SHALL contain `last_<job_key>_at` with value equal to `now`.

```
Given fake_time = _FakeTime(start=1_000_000)
  And sched._tick() has run (setting metadata)
 When db.get_metadata() is queried
 Then metadata["last_openrouter_refresh_at"] == "1000000"
```

---

### 4.3 — Error Handling (`TestErrorHandling`)

#### Scenario E1: Failing Job Doesn't Kill Loop

- **Given** a scheduler whose first `_tick()` raises (patch `_tick` to raise on first call, succeed on second),
- **When** `_tick_loop` runs two iterations,
- **Then** the second tick SHALL execute successfully,
- **And** the error SHALL be logged with `exc_info=True`.

```
Given tick_side_effects = [RuntimeError("boom"), None]
  And _tick patched with side_effect sequence
  And _stop_event.set() called after 2 ticks (via mock wait)
 When _tick_loop runs
 Then _tick was called at least 2 times
  And caplog contains "Error inesperado en tick del scheduler"
```

#### Scenario E2: Failed Job Does Not Persist Metadata

- **Given** a `job_fn` that raises `RuntimeError`,
- **When** `_run_job_if_due` is called with `enabled=True` and the interval elapsed,
- **Then** `job_fn` SHALL be called,
- **And** `db.set_metadata` SHALL NOT be called for the failed job's meta_key.

```
Given job_fn = AsyncMock(side_effect=RuntimeError("fail"))
  And metadata = {}
 When await _run_job_if_due(job_key="test", interval_seconds=10, metadata=metadata, now=100, job_fn=job_fn, enabled=True)
 Then job_fn.await_count == 1
  And "last_test_at" not in metadata
```

---

### 4.4 — Multi-Phase Ranking Embed (`TestMultiPhaseRankingEmbed`)

#### Scenario R1: Iterate Phases — Publish Per Phase

- **Given** `phases_enabled = ["orchestrator", "coding"]`, `ranking_embed_per_phase = "true"`,
- **And** `compute_ranking_for_phase` returns 5+ models for both phases,
- **When** `_job_ranking_embed()` runs,
- **Then** `embed_publisher` SHALL be called twice (once per phase).

```
Given config phases_enabled=["orchestrator","coding"], per_phase=true, channel_id set
  And compute_ranking_for_phase returns 5 models for each phase
 When await sched._job_ranking_embed()
 Then embed_publisher.call_count == 2
```

#### Scenario R2: Skip Empty Phase

- **Given** `phases_enabled = ["orchestrator", "empty_phase"]`, `ranking_embed_per_phase = "true"`,
- **And** `compute_ranking_for_phase` returns 5 models for "orchestrator" and 3 for "empty_phase",
- **When** `_job_ranking_embed()` runs,
- **Then** `embed_publisher` SHALL be called once (only "orchestrator"),
- **And** a warning log containing "empty_phase" and "rankeables" SHALL be emitted.

```
Given phases_enabled=["orchestrator","empty_phase"], per_phase=true
  And compute returns 5 for orchestrator, 3 for empty_phase
 When await sched._job_ranking_embed()
 Then embed_publisher.call_count == 1
  And caplog contains "empty_phase" and "rankeables"
```

#### Scenario R3: Per-Phase False — Single Embed

- **Given** `phases_enabled = ["orchestrator", "coding"]`, `ranking_embed_per_phase = "false"`,
- **And** `compute_ranking_for_phase` returns 5+ models for both phases,
- **When** `_job_ranking_embed()` runs,
- **Then** `embed_publisher` SHALL be called exactly once with the first phase only.

```
Given phases_enabled=["orchestrator","coding"], per_phase=false
  And compute returns 5 models for each phase
 When await sched._job_ranking_embed()
 Then embed_publisher.call_count == 1
  And "orchestrator" in first_call_embed_title
```

#### Scenario R4: Unknown Phase Fallback (Empty phases_enabled → falls back to ranking_phase config)

- **Given** `phases_enabled = ""` (empty string), `ranking_phase = "custom_phase"`,
- **And** `compute_ranking_for_phase` returns 5+ models for "custom_phase",
- **When** `_job_ranking_embed()` runs,
- **Then** `compute_ranking_for_phase` SHALL be called with `phase="custom_phase"`,
- **And** `embed_publisher` SHALL be called once.

```
Given phases_enabled="", ranking_phase="custom_phase", channel_id set
  And compute returns 5 models for custom_phase
 When await sched._job_ranking_embed()
 Then compute_ranking_for_phase was called with phase="custom_phase"
  And embed_publisher.call_count == 1
```

---

### 4.5 — Weekly Report Dispatch (`TestWeeklyReportDispatch`)

#### Scenario W1: No Channel Configured

- **Given** `weekly_report_channel_id` is empty (default),
- **And** `weekly_report_enabled = "true"`,
- **When** `_job_weekly_report()` runs,
- **Then** `embed_publisher` SHALL NOT be called,
- **And** `push_event` SHALL be called with `detail` containing "Sin canal configurado".

```
Given config has weekly_report_enabled=true, weekly_report_channel_id=""
 When await sched._job_weekly_report()
 Then embed_publisher.call_count == 0
  And push_event called with kind="openrouter", detail containing "Sin canal configurado"
```

---

### 4.6 — Disabled Plugin Skips Tick (`TestDisabledPluginSkipsTick`)

#### Scenario DP1: Disabled Job Not Dispatched

- **Given** `enabled=False` for a job,
- **When** `_run_job_if_due` is called with `enabled=False`,
- **Then** `job_fn` SHALL NOT be called,
- **And** no metadata SHALL be read or written.

```
Given job_fn = AsyncMock()
 When await _run_job_if_due(job_key="bfcl_scrape", interval_seconds=86400, metadata={}, now=999, job_fn=job_fn, enabled=False)
 Then job_fn.await_count == 0
```

---

### 4.7 — Time Provider Injection (`TestTimeProviderInjection`)

#### Scenario TP1: Custom Time Provider Used

- **Given** a `_FakeTime(start=5_000_000)`,
- **When** a tick runs and a job fires,
- **Then** the persisted metadata timestamp SHALL equal `5_000_000`.

```
Given fake_time = _FakeTime(start=5_000_000)
  And sched = _make_scheduler(clock=fake_time)
 When await sched._tick()
 Then metadata["last_openrouter_refresh_at"] == "5000000"
```

---

### 4.8 — Teardown Callback (`TestTeardownCallback`)

#### Scenario TD1: Stop Sets Stop Event and Terminates Task

- **Given** a running scheduler,
- **When** `stop()` is called,
- **Then** `sched._stop_event.is_set()` SHALL be `True`,
- **And** `sched._task.done()` or `sched._task.cancelled()` SHALL be `True`.

```
Given sched.start() has been called
 When await sched.stop()
 Then sched._stop_event.is_set() is True
  And sched._task.done() or sched._task.cancelled() is True
```

---

## 5. Implementation Constraints

1. **TDD Discipline:** Strict TDD is active per `openspec/config.yaml`. Each test MUST be written first (RED), then verified GREEN. No implementation changes to `scheduler.py` are expected.
2. **File isolation:** All 15 tests reside in `tests/test_openrouter_ranking_scheduler_coverage.py`. No modifications to existing test files or `conftest.py`.
3. **Fixture reuse:** Import `Counter`, `_make_db_model`, `_ok_result`, `_error_result` from `tests/test_openrouter_ranking_scheduler.py` if compatible; otherwise define local equivalents (`_FakeTime`).
4. **Patch targets:** Function-local imports (e.g., `build_ranking_embed`, `push_event`) SHALL be patched at the source module path:
   - `src.bot.plugins.openrouter_prices.ranking.compute_ranking_for_phase`
   - `src.bot.plugins.openrouter_prices.discord_embeds.build_weekly_price_embed`
   - `src.web.routes.activity.push_event`
5. **Snowflake safety:** Discord channel IDs in test config SHALL be string values (e.g., `"123456789012345678"`).
6. **Timeout:** All tests SHALL use `@pytest.mark.timeout(5)` to prevent hanging on async mock misconfiguration.
7. **Async:** All test methods SHALL be `async def` with `pytest-asyncio` (mode `auto`).

---

## 6. Test Summary Matrix

| Test Class | Scenario ID | Test Method Name | Covers REQ | Lines Targeted |
|------------|-------------|------------------|------------|----------------|
| TestLifecycleEdgeCases | L1 | `test_start_twice_creates_new_task` | REQ-01.1 | 86–89 |
| TestLifecycleEdgeCases | L2 | `test_stop_before_start_is_noop` | REQ-01.2 | 91–102 |
| TestLifecycleEdgeCases | L3 | `test_stop_cancels_running_tick` | REQ-01.3, REQ-08.1 | 93–102 |
| TestLifecycleEdgeCases | L4 | `test_stop_idempotent` | REQ-01.4 | 91–102 |
| TestJobDispatchInterval | D1 | `test_interval_elapsed[param]` | REQ-02.1, REQ-07.1 | 208–228 |
| TestJobDispatchInterval | D2 | `test_within_interval_skipped[param]` | REQ-02.2 | 218 |
| TestJobDispatchInterval | D3 | `test_metadata_persisted_after_success` | REQ-02.3 | 227 |
| TestErrorHandling | E1 | `test_tick_loop_error_survives` | REQ-03.2 | 149–161 |
| TestErrorHandling | E2 | `test_failed_job_does_not_persist_metadata` | REQ-03.1 | 222–225 |
| TestMultiPhaseRankingEmbed | R1 | `test_iterate_phases_publish_per_phase` | REQ-04.1 | 381–419 |
| TestMultiPhaseRankingEmbed | R2 | `test_skip_empty_phase` | REQ-04.2 | 386–391 |
| TestMultiPhaseRankingEmbed | R3 | `test_per_phase_false_single_embed` | REQ-04.3 | 372–374 |
| TestMultiPhaseRankingEmbed | R4 | `test_unknown_phase_fallback_to_ranking_phase` | REQ-04.4 | 365–368 |
| TestWeeklyReportDispatch | W1 | `test_no_channel_configured` | REQ-05.1 | 288–294 |
| TestDisabledPluginSkipsTick | DP1 | `test_disabled_job_not_dispatched` | REQ-06.1 | 208–210 |
| TestTimeProviderInjection | TP1 | `test_custom_time_provider_used` | REQ-07.1 | 77 |
| TestTeardownCallback | TD1 | `test_stop_sets_stop_event_and_terminates_task` | REQ-08.1 | 93–102 |

**Total:** 17 scenario entries → 15 test methods (D1 and D2 are parametrized into single `@pytest.mark.parametrize` test methods with 4 parameters each, counting as 2 methods but 8 parameter combinations).

---

## 7. Risks

| Risk | Level | Mitigation |
|------|-------|------------|
| `_tick_loop` mock complexity: `asyncio.wait_for` must be patched to avoid 60s real timeout | LOW | Replace `asyncio.wait_for` with `await asyncio.sleep(0)` via patch, or use `_stop_event.wait()` mock |
| `push_event` import is function-local in `scheduler.py` lines 113, 282, 343 | LOW | Patch at `src.web.routes.activity.push_event` (source module), not at scheduler namespace |
| `build_weekly_price_embed` and `build_ranking_embed` imports are function-local | LOW | Patch at `src.bot.plugins.openrouter_prices.discord_embeds.build_*` |
| Parametrized tests may obscure individual failures | LOW | Use clear `ids` parameter in `@pytest.mark.parametrize` |

---

## 8. Success Criteria

1. All 15 test methods pass: `uv run pytest tests/test_openrouter_ranking_scheduler_coverage.py -v`
2. No regressions: `uv run pytest tests/test_openrouter_ranking_scheduler.py` — 20 existing tests still pass
3. Coverage ≥ 80 %: `uv run pytest --cov=src/bot/plugins/openrouter_prices/scheduler tests/test_openrouter_ranking_scheduler_coverage.py`
4. No edits to `scheduler.py`
5. Strict TDD evidence: RED → GREEN for each test

---

## 9. Out of Scope

- No changes to `scheduler.py` source code
- No changes to existing test files or `conftest.py`
- No integration tests requiring a live bot or Discord connection
- No coverage of already-tested lines (no redundant tests)
