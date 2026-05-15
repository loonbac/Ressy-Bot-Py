# Tasks: openrouter-ranking

Generated: 2026-05-14
Delivery strategy: auto-chain / stacked-to-main
TDD mode: STRICT — RED test written and run (failing) before any implementation code.
Test runner: `uv run pytest`

---

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~2000 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR1 / PR2 / PR3 (see below) |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |
| Decision needed before apply | No |

`sdd-apply` MUST implement ONLY PR 1 in the first batch.

---

## PR 1 — Foundation: DB Schema + Pure Functions + Seeds

**Goal**: All new tables seeded and tested; pure scoring functions fully exercised; alias fuzzy-match verified. No scrapers, no scheduler, no API. ~400–500 lines including tests.

**Spec coverage**: REQ-EXT-2, REQ-EXT-5, REQ-EXT-11, REQ-EXT-13, REQ-EXT-14

---

### Task 1.1 — RED: DB schema + seeds tests

| Field | Value |
|-------|-------|
| Step | RED |
| Test file | `tests/test_openrouter_ranking_database.py` |
| Spec refs | REQ-EXT-2 (all scenarios), REQ-EXT-11 (seed scenarios) |
| Commit | `test(openrouter-ranking): RED database schema, seeds, upsert contracts` |

**What the tests assert (write these first; all must fail RED):**

- `test_new_tables_created_on_connect` — after `db.connect()` on `:memory:`, tables `benchmarks`, `model_benchmarks`, `phase_profiles`, `model_aliases`, `scrape_runs` all exist in `sqlite_master`.
- `test_benchmarks_seeded_8_rows` — `SELECT COUNT(*) FROM benchmarks` = 8 after connect; rows include slugs: `ifbench`, `multichallenge`, `tau2_bench_telecom`, `bfcl_v3`, `bfcl_parallel`, `aa_omniscience`, `ruler`, `longbench`.
- `test_inactive_benchmarks_have_zero_weight` — `multichallenge`, `ruler`, `longbench` rows have weight=0 in `phase_profiles` for phase `orchestrator`.
- `test_phase_profiles_seeded_orchestrator` — `SELECT COUNT(*) FROM phase_profiles WHERE phase='orchestrator'` = 8; active weights sum to 100.0 after excluding zeros.
- `test_seed_idempotent_on_reconnect` — connect, connect again (same `:memory:` instance calling `_create_schema` + `_seed_defaults` twice); row count remains 8 in `benchmarks`; no duplicates.
- `test_new_config_keys_seeded_14` — after connect, all 14 new config keys from REQ-EXT-11 exist with their specified defaults.
- `test_existing_config_keys_not_overwritten` — insert custom value for `enabled`, call `_seed_defaults` again; value remains unchanged.
- `test_upsert_model_benchmark_inserts` — call `db.upsert_model_benchmark(model_id="m1", benchmark_slug="bfcl_v3", score=0.85, source="bfcl_github")`; row appears in `model_benchmarks`.
- `test_upsert_model_benchmark_updates_on_conflict` — insert row, then upsert same (model_id, benchmark_slug) with new score; single row remains with updated score.
- `test_upsert_model_benchmark_updates_fetched_at` — two successive upserts; `fetched_at` in second call is >= first call.
- `test_get_benchmarks_returns_all` — `db.get_benchmarks()` returns list of 8 dicts.
- `test_get_phase_profile_returns_weights_dict` — `db.get_phase_profile("orchestrator")` returns dict mapping benchmark_slug → weight.
- `test_get_phase_profile_unknown_returns_none` — `db.get_phase_profile("nonexistent")` returns `None`.
- `test_get_model_benchmarks_for_phase_empty` — fresh DB, `db.get_model_benchmarks_for_phase("orchestrator")` returns `{}`.
- `test_insert_scrape_run_and_finish` — `db.start_scrape_run("aa")` returns int id; `db.finish_scrape_run(id, status="ok", rows_updated=3)` sets finished_at + status.

---

### Task 1.2 — GREEN: Extend database.py with new tables, seeds, CRUD

| Field | Value |
|-------|-------|
| Step | GREEN |
| Impl file | `src/bot/plugins/openrouter_prices/database.py` |
| Spec refs | REQ-EXT-2, REQ-EXT-11 |
| Commit | `feat(openrouter-ranking): extend database schema, seeds, CRUD methods` |

**What to implement:**

- In `_create_schema()`: add `CREATE TABLE IF NOT EXISTS` for all 5 new tables (benchmarks, model_benchmarks, phase_profiles, model_aliases, scrape_runs) with exact column sets from design DB Schema Summary.
- In `_seed_defaults()`: append 14 new `INSERT OR IGNORE` rows for REQ-EXT-11 config keys.
- New method `_seed_benchmarks()` called from `_seed_defaults`: 8 `INSERT OR IGNORE` rows into `benchmarks`.
- New method `_seed_phase_profiles()`: seed `orchestrator` profile into `phase_profiles` from `seeds/orchestrator_phase_weights.json`; use `INSERT OR IGNORE` so custom edits survive restart.
- New methods: `upsert_model_benchmark(model_id, benchmark_slug, score, raw_value, source)`, `get_benchmarks()`, `get_phase_profile(phase)`, `get_model_benchmarks_for_phase(phase)`, `start_scrape_run(source)`, `finish_scrape_run(run_id, status, rows_updated, error)`.

