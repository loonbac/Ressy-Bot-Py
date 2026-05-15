# OpenRouter Prices Plugin — Specification

## Purpose

Full specification for the new `openrouter-prices` plugin: fetch, persist, cache,
and expose OpenRouter model prices via REST API and Discord slash command. Foundation
for future ranking logic and scheduled embed delivery.

## Out of Scope

- Frontend / React dashboard UI (deferred — user provides template later)
- Ranking heuristics for "best models" (criteria undefined)
- Scheduled Discord channel embed delivery (format + channel pending)
- Authentication on OpenRouter endpoints (public API only)

---

## Requirements

### Requirement: REQ-1 — Fetch model catalog from OpenRouter

The plugin MUST fetch `https://openrouter.ai/api/v1/models` via HTTP GET when the
local cache is absent or expired. Responses MUST be stored in SQLite. Pricing fields
MUST be stored as raw decimal strings to preserve precision.

#### Scenario: First fetch — cold start

- GIVEN the DB has no rows in `or_models` and no `last_fetched_at` record
- WHEN `GET /models` or any endpoint that needs models is called
- THEN the plugin calls the OpenRouter API, persists all returned models, and
  returns the populated list; `last_fetched_at` is set to now

#### Scenario: Subsequent fetch within TTL — cache hit

- GIVEN `last_fetched_at + ttl_seconds > now`
- WHEN `GET /models` is called
- THEN no HTTP request is made; rows are returned directly from the DB

#### Scenario: Force-refresh ignores TTL

- GIVEN the cache is still valid (within TTL)
- WHEN `POST /refresh` is called
- THEN the plugin calls the OpenRouter API unconditionally, updates the DB, and
  updates `last_fetched_at`

#### Scenario: HTTP failure — fallback to DB snapshot

- GIVEN the OpenRouter API returns a 5xx or a network error occurs
- WHEN a fetch is attempted (cold start or refresh)
- THEN the plugin logs the error, does NOT clear existing rows, and returns the
  last persisted snapshot with a `cache_stale: true` flag in the response

---

### Requirement: REQ-2 — REST endpoints

The plugin MUST expose the following endpoints under `/api/plugins/openrouter-prices/`.
All responses MUST use Spanish neutro peruano for `detail` error messages.

(Extended in openrouter-ranking change: 7 new endpoints added; original 6 endpoints unchanged)

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

`GET /models` MUST support optional query params: `text_only` (boolean, default true),
`sort_by` (`prompt` or `completion`, default `prompt`), `order` (`asc`/`desc`,
default `asc`), `limit` (positive int, default 50).

`GET /rankings/{phase}` MUST support optional `limit` (default 10, max 50).

#### Scenario: List models with filters

- GIVEN the DB has 200 models, some with non-text input modalities
- WHEN `GET /models?text_only=true&sort_by=prompt&order=asc&limit=10` is called
- THEN 10 models with `text` in `input_modalities` are returned, sorted by
  `prompt_usd_mtok` ascending; each row includes `id` (string), `name`,
  `prompt_usd_mtok` (float), `completion_usd_mtok` (float)

#### Scenario: Single model — found

- GIVEN model `anthropic/claude-3-haiku` exists in the DB
- WHEN `GET /models/anthropic%2Fclaude-3-haiku` is called
- THEN 200 with full model detail is returned

#### Scenario: Single model — not found

- GIVEN the model ID does not exist in the DB
- WHEN `GET /models/{model_id}` is called
- THEN 404 with `{detail: "Modelo no encontrado"}`

#### Scenario: PUT /config — valid update

- GIVEN the plugin is running with default config
- WHEN `PUT /config` is called with `{"ttl_seconds": 7200}`
- THEN 200; subsequent cache checks use the new TTL; an activity event is emitted

#### Scenario: PUT /config — invalid input

- GIVEN a request body with `{"ttl_seconds": -1}`
- WHEN `PUT /config` is called
- THEN 400 with `{detail: "El valor de ttl_seconds debe ser mayor a 0"}`

#### Scenario: GET /status

- GIVEN the plugin has fetched models at least once
- WHEN `GET /status` is called
- THEN 200 with `{enabled, last_fetched_at, models_count, cache_valid, ttl_seconds}`

