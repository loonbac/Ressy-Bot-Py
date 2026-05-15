# Apply Progress — openrouter-ranking PR 1 + PR 2

## Scope (PR 1 of 3)

Tasks 1.1–1.9: ranking pure functions, aliases fuzzy match, DB schema extensions,
seeds JSON, Pydantic models. No scrapers, no scheduler, no API endpoints.

## TDD Cycle Evidence (PR 1)

| Task | RED file:test | RED status | GREEN file | GREEN status | Notes |
|------|--------------|------------|------------|--------------|-------|
| 1.1 Write ranking tests | tests/test_openrouter_ranking_ranking.py | ModuleNotFoundError (CORRECT RED) | src/.../ranking.py | 32 passed | Pure functions + async compute_ranking_for_phase with MockDB |
| 1.2 Implement ranking.py | src/.../ranking.py | — | tests/...ranking.py | 32 GREEN | normalize_higher/lower, weighted_score, rank_top_n, compute_ranking_for_phase |
| 1.3 Write aliases tests | tests/test_openrouter_ranking_aliases.py | ModuleNotFoundError (CORRECT RED) | src/.../aliases.py | 13 passed | fuzzy_match + resolve_alias with :memory: DB |
| 1.4 Implement aliases.py | src/.../aliases.py | — | tests/...aliases.py | 13 GREEN | difflib.SequenceMatcher, threshold 0.75 |
| 1.5 Write DB ext tests | tests/test_openrouter_ranking_database_ext.py | 28 FAILED (schema missing) | database.py | 29 GREEN | 5 new tables, seeds, CRUD |
| 1.6 Extend database.py schema | src/.../database.py | — | — | — | 5 new tables + indexes |
| 1.7 Add seed methods | src/.../database.py | — | — | — | _seed_benchmarks + _seed_phase_profile |
| 1.8 Add DB CRUD methods | src/.../database.py | — | — | — | get_benchmarks, upsert_model_benchmark, list_model_benchmarks, get_phase_profile, get_alias, upsert_alias, list_aliases, list_all_model_slugs, record_scrape_run, list_scrape_runs |
| 1.9 Add Pydantic models | src/.../models.py | — | — | GREEN | BenchmarkRow, ModelBenchmarkRow, PhaseProfileEntry, AliasRow, ScrapeRun, RankingBreakdown, RankingEntry, RankingResponse |

## Files Created (PR 1)

- `src/bot/plugins/openrouter_prices/ranking.py` — pure functions (normalize, weighted_score, rank_top_n, compute_ranking_for_phase)
- `src/bot/plugins/openrouter_prices/aliases.py` — fuzzy_match + resolve_alias
- `src/bot/plugins/openrouter_prices/seeds/__init__.py` — marker vacío
- `src/bot/plugins/openrouter_prices/seeds/benchmarks_seed.json` — 8 benchmarks
- `src/bot/plugins/openrouter_prices/seeds/orchestrator_phase_weights.json` — 11 entradas (8 benchmarks + 3 feature factors)
- `tests/test_openrouter_ranking_ranking.py` — 32 tests
- `tests/test_openrouter_ranking_aliases.py` — 13 tests
- `tests/test_openrouter_ranking_database_ext.py` — 29 tests

## Files Modified (PR 1)

- `src/bot/plugins/openrouter_prices/database.py` — 5 nuevas tablas (benchmarks, model_benchmarks, phase_profiles, model_aliases, scrape_runs), 1 nuevo índice, 14 nuevas claves config (REQ-EXT-11), métodos: get_benchmarks, upsert_model_benchmark, list_model_benchmarks, get_phase_profile, get_alias, upsert_alias, list_aliases, list_all_model_slugs, record_scrape_run, list_scrape_runs, _seed_benchmarks, _seed_phase_profile
- `src/bot/plugins/openrouter_prices/models.py` — añadidos: BenchmarkRow, ModelBenchmarkRow, PhaseProfileEntry, AliasRow, ScrapeRun, RankingBreakdown, RankingEntry, RankingResponse

## Test Results (PR 1)

```
tests/test_openrouter_ranking_ranking.py      32 passed
tests/test_openrouter_ranking_aliases.py      13 passed
tests/test_openrouter_ranking_database_ext.py 29 passed
Total new tests: 74 passed
```

## Regression Check (PR 1)

```
tests/test_openrouter_prices_database.py      31 passed
tests/test_openrouter_prices_models.py        18 passed
tests/test_openrouter_prices_client.py         9 passed
tests/test_openrouter_prices_cog.py           22 passed
tests/test_openrouter_prices_api.py           21 passed
tests/test_openrouter_prices_integration.py   15 passed
Total existing openrouter tests: 116 passed (100% green)
```

---

## Scope (PR 2 of 3)

Tasks 2.1–2.7 COMPLETE: scrapers/base.py (ScrapeResult + Scraper Protocol), scrapers/bfcl.py
(httpx mocked, GitHub Contents API), scrapers/artificial_analysis.py (DI page_factory,
no Chromium real en tests), scheduler.py (PluginScheduler con time_provider inyectado).

