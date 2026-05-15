# Proposal: OpenRouter Ranking — Benchmark Scoring & Scheduled Reports

## Intent

The existing `openrouter_prices` plugin ships, fetches prices, and exposes them via API and slash command. The next natural step is **quality ranking**: automatically score models against benchmark data and surface the best options for specific SDD phases via weekly/bi-weekly Discord embeds. Without this, choosing a model requires manual comparison across multiple external sites. The plugin already stores model metadata that contains enough signal (`supported_parameters`, pricing fields) for feature-based scoring; the missing piece is external benchmark ingestion.

## Scope

### In Scope

- **Schema extension** on `data/plugins/openrouter_prices.db` (additive, idempotent migrations): `benchmarks`, `model_benchmarks`, `phase_profiles`, `model_aliases` tables; 12 new `config` keys for scheduling
- **Benchmark scrapers**: `scrapers/artificial_analysis.py` (Playwright headless, reuses Chromium pattern from `blackboard/scraper.py`) and `scrapers/bfcl.py` (httpx → raw.githubusercontent.com, parse latest dated folder)
- **Ranking engine** (`ranking.py`): pure functions — normalize scores, weighted sum, renormalize active weights to 100%, rank top-N; initial profile = `orchestrator` phase (8 benchmarks, active weight 78%)
- **Alias resolver** (`aliases.py`): fuzzy name matching between OpenRouter `canonical_slug` and external benchmark keys via `difflib.SequenceMatcher` (stdlib-only, no new dep); admin endpoint to correct mismatches
- **Background scheduler** (`scheduler.py`): `asyncio.create_task` loop; reads config TTL, fires scrapers + Discord reports; gracefully stopped on plugin shutdown (teardown hook added to `__init__.py`)
- **Discord embed builders** (`discord_embeds.py`): weekly price report embed + bi-weekly ranking embed; top-10 cap; Discord 25-field / 6000-char limits enforced
- **7 new API endpoints** under `/api/plugins/openrouter-prices/`: `GET/PUT` ranking config, `GET /rankings/{phase}`, `GET /benchmarks`, `POST /scrape/{source}` (manual trigger), `GET /aliases`, `PUT /aliases/{openrouter_id}`
- **Activity feed events**: scrape start/end, report sent, new model detected, benchmark score updated
- **TDD-first test suite**: 7 new test files targeting ≥85% coverage on new modules

### Out of Scope

- Frontend dashboard UI (user will supply template in a separate change)
- Ranking profiles for phases other than `orchestrator` (same infrastructure, different weights JSON — deferred)
- MultiChallenge, RULER, LongBench scrapers (weights reserved at 0% in seed JSON; infrastructure ready)
- "Most-used models" via HTML scrape of `/rankings` page — v1 proxy: cheapest text-modality models by `pricing_prompt`

## Capabilities

### New Capabilities

- `openrouter-ranking`: benchmark ingestion (Playwright + httpx), weighted scoring engine, phase-scoped ranking API, scheduled Discord reports

### Modified Capabilities

- `openrouter-prices`: extended schema, new config keys, scheduler lifecycle in `setup()`/teardown, new API endpoints appended to `api.py`

## Approach

Extend the existing plugin in-place (no new plugin namespace). The scoring pipeline is:

1. **Ingest** — scrapers write raw scores to `model_benchmarks`; alias table bridges OpenRouter IDs to external keys
2. **Score** — `ranking.py` reads `model_benchmarks` + `phase_profiles`, normalizes each benchmark (min-max), applies weights, sums, renormalizes active weights to 100%
3. **Deliver** — `scheduler.py` runs two async loops (configurable periods); on trigger calls `discord_embeds.py` → `bot.get_channel().send(embed=...)`
4. **Degrade** — every scraper call wrapped in `try/except`; errors push activity event, scheduler continues; API falls back to last-known scores