---

### Requirement: REQ-3 — SQLite persistence

The plugin MUST create `data/plugins/openrouter_prices.db` on first run. The schema
MUST include a `config` (key/value) table and an `or_models` table.

#### Scenario: Schema creation on cold start

- GIVEN `openrouter_prices.db` does not exist
- WHEN `setup()` is called
- THEN the DB file is created and both tables exist with correct columns

#### Scenario: Upsert on refresh — models updated, not deleted

- GIVEN 150 models are in the DB from a previous fetch
- WHEN `POST /refresh` succeeds and the API returns 140 models (10 removed)
- THEN the 140 returned models are upserted; the 10 absent models have
  `is_stale = TRUE`; no rows are deleted

#### Scenario: Pricing precision preserved

- GIVEN OpenRouter returns `"prompt": "0.00000025"` for a model
- WHEN the model is persisted and later read
- THEN the raw string `"0.00000025"` is stored; `prompt_usd_mtok` = 0.25 (float)
  in the API response

---

### Requirement: REQ-4 — Configuration storage

The plugin MUST seed default config on first boot via `INSERT OR IGNORE`. Config keys:
`ttl_seconds` (default 3600), `enabled` (default true), `max_models_command`
(default 10), `discord_channel_id` (default null).

#### Scenario: Idempotent seed

- GIVEN `setup()` is called twice (e.g., restart)
- WHEN the second call runs
- THEN existing config values are NOT overwritten; no duplicate rows are inserted

#### Scenario: PUT /config — partial update

- GIVEN current config has `ttl_seconds=3600, enabled=true`
- WHEN `PUT /config` with `{"enabled": false}` is called
- THEN only `enabled` changes to false; `ttl_seconds` remains 3600

#### Scenario: PUT /config — invalid channel_id type

- GIVEN a request body with `{"discord_channel_id": 12345}` (integer, not string)
- WHEN `PUT /config` is called
- THEN 400 with `{detail: "discord_channel_id debe ser un string (Snowflake)"}`

---

### Requirement: REQ-5 — Discord slash command `/precios-openrouter`

The cog MUST register a guild-only slash command `/precios-openrouter`. The response
MUST be ephemeral. It MUST show the top N cheapest models with `text` in
`input_modalities`, sorted by `prompt_usd_mtok + completion_usd_mtok` ascending,
where N comes from config `max_models_command`.

#### Scenario: Command succeeds — plugin enabled

- GIVEN the plugin is enabled and the DB has ≥10 text-input models
- WHEN a user runs `/precios-openrouter`
- THEN an ephemeral embed is returned with the top 10 cheapest models;
  each entry shows model name, prompt price ($/Mtok), completion price ($/Mtok);
  the embed footer shows `Actualizado: {last_fetched_at}` in ISO format

#### Scenario: Plugin disabled

- GIVEN `enabled = false` in config
- WHEN a user runs `/precios-openrouter`
- THEN an ephemeral message is returned: "Este plugin está desactivado."

#### Scenario: Modalities filter

- GIVEN the DB contains models with only image or audio input modalities
- WHEN `/precios-openrouter` is called
- THEN those models do NOT appear in the embed results

---

### Requirement: REQ-6 — Activity feed integration

The plugin MUST emit events via `push_event` from `src.web.routes.activity`. The
string `"openrouter"` MUST be added to `ALLOWED_KINDS` in
`src/web/routes/activity.py`.

#### Scenario: Successful refresh emits event

- GIVEN `POST /refresh` completes successfully
- WHEN the response is returned
- THEN `push_event(kind="openrouter", title="Precios actualizados", detail="N modelos actualizados", meta={"count": N, "source": "openrouter"})` is called

#### Scenario: Failed refresh emits error event

- GIVEN the OpenRouter API returns 503
- WHEN `POST /refresh` is called
- THEN `push_event(kind="openrouter", title="Error al actualizar precios", detail="...", meta={"error": "..."})` is called

#### Scenario: Config update emits event

- GIVEN the plugin is running
- WHEN `PUT /config` succeeds
- THEN `push_event(kind="openrouter", title="Configuración actualizada", detail="...", meta={...})` is called