## TDD Cycle Evidence (PR 2)

| Task | RED file:test | RED status | GREEN file | GREEN status | Notes |
|------|--------------|------------|------------|--------------|-------|
| 2.1 Write scrapers/base tests | tests/test_openrouter_ranking_scrapers_base.py | ModuleNotFoundError (CORRECT RED) | scrapers/base.py | 8 passed | ScrapeResult dataclass + Scraper Protocol runtime_checkable |
| 2.2 Implement scrapers/base.py | scrapers/base.py | — | tests/...scrapers_base.py | 8 GREEN | @runtime_checkable Protocol, field(default_factory=list) |
| 2.3 Write bfcl scraper tests | tests/test_openrouter_ranking_scrapers_bfcl.py | ModuleNotFoundError (CORRECT RED) | scrapers/bfcl.py | 14 passed | 14 tests: ok, 403, 404, empty folder, malformed JSON, alias paths |
| 2.4 Implement scrapers/bfcl.py | scrapers/bfcl.py | — | tests/...scrapers_bfcl.py | 14 GREEN | LEADERBOARD_FILE_PROBES list, BFCL_KEY_MAP, GitHub Contents sort desc |
| 2.5 Write AA scraper tests | tests/test_openrouter_ranking_scrapers_aa.py | ModuleNotFoundError (CORRECT RED) | scrapers/artificial_analysis.py | 14 passed | 14 tests: ok, DOM changed, fallback selector, alias resolution |
| 2.6 Implement scrapers/artificial_analysis.py | scrapers/artificial_analysis.py | — | tests/...scrapers_aa.py | 14 GREEN | _SELECTORS fallback list, page_factory DI, nth-child cell extraction |
| 2.7 Implement scheduler.py + tests | tests/test_openrouter_ranking_scheduler.py | ModuleNotFoundError (CORRECT RED) | scheduler.py | 16 passed | time_provider inyectado, per-job try/except, start/stop asyncio.CancelledError |

## Files Created (PR 2)

- `src/bot/plugins/openrouter_prices/scrapers/__init__.py` — marker con docstring
- `src/bot/plugins/openrouter_prices/scrapers/base.py` — ScrapeResult + Scraper Protocol
- `src/bot/plugins/openrouter_prices/scrapers/bfcl.py` — BFCLScraper (GITHUB_CONTENTS_URL, LEADERBOARD_FILE_PROBES, BFCL_KEY_MAP)
- `src/bot/plugins/openrouter_prices/scrapers/artificial_analysis.py` — ArtificialAnalysisScraper (DI page_factory, _SELECTORS fallback, _parse_percentage)
- `src/bot/plugins/openrouter_prices/scheduler.py` — PluginScheduler (tick loop, per-job isolation, time_provider)
- `tests/test_openrouter_ranking_scrapers_base.py` — 8 tests
- `tests/test_openrouter_ranking_scrapers_bfcl.py` — 14 tests
- `tests/test_openrouter_ranking_scrapers_aa.py` — 14 tests
- `tests/test_openrouter_ranking_scheduler.py` — 16 tests

## Test Results (PR 2)

```
tests/test_openrouter_ranking_scrapers_base.py   8 passed
tests/test_openrouter_ranking_scrapers_bfcl.py  14 passed
tests/test_openrouter_ranking_scrapers_aa.py    14 passed
tests/test_openrouter_ranking_scheduler.py      16 passed
Total new PR2 tests: 52 passed
```

## Regression Check (PR 2)

```
All 116 baseline openrouter_prices tests: still GREEN
All 74 PR1 tests: still GREEN
Total: 242 passed (116 baseline + 74 PR1 + 52 PR2)
```

## Deviations from Design

- `record_scrape_run` in database.py accepts all params at once (no staged insert).
  BFCLScraper adapted to build ScrapeResult first, then call record_scrape_run once.
  Functionally equivalent; simplifies the implementation.
- `leaderboard_404_returns_error` test updated to mock ALL probes returning 404
  (not just one) because LEADERBOARD_FILE_PROBES has 5 entries and exhausting
  AsyncMock side_effect raises StopIteration → used a side_effect function instead.
- Weekly report and ranking embed jobs are stubs in PR2 (pass); full implementations
  in PR3 once discord_embeds.py is available.

## PR 3 Handoff

PR 3 debe implementar:
- `src/bot/plugins/openrouter_prices/discord_embeds.py` (build_weekly_price_embed, build_ranking_embed)
- `src/bot/plugins/openrouter_prices/api.py` — 6 new endpoints (rankings, benchmarks, scrape, aliases, scrape-runs)
- `src/bot/plugins/openrouter_prices/__init__.py` — wiring: scheduler start/stop + teardown callback
- `src/web/app.py` — teardown_callbacks iteration in _lifespan