**Also create:**

- `src/bot/plugins/openrouter_prices/seeds/__init__.py` — empty.
- `src/bot/plugins/openrouter_prices/seeds/benchmarks_seed.json` — 8 benchmark rows (id/slug/display_name/source/higher_is_better).
- `src/bot/plugins/openrouter_prices/seeds/orchestrator_phase_weights.json` — 8 benchmark entries with weights per proposal table (IFBench=20, MultiChallenge=0, τ²-Bench=15, BFCL_v3=20, BFCL_parallel=15, AA_Omniscience=8, RULER=0, LongBench=0; total active = 78 → renormalized to 100 at compute time).

**All 15 tests in 1.1 must now pass GREEN.**

---

### Task 1.3 — RED: Pydantic models tests

| Field | Value |
|-------|-------|
| Step | RED |
| Test file | `tests/test_openrouter_ranking_models.py` |
| Spec refs | REQ-EXT-2, REQ-EXT-5, REQ-EXT-10 |
| Commit | `test(openrouter-ranking): RED Pydantic models BenchmarkRow, AliasRow, RankingEntry` |

**What the tests assert:**

- `test_benchmark_row_fields` — `BenchmarkRow(id=1, slug="bfcl_v3", display_name="BFCL v3", source="bfcl_github", higher_is_better=True)` instantiates without error; `.slug` is accessible.
- `test_alias_row_fields` — `AliasRow(openrouter_id="x/y", artificial_analysis_name=None, bfcl_key=None, match_confidence=None, matched=False)` instantiates.
- `test_alias_row_matched_true` — `matched=True` accepted.
- `test_ranking_entry_fields` — `RankingEntry(model_id="x/y", name="X Y", score=0.87, benchmark_breakdown={"bfcl_v3": 0.5})` instantiates; `.score` in [0,1].
- `test_scrape_run_row_fields` — `ScrapeRunRow(id=1, source="aa", started_at=..., finished_at=None, status="running", error=None, rows_updated=None)` instantiates.
- `test_alias_update_body_empty_ok` — `AliasUpdateBody()` (no fields) instantiates; all fields are `None`.

---

### Task 1.4 — GREEN: Add new Pydantic models to models.py

| Field | Value |
|-------|-------|
| Step | GREEN |
| Impl file | `src/bot/plugins/openrouter_prices/models.py` |
| Spec refs | REQ-EXT-2, REQ-EXT-5, REQ-EXT-10 |
| Commit | `feat(openrouter-ranking): add BenchmarkRow, AliasRow, RankingEntry, ScrapeRunRow models` |

**What to implement:**

- Add `BenchmarkRow`, `ModelBenchmark`, `AliasRow`, `AliasUpdateBody`, `RankingEntry`, `ScrapeRunRow` Pydantic models. All fields must match the column sets in the design DB Schema Summary. `AliasUpdateBody` fields all optional (empty PUT body is a no-op). Existing models untouched.

**All 6 tests in 1.3 must now pass GREEN.**

---

### Task 1.5 — RED: Ranking pure functions tests

| Field | Value |
|-------|-------|
| Step | RED |
| Test file | `tests/test_openrouter_ranking_ranking.py` |
| Spec refs | REQ-EXT-5 (all scenarios) |
| Commit | `test(openrouter-ranking): RED normalize_scores, weighted_score, rank_top_n` |

**What the tests assert:**

- `test_normalize_higher_is_better` — `normalize_scores({"a": 10.0, "b": 0.0, "c": 5.0}, higher_is_better=True)` == `{"a": 1.0, "b": 0.0, "c": 0.5}`.
- `test_normalize_lower_is_better` — `normalize_scores({"a": 10.0, "b": 0.0, "c": 5.0}, higher_is_better=False)` == `{"a": 0.0, "b": 1.0, "c": 0.5}`.
- `test_normalize_all_equal_returns_zeros` — all values equal → all 0.0 (avoid divide-by-zero).
- `test_normalize_single_value_returns_one` — single entry → 1.0 (higher_is_better=True) or 0.0 (lower).
- `test_weighted_score_basic` — two benchmarks with weights 60/40; weighted_score returns per-model float sum.
- `test_weighted_score_missing_model_zero` — model not in a benchmark dict contributes 0 for that benchmark; result is float (no NaN).
- `test_rank_top_n_sorted_descending` — 5 models, ask for top 3 → list of 3 tuples sorted score desc.
- `test_rank_top_n_fewer_than_n` — 2 models, ask for top 10 → list of 2.
- `test_renormalize_weights_excludes_zeros` — `renormalize_weights({"a": 20, "b": 0, "c": 80})` returns `{"a": 0.2, "b": 0.0, "c": 0.8}` (zeros preserved, actives sum to 1.0).
- `test_renormalize_all_zero_returns_empty` — all-zero weights → all 0.0 (no division by zero).
- `test_compute_ranking_returns_shape` — async test; inject mock `db` returning canned phase_profile + model_benchmarks for 12 models; `compute_ranking_for_phase(db, "orchestrator", n=10)` returns list of 10 dicts each with keys `model_id`, `name`, `score`; sorted desc.
- `test_compute_ranking_unknown_phase_returns_none` — mock db returns `None` for phase_profile → function returns `None` (API layer converts to 404).

