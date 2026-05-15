# Delta Spec: openrouter-ranking → extends openrouter-prices

## Domain

`openrouter-prices` (modified capability — all new requirements are additive)

---

## ADDED Requirements

### Requirement: REQ-EXT-1 — Auto-discovery of new OpenRouter models

The scheduler MUST detect models absent from `or_models` after each OpenRouter sync and emit an activity event per new model. The scheduler MUST NOT emit events when no new model is found. On sync failure the scheduler MUST fall back to cached data and emit an error event, then continue running.

#### Scenario: New model detected during cron

- GIVEN a daily OpenRouter sync runs
- WHEN the API response contains a model ID not present in `or_models`
- THEN `push_event(kind="openrouter", title="Modelo OpenRouter nuevo detectado", meta={"model_id": "<id>"})` is called
- AND the new model is upserted into `or_models`

#### Scenario: No new models — no event spam

- GIVEN all model IDs from the API already exist in `or_models`
- WHEN the daily sync completes
- THEN no "nuevo detectado" activity event is emitted

#### Scenario: OpenRouter unreachable during cron

- GIVEN the OpenRouter API returns a network error or 5xx
- WHEN the scheduler fires its sync job
- THEN the scheduler emits `push_event(kind="openrouter", title="Sincronización OpenRouter falló", ...)`, does NOT clear cached rows, and continues the scheduling loop without crashing

---

### Requirement: REQ-EXT-2 — Benchmarks data model

The DB schema MUST include `benchmarks`, `model_benchmarks`, `phase_profiles`, and `model_aliases` tables created via `CREATE TABLE IF NOT EXISTS`. `benchmarks` MUST be seeded with the eight initial rows on first boot via `INSERT OR IGNORE`. `phase_profiles` MUST be seeded with the `orchestrator` weights JSON on first boot. All migrations MUST be idempotent.

#### Scenario: benchmarks table seeded on cold start

- GIVEN `openrouter_prices.db` is newly created
- WHEN `setup()` runs
- THEN `benchmarks` contains rows for: IFBench, MultiChallenge (weight=0), τ²-Bench Telecom, BFCL v3, BFCL Parallel, AA-Omniscience Non-Hallucination Rate, RULER (weight=0), LongBench (weight=0)

#### Scenario: model_benchmarks upsert preserves existing data

- GIVEN `model_benchmarks` has an existing `(model_id, benchmark_id)` row
- WHEN a scraper writes a new score for the same pair
- THEN the row is updated (`ON CONFLICT DO UPDATE`); `fetched_at` and `source` reflect the latest scrape; no duplicate rows are inserted

#### Scenario: phase_profiles seeded with orchestrator weights

- GIVEN a fresh DB
- WHEN `setup()` runs
- THEN `phase_profiles` contains a row with `phase_id="orchestrator"` and weights matching the proposal table (active benchmarks sum to 100% after renormalization)

#### Scenario: Repeated setup is idempotent

- GIVEN `setup()` was previously called (tables + seeds exist)
- WHEN `setup()` is called again (restart)
- THEN no duplicate rows are inserted; no errors are raised; custom edits to weights are NOT overwritten

---

### Requirement: REQ-EXT-3 — Artificial Analysis scraper

The AA scraper MUST use Playwright Chromium to navigate `artificialanalysis.ai/models`, wait for the benchmark table to render, and extract rows. It MUST update `model_benchmarks` for IFBench, τ²-Bench Telecom, and AA-Omniscience scores. It MUST use fuzzy alias matching (threshold 0.75) to link AA model names to OpenRouter IDs. On any DOM or network failure it MUST emit an activity error event and return without modifying the DB. The scraper MUST be skipped if it ran within `aa_scrape_interval_days`.

#### Scenario: Scraper extracts and persists scores

- GIVEN Playwright opens the AA models page and the benchmark table is rendered
- WHEN the scraper parses table rows for a known model
- THEN `model_benchmarks` is upserted with scores for IFBench, τ²-Bench Telecom, and AA-Omniscience; `source = "artificial_analysis"`

#### Scenario: Unknown model name — fuzzy below threshold

- GIVEN an AA model name does not match any OpenRouter canonical slug above ratio 0.75
- WHEN the scraper processes that row
- THEN a row is inserted into `model_aliases` with `matched=false`; no `model_benchmarks` row is written for that model