#### Scenario: `"openrouter"` kind is recognized

- GIVEN `src/web/routes/activity.py` is running
- WHEN an event with `kind="openrouter"` is pushed
- THEN the event is stored/broadcast without falling back to the `"system"` kind

---

### Requirement: REQ-7 — Plugin lifecycle

The plugin MUST follow the `setup(bot, config_manager, app)` contract. `setup()` MUST
open the DB, seed defaults (including 16 new config keys and 4 new tables from openrouter-ranking extension), register the router at `/api/plugins/openrouter-prices`,
add the cog via `bot.add_cog()`, store state on `app.state`, and start the background scheduler as an asyncio task. The plugin MUST register a teardown hook that cancels the scheduler task and closes the DB connection. The plugin MUST be imported and awaited in `src/__main__.py`.

(Extended in openrouter-ranking change: scheduler startup and teardown hook added; schema extensions for 4 new tables; 14 new config keys seeded. Extended in add-sdd-init-phase-profile change: 2 more config keys — `phases_enabled` and `ranking_embed_per_phase`.)

#### Scenario: Setup completes without error

- GIVEN no prior DB exists and all dependencies are available
- WHEN `setup(bot, config_manager, app)` is called
- THEN the DB is created, defaults seeded (original 4 + 16 new config keys), schema includes 4 new tables, cog registered, router mounted, scheduler started, and `app.state.openrouter_prices_db` is set

#### Scenario: Plugin wired in `__main__.py`

- GIVEN `src/__main__.py` is the application entry point
- WHEN the bot starts
- THEN `setup_openrouter_prices(bot, cm, app)` is awaited before serving requests

#### Scenario: Graceful shutdown

- GIVEN the bot is shutting down and the scheduler task is running
- WHEN the teardown sequence runs
- THEN the scheduler asyncio task is cancelled cleanly, the aiosqlite connection is closed without error, and no pending task warnings are logged

---

### Requirement: REQ-8 — Spanish neutro peruano in user-visible text

All `detail` strings in error responses and all Discord-facing text MUST use Spanish
neutro peruano. Rioplatense forms are prohibited.

#### Scenario: Error detail language check

- GIVEN any endpoint returns a 4xx or 5xx error
- WHEN the response body is inspected
- THEN `detail` contains no Rioplatense forms (`tenés`, `podés`, `configurá`,
  `dale`, `che`, `fijate`); imperative forms use standard Spanish (`configura`,
  `ejecuta`, `reinicia`)

---

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

### Requirement: REQ-EXT-8 — Bi-weekly multi-phase ranking embed

The bot MUST post a bi-weekly embed for each enabled phase to `ranking_embed_channel_id`. The scheduler MUST read `phases_enabled` and iterate phases. For each phase, the top N models (from `ranking_embed_per_phase` config) are included. Embed title MUST be `Top N modelos SDD — {phase}`. If a phase has fewer than 5 models, a warning embed is posted instead. If `ranking_embed_enabled = "false"`, no embed is sent for any phase.

(Previously: Single-phase embed using `ranking_phase` config. Now iterates `phases_enabled` with per-phase limits.)

#### Scenario: Multi-phase embed posted on schedule

- GIVEN `ranking_embed_enabled="true"`, `phases_enabled='["orchestrator","sdd_init"]'`
- WHEN the scheduler fires the ranking embed job
- THEN separate embeds are posted for each enabled phase with titles "Top N modelos SDD — Orchestrator" and "Top N modelos SDD — Sdd Init"

#### Scenario: Feature disabled

- GIVEN `ranking_embed_enabled = "false"`
- WHEN the scheduler fires the ranking embed job
- THEN the job returns immediately; no embeds are sent for any phase

#### Scenario: Insufficient benchmark data for one phase

- GIVEN `sdd_init` has fewer than 5 models with benchmarks
- WHEN the ranking embed job fires
- THEN a warning embed is posted for `sdd_init`; other phases post normally

#### Scenario: GET /rankings/sdd_init returns ranked list

- GIVEN `phase_profiles` has `sdd_init` weights
- WHEN `GET /rankings/sdd_init` is called
- THEN 200 with ranked model list (same shape as orchestrator)

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