---

### Task 1.6 — GREEN: Implement ranking.py pure functions

| Field | Value |
|-------|-------|
| Step | GREEN |
| Impl file | `src/bot/plugins/openrouter_prices/ranking.py` (new file) |
| Spec refs | REQ-EXT-5 |
| Commit | `feat(openrouter-ranking): pure ranking functions normalize, weighted_score, rank_top_n` |

**What to implement:**

Exactly the four function signatures from the design:
```
normalize_scores(values: dict[str, float], higher_is_better: bool = True) -> dict[str, float]
weighted_score(per_benchmark: dict[str, dict[str, float]], weights: dict[str, float]) -> dict[str, float]
rank_top_n(scores: dict[str, float], n: int) -> list[tuple[str, float]]
renormalize_weights(weights: dict[str, float]) -> dict[str, float]
async compute_ranking_for_phase(db, phase: str, n: int = 10) -> list[dict] | None
```

- `normalize_scores`: min-max to [0,1]; if max==min return all 0.0.
- `weighted_score`: for each model, sum `normalized_per_benchmark[model] * weight` for each benchmark; missing model key in a benchmark dict → 0.0.
- `rank_top_n`: sort dict by value desc, return top n as list of (model_id, score) tuples.
- `renormalize_weights`: sum active (>0) weights; divide each by sum; zeros remain 0.0.
- `compute_ranking_for_phase`: calls `db.get_phase_profile(phase)` (None → return None); calls `db.get_model_benchmarks_for_phase(phase)`; builds per-benchmark score dicts; normalizes each; computes weighted_score per model; rank_top_n; returns list of dicts `{model_id, name, score}`.

**All 12 tests in 1.5 must now pass GREEN.**

---

### Task 1.7 — RED: Alias resolver tests

| Field | Value |
|-------|-------|
| Step | RED |
| Test file | `tests/test_openrouter_ranking_aliases.py` |
| Spec refs | REQ-EXT-3 (fuzzy scenarios), REQ-EXT-10 |
| Commit | `test(openrouter-ranking): RED fuzzy_match, resolve_alias` |

**What the tests assert:**

- `test_fuzzy_match_above_threshold` — `fuzzy_match("Claude 3.5 Sonnet", ["Claude 3.5 Sonnet", "GPT-4o"], threshold=0.75)` returns `("Claude 3.5 Sonnet", ratio >= 0.75)`.
- `test_fuzzy_match_below_threshold` — `fuzzy_match("ZZZ-Unknown", ["Claude 3.5 Sonnet", "GPT-4o"], threshold=0.75)` returns `(None, ratio < 0.75)`.
- `test_fuzzy_match_empty_candidates` — returns `(None, 0.0)`.
- `test_fuzzy_match_exact` — exact string match returns ratio 1.0.
- `test_fuzzy_match_picks_best_among_multiple` — three candidates; returns the one with highest ratio.
- `test_resolve_alias_finds_existing_explicit` — db has explicit alias for `openrouter_id` with `artificial_analysis_name` set → returns that name without fuzzy logic.
- `test_resolve_alias_fuzzy_above_threshold_upserts_matched` — no explicit alias; `source="aa"`, `external_name="Claude 3.5 Sonnet"`, OR slug candidates contain "claude-3.5-sonnet" (similar enough) → inserts/updates `model_aliases` with `matched=True`; returns openrouter_id.
- `test_resolve_alias_fuzzy_below_threshold_upserts_unmatched` — ratio < 0.75 → inserts row with `matched=False`; returns `None`.
- `test_resolve_alias_uses_cached_alias` — alias row already exists with `matched=True`; no fuzzy computation needed; returns cached name directly.

---

### Task 1.8 — GREEN: Implement aliases.py

| Field | Value |
|-------|-------|
| Step | GREEN |
| Impl file | `src/bot/plugins/openrouter_prices/aliases.py` (new file) |
| Spec refs | REQ-EXT-3, REQ-EXT-10 |
| Commit | `feat(openrouter-ranking): aliases fuzzy_match and resolve_alias` |

**What to implement:**

```python
def fuzzy_match(target: str, candidates: list[str], threshold: float = 0.75) -> tuple[str | None, float]
async def resolve_alias(db, openrouter_id: str, source: str, external_name: str) -> str | None
```

- `fuzzy_match`: iterate candidates using `difflib.SequenceMatcher(None, target.lower(), c.lower()).ratio()`; return best match above threshold or `(None, best_ratio)` if all below.
- `resolve_alias`: check `model_aliases` for existing row for `openrouter_id`; if explicit mapping exists for `source`, return it; otherwise fuzzy-match `external_name` against all known OR slugs from DB; upsert `model_aliases` with result; return matched id or `None`.
- Add DB methods needed: `get_alias(openrouter_id)`, `upsert_alias(openrouter_id, source, external_name, matched, confidence)`, `list_all_model_slugs()` → these go into `database.py` as part of this task's GREEN step.