#### Scenario: DOM selector change — graceful degradation

- GIVEN the AA page DOM structure has changed and the expected selector raises an exception
- WHEN the scraper runs
- THEN `push_event(kind="openrouter", title="Scrape Artificial Analysis falló", detail="<error>")` is called; the DB is not modified; the scheduler continues

#### Scenario: Idempotency — skip within interval

- GIVEN the scraper last ran less than `aa_scrape_interval_days` ago
- WHEN the scheduler fires the AA scrape job
- THEN the scraper is skipped; no Playwright browser is launched; no activity event emitted for "completed"

---

### Requirement: REQ-EXT-4 — BFCL scraper

The BFCL scraper MUST discover the latest dated results folder via the GitHub Contents API on `HuanzhiMao/BFCL-Result`, fetch the scores JSON via `raw.githubusercontent.com`, and upsert BFCL v3 and BFCL Parallel scores into `model_benchmarks`. On GitHub rate limit (HTTP 403) or unreachable repo, it MUST fall back to cached data and emit an activity error event.

#### Scenario: Successful BFCL scrape

- GIVEN the GitHub Contents API returns at least one dated folder
- WHEN the scraper fetches the latest folder's scores JSON
- THEN `model_benchmarks` is upserted with `benchmark_id` for BFCL v3 and BFCL Parallel per model; `source = "bfcl_github"`

#### Scenario: GitHub rate limit hit

- GIVEN the GitHub API returns HTTP 403
- WHEN the scraper runs
- THEN cached `model_benchmarks` for BFCL benchmarks are NOT cleared; `push_event(kind="openrouter", title="Scrape BFCL falló", detail="Rate limit GitHub")` is called

#### Scenario: BFCL repo unreachable

- GIVEN `raw.githubusercontent.com` is unreachable (network error)
- WHEN the scraper runs
- THEN cached data is preserved; activity error event is emitted; scheduler continues

#### Scenario: Idempotency — skip within interval

- GIVEN the scraper last ran less than `bfcl_scrape_interval_days` ago
- WHEN the scheduler fires the BFCL job
- THEN the scraper is skipped without making any HTTP request

---

### Requirement: REQ-EXT-5 — Ranking computation

The ranking engine MUST expose pure functions: `normalize(values, higher_is_better) -> dict[model_id, float]` using min-max scaling to [0,1], and `weighted_sum(normalized, weights) -> float`. `compute_ranking(phase, limit) -> list` MUST return models sorted by score descending. Missing benchmark scores MUST contribute 0 (no NaN propagation). Active weights MUST be renormalized to sum=100% before computation. Feature-flag factors (cache read ratio, reasoning effort, verbosity) MUST be treated as benchmarks with their own weights and normalization rules.

#### Scenario: compute_ranking returns correct shape

- GIVEN `phase_profiles` has `orchestrator` weights and `model_benchmarks` has scores for ≥10 models
- WHEN `compute_ranking("orchestrator", limit=10)` is called
- THEN a list of exactly 10 dicts is returned; each has `model_id`, `name`, `score` (float in [0,1]); list is sorted by `score` descending

#### Scenario: normalize — min-max correctness

- GIVEN a dict of model scores `{"a": 10.0, "b": 0.0, "c": 5.0}` with `higher_is_better=True`
- WHEN `normalize(values, higher_is_better=True)` is called
- THEN result is `{"a": 1.0, "b": 0.0, "c": 0.5}`

#### Scenario: Missing benchmark score contributes 0

- GIVEN model X has no row in `model_benchmarks` for BFCL v3
- WHEN `compute_ranking("orchestrator")` is called
- THEN model X receives 0.0 for BFCL v3 in its weighted sum; `score` is a valid float (not NaN)

#### Scenario: Inactive benchmark weights excluded from renormalization

- GIVEN RULER, LongBench, MultiChallenge have weight=0 in `orchestrator` profile
- WHEN `compute_ranking` renormalizes weights
- THEN only benchmarks with weight > 0 are included in the 100% renormalization sum; the three inactive benchmarks contribute 0

#### Scenario: Feature-flag cache ratio normalization