`difflib.SequenceMatcher` chosen over `rapidfuzz` to avoid a new transitive dep; ratio threshold 0.75.

Playwright reuse: lazy `async with async_playwright()` inside each AA scrape call; no persistent browser process between scrapes.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/bot/plugins/openrouter_prices/database.py` | Modified | 4 new tables, 12 new config keys, `_create_schema` extended |
| `src/bot/plugins/openrouter_prices/__init__.py` | Modified | Start scheduler in `setup()`, stop on teardown |
| `src/bot/plugins/openrouter_prices/api.py` | Modified | 7 new endpoints appended |
| `src/bot/plugins/openrouter_prices/models.py` | Modified | Pydantic models for benchmarks, rankings, aliases |
| `src/bot/plugins/openrouter_prices/scrapers/` | New | `__init__.py`, `artificial_analysis.py`, `bfcl.py` |
| `src/bot/plugins/openrouter_prices/ranking.py` | New | Pure scoring functions |
| `src/bot/plugins/openrouter_prices/scheduler.py` | New | Async background task loop |
| `src/bot/plugins/openrouter_prices/aliases.py` | New | Fuzzy name matching + admin helpers |
| `src/bot/plugins/openrouter_prices/discord_embeds.py` | New | Embed builders for reports |
| `data/plugins/seeds/orchestrator_phase_weights.json` | New | Initial weights seeded on first boot |
| `tests/test_openrouter_ranking_*.py` × 7 | New | TDD red→green for all new modules |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Artificial Analysis DOM changes break selector | Med | try/except + cached fallback + activity-feed warning; selector versioned in constant |
| BFCL repo date-folder structure changes | Low | Dynamic folder discovery via GitHub `contents` API (60 req/hr anon, fine for weekly) |
| Fuzzy alias matching wrong (model name collision) | Med | Threshold 0.75; admin PUT endpoint to fix; alias stored once and reused |
| Playwright startup time on weekly cron | Low | Lazy-init; async with; browser not kept alive |
| Discord embed limits exceeded (25 fields, 6000 chars) | Low | Hard cap at top-10; truncate descriptions at 80 chars |
| Scheduler crash kills bot | Low | Each scraper in isolated try/except; scheduler loop catches all exceptions |
| Existing 121 tests regressed | Low | Schema migration is additive (IF NOT EXISTS); no existing columns removed |

## Rollback Plan

- All schema changes use `CREATE TABLE IF NOT EXISTS` and `INSERT OR IGNORE` — removing new files and reverting `__init__.py` / `api.py` / `database.py` to pre-change state leaves the DB intact and working
- New tables are never read by old code paths; removing them with `DROP TABLE` is safe after reverting code
- Git revert to pre-change commit; `uv run pytest` must still show 121 green

## Dependencies

- Playwright Chromium already installed (`uv run playwright install chromium` already run for Blackboard)
- `difflib` stdlib (no new dep)
- GitHub raw API (anonymous, no token, 60 req/hr — weekly scrape is 1 req/run)
- `httpx` already in project deps

## Success Criteria

- [ ] Daily cron detects new OpenRouter models; activity event emitted
- [ ] Weekly cron scrapes Artificial Analysis (IFBench, τ²-Bench Telecom, AA-Omniscience) via Playwright without error
- [ ] Weekly cron scrapes BFCL GitHub (v3 + Parallel scores) via httpx without error
- [ ] `GET /rankings/orchestrator` returns top-10 models with weighted score breakdown
- [ ] Weekly price report embed posted to configured channel on schedule
- [ ] Bi-weekly ranking embed posted with top-10 orchestrator models
- [ ] All scraper errors degrade gracefully: cache fallback, activity event, no bot crash
- [ ] `PUT /config` with new keys persists and reschedules without restart
- [ ] New test suite: ≥85% coverage, TDD red→green documented in apply-progress
- [ ] `uv run pytest` shows 121 original tests still green after all changes