**All 9 tests in 1.7 must now pass GREEN.**

---

### Task 1.9 — Regression check PR 1

| Field | Value |
|-------|-------|
| Step | VERIFY |
| Command | `uv run pytest` |
| Spec refs | REQ-EXT-13, REQ-EXT-14 |
| Commit | (no new commit — verification only) |

**Criteria:**
- All original 121 tests still green.
- All new tests in `test_openrouter_ranking_database.py`, `test_openrouter_ranking_models.py`, `test_openrouter_ranking_ranking.py`, `test_openrouter_ranking_aliases.py` pass.
- No individual test exceeds 5s.
- Spanish audit: `rg -n "tenés|podés|querés|configurá|seleccioná|ejecutá|reiniciá|guardá|vos sos" src/bot/plugins/openrouter_prices/` must return no matches.

---

## PR 2 — Scrapers + Scheduler

**Goal**: Both scrapers fully mocked and tested; PluginScheduler loop tested with injected clock. No real Chromium, no real GitHub, no real Discord. ~600–700 lines including tests.

**Spec coverage**: REQ-EXT-1, REQ-EXT-3, REQ-EXT-4, REQ-EXT-6, REQ-EXT-13

**Sequential dependency**: Must merge after PR 1 (uses DB methods and aliases.py from PR 1).

---

### Task 2.1 — [x] RED: Scraper base + BFCL tests

| Field | Value |
|-------|-------|
| Step | RED |
| Test file | `tests/test_openrouter_ranking_bfcl.py` |
| Spec refs | REQ-EXT-4 (all scenarios) |
| Commit | `test(openrouter-ranking): RED BFCLScraper with mocked httpx` |

**What the tests assert:**

- `test_bfcl_scraper_discovers_latest_folder` — mock `httpx.AsyncClient.get` for Contents API returns 3 dated folders; scraper picks latest YYYY-MM-DD.
- `test_bfcl_scraper_upserts_scores` — mock returns canned `overall_results.json` with 3 model entries; after `scraper.scrape(db)`, `model_benchmarks` has rows for `bfcl_v3` and `bfcl_parallel` for those models.
- `test_bfcl_scraper_rate_limit_preserves_cache` — mock returns 403; existing `model_benchmarks` rows unchanged; `push_event` called with `title="Scrape BFCL fallo"`.
- `test_bfcl_scraper_network_error_preserves_cache` — mock raises `httpx.ConnectError`; cache preserved; activity error event emitted.
- `test_bfcl_scraper_skipped_within_interval` — `last_run_at` = now - 1h; `bfcl_scrape_interval_days = 7`; scraper returns early; no HTTP call made.
- `test_bfcl_scrape_run_recorded` — successful scrape; `scrape_runs` has a finished row with `status="ok"`.
- `test_bfcl_key_map_constant_exists` — `BFCLScraper.BFCL_KEY_MAP` dict has keys `"overall_accuracy"` and `"parallel_function"`.

---

### Task 2.2 — [x] GREEN: Implement scrapers/base.py + scrapers/bfcl.py

| Field | Value |
|-------|-------|
| Step | GREEN |
| Impl files | `src/bot/plugins/openrouter_prices/scrapers/__init__.py`, `src/bot/plugins/openrouter_prices/scrapers/base.py`, `src/bot/plugins/openrouter_prices/scrapers/bfcl.py` |
| Spec refs | REQ-EXT-4 |
| Commit | `feat(openrouter-ranking): scrapers base Protocol + BFCLScraper` |

**What to implement:**

- `scrapers/base.py`: `ScrapeResult` dataclass `(source: str, rows_updated: int, error: str | None)`; `Scraper` Protocol with `async def scrape(db) -> ScrapeResult`.
- `scrapers/bfcl.py`: `BFCLScraper` — `BFCL_KEY_MAP = {"overall_accuracy": "bfcl_v3", "parallel_function": "bfcl_parallel"}`; constructor takes `client: httpx.AsyncClient | None = None` (injectable for tests); GitHub Contents API URL + raw URL constants; `_should_skip(db)` checks `scrape_runs` last run vs config interval; `async def scrape(db) -> ScrapeResult`; all exceptions caught; `push_event` on error; `start_scrape_run` / `finish_scrape_run` called.

**All 7 tests in 2.1 must now pass GREEN.**

---

### Task 2.3 — [x] RED: Artificial Analysis scraper tests

| Field | Value |
|-------|-------|
| Step | RED |
| Test file | `tests/test_openrouter_ranking_aa.py` |
| Spec refs | REQ-EXT-3 (all scenarios) |
| Commit | `test(openrouter-ranking): RED ArtificialAnalysisScraper with mock Page DI` |

**What the tests assert:**