- GIVEN model A has `input_cache_read / pricing.prompt = 0.8` and model B has ratio = 0.2
- WHEN the cache ratio factor is normalized with `higher_is_better=False` (lower ratio = better)
- THEN model B scores higher than model A for that factor

---

### Requirement: REQ-EXT-6 — Scheduler lifecycle

The scheduler MUST start as `asyncio.create_task` inside `setup()`. It MUST read config keys for all job intervals and dispatch scrape + report jobs accordingly. It MUST reschedule within ≤60s when config is updated via PUT /config. It MUST cancel cleanly on bot shutdown without asyncio warnings. Each job MUST be isolated in try/except; a failing job MUST NOT stop the scheduler loop.

#### Scenario: Scheduler starts with setup

- GIVEN `setup()` is called
- WHEN it completes
- THEN an asyncio background task is running; scheduler state is accessible on `app.state`

#### Scenario: Config change reschedules jobs

- GIVEN the scheduler is running with `openrouter_refresh_interval_hours=24`
- WHEN `PUT /config` is called with `{"openrouter_refresh_interval_hours": "12"}`
- THEN within 60s the scheduler uses the new interval for the next tick

#### Scenario: Scheduler survives individual job failure

- GIVEN a scraper job raises an unhandled exception
- WHEN the scheduler loop catches it
- THEN an activity error event is emitted; the scheduler continues and the next job fires on schedule

#### Scenario: Clean shutdown

- GIVEN the bot is shutting down and the scheduler task is running
- WHEN the teardown hook in `__init__.py` is called
- THEN the asyncio task is cancelled; no `Task was destroyed but it is pending!` warnings are logged

---

### Requirement: REQ-EXT-7 — Weekly Discord price report

The bot MUST post a weekly embed to `weekly_report_channel_id` listing the top N cheapest text-modality models by `pricing_prompt`. If the channel is not configured, the report MUST be skipped with an activity event. Discord channel errors MUST be caught; the bot MUST NOT crash. Embeds exceeding 6000 chars MUST be truncated with footer "Lista recortada". If `weekly_report_enabled = "false"`, no report is sent.

#### Scenario: Report posted on schedule

- GIVEN `weekly_report_enabled="true"`, `weekly_report_channel_id` is set, and the configured day+hour is reached
- WHEN the scheduler fires the weekly report job
- THEN `bot.get_channel(channel_id).send(embed=...)` is called with an embed listing the top N cheapest text models; `push_event(kind="openrouter", title="Reporte semanal de precios enviado")` is called

#### Scenario: Channel not configured — skipped

- GIVEN `weekly_report_channel_id = ""`
- WHEN the weekly report job fires
- THEN `push_event(kind="openrouter", title="Reporte semanal de precios falló", detail="Sin canal configurado")` is called; no Discord API call is made

#### Scenario: Embed over 6000 chars — truncated

- GIVEN the model list would produce an embed exceeding 6000 chars
- WHEN the embed is built
- THEN rows are removed until the total is under 6000 chars; the embed footer contains "Lista recortada"

#### Scenario: Feature disabled

- GIVEN `weekly_report_enabled = "false"`
- WHEN the scheduler fires the weekly report job
- THEN the job returns immediately; no embed is sent; no activity event for "enviado"

---

### Requirement: REQ-EXT-8 — Bi-weekly orchestrator ranking embed

The bot MUST post a bi-weekly embed to `ranking_embed_channel_id` with the top 10 models for the `orchestrator` phase profile. The embed MUST include rank, model name, score, and top-3 contributing benchmarks per model. If top-1 changed since the last embed, a rank-change marker MUST be shown. If fewer than 5 models have benchmark scores, a warning embed MUST be posted instead. If `ranking_embed_enabled = "false"`, no embed is sent.

#### Scenario: Ranking embed posted on schedule

- GIVEN `ranking_embed_enabled="true"`, `ranking_embed_channel_id` is set, `ranking_embed_cron_days=14`, and the interval has elapsed
- WHEN the scheduler fires the ranking embed job
- THEN an embed is posted listing rank 1–10, each row showing model name, score (2 decimal places), and top-3 benchmark names contributing most to the score
- AND `push_event(kind="openrouter", title="Embed bi-semanal de ranking enviado")` is called

#### Scenario: Top-1 change marker