The plugin MUST seed 16 new config keys via `INSERT OR IGNORE` on boot (14 existing + 2 new). `PUT /config` MUST validate types and ranges for all new keys; invalid values MUST return 400 with Spanish neutro peruano `detail`.

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
| `phases_enabled` | `'["orchestrator", "sdd_init"]'` |
| `ranking_embed_per_phase` | `"10"` |

#### Scenario: New keys seeded on first boot

- GIVEN a fresh DB (or DB with only original 4 keys)
- WHEN `setup()` runs
- THEN all 16 new keys (total 20) exist in `config` with their defaults; existing custom values are not overwritten

#### Scenario: PUT /config validates interval range

- GIVEN `openrouter_refresh_interval_hours` must be a positive integer string
- WHEN `PUT /config` is called with `{"openrouter_refresh_interval_hours": "0"}`
- THEN 400 with `{detail: "openrouter_refresh_interval_hours debe ser mayor a 0"}`

#### Scenario: PUT /config validates boolean string

- GIVEN `aa_scrape_enabled` must be `"true"` or `"false"`
- WHEN `PUT /config` is called with `{"aa_scrape_enabled": "maybe"}`
- THEN 400 with `{detail: "aa_scrape_enabled debe ser 'true' o 'false'"}`

#### Scenario: PUT /config validates phases_enabled format

- GIVEN a request body with `{"phases_enabled": "not-json"}`
- WHEN `PUT /config` is called
- THEN 400 with `{detail: "phases_enabled debe ser un arreglo JSON de strings."}`

#### Scenario: PUT /config validates ranking_embed_per_phase range

- GIVEN a request body with `{"ranking_embed_per_phase": "0"}`
- WHEN `PUT /config` is called
- THEN 400 with `{detail: "ranking_embed_per_phase debe ser mayor a 0."}`

---

### Requirement: REQ-EXT-12 — Activity feed event vocabulary extension

The existing `"openrouter"` activity kind MUST be used for all new events. New event titles (Spanish neutro peruano) per the vocabulary table below. No new kind value is added to `ALLOWED_KINDS`.

| Event | title string |
|-------|-------------|
| New model found | `"Modelo OpenRouter nuevo detectado"` |
| OR sync OK | `"Sincronización OpenRouter completada"` |
| OR sync fail | `"Sincronización OpenRouter falló"` |
| AA scrape OK | `"Scrape Artificial Analysis completado"` |
| AA scrape fail | `"Scrape Artificial Analysis falló"` |
| BFCL scrape OK | `"Scrape BFCL completado"` |
| BFCL scrape fail | `"Scrape BFCL falló"` |
| Weekly report OK | `"Reporte semanal de precios enviado"` |
| Weekly report fail | `"Reporte semanal de precios falló"` |
| Ranking embed OK | `"Embed bi-semanal de ranking enviado"` |
| Ranking embed fail | `"Embed bi-semanal de ranking falló"` |

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
- THEN the test file is written and run (fails RED) before any implementation code is added

#### Scenario: No test exceeds 5s

- GIVEN all new tests run under pytest
- WHEN `uv run pytest` executes the new test files
- THEN no individual test exceeds 5 seconds; any test timing out is marked FAIL

---

### Requirement: REQ-EXT-14 — No regression on existing behavior

The 121 existing tests MUST remain green after the extension lands. Existing endpoints MUST be unchanged in shape and behavior.

#### Scenario: Existing test suite still green

- GIVEN all new code, schema migrations, and scheduler are applied
- WHEN `uv run pytest` runs the full suite
- THEN the original 121 tests pass; no existing test is modified

#### Scenario: Existing endpoints unchanged

- GIVEN the extension is fully deployed
- WHEN `GET /models?text_only=true&limit=5` is called
- THEN the response shape is identical to the pre-extension response; no new mandatory fields added

---

### Requirement: REQ-EXT-15 — Phase weight seed discovery and validation

