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

| Endpoint | Method | Success | Error |
|----------|--------|---------|-------|
| `/models` | GET | 200 list | 500 if DB fails |
| `/models/{model_id}` | GET | 200 single model | 404 if not found |
| `/config` | GET | 200 config object | — |
| `/config` | PUT | 200 updated config | 400 on invalid input |
| `/refresh` | POST | 200 `{updated_count, last_fetched_at}` | 500 on fetch failure |
| `/status` | GET | 200 status object | — |

`GET /models` MUST support optional query params: `text_only` (boolean, default true),
`sort_by` (`prompt` or `completion`, default `prompt`), `order` (`asc`/`desc`,
default `asc`), `limit` (positive int, default 50).

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
open the DB, seed defaults, register the router at `/api/plugins/openrouter-prices`,
add the cog via `bot.add_cog()`, and store state on `app.state`. The plugin MUST be
imported and awaited in `src/__main__.py`.

#### Scenario: Setup completes without error

- GIVEN no prior DB exists and all dependencies are available
- WHEN `setup(bot, config_manager, app)` is called
- THEN the DB is created, defaults seeded, cog registered, router mounted,
  and `app.state.openrouter_prices_db` is set

#### Scenario: Plugin wired in `__main__.py`

- GIVEN `src/__main__.py` is the application entry point
- WHEN the bot starts
- THEN `setup_openrouter_prices(bot, cm, app)` is awaited before serving requests

#### Scenario: Graceful shutdown

- GIVEN the bot is shutting down
- WHEN the shutdown sequence runs (mirroring existing plugin teardown pattern)
- THEN the aiosqlite connection is closed without error

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

## Cross-Cutting Additive Changes

These changes are purely additive to existing specs and require no modification:

| Spec | Change |
|------|--------|
| `plugin-system` | New plugin `openrouter_prices` conforms to the existing `setup(bot, config_manager, app)` contract — no behavioral change to the spec |
| `bot-commands` | New command `/precios-openrouter` added; no existing command modified |