- GIVEN the previous embed's top-1 model ID is stored
- WHEN `compute_ranking` returns a different model at rank 1
- THEN the embed for that model includes a visible rank-change marker (e.g., "Subio al #1")

#### Scenario: Insufficient benchmark data

- GIVEN fewer than 5 models have at least one `model_benchmarks` row
- WHEN the ranking embed job fires
- THEN a warning embed is posted with text "Datos insuficientes; X modelos sin benchmarks"; no score table is shown

#### Scenario: Feature disabled

- GIVEN `ranking_embed_enabled = "false"`
- WHEN the scheduler fires the ranking embed job
- THEN the job returns immediately; no embed is sent

---

### Requirement: REQ-EXT-9 — Manual scrape trigger endpoint

The plugin MUST expose `POST /api/plugins/openrouter-prices/scrape/{source}` where `source` is one of `{openrouter, aa, bfcl}`. A successful trigger MUST return 200 with `{started: true, source: "<source>"}`. An invalid source MUST return 400. A concurrent scrape in progress MUST return 409.

#### Scenario: Valid source triggers scrape

- GIVEN no scrape is in progress for the requested source
- WHEN `POST /scrape/aa` is called
- THEN the scraper is dispatched as a background task; 200 `{started: true, source: "aa"}` is returned immediately

#### Scenario: Invalid source

- GIVEN source `"unknown"` is not in the allowed set
- WHEN `POST /scrape/unknown` is called
- THEN 400 with `{detail: "Fuente de scrape invalida. Valores permitidos: openrouter, aa, bfcl"}`

#### Scenario: Concurrent scrape conflict

- GIVEN a scrape for `bfcl` is already running
- WHEN `POST /scrape/bfcl` is called again
- THEN 409 with `{detail: "Scrape ya en curso"}`

---

### Requirement: REQ-EXT-10 — Alias management endpoints

The plugin MUST expose `GET /aliases` returning all rows from `model_aliases`. It MUST expose `PUT /aliases/{openrouter_id}` accepting `{artificial_analysis_name, bfcl_key}` to update alias mappings. An empty PUT body MUST be a no-op returning the current row.

#### Scenario: GET aliases returns full list

- GIVEN `model_aliases` has rows with matched and unmatched entries
- WHEN `GET /aliases` is called
- THEN 200 with a list including both matched and unmatched alias rows; each row has `openrouter_id`, `artificial_analysis_name`, `bfcl_key`, `matched`

#### Scenario: PUT alias updates mapping

- GIVEN `model_aliases` has a row for `openrouter_id = "anthropic/claude-3-haiku"` with `matched=false`
- WHEN `PUT /aliases/anthropic%2Fclaude-3-haiku` is called with `{"artificial_analysis_name": "Claude 3 Haiku", "bfcl_key": "claude-3-haiku"}`
- THEN the row is updated; next scraper run uses the explicit mapping; `matched=true`

#### Scenario: Empty PUT body is a no-op

- GIVEN a valid `openrouter_id` exists in `model_aliases`
- WHEN `PUT /aliases/{openrouter_id}` is called with `{}`
- THEN 200 with the current row unchanged; no DB write performed

---

### Requirement: REQ-EXT-11 — Extended configuration keys

The plugin MUST seed 12 new config keys via `INSERT OR IGNORE` on boot. `PUT /config` MUST validate types and ranges for all new keys; invalid values MUST return 400 with Spanish neutro peruano `detail`. Keys and defaults:

| Key | Default |
|-----|---------|
| `openrouter_refresh_interval_hours` | `"24"` |
| `aa_scrape_enabled` | `"true"` |
| `aa_scrape_interval_days` | `"7"` |
| `bfcl_scrape_enabled` | `"true"` |
| `bfcl_scrape_interval_days` | `"7"` |
| `weekly_report_enabled` | `"true"` |
| `weekly_report_channel_id` | `""` |
| `weekly_report_day` | `"monday"` |
| `weekly_report_hour` | `"9"` |
| `weekly_report_count` | `"10"` |
| `ranking_embed_enabled` | `"true"` |
| `ranking_embed_channel_id` | `""` |
| `ranking_embed_cron_days` | `"14"` |
| `ranking_phase` | `"orchestrator"` |

#### Scenario: New keys seeded on first boot