The database seed loader MUST discover all files matching `seeds/*_phase_weights.json`. For each file, the loader MUST validate that the sum of all `weight` values in the `weights` array equals 1.0 (within floating-point tolerance ±0.001). Files whose weights do not sum to 1.0 MUST be skipped with a logged warning; no rows MUST be inserted for invalid files. Valid files MUST be seeded into `phase_profiles` via `INSERT OR IGNORE` (idempotent — custom edits are never overwritten). The seed file `seeds/sdd_init_phase_weights.json` MUST contain weights summing to exactly 1.0 and `_metadata` with a `rationale` field explaining each weight.

#### Scenario: Cold start seeds all valid phase weight files

- GIVEN `seeds/orchestrator_phase_weights.json` and `seeds/sdd_init_phase_weights.json` both exist and sum to 1.0
- WHEN `setup()` runs on a fresh DB
- THEN `phase_profiles` contains rows for both `orchestrator` and `sdd_init` phases; each phase has weights matching its seed file

#### Scenario: Invalid weight file skipped with warning

- GIVEN `seeds/bad_phase_weights.json` exists with weights summing to 0.85
- WHEN `setup()` runs
- THEN no rows are inserted for the `bad` phase; a warning is logged containing the filename and actual sum; other valid phase files are seeded normally

#### Scenario: Repeated setup is idempotent

- GIVEN `phase_profiles` already has rows for `orchestrator` and `sdd_init`
- WHEN `setup()` is called again (restart)
- THEN no duplicate rows are inserted; existing custom weight edits are NOT overwritten

#### Scenario: compute_ranking_for_phase returns results for sdd_init

- GIVEN `phase_profiles` has `sdd_init` weights and `model_benchmarks` has scores for ≥5 models
- WHEN `compute_ranking_for_phase("sdd_init", n=10)` is called
- THEN a list of ranked models is returned with valid scores; the `orchestrator` ranking is unchanged (regression guard)

### Requirement: REQ-EXT-16 — Multi-phase ranking embed scheduling

The scheduler ranking embed job MUST iterate over all phases listed in the `phases_enabled` config key (JSON array string). For each enabled phase, the job MUST call `compute_ranking_for_phase`. Phases with fewer than 5 ranked models MUST be skipped (no embed posted for that phase). The embed title MUST be parameterized by phase name. If `phases_enabled` is empty or missing, the job MUST fall back to `ranking_phase` config for single-phase behavior.

#### Scenario: Iterates enabled phases and posts embeds

- GIVEN `phases_enabled = '["orchestrator","sdd_init"]'` and both phases have ≥5 ranked models
- WHEN the ranking embed job fires
- THEN separate embeds are posted for each phase; each embed title includes the phase name

#### Scenario: Skips phase with insufficient data

- GIVEN `phases_enabled = '["orchestrator","sdd_init"]'` and `sdd_init` has only 3 ranked models
- WHEN the ranking embed job fires
- THEN an embed is posted for `orchestrator`; `sdd_init` is skipped without posting an embed

#### Scenario: Falls back to single phase when config empty

- GIVEN `phases_enabled = ''` and `ranking_phase = 'orchestrator'`
- WHEN the ranking embed job fires
- THEN a single embed is posted for `orchestrator` (backward-compatible behavior)

### Requirement: REQ-EXT-17 — Phases status endpoint

The plugin MUST expose `GET /api/plugins/openrouter-prices/phases` returning a list of all seeded phases with their weights and enabled status. Each entry MUST include `phase`, `weights` (array of `{benchmark_slug, weight}`), and `enabled` (boolean, derived from `phases_enabled` config).

#### Scenario: Returns all phases with weights

- GIVEN `phase_profiles` has rows for `orchestrator` and `sdd_init`
- WHEN `GET /phases` is called
- THEN 200 with a list of two entries; each entry has `phase`, `weights`, and `enabled` fields

#### Scenario: Phase enabled status reflects config

- GIVEN `phases_enabled = '["sdd_init"]'`
- WHEN `GET /phases` is called
- THEN the `orchestrator` entry has `enabled: false` and the `sdd_init` entry has `enabled: true`

---

## Cross-Cutting Additive Changes

These changes are purely additive to existing specs and require no modification:

| Spec | Change |
|------|--------|
| `plugin-system` | New plugin `openrouter_prices` conforms to the existing `setup(bot, config_manager, app)` contract — no behavioral change to the spec |
| `bot-commands` | New command `/precios-openrouter` added; no existing command modified |