- `test_aa_scraper_extracts_scores_from_canned_html` — inject `page_factory` returning `MockPage` with pre-baked table HTML; `scraper.scrape(db)` → `model_benchmarks` upserted for IFBench, τ²-Bench Telecom, AA-Omniscience.
- `test_aa_scraper_unknown_model_below_threshold` — canned HTML model name has ratio < 0.75 against any OR slug; row inserted into `model_aliases` with `matched=False`; no `model_benchmarks` row.
- `test_aa_scraper_dom_failure_emits_event` — `page_factory` raises `Exception("selector error")`; `push_event` called with `title="Scrape Artificial Analysis fallo"`; DB unmodified.
- `test_aa_scraper_skipped_within_interval` — `last_run_at` = now - 2h, interval = 7 days; no `page_factory` call made.
- `test_aa_scraper_debug_snapshot_on_failure` — on DOM exception, debug HTML snapshot written to `tmp_path`; path contains `aa_debug_`.
- `test_aa_scrape_run_recorded_on_success` — `scrape_runs` has `status="ok"` after successful scrape.
- `test_aa_no_real_chromium_launched` — `page_factory` mock is called (not `async_playwright`); `async_playwright` not imported in test.

---

### Task 2.4 — [x] GREEN: Implement scrapers/artificial_analysis.py

| Field | Value |
|-------|-------|
| Step | GREEN |
| Impl file | `src/bot/plugins/openrouter_prices/scrapers/artificial_analysis.py` |
| Spec refs | REQ-EXT-3 |
| Commit | `feat(openrouter-ranking): ArtificialAnalysisScraper with DI page_factory` |

**What to implement:**

- `ArtificialAnalysisScraper(page_factory=None, debug_dir=None)` — `page_factory` is `Callable[[], Awaitable[Page]]`; defaults to real Playwright `async_playwright` launch when `None`.
- Constants: `AA_URL`, `AA_TABLE_SELECTOR = '[data-testid="models-table"]'` (note: tentative, comment in code).
- `_should_skip(db)`, `async def scrape(db) -> ScrapeResult`.
- On DOM exception: write `data/plugins/aa_debug_<timestamp>.html` (configurable via `debug_dir`); emit activity event; return `ScrapeResult(error=str(e))`.
- Real Playwright code path marked `# pragma: no cover` — only exercised under `@pytest.mark.slow`.

**All 7 tests in 2.3 must now pass GREEN.**

---

### Task 2.5 — [x] RED: Scheduler tests

| Field | Value |
|-------|-------|
| Step | RED |
| Test file | `tests/test_openrouter_ranking_scheduler.py` |
| Spec refs | REQ-EXT-1, REQ-EXT-6 (all scenarios) |
| Commit | `test(openrouter-ranking): RED PluginScheduler lifecycle and job dispatch` |

**What the tests assert:**

- `test_scheduler_starts_background_task` — `await scheduler.start()`; task is running (`not task.done()`).
- `test_scheduler_stops_cleanly` — start then `await scheduler.stop()`; no `asyncio.CancelledError` propagates; task is done.
- `test_tick_dispatches_aa_when_due` — inject `_now_fn` returning T+7days; mock AA scraper spy; call `_tick()` directly; AA scraper called once.
- `test_tick_skips_aa_when_not_due` — `_now_fn` returning T+1h; AA scraper NOT called.
- `test_tick_dispatches_bfcl_when_due` — analogous to AA test.
- `test_tick_job_exception_does_not_crash_scheduler` — mock scraper raises `RuntimeError`; activity event emitted; scheduler loop still running after exception.
- `test_trigger_scrape_returns_true_when_idle` — `scheduler.trigger_scrape("aa")` returns `True` when no scrape in progress.
- `test_trigger_scrape_returns_false_when_busy` — set internal `_scraping["aa"] = True`; `trigger_scrape("aa")` returns `False` (409 case).
- `test_scheduler_reads_config_interval_from_db` — `openrouter_refresh_interval_hours=12` in db config; scheduler uses 12h, not hardcoded 24h.
- `test_new_model_detected_emits_event` — mock `client.fetch_models()` returns model not in `or_models`; scheduler sync job calls `push_event(kind="openrouter", title="Modelo OpenRouter nuevo detectado")`.
- `test_no_event_when_no_new_model` — all model IDs already in DB; no event emitted.
- `test_sync_failure_emits_error_event` — `client.fetch_models()` raises; `push_event(title="Sincronizacion OpenRouter fallo")` called; loop continues.

---

### Task 2.6 — [x] GREEN: Implement scheduler.py

| Field | Value |
|-------|-------|
| Step | GREEN |
| Impl file | `src/bot/plugins/openrouter_prices/scheduler.py` (new file) |
| Spec refs | REQ-EXT-1, REQ-EXT-6 |
| Commit | `feat(openrouter-ranking): PluginScheduler async task loop with injected clock` |

**What to implement:**

```python
class PluginScheduler:
    def __init__(self, bot, db, client, aa_scraper_factory, bfcl_scraper,
                 _now_fn: Callable[[], float] = time.time): ...
    async def start(self) -> None
    async def stop(self) -> None
    async def _tick_loop(self) -> None   # while not stop_event: await asyncio.sleep(60); await _tick()
    async def _tick(self) -> None        # check each job interval; dispatch
    async def trigger_scrape(self, source: str) -> bool
    def is_scraping(self, source: str) -> bool
```