- GIVEN a fresh DB (or DB that only has the original 4 keys)
- WHEN `setup()` runs
- THEN all 14 keys (original 4 + 14 new, but using INSERT OR IGNORE) exist in `config` with their defaults; existing custom values are not overwritten

#### Scenario: PUT /config validates interval range

- GIVEN `openrouter_refresh_interval_hours` must be a positive integer string
- WHEN `PUT /config` is called with `{"openrouter_refresh_interval_hours": "0"}`
- THEN 400 with `{detail: "openrouter_refresh_interval_hours debe ser mayor a 0"}`

#### Scenario: PUT /config validates boolean string

- GIVEN `aa_scrape_enabled` must be `"true"` or `"false"`
- WHEN `PUT /config` is called with `{"aa_scrape_enabled": "maybe"}`
- THEN 400 with `{detail: "aa_scrape_enabled debe ser 'true' o 'false'"}`

---

### Requirement: REQ-EXT-12 — Activity feed event vocabulary extension

The existing `"openrouter"` activity kind MUST be used for all new events. New event titles (Spanish neutro peruano) MUST include the strings defined below. No new kind value is added to `ALLOWED_KINDS`.

| Event | title string |
|-------|-------------|
| New model found | `"Modelo OpenRouter nuevo detectado"` |
| OR sync OK | `"Sincronizacion OpenRouter completada"` |
| OR sync fail | `"Sincronizacion OpenRouter fallo"` |
| AA scrape OK | `"Scrape Artificial Analysis completado"` |
| AA scrape fail | `"Scrape Artificial Analysis fallo"` |
| BFCL scrape OK | `"Scrape BFCL completado"` |
| BFCL scrape fail | `"Scrape BFCL fallo"` |
| Weekly report OK | `"Reporte semanal de precios enviado"` |
| Weekly report fail | `"Reporte semanal de precios fallo"` |
| Ranking embed OK | `"Embed bi-semanal de ranking enviado"` |
| Ranking embed fail | `"Embed bi-semanal de ranking fallo"` |

#### Scenario: All new event titles use correct kind

- GIVEN any new scheduler job completes or fails
- WHEN `push_event` is called
- THEN `kind="openrouter"` is used in every call; no call uses `kind="system"` for these events

#### Scenario: Spanish neutro peruano enforced

- GIVEN any new activity event title or detail string
- WHEN inspected
- THEN no Rioplatense forms are present (`tenés`, `podés`, imperative tildes)

---

### Requirement: REQ-EXT-13 — Strict TDD compliance

Every new public function MUST have at minimum one failing test (RED) written before implementation. All new tests MUST use `pytest-timeout` with `@pytest.mark.timeout(5)`. The apply-progress artifact MUST include a TDD Cycle Evidence table per task.

#### Scenario: Test file exists before implementation file

- GIVEN a new module (e.g., `ranking.py`) is to be implemented
- WHEN the apply task for that module begins
- THEN the test file `tests/test_openrouter_ranking_*.py` is written and run (fails RED) before any implementation code is added

#### Scenario: No test exceeds 5s

- GIVEN all new tests run under pytest
- WHEN `uv run pytest` executes the new test files
- THEN no individual test exceeds 5 seconds; any test timing out is marked FAIL

---

### Requirement: REQ-EXT-14 — No regression on existing behavior

The 121 existing tests MUST remain green after the extension lands. Existing endpoints (`GET /models`, `GET /config`, `POST /refresh`, `GET /status`, `/precios-openrouter`) MUST be unchanged in shape and behavior.

#### Scenario: Existing test suite still green

- GIVEN all new code, schema migrations, and scheduler are applied
- WHEN `uv run pytest` runs the full suite
- THEN the original 121 tests pass; no existing test is modified to accommodate new code

#### Scenario: Existing endpoints unchanged

- GIVEN the extension is fully deployed
- WHEN `GET /models?text_only=true&limit=5` is called
- THEN the response shape is identical to the pre-extension response; no new mandatory fields added; no existing field removed or renamed

---

## MODIFIED Requirements

### Requirement: REQ-7 — Plugin lifecycle

