# Design: cleanup-scheduler-coverage

**Change ID:** cleanup-scheduler-coverage  
**Phase:** Design  
**Date:** 2026-05-14  
**Preceding artifacts:** `proposal.md`, `specs/delta-spec.md`  
**Target:** `src/bot/plugins/openrouter_prices/scheduler.py` — raise coverage from 66% to ≥80%  
**Output file:** `tests/test_openrouter_ranking_scheduler_coverage.py` (~280 lines, ~22 tests)

---

## 1. Design Decisions

### D1 — New file, no source edits

One new test file. No modifications to `scheduler.py`, existing tests, or `conftest.py`. If a genuine bug is discovered during the RED phase, it triggers a separate decision point per the proposal.

### D2 — Fixture reuse via import

Import `Counter`, `_make_db_model`, `_ok_result`, `_ok_result`, `_error_result`, and `_make_scheduler` from `tests/test_openrouter_ranking_scheduler.py`. These are module-level helpers and fixtures — no conftest changes needed.

Add one new local helper: `_FakeTime` (identical in spirit to `Counter` but named for semantic clarity when used in `_run_job_if_due` tests that don't need the `_make_scheduler` wrapper). However, since `Counter` already has the exact same interface as `_FakeTime` from the spec, and `_make_scheduler` accepts `clock=` which is `Counter`, we use `Counter` everywhere and skip `_FakeTime` to avoid duplication. For tests that call `_run_job_if_due` directly, we pass `now=fake_time()`.

### D3 — Patch targets for function-local imports

`scheduler.py` uses function-local imports for:
- `push_event` → patch at `src.web.routes.activity.push_event`
- `build_weekly_price_embed` → patch at `src.bot.plugins.openrouter_prices.discord_embeds.build_weekly_price_embed`
- `build_ranking_embed` → patch at `src.bot.plugins.openrouter_prices.discord_embeds.build_ranking_embed`
- `compute_ranking_for_phase` → patch at `src.bot.plugins.openrouter_prices.ranking.compute_ranking_for_phase`

These are the correct patch targets because the imports are inside function bodies.

### D4 — Scheduler teardown

Every test that calls `sched.start()` must include `try: ... finally: await sched.stop()` to prevent leaked tasks. The `_tick_loop` tests use `@patch("asyncio.wait_for")` to replace the 60s timeout with a producer-controlled awaitable.

### D5 — Deterministic timing

All time-dependent tests use `Counter` as the injected `time_provider`. No real `asyncio.sleep` or `time.time()` calls. The `_run_job_if_due` tests call the method directly with `now=` arguments rather than going through `_tick()`.

---

## 2. File Layout

```
tests/test_openrouter_ranking_scheduler_coverage.py
├── Imports (from test_openrouter_ranking_scheduler + stdlib)
├── TestIsScraping                          (2 tests)
├── TestTriggerScrape                       (5 tests)
├── TestTickLoop                            (3 tests)
├── TestRunJobIfDue                         (3 tests, 2 parametrized)
├── TestJobWeeklyReport                     (5 tests)
├── TestJobRankingEmbed                      (4 tests)
└── Total: ~22 tests
```

---

## 3. Test Classes and Methods

### 3.1 — TestIsScraping (lines 105)

Covers `is_scraping()` true/false branches.

| # | Method | Setup | Assertion |
|---|--------|-------|-----------|
| 1 | `test_is_scraping_returns_true` | Add source to `_active_scrapes` via `sched._active_scrapes.add("bfcl")` | `sched.is_scraping("bfcl") == True` |
| 2 | `test_is_scraping_returns_false` | Empty `_active_scrapes` | `sched.is_scraping("bfcl") == False` |

**Patch:** None. Direct state manipulation.

---

### 3.2 — TestTriggerScrape (lines 105, 113–141)

Covers the conflict path (source already active → return False) and the inner `_run()` dispatch for bfcl/aa/openrouter, exception handling, and `push_event`.

| # | Method | Setup | Assertion | Lines |
|---|--------|-------|-----------|-------|
| 1 | `test_trigger_scrape_conflict_returns_false` | Add "bfcl" to `_active_scrapes`, call `trigger_scrape("bfcl")` | Returns `False`; no task created | 105 |
| 2 | `test_trigger_scrape_bfcl_dispatches` | Call `trigger_scrape("bfcl")`, await inner task | `bfcl_scraper.scrape` called once with `db` | 113–119 |
| 3 | `test_trigger_scrape_aa_dispatches` | Call `trigger_scrape("aa")`, await inner task | `aa_scraper.scrape` called once with `db` | 120 |
| 4 | `test_trigger_scrape_openrouter_dispatches` | Call `trigger_scrape("openrouter")`, await inner task | `mock_client.fetch_models` called once | 121 |
| 5 | `test_trigger_scrape_exception_pushes_event` | `bfcl_scraper.scrape` raises; call `trigger_scrape("bfcl")`, await inner task | `push_event` called with kind="openrouter" and detail containing error message; `_active_scrapes` is empty after cleanup | 123–141 |

**Strategy for awaiting inner task:** `trigger_scrape` creates `asyncio.create_task(_run())`. To await the inner task, we:
1. Call `result = await sched.trigger_scrape(source)` — this returns immediately (True).
2. Await a short `asyncio.sleep(0.1)` to let the inner task execute.
3. For exception tests, `asyncio.sleep(0.2)` gives time for exception handling.

**Patches:**
- Test 5: `@patch("src.web.routes.activity.push_event")`

---

### 3.3 — TestTickLoop (lines 149–161)

Covers the main loop error handling, `TimeoutError` branch, and stop-event exit.

| # | Method | Setup | Assertion | Lines |
|---|--------|-------|-----------|-------|
| 1 | `test_tick_loop_continues_after_exception` | Patch `_tick` to raise on first call then succeed; patch `asyncio.wait_for` to raise `TimeoutError` after each tick | `_tick` called ≥2 times; no crash | 149–161 |
| 2 | `test_tick_loop_breaks_on_stop_event_via_wait_for` | Patch `asyncio.wait_for` to return (simulating stop_event.set()); `_tick` never raises | Loop exits after first `wait_for` return; `_task.done()` is True | 157–158 |
| 3 | `test_tick_loop_timeout_continues_to_next_tick` | Patch `asyncio.wait_for` to raise `TimeoutError` on first call, then return on second; `_tick` is an AsyncMock | `_tick` called at least twice; `_task` completes | 159–160 |

**Strategy for `_tick_loop`:** These tests are the most complex. We patch `asyncio.wait_for` to control the sleep/wait behavior deterministically, and we patch `sched._tick` to control per-tick behavior. The `_stop_event` is set externally when we want the loop to terminate.

**Detailed flow for Test 1 (tick_loop survives exception):**
```python
call_count = 0
async def ticking_tick():
    nonlocal call_count
    call_count += 1
    if call_count == 1:
        raise RuntimeError("boom")

async def fake_wait_for(aw, timeout):
    raise asyncio.TimeoutError()

sched._tick = ticking_tick
with patch("asyncio.wait_for", side_effect=fake_wait_for):
    await sched._tick_loop()
assert call_count >= 1
```

Wait — this would loop forever because `_stop_event` is never set. We need to set `_stop_event` after N ticks or make `wait_for` return at some point.

**Revised strategy:** Use a producer mock for `asyncio.wait_for` that:
- First call: raise `TimeoutError` (normal tick interval)
- Second call: return (simulating stop event)

And for the exception test:
- `_tick` raises on first call
- First `wait_for`: `TimeoutError` → next tick
- Second call to `_tick`: succeeds
- Second `wait_for`: returns (stop event set)

This avoids infinite loops.

---

### 3.4 — TestRunJobIfDue (lines 208, 219, 221)

Covers disabled early return, within-interval skip, and past-interval execution with metadata persistence.

| # | Method | Setup | Assertion | Lines |
|---|--------|-------|-----------|-------|
| 1 | `test_disabled_returns_immediately` | `enabled=False`, call `_run_job_if_due` | `job_fn` not called | 208–210 |
| 2 | `test_interval_elapsed[param]` (4 params: 1h, 24h, 7d, 14d) | `_FakeTime`/`Counter`, first call seeds metadata, advance past interval, second call | `job_fn` called once | 217–224 |
| 3 | `test_within_interval_skipped[param]` (4 params) | Same as above but advance < interval | `job_fn` not called | 218–219 |
| 4 | `test_metadata_persisted_after_success` | `job_fn` succeeds; check `db.get_metadata()` | `last_<key>_at == str(now)` | 227 |

**Tests 2 and 3 are parametrized** using `@pytest.mark.parametrize` with `ids=["1h", "24h", "7d", "14d"]`.

**Note:** Tests 2–4 call `sched._run_job_if_due()` directly, not through `_tick()`. This gives precise control over `now`, `metadata`, and `enabled` without needing the full scheduler config roundtrip.

**For test 4 (metadata persisted):** We go through the full scheduler tick path since `_run_job_if_due` calls `self._db.set_metadata()`. Alternatively, we call it directly on a scheduler with a real `db` fixture and verify the DB state.

**Revised approach — direct call with dict metadata:**
Looking at the source more carefully, `_run_job_if_due` takes `metadata` as a dict parameter. The test can pass a plain dict and verify the scheduler calls `self._db.set_metadata(meta_key, str(now))`. For a direct test, we need to verify the DB side effect or mock it.

Actually, `_run_job_if_due` calls `await self._db.set_metadata(meta_key, str(now))` on `self._db`. Since the scheduler has a real DB, we can verify via `await db.get_metadata()`. But `_run_job_if_due` also takes `metadata` as a parameter — that's read-only lookup.

The simplest path: use a real `db` fixture, call `_run_job_if_due` on the scheduler, then verify `await db.get_metadata()`.

---

### 3.5 — TestJobWeeklyReport (lines 288–334)

Covers no-channel early return, disabled early return, invalid count fallback, successful publish, and failed publish.

| # | Method | Setup | Assertion | Lines |
|---|--------|-------|-----------|-------|
| 1 | `test_no_channel_configured_pushes_event` | `weekly_report_channel_id=""`, `weekly_report_enabled="true"` | `embed_publisher` not called; `push_event` called with "Sin canal configurado" | 288–294 |
| 2 | `test_disabled_returns_early` | `weekly_report_channel_id="123"`, `weekly_report_enabled="false"` | `embed_publisher` not called | 296 |
| 3 | `test_invalid_count_defaults_to_10` | `weekly_report_count="abc"`, channel set, enabled | `db.list_models` called with `limit=10` | 303 |
| 4 | `test_successful_publish_pushes_event` | Valid config, `embed_publisher` returns `True`, seeded models | `embed_publisher` called; `push_event` with title containing "enviado" | 319–324 |
| 5 | `test_failed_publish_pushes_failure_event` | Valid config, `embed_publisher` returns `False` | `push_event` called with title containing "fallo" | 326–330 |

**Patches:**
- All tests: `@patch("src.web.routes.activity.push_event")`
- Tests 4 and 5: `@patch("src.bot.plugins.openrouter_prices.discord_embeds.build_weekly_price_embed")`

---

### 3.6 — TestJobRankingEmbed (lines 350, 363–364, 368, 412)

Covers disabled early return, JSON decode error fallback, empty phases fallback, and publish failure.

| # | Method | Setup | Assertion | Lines |
|---|--------|-------|-----------|-------|
| 1 | `test_disabled_returns_early` | `ranking_embed_enabled="false"` | `embed_publisher` not called | 350 |
| 2 | `test_empty_phases_fallback_to_ranking_phase` | `phases_enabled=""`, `ranking_phase="custom_phase"` | `compute_ranking_for_phase` called with `phase="custom_phase"` | 365–368 |
| 3 | `test_json_decode_error_fallback` | `phases_enabled="{invalid"` (broken JSON) | Falls back to `[config.get("ranking_phase", "orchestrator")]` | 363–364 |
| 4 | `test_publish_failure_still_pushes_event` | `embed_publisher` returns `False` for a valid phase | `push_event` called with title containing "fallo" | 411–412 |

**Patches:**
- All tests: `@patch("src.web.routes.activity.push_event")`
- Tests 2–4: `@patch("src.bot.plugins.openrouter_prices.ranking.compute_ranking_for_phase")`
- Tests 2–4: `@patch("src.bot.plugins.openrouter_prices.discord_embeds.build_ranking_embed")`

---

## 4. Fixture Architecture

### Reused fixtures (imported from existing test file)

| Fixture | Source | Type | Purpose |
|---------|--------|------|---------|
| `db` | `test_openrouter_ranking_scheduler.py` | `pytest.fixture` (async) | In-memory SQLite DB |
| `bfcl_scraper` | `test_openrouter_ranking_scheduler.py` | `pytest.fixture` | `MagicMock` with `AsyncMock` scrape |
| `aa_scraper` | `test_openrouter_ranking_scheduler.py` | `pytest.fixture` | `MagicMock` with `AsyncMock` scrape |
| `mock_client` | `test_openrouter_ranking_scheduler.py` | `pytest.fixture` | `MagicMock` with `AsyncMock fetch_models` |
| `embed_publisher` | `test_openrouter_ranking_scheduler.py` | `pytest.fixture` | `AsyncMock(return_value=True)` |

### Reused helpers (imported from existing test file)

| Helper | Purpose |
|--------|---------|
| `Counter` | Deterministic time provider — `__call__()` returns `value`, `advance(N)` increments |
| `_make_db_model(id, name)` | Creates a model dict matching `upsert_models` expectations |
| `_ok_result(source)` | Creates a `ScrapeResult` with status="ok" |
| `_make_scheduler(db, bfcl_scraper, aa_scraper, mock_client, embed_publisher, clock=None, config_overrides=None)` | Constructs `PluginScheduler` with all mocks pre-wired |

### New local helpers

None — `Counter` serves the role of `_FakeTime` from the spec; using it avoids duplication.

---

## 5. Mock Strategy

### 5.1 — `asyncio.wait_for` patching (TestTickLoop)

The `_tick_loop` method calls `await asyncio.wait_for(self._stop_event.wait(), timeout=_TICK_INTERVAL)` which would block for 60 seconds in tests. We patch `asyncio.wait_for` at the module level with a controllable mock:

```python
call_count = 0
async def fake_wait_for(aw, timeout):
    nonlocal call_count
    call_count += 1
    if call_count <= n_ticks:
        raise asyncio.TimeoutError()  # simulate normal tick interval
    # After n_ticks, simulate stop_event being set
    return None  # wait_for returns → break
```

This gives deterministic control over tick iterations without real time delays.

### 5.2 — `push_event` patching

`push_event` is imported inside function bodies in `scheduler.py` (lines 113, 282, 343). Patch at `src.web.routes.activity.push_event` — the source module path. The patch object's `.assert_called_with()` verifies the call.

### 5.3 — `compute_ranking_for_phase` patching

Used in `TestJobRankingEmbed`. Patch at `src.bot.plugins.openrouter_prices.ranking.compute_ranking_for_phase`. Returns a list of 5+ ranked model dicts.

### 5.4 — `build_weekly_price_embed` / `build_ranking_embed` patching

Both are function-local imports in `scheduler.py`. Patch at:
- `src.bot.plugins.openrouter_prices.discord_embeds.build_weekly_price_embed`
- `src.bot.plugins.openrouter_prices.discord_embeds.build_ranking_embed`

### 5.5 — `_tick` patching (TestTickLoop)

Patch `sched._tick` as an instance method to control per-tick behavior:
- Success: `AsyncMock()` (default)
- Raise on first call: `AsyncMock(side_effect=[RuntimeError("boom"), None])`

---

## 6. Data Flow

### 6.1 — `_run_job_if_due` tests (direct call)

```
Counter(start=0) → _run_job_if_due(job_key, interval, metadata={}, now=counter(), job_fn=AsyncMock(), enabled=True)
  → checks metadata for meta_key
  → if last_run + interval <= now: calls job_fn()
  → on success: db.set_metadata(meta_key, str(now))
```

The test constructs a `PluginScheduler` via `_make_scheduler` (which uses a real DB), then calls `sched._run_job_if_due()` directly with controlled `metadata` dict and `now` values.

### 6.2 — `_job_weekly_report` tests

```
_make_scheduler → db.update_config({...}) → await sched._job_weekly_report()
  → reads config from db
  → checks channel_id, enabled, count
  → calls db.list_models() → build_weekly_price_embed() → embed_publisher()
  → push_event(kind, title, detail)
```

### 6.3 — `_job_ranking_embed` tests

```
_make_scheduler → db.update_config({...}) → await sched._job_ranking_embed()
  → reads config from db
  → parses phases_enabled JSON
  → for each phase: compute_ranking_for_phase(db, phase, n=10)
  → if len(ranked) >= 5: build_ranking_embed() → embed_publisher()
  → push_event(...)
```

---

## 7. Scheduler Teardown Contract

Every test that calls `sched.start()` must include teardown:

```python
async def test_something(self, db, bfcl_scraper, aa_scraper, mock_client, embed_publisher):
    sched = _make_scheduler(db, bfcl_scraper, aa_scraper, mock_client, embed_publisher)
    try:
        await sched.start()
        # ... test logic ...
    finally:
        await sched.stop()
```

Tests that call `_tick()`, `_run_job_if_due()`, `_job_weekly_report()`, or `_job_ranking_embed()` directly do NOT need `start()`/`stop()` because they don't create background tasks.

The `trigger_scrape` test creates a fire-and-forget task internally; the test must await it with a short sleep or track it explicitly.

---

## 8. Test Matrix Summary

| Class | # | Method Name | Lines Targeted | Key Patch |
|-------|---|-------------|----------------|-----------|
| TestIsScraping | 1 | `test_is_scraping_returns_true` | 105 | None |
| TestIsScraping | 2 | `test_is_scraping_returns_false` | 105 | None |
| TestTriggerScrape | 3 | `test_trigger_scrape_conflict_returns_false` | 105 | None |
| TestTriggerScrape | 4 | `test_trigger_scrape_bfcl_dispatches` | 113–119 | None |
| TestTriggerScrape | 5 | `test_trigger_scrape_aa_dispatches` | 120 | None |
| TestTriggerScrape | 6 | `test_trigger_scrape_openrouter_dispatches` | 121 | None |
| TestTriggerScrape | 7 | `test_trigger_scrape_exception_pushes_event` | 123–141 | `push_event` |
| TestTickLoop | 8 | `test_tick_loop_continues_after_exception` | 149–161 | `asyncio.wait_for`, `_tick` |
| TestTickLoop | 9 | `test_tick_loop_breaks_on_stop_event` | 157–158 | `asyncio.wait_for` |
| TestTickLoop | 10 | `test_tick_loop_timeout_continues` | 159–160 | `asyncio.wait_for` |
| TestRunJobIfDue | 11 | `test_disabled_returns_immediately` | 208–210 | None |
| TestRunJobIfDue | 12 | `test_interval_elapsed[1h/24h/7d/14d]` | 217–224 | None |
| TestRunJobIfDue | 13 | `test_within_interval_skipped[1h/24h/7d/14d]` | 218–219 | None |
| TestRunJobIfDue | 14 | `test_metadata_persisted_after_success` | 227 | None |
| TestJobWeeklyReport | 15 | `test_no_channel_configured_pushes_event` | 288–294 | `push_event` |
| TestJobWeeklyReport | 16 | `test_disabled_returns_early` | 296 | `push_event` |
| TestJobWeeklyReport | 17 | `test_invalid_count_defaults_to_10` | 303 | `push_event`, `build_weekly_price_embed` |
| TestJobWeeklyReport | 18 | `test_successful_publish_pushes_event` | 319–324 | `push_event`, `build_weekly_price_embed` |
| TestJobWeeklyReport | 19 | `test_failed_publish_pushes_failure_event` | 326–330 | `push_event`, `build_weekly_price_embed` |
| TestJobRankingEmbed | 20 | `test_disabled_returns_early` | 350 | `push_event` |
| TestJobRankingEmbed | 21 | `test_empty_phases_fallback_to_ranking_phase` | 365–368 | `push_event`, `compute_ranking_for_phase` |
| TestJobRankingEmbed | 22 | `test_json_decode_error_fallback` | 363–364 | `push_event`, `compute_ranking_for_phase` |
| TestJobRankingEmbed | 23 | `test_publish_failure_pushes_event` | 411–412 | `push_event`, `compute_ranking_for_phase`, `build_ranking_embed` |

**Total: 23 test methods (parametrized D1/D2 count as 2 methods × 4 params each = 8 runtime cases).**

**Coverage projection:** 23 tests covering ~51 uncovered statements and ~23 uncovered branches → projected ~96% statement coverage.

---

## 9. Edge Cases and Risks

### 9.1 — `trigger_scrape` inner task timing

`trigger_scrape` creates an `asyncio.create_task(_run())` and returns `True` immediately. The test must give the inner task a chance to run by doing `await asyncio.sleep(0.05)` (or similar). For exception tests, `asyncio.sleep(0.1)` gives time for the exception handler to run.

**Mitigation:** Use `asyncio.sleep(0.1)` and assert on mock call counts. If flaky, increase to `0.2`.

### 9.2 — `_tick_loop` infinite loop risk

If our `asyncio.wait_for` mock never triggers the stop condition, the test hangs. The `@pytest.mark.timeout(5)` decorator kills it.

**Mitigation:** Every `_tick_loop` test sets `sched._stop_event` after a controlled number of iterations, or uses a mock that returns after N calls.

### 9.3 — `_job_weekly_report` models fixture

`_job_weekly_report` calls `await self._db.list_models(text_only=True, ...)`. The DB must be seeded with models before the job runs, otherwise `models` will be empty and the embed will have no data.

**Mitigation:** Seed the DB via `await db.upsert_models([_make_db_model(...)], fetched_at=clock())` in the test setup for tests that verify successful publish.

### 9.4 — `push_event` is a function-local import

Patching must target the source module, not the scheduler's namespace. All function-local imports in `scheduler.py` are:
- Line 113: `from src.web.routes.activity import push_event`
- Line 282: `from src.web.routes.activity import push_event`
- Line 343: `from src.web.routes.activity import push_event`
- Line 290: `from .discord_embeds import build_weekly_price_embed`
- Line 348: `from .discord_embeds import build_ranking_embed`

**Patch paths:** Use `@patch("src.web.routes.activity.push_event")` and `@patch("src.bot.plugins.openrouter_prices.discord_embeds.build_weekly_price_embed")` etc.

---

## 10. Detailed Test Specifications

### TestTriggerScrape — detailed plan

**All tests in this class share:** A scheduler constructed via `_make_scheduler(db, bfcl_scraper, aa_scraper, mock_client, embed_publisher)`. The `embed_publisher` is not relevant for scrape dispatch but is needed for construction.

**Test 3: `test_trigger_scrape_conflict_returns_false`**
```python
sched = _make_scheduler(...)
sched._active_scrapes.add("bfcl")
result = await sched.trigger_scrape("bfcl")
assert result is False
```

**Test 4: `test_trigger_scrape_bfcl_dispatches`**
```python
sched = _make_scheduler(...)
result = await sched.trigger_scrape("bfcl")
assert result is True
await asyncio.sleep(0.1)  # let inner task run
bfcl_scraper.scrape.assert_called_once_with(db)
assert "bfcl" not in sched._active_scrapes  # cleanup
```

**Test 5: `test_trigger_scrape_aa_dispatches`**
Same pattern as Test 4 but with `source="aa"` and `aa_scraper`.

**Test 6: `test_trigger_scrape_openrouter_dispatches`**
Same pattern as Test 4 but with `source="openrouter"` and `mock_client.fetch_models`.

**Test 7: `test_trigger_scrape_exception_pushes_event`**
```python
bfcl_scraper.scrape = AsyncMock(side_effect=RuntimeError("network down"))
with patch("src.web.routes.activity.push_event") as mock_push:
    result = await sched.trigger_scrape("bfcl")
    assert result is True
    await asyncio.sleep(0.2)
    mock_push.assert_called_once()
    assert "network down" in mock_push.call_args[1].get("detail", "") or \
           "network down" in str(mock_push.call_args)
assert "bfcl" not in sched._active_scrapes  # cleaned up even on error
```

---

### TestTickLoop — detailed plan

**Test 8: `test_tick_loop_continues_after_exception`**
```python
sched = _make_scheduler(...)
call_count = 0
original_tick = sched._tick

async def flaky_tick():
    nonlocal call_count
    call_count += 1
    if call_count == 1:
        raise RuntimeError("boom")

sched._tick = flaky_tick
tick_count = 0

async def fake_wait_for(aw, timeout):
    nonlocal tick_count
    tick_count += 1
    if tick_count >= 2:
        sched._stop_event.set()
    raise asyncio.TimeoutError()

with patch("asyncio.wait_for", side_effect=fake_wait_for):
    await sched._tick_loop()

assert call_count >= 1  # at least the failing tick ran
```

**Test 9: `test_tick_loop_breaks_on_stop_event`**
```python
sched = _make_scheduler(...)
sched._tick = AsyncMock()

async def wait_for_returns(aw, timeout):
    return None  # simulates stop_event.wait() completing

with patch("asyncio.wait_for", side_effect=wait_for_returns):
    await sched._tick_loop()

# Loop should have broken after wait_for returned
sched._tick.assert_called()
```

**Test 10: `test_tick_loop_timeout_continues`**
```python
sched = _make_scheduler(...)
sched._tick = AsyncMock()
tick_count = 0

async def wait_for_then_stop(aw, timeout):
    nonlocal tick_count
    tick_count += 1
    if tick_count < 3:
        raise asyncio.TimeoutError()
    return None  # stop after 2 timeouts

with patch("asyncio.wait_for", side_effect=wait_for_then_stop):
    await sched._tick_loop()

assert sched._tick.call_count >= 2
```

---

### TestRunJobIfDue — detailed plan

**Test 11: `test_disabled_returns_immediately`**
```python
sched = _make_scheduler(db, ...)
job_fn = AsyncMock()
await sched._run_job_if_due(
    job_key="bfcl_scrape",
    interval_seconds=86_400,
    metadata={},
    now=1_000_000,
    job_fn=job_fn,
    enabled=False,
)
job_fn.assert_not_called()
```

**Tests 12–13: parametrized interval tests**
```python
@pytest.mark.parametrize("label,interval_seconds,advance", [
    ("1h", 3600, 3601),
    ("24h", 86400, 86401),
    ("7d", 604800, 604801),
    ("14d", 1209600, 1209601),
], ids=["1h", "24h", "7d", "14d"])
async def test_interval_elapsed(self, label, interval_seconds, advance, db, ...):
    clock = Counter(start=0)
    sched = _make_scheduler(db, ..., clock=clock)
    job_fn = AsyncMock()
    metadata = {}
    # First call at t=0 — seeds metadata
    await sched._run_job_if_due(
        job_key="bfcl_scrape", interval_seconds=interval_seconds,
        metadata=metadata, now=clock(), job_fn=job_fn, enabled=True,
    )
    job_fn.assert_called_once()
    # Advance past interval
    clock.advance(advance)
    job_fn.reset_mock()
    metadata["last_bfcl_scrape_at"] = "0"
    # Second call — interval elapsed
    await sched._run_job_if_due(
        job_key="bfcl_scrape", interval_seconds=interval_seconds,
        metadata=metadata, now=clock(), job_fn=job_fn, enabled=True,
    )
    job_fn.assert_called_once()
```

**Alternative approach for parametrized tests:** Use `_run_job_if_due` with a fresh `metadata={}` for each call. On the first call with no metadata, `last_bfcl_scrape_at` defaults to "0", so `now - 0 >= interval_seconds` is true, and the job fires. The `_run_job_if_due` method then calls `db.set_metadata()`. For the second call, we'd need to read from `db.get_metadata()`. However, since `_run_job_if_due` takes `metadata` as a dict parameter (passed in from `_tick`), we can control it directly.

**Simpler approach for test 12 (interval elapsed):**
```python
clock = Counter(start=1_000_000)
sched = _make_scheduler(...)
# First call: metadata has no last_run → job fires
await sched._run_job_if_due(
    job_key="bfcl_scrape", interval_seconds=interval_seconds,
    metadata={}, now=clock(), job_fn=job_fn, enabled=True,
)
assert job_fn.call_count == 1
```

Wait, we need to test that it fires when the interval has elapsed. The simplest: call once with empty metadata (fires because `now - 0 >= interval`), then verify it fires. For the "within interval" test, set `metadata={"last_bfcl_scrape_at": str(clock.value)}` and verify it does NOT fire.

**Revised approach — clean and deterministic:**

For **test 12 (interval elapsed):**
- `metadata = {}`, `now = interval_seconds + 1` (much later than default `last_run=0`)
- `job_fn` should be called

For **test 13 (within interval):**
- `metadata = {"last_bfcl_scrape_at": str(now - interval_seconds + 100)}` (recently run)
- `job_fn` should NOT be called

**Test 14: `test_metadata_persisted_after_success`**
```python
clock = Counter(start=5_000_000)
sched = _make_scheduler(db, ..., clock=clock)
job_fn = AsyncMock()
await sched._run_job_if_due(
    job_key="openrouter_refresh", interval_seconds=86_400,
    metadata={}, now=clock(), job_fn=job_fn, enabled=True,
)
result = await db.get_metadata()
assert result["last_openrouter_refresh_at"] == "5000000"
```

---

### TestJobWeeklyReport — detailed plan

**Test 15: `test_no_channel_configured_pushes_event`**
```python
await db.update_config({"weekly_report_enabled": "true", "weekly_report_channel_id": ""})
with patch("src.web.routes.activity.push_event") as mock_push:
    await sched._job_weekly_report()
mock_push.assert_called_once()
call_kwargs = mock_push.call_args[1] if mock_push.call_args[1] else mock_push.call_args.kwargs
assert "Sin canal configurado" in call_kwargs.get("detail", str(call_kwargs))
embed_publisher.assert_not_called()
```

**Test 16: `test_disabled_returns_early`**
```python
await db.update_config({"weekly_report_enabled": "false", "weekly_report_channel_id": "123456789012345678"})
with patch("src.web.routes.activity.push_event"):
    await sched._job_weekly_report()
embed_publisher.assert_not_called()
```

**Test 17: `test_invalid_count_defaults_to_10`**
```python
await db.update_config({
    "weekly_report_enabled": "true",
    "weekly_report_channel_id": "123456789012345678",
    "weekly_report_count": "not_a_number",
})
await db.upsert_models([_make_db_model("test/model", "Test Model")], clock())
with patch("src.web.routes.activity.push_event"), \
     patch("src.bot.plugins.openrouter_prices.discord_embeds.build_weekly_price_embed") as mock_build:
    mock_build.return_value = MagicMock()
    await sched._job_weekly_report()
# Verify list_models was called (implicitly uses count=10)
db_spy = AsyncMock(wraps=db)  # Alternative: check mock_build received≤10 models
```

Better: check `build_weekly_price_embed` was called with `count` models or that `list_models` was called with `limit=10`. Since `db` is a real DB, we can spy on `db.list_models`.

**Test 18: `test_successful_publish_pushes_event`**
```python
await db.update_config({...valid config...})
await db.upsert_models([...], clock())
with patch("src.web.routes.activity.push_event") as mock_push, \
     patch("...build_weekly_price_embed") as mock_build:
    mock_build.return_value = MagicMock()
    await sched._job_weekly_report()
embed_publisher.assert_called_once()
assert mock_push.call_count == 1
# Check title contains "enviado"
```

**Test 19: `test_failed_publish_pushes_failure_event`**
```python
embed_publisher_fails = AsyncMock(return_value=False)
sched = _make_scheduler(db, ..., embed_publisher=embed_publisher_fails)
# ... same setup ...
with patch("src.web.routes.activity.push_event") as mock_push, \
     patch("...build_weekly_price_embed"):
    await sched._job_weekly_report()
assert "fallo" in mock_push.call_args.kwargs.get("title", "").lower() or \
       "fallo" in str(mock_push.call_args).lower()
```

---

### TestJobRankingEmbed — detailed plan

**Test 20: `test_disabled_returns_early`**
```python
await db.update_config({"ranking_embed_enabled": "false", "ranking_embed_channel_id": "123"})
with patch("src.web.routes.activity.push_event"):
    await sched._job_ranking_embed()
embed_publisher.assert_not_called()
```

**Test 21: `test_empty_phases_fallback_to_ranking_phase`**
```python
await db.update_config({
    "ranking_embed_enabled": "true",
    "ranking_embed_channel_id": "123456789012345678",
    "phases_enabled": "",
    "ranking_phase": "custom_phase",
})
with patch("...compute_ranking_for_phase", new=AsyncMock(return_value=[
    {"rank": 1, "model_id": "x", "name": "X", "score": 0.9, "breakdown": []}
] * 5)) as mock_compute, \
     patch("...build_ranking_embed", return_value=MagicMock()), \
     patch("src.web.routes.activity.push_event"):
    await sched._job_ranking_embed()
mock_compute.assert_called_once()
assert mock_compute.call_args[0][1] == "custom_phase"
```

**Test 22: `test_json_decode_error_fallback`**
```python
await db.update_config({
    "ranking_embed_enabled": "true",
    "ranking_embed_channel_id": "123456789012345678",
    "phases_enabled": "{invalid json",
    "ranking_phase": "orchestrator",
})
# Same pattern as test 21, verify compute_ranking_for_phase called with "orchestrator"
```

**Test 23: `test_publish_failure_pushes_event`**
```python
embed_fails = AsyncMock(return_value=False)
sched = _make_scheduler(db, ..., embed_publisher=embed_fails)
await db.update_config({
    "ranking_embed_enabled": "true",
    "ranking_embed_channel_id": "123456789012345678",
    "phases_enabled": '["orchestrator"]',
})
with patch("...compute_ranking_for_phase", return_value=[
    {"rank": i+1, "model_id": f"m/{i}", "name": f"M{i}", "score": 0.9, "breakdown": []}
    for i in range(5)
]), patch("...build_ranking_embed", return_value=MagicMock()), \
     patch("src.web.routes.activity.push_event") as mock_push:
    await sched._job_ranking_embed()
assert mock_push.call_count >= 1
# Verify title contains "fallo"
```

---

## 11. Coverage Impact

| Area | Current Coverage (lines) | Target Lines | Est. New Coverage |
|------|--------------------------|--------------|-------------------|
| `is_scraping` | Partial | 105 | +1 stmt, +1 branch |
| `trigger_scrape` inner `_run()` | Not covered | 113–141 | +12 stmts, +5 branches |
| `_tick_loop` | Partial | 149–161 | +8 stmts, +3 branches |
| `_run_job_if_due` branches | Partial | 208, 219, 221 | +4 stmts, +2 branches |
| `_job_weekly_report` | Not covered | 288–334 | +20 stmts, +8 branches |
| `_job_ranking_embed` gaps | Partial | 350, 363–364, 368, 412 | +6 stmts, +4 branches |
| **Total** | 110/167 (66%) | ~51 new stmts | ~161/167 (~96%) |

---

## 12. Risks and Mitigations

| Risk | Level | Mitigation |
|------|-------|------------|
| `asyncio.wait_for` mock complexity in `_tick_loop` | LOW | Deterministic mock with call counter; `@pytest.mark.timeout(5)` safety net |
| `trigger_scrape` inner task timing | LOW | `asyncio.sleep(0.1)` after `trigger_scrape`; increase to `0.2` if flaky |
| `_job_weekly_report` DB seeding | LOW | Use `db.upsert_models()` with `_make_db_model` helper |
| Function-local imports need correct patch paths | LOW | Verified patch targets from source analysis |
| Parametrized tests obscuring failures | LOW | Use `ids=["1h", "24h", "7d", "14d"]` for readable test names |

---

## 13. TDD Protocol

Strict TDD is active per `openspec/config.yaml`. Implementation sequence:

1. **RED:** Write each test class in `tests/test_openrouter_ranking_scheduler_coverage.py`. Run `uv run pytest tests/test_openrouter_ranking_scheduler_coverage.py` — all tests must FAIL (confirm they execute and assert correctly).
2. **GREEN:** If any test fails due to missing implementation (bug in `scheduler.py`), document as a separate discovery. Otherwise, all tests should pass against the current source.
3. **REFACTOR:** No refactoring needed since we're only adding tests.
4. **VERIFY:** Run full suite: `uv run pytest tests/test_openrouter_ranking_scheduler_coverage.py tests/test_openrouter_ranking_scheduler.py`. All 43 tests must pass. Check coverage: `uv run pytest --cov=src/bot/plugins/openrouter_prices/scheduler tests/test_openrouter_ranking_scheduler_coverage.py` — must be ≥80%.