- `asyncio.Event` for stop signal; `_scraping: dict[str, bool]` for 409 guard.
- Each job in `_tick` wrapped in `try/except Exception`; errors push activity event.
- `_now_fn` injectable so tests can advance time without real sleep.
- OR sync job: fetch models, compare IDs to `db.list_model_ids()`, emit per-new-model events, upsert.

**All 12 tests in 2.5 must now pass GREEN.**

---

### Task 2.7 — [x] Regression check PR 2 (242 passed)

| Field | Value |
|-------|-------|
| Step | VERIFY |
| Command | `uv run pytest` |
| Spec refs | REQ-EXT-13, REQ-EXT-14 |

**Criteria:**
- All original 121 tests green.
- All PR 1 + PR 2 new tests green.
- No test exceeds 5s.
- Spanish audit: same `rg` check extended to new scraper and scheduler files.

---

## PR 3 — API + Embeds + Wiring + Integration

**Goal**: All 6 new API endpoints, embed builders, `__init__.py` wiring with teardown, `web/app.py` teardown_callbacks pattern, integration smoke tests. ~500–600 lines including tests.

**Spec coverage**: REQ-EXT-7, REQ-EXT-8, REQ-EXT-9, REQ-EXT-10, REQ-EXT-11 (PUT validation), REQ-EXT-12, REQ-EXT-13, REQ-EXT-14, REQ-7 (modified), REQ-2 (modified)

**Sequential dependency**: Must merge after PR 2.

---

### Task 3.1 — RED: Discord embed builder tests

| Field | Value |
|-------|-------|
| Step | RED |
| Test file | `tests/test_openrouter_ranking_embeds.py` |
| Spec refs | REQ-EXT-7, REQ-EXT-8 |
| Commit | `test(openrouter-ranking): RED embed builders weekly price report and ranking` |

**What the tests assert:**

- `test_weekly_price_embed_title` — `build_weekly_price_embed(models=[...])` returns `discord.Embed` with non-empty title (Spanish).
- `test_weekly_price_embed_fields_count` — 10 models → embed has exactly 10 fields.
- `test_weekly_price_embed_truncated_at_6000_chars` — inject 50 models with long names; embed total char count ≤ 6000; footer contains "Lista recortada".
- `test_ranking_embed_title` — `build_ranking_embed(entries=[...], phase="orchestrator")` returns embed with title.
- `test_ranking_embed_top10_cap` — 15 entries passed; embed has exactly 10 fields.
- `test_ranking_embed_rank_change_marker` — `previous_top1="old/model"`, entries[0].model_id="new/model" → embed field for rank 1 contains "Subio al #1".
- `test_ranking_embed_no_marker_when_same_top1` — previous_top1 == entries[0].model_id → no rank-change marker.
- `test_ranking_embed_insufficient_data_warning` — fewer than 5 entries → embed description contains "Datos insuficientes".
- `test_embed_score_two_decimal_places` — score field value matches regex `\d+\.\d{2}`.
- `test_embed_benchmark_breakdown_top3` — each entry's field shows at most 3 benchmark names.

---

### Task 3.2 — GREEN: Implement discord_embeds.py

| Field | Value |
|-------|-------|
| Step | GREEN |
| Impl file | `src/bot/plugins/openrouter_prices/discord_embeds.py` (new file) |
| Spec refs | REQ-EXT-7, REQ-EXT-8 |
| Commit | `feat(openrouter-ranking): discord_embeds weekly price report and ranking embed builders` |

**What to implement:**

```python
def build_weekly_price_embed(models: list[dict], count: int = 10) -> discord.Embed
def build_ranking_embed(entries: list[RankingEntry], phase: str,
                        previous_top1: str | None = None) -> discord.Embed
```

- Both functions: build `discord.Embed`; enforce 25-field Discord limit (top 10 cap); truncate total to < 6000 chars; add "Lista recortada" footer when truncated.
- `build_ranking_embed`: detect top-1 change; "Datos insuficientes" warning when < 5 entries; score formatted `f"{entry.score:.2f}"`; top-3 benchmark breakdown from `entry.benchmark_breakdown`.
- All user-visible strings in Spanish neutro peruano.

**All 10 tests in 3.1 must now pass GREEN.**

---

### Task 3.3 — RED: New API endpoints tests

| Field | Value |
|-------|-------|
| Step | RED |
| Test file | `tests/test_openrouter_ranking_api.py` |
| Spec refs | REQ-EXT-9, REQ-EXT-10, REQ-EXT-11, REQ-2 |
| Commit | `test(openrouter-ranking): RED new API endpoints rankings, benchmarks, scrape, aliases` |

**What the tests assert (FastAPI TestClient + mocked scheduler/db):**