The plugin MUST follow the `setup(bot, config_manager, app)` contract. `setup()` MUST open the DB, seed defaults (including the 14 new config keys and 4 new tables), register the router at `/api/plugins/openrouter-prices`, add the cog via `bot.add_cog()`, store state on `app.state`, and start the background scheduler as an asyncio task. The plugin MUST register a teardown hook that cancels the scheduler task and closes the DB connection.

(Previously: `setup()` did not start a scheduler; teardown only closed the DB)

#### Scenario: Setup completes without error

- GIVEN no prior DB exists and all dependencies are available
- WHEN `setup(bot, config_manager, app)` is called
- THEN the DB is created, defaults seeded (original + new keys), cog registered, router mounted, scheduler started, and `app.state.openrouter_prices_db` is set

#### Scenario: Plugin wired in `__main__.py`

- GIVEN `src/__main__.py` is the application entry point
- WHEN the bot starts
- THEN `setup_openrouter_prices(bot, cm, app)` is awaited before serving requests

#### Scenario: Graceful shutdown

- GIVEN the bot is shutting down and the scheduler task is running
- WHEN the teardown hook runs
- THEN the scheduler asyncio task is cancelled cleanly; the aiosqlite connection is closed without error; no asyncio pending task warnings

---

### Requirement: REQ-2 — REST endpoints

The plugin MUST expose the following endpoints under `/api/plugins/openrouter-prices/`. All responses MUST use Spanish neutro peruano for `detail` error messages.

(Previously: only 6 endpoints; 7 new endpoints are appended in this change)

| Endpoint | Method | Success | Error |
|----------|--------|---------|-------|
| `/models` | GET | 200 list | 500 if DB fails |
| `/models/{model_id}` | GET | 200 single model | 404 if not found |
| `/config` | GET | 200 config object | — |
| `/config` | PUT | 200 updated config | 400 on invalid input |
| `/refresh` | POST | 200 `{updated_count, last_fetched_at}` | 500 on fetch failure |
| `/status` | GET | 200 status object | — |
| `/rankings/{phase}` | GET | 200 ranked list | 404 if phase unknown |
| `/benchmarks` | GET | 200 benchmark rows | — |
| `/scrape/{source}` | POST | 200 `{started, source}` | 400/409 |
| `/aliases` | GET | 200 alias list | — |
| `/aliases/{openrouter_id}` | PUT | 200 updated alias | 404 if not found |

`GET /models` query params unchanged. `GET /rankings/{phase}` MUST support optional `limit` (default 10, max 50).

#### Scenario: List models with filters (unchanged)

- GIVEN the DB has 200 models, some with non-text input modalities
- WHEN `GET /models?text_only=true&sort_by=prompt&order=asc&limit=10` is called
- THEN 10 models with `text` in `input_modalities` are returned, sorted by `prompt_usd_mtok` ascending

#### Scenario: GET /rankings/{phase} — known phase

- GIVEN `phase_profiles` has an `orchestrator` entry and `model_benchmarks` has data
- WHEN `GET /rankings/orchestrator?limit=5` is called
- THEN 200 with a list of 5 models; each has `model_id`, `name`, `score` (float), `benchmark_breakdown` (list of top-3 contributing benchmarks)

#### Scenario: GET /rankings/{phase} — unknown phase

- GIVEN `phase_profiles` has no row for `phase_id = "unknown"`
- WHEN `GET /rankings/unknown` is called
- THEN 404 with `{detail: "Perfil de fase no encontrado"}`

#### Scenario: Single model — not found (unchanged)

- GIVEN the model ID does not exist in the DB
- WHEN `GET /models/{model_id}` is called
- THEN 404 with `{detail: "Modelo no encontrado"}`

#### Scenario: PUT /config — valid update (unchanged)

- GIVEN the plugin is running with default config
- WHEN `PUT /config` is called with `{"ttl_seconds": 7200}`
- THEN 200; subsequent cache checks use the new TTL; an activity event is emitted

#### Scenario: PUT /config — invalid input (unchanged)

- GIVEN a request body with `{"ttl_seconds": -1}`
- WHEN `PUT /config` is called
- THEN 400 with `{detail: "El valor de ttl_seconds debe ser mayor a 0"}`

---

## Out of Scope (this change)

- Frontend dashboard UI
- Ranking profiles for phases other than `orchestrator`
- MultiChallenge, RULER, LongBench scrapers (weight=0 reserved)