Dependencies confirmed available: database.py, aliases.py, ranking.py, scheduler.py, scrapers/*.py

---

## Scope (PR 3 of 3) — COMPLETE

Tasks 3.1–3.8: discord_embeds.py, api.py (6 new endpoints + PUT /config validation for 14 new keys),
__init__.py setup() wiring (scheduler + teardown callback), web/app.py teardown_callbacks in _lifespan.

## TDD Cycle Evidence (PR 3)

| Task | RED file:test | RED status | GREEN file | GREEN status | Notes |
|------|--------------|------------|------------|--------------|-------|
| 3.1 Write embed tests | tests/test_openrouter_ranking_embeds.py | ModuleNotFoundError discord_embeds (CORRECT RED) | discord_embeds.py | 21 passed | build_weekly/ranking + publish_embed_to_channel |
| 3.2 Write API ext tests | tests/test_openrouter_ranking_api_ext.py | 21 failed / 6 passed (endpoints missing, CORRECT RED) | api.py extensions | 27 passed | 6 endpoints + config validation |
| 3.3 Write integration tests | tests/test_openrouter_ranking_integration.py | 7 failed / 1 passed (CORRECT RED) | setup() + web/app.py | 9 passed | smoke: setup wires state, teardown callback, endpoints |
| 3.4 Implement discord_embeds.py | src/.../discord_embeds.py | — | tests/...embeds.py | 21 GREEN | build_weekly (6000 char truncation, 25-field cap), build_ranking (top1 marker), publish_embed (snowflake string conv) |
| 3.5 Implement API extensions | src/.../api.py | — | tests/...api_ext.py | 27 GREEN | GET /rankings/{phase}, GET /benchmarks, POST /scrape/{source}, GET /aliases, PUT /aliases/{id}, GET /scrape-runs, PUT /config validation |
| 3.6 Add trigger_scrape + is_scraping | src/.../scheduler.py | — | — | GREEN | Active scrape tracking via _active_scrapes set |
| 3.7 Implement weekly_report + ranking_embed jobs | src/.../scheduler.py | — | — | GREEN | Full implementations replacing PR2 stubs |
| 3.8 Wire setup() + teardown | src/.../\_\_init\_\_.py + src/web/app.py | — | tests/.../integration.py | 9 GREEN | teardown_callbacks pattern (ADR-LIFECYCLE) |

## Files Created (PR 3)

- `src/bot/plugins/openrouter_prices/discord_embeds.py` — build_weekly_price_embed, build_ranking_embed, publish_embed_to_channel
- `tests/test_openrouter_ranking_embeds.py` — 21 tests
- `tests/test_openrouter_ranking_api_ext.py` — 27 tests
- `tests/test_openrouter_ranking_integration.py` — 9 tests

## Files Modified (PR 3)

- `src/bot/plugins/openrouter_prices/api.py` — 6 new endpoints + PUT /config validation for 14 new keys (REQ-EXT-11)
- `src/bot/plugins/openrouter_prices/scheduler.py` — trigger_scrape, is_scraping, _active_scrapes, full _job_weekly_report, full _job_ranking_embed
- `src/bot/plugins/openrouter_prices/__init__.py` — setup() extended: BFCLScraper, ArtificialAnalysisScraper, PluginScheduler, teardown callback, app.state wiring
- `src/web/app.py` — _lifespan: teardown_callbacks iteration after yield; create_app: teardown_callbacks list init

## Test Results (PR 3)

```
tests/test_openrouter_ranking_embeds.py       21 passed
tests/test_openrouter_ranking_api_ext.py      27 passed
tests/test_openrouter_ranking_integration.py   9 passed
Total new PR3 tests: 57 passed
```

## Regression Check (PR 3)

```
All 299 openrouter tests (baseline 116 + PR1 74 + PR2 52 + PR3 57): GREEN
tests/test_websocket.py + tests/test_activity_kinds.py: GREEN (10 passed)
Pre-existing failures in test_welcome_plugin.py, test_music_player.py, test_blackboard_plugin.py:
  → 12 failures confirmed pre-existing (from working tree music_player + welcome_plugin modifications)
  → NOT caused by PR3 changes
```

## Spanish Neutro Audit (PR 3)

Grep for Rioplatense forms across all new/modified PR3 files:
- Result: No violations found. False positives (partial word matches) excluded.
- All user-facing strings use Spanish neutro peruano.

## Deviations from Design

- `trigger_scrape` uses `asyncio.create_task` to run the scrape in background, matching the spec's "dispatched as a background task; 200 returned immediately".
- `_active_scrapes: set[str]` used for conflict detection — simple and race-condition-safe within single-process async.
- Integration tests use module-level patches (patching the sub-module classes) rather than top-level imports since `setup()` uses lazy local imports.

## Verify Handoff

All 299 openrouter tests green. sdd-verify can now run against:
- Spec: obs #900
- Tasks: obs #902
- Apply-progress: this file / engram sdd/openrouter-ranking/apply-progress