- `test_get_rankings_known_phase` — mock db returns 10 ranking entries; `GET /rankings/orchestrator` → 200 with list of 10 items each having `model_id`, `name`, `score`, `benchmark_breakdown`.
- `test_get_rankings_unknown_phase` — `GET /rankings/unknown` → 404 `{"detail": "Perfil de fase no encontrado"}`.
- `test_get_benchmarks` — mock db returns 8 benchmarks; `GET /benchmarks` → 200 list of 8 items.
- `test_post_scrape_valid_source_aa` — `POST /scrape/aa` → 200 `{"started": true, "source": "aa"}`.
- `test_post_scrape_invalid_source` — `POST /scrape/unknown` → 400 `{"detail": "Fuente de scrape invalida. Valores permitidos: openrouter, aa, bfcl"}`.
- `test_post_scrape_conflict` — mock `scheduler.trigger_scrape("bfcl")` returns False → 409 `{"detail": "Scrape ya en curso"}`.
- `test_get_aliases` — mock db returns 3 alias rows; `GET /aliases` → 200 list of 3.
- `test_put_alias_updates` — `PUT /aliases/anthropic%2Fclaude-3-haiku` with body `{"artificial_analysis_name": "Claude 3 Haiku"}` → 200 updated row.
- `test_put_alias_not_found` — model_id not in db → 404.
- `test_put_alias_empty_body_noop` — `{}` body → 200 current row unchanged.
- `test_put_config_invalid_interval_zero` — `{"openrouter_refresh_interval_hours": "0"}` → 400 `{"detail": "openrouter_refresh_interval_hours debe ser mayor a 0"}`.
- `test_put_config_invalid_boolean` — `{"aa_scrape_enabled": "maybe"}` → 400 `{"detail": "aa_scrape_enabled debe ser 'true' o 'false'"}`.
- `test_get_scrape_runs` — `GET /scrape-runs` → 200 list; `GET /scrape-runs?source=aa` filters by source.

---

### Task 3.4 — GREEN: Extend api.py with new endpoints + PUT /config validation

| Field | Value |
|-------|-------|
| Step | GREEN |
| Impl file | `src/bot/plugins/openrouter_prices/api.py` |
| Spec refs | REQ-EXT-9, REQ-EXT-10, REQ-EXT-11, REQ-2 |
| Commit | `feat(openrouter-ranking): new API endpoints rankings, benchmarks, scrape, aliases` |

**What to implement:**

Append to existing `api.py`:
- `GET /rankings/{phase}` → `compute_ranking_for_phase(db, phase)` or 404.
- `GET /benchmarks` → `db.get_benchmarks()`.
- `POST /scrape/{source}` → validate source in `{"openrouter", "aa", "bfcl"}`; call `scheduler.trigger_scrape(source)`; 200/400/409.
- `GET /aliases` → `db.list_aliases()`.
- `PUT /aliases/{openrouter_id}` → `db.update_alias(...)`; 200/404; empty body is no-op.
- `GET /scrape-runs` (with optional `?source=` and `?limit=`) → `db.list_scrape_runs(...)`.
- Extend PUT `/config` validation: check new key names; validate interval > 0; validate boolean strings; Spanish neutro error messages.
- All error `detail` strings: Spanish neutro peruano; no Rioplatense forms.

**All 13 tests in 3.3 must now pass GREEN.**

---

### Task 3.5 — RED: Lifespan teardown + __init__.py wiring tests

| Field | Value |
|-------|-------|
| Step | RED |
| Test file | `tests/test_openrouter_ranking_scheduler.py` (extend existing file, new class) |
| Spec refs | REQ-EXT-6 (clean shutdown), REQ-7 (modified) |
| Commit | `test(openrouter-ranking): RED teardown_callbacks wiring and scheduler lifecycle via setup` |

**What the tests assert:**

- `test_setup_stores_scheduler_on_app_state` — call `setup(mock_bot, mock_cm, mock_app)`; `app.state.openrouter_prices_scheduler` is a `PluginScheduler` instance.
- `test_setup_appends_teardown_callback` — after `setup()`, `app.state.teardown_callbacks` has one callable.
- `test_teardown_callback_stops_scheduler` — call the teardown callable; `scheduler.stop()` called once.
- `test_lifespan_iterates_teardown_callbacks` — use `AsyncClient` on a real `create_app()` + `setup()`; lifespan `__aexit__` calls teardown_callbacks; no pending-task asyncio warnings.

---

### Task 3.6 — GREEN: Extend __init__.py setup() + web/app.py teardown_callbacks

| Field | Value |
|-------|-------|
| Step | GREEN |
| Impl files | `src/bot/plugins/openrouter_prices/__init__.py`, `src/web/app.py` |
| Spec refs | REQ-EXT-6, REQ-7 |
| Commit | `feat(openrouter-ranking): wire PluginScheduler into setup() and teardown_callbacks` |

**What to implement:**

- `web/app.py`: in `create_app()`, set `app.state.teardown_callbacks = []`. In `_lifespan`, after `yield`, iterate and `await cb()` for each in `app.state.teardown_callbacks`.
- `__init__.py` `setup()`: import `PluginScheduler`; instantiate with `bot`, `db`, `client`, scraper factories; call `await scheduler.start()`; store on `app.state.openrouter_prices_scheduler`; append `scheduler.stop` to `app.state.teardown_callbacks`.

**All 4 tests in 3.5 must now pass GREEN.**

---

### Task 3.7 — RED: Integration smoke test

| Field | Value |
|-------|-------|
| Step | RED |
| Test file | `tests/test_openrouter_ranking_integration.py` (new file) |
| Spec refs | REQ-EXT-14, REQ-2 |
| Commit | `test(openrouter-ranking): RED integration smoke setup→GET /rankings/orchestrator` |

**What the tests assert:**

- `test_existing_models_endpoint_unchanged` — full setup on `:memory:` DB; `GET /models?text_only=true&limit=5` shape identical to pre-extension shape.
- `test_rankings_endpoint_returns_empty_list_fresh_db` — fresh DB (no model_benchmarks rows); `GET /rankings/orchestrator` → 200 with empty list (not error).
- `test_benchmarks_endpoint_returns_8_rows` — `GET /benchmarks` → 200 with 8 items.
- `test_setup_teardown_no_pending_tasks` — setup + lifespan close; no asyncio warnings in stderr.
- `test_original_121_still_green` — marker test: assert `True` (actual verification is the `uv run pytest` run below).

---

### Task 3.8 — GREEN: Wire integration test + final regression

| Field | Value |
|-------|-------|
| Step | GREEN + VERIFY |
| Command | `uv run pytest` |
| Spec refs | REQ-EXT-13, REQ-EXT-14 |
| Commit | `test(openrouter-ranking): integration smoke tests` (test file only) |

**Criteria for GREEN:**
- All 5 integration tests pass.
- `uv run pytest` shows 121 + all new tests green.
- No individual test exceeds 5s.

**Spanish audit (final, mandatory):**
```
rg -n "tenés|podés|querés|configurá|seleccioná|ejecutá|reiniciá|guardá|vos sos|che " \
  src/bot/plugins/openrouter_prices/ tests/test_openrouter_ranking_
```
Must return zero matches.

---

## Task Dependency Graph

```
PR 1 (foundation — no deps):
  1.1 (RED db) → 1.2 (GREEN db) → 1.3 (RED models) → 1.4 (GREEN models)
                                 → 1.5 (RED ranking) → 1.6 (GREEN ranking)
                                 → 1.7 (RED aliases) → 1.8 (GREEN aliases)
  → 1.9 (regression check PR1)

PR 2 (deps: PR1 merged):
  2.1 (RED bfcl) → 2.2 (GREEN bfcl)
  2.3 (RED aa)   → 2.4 (GREEN aa)
  2.5 (RED sched)→ 2.6 (GREEN sched)
  → 2.7 (regression check PR2)

PR 3 (deps: PR2 merged):
  3.1 (RED embeds)→ 3.2 (GREEN embeds)
  3.3 (RED api)  → 3.4 (GREEN api)
  3.5 (RED wiring)→ 3.6 (GREEN wiring)
  3.7 (RED integ) → 3.8 (GREEN integ + verify)
```

**Parallel within PR 1**: Tasks 1.3+1.5+1.7 (RED steps for models, ranking, aliases) can be written in parallel since they have no inter-dependency. Their GREEN steps all depend on 1.2 completing first.

**Parallel within PR 2**: Tasks 2.1 and 2.3 (BFCL and AA RED) can be written in parallel.

**Parallel within PR 3**: Tasks 3.1 and 3.3 (embeds and API RED) can be written in parallel.

---

## File Manifest

### PR 1

| File | Action |
|------|--------|
| `src/bot/plugins/openrouter_prices/database.py` | Modified |
| `src/bot/plugins/openrouter_prices/models.py` | Modified |
| `src/bot/plugins/openrouter_prices/ranking.py` | Created |
| `src/bot/plugins/openrouter_prices/aliases.py` | Created |
| `src/bot/plugins/openrouter_prices/seeds/__init__.py` | Created |
| `src/bot/plugins/openrouter_prices/seeds/benchmarks_seed.json` | Created |
| `src/bot/plugins/openrouter_prices/seeds/orchestrator_phase_weights.json` | Created |
| `tests/test_openrouter_ranking_database.py` | Created |
| `tests/test_openrouter_ranking_models.py` | Created |
| `tests/test_openrouter_ranking_ranking.py` | Created |
| `tests/test_openrouter_ranking_aliases.py` | Created |

### PR 2

| File | Action |
|------|--------|
| `src/bot/plugins/openrouter_prices/scrapers/__init__.py` | Created |
| `src/bot/plugins/openrouter_prices/scrapers/base.py` | Created |
| `src/bot/plugins/openrouter_prices/scrapers/bfcl.py` | Created |
| `src/bot/plugins/openrouter_prices/scrapers/artificial_analysis.py` | Created |
| `src/bot/plugins/openrouter_prices/scheduler.py` | Created |
| `tests/test_openrouter_ranking_bfcl.py` | Created |
| `tests/test_openrouter_ranking_aa.py` | Created |
| `tests/test_openrouter_ranking_scheduler.py` | Created |

### PR 3

| File | Action |
|------|--------|
| `src/bot/plugins/openrouter_prices/api.py` | Modified |
| `src/bot/plugins/openrouter_prices/__init__.py` | Modified |
| `src/bot/plugins/openrouter_prices/discord_embeds.py` | Created |
| `src/web/app.py` | Modified |
| `tests/test_openrouter_ranking_embeds.py` | Created |
| `tests/test_openrouter_ranking_api.py` | Created (extends existing) |
| `tests/test_openrouter_ranking_integration.py` | Created |
