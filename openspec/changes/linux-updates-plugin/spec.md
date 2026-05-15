# Spec: linux-updates-plugin

## Purpose

New plugin that consumes the public [endoflife.date](https://endoflife.date) API to track EOL dates of Linux distributions (Ubuntu, Debian, Fedora, Rocky Linux, Linux Mint, Linux kernel). Provides REST endpoints, Discord slash commands, periodic refresh scheduler, and follows the project plugin pattern.

## Defaults

| Key | Default | Description |
|-----|---------|-------------|
| `enabled` | `"true"` | Plugin habilitado al inicio |
| `refresh_interval_hours` | `"12"` | Cada 12 horas, una vez al medio dia |
| `eol_warning_days` | `"90"` | Ventana de warning antes de EOL |
| `discord_channel_id` | `""` | Canal para notificaciones automaticas |

## ADDED Requirements

### Requirement: REQ-PROD-01 — Product catalog seed

The plugin MUST seed 6 fixed products via `INSERT OR IGNORE` on first boot: ubuntu, debian, fedora, rocky-linux, linuxmint, linux. Each product has `slug` (PK), `display_name`, `last_check_at` (nullable), `last_check_status` (`ok`|`error`), `last_check_error` (nullable). Repeated setup MUST NOT overwrite existing data.

- **GIVEN** a fresh DB
- **WHEN** `connect()` runs
- **THEN** `products` contains 6 rows with `last_check_at=NULL`, `last_check_status='ok'`

- **GIVEN** products already seeded with custom data
- **WHEN** `connect()` runs again
- **THEN** no rows are overwritten; `INSERT OR IGNORE` skips all 6

### Requirement: REQ-PROD-02 — Product status tracking

`last_check_status` MUST be `'ok'` on successful refresh and `'error'` on failure with `last_check_error` set to the error message. On failure, existing release data MUST remain intact (graceful degradation).

- **GIVEN** refresh for "ubuntu" succeeds
- **WHEN** `upsert_releases` completes
- **THEN** `last_check_status='ok'`, `last_check_error=NULL`, `last_check_at` updated

- **GIVEN** refresh for "ubuntu" fails with timeout
- **WHEN** the error is caught
- **THEN** `last_check_status='error'`, `last_check_error` contains message, prior releases unchanged

### Requirement: REQ-REL-01 — Release storage

Each release is 1 row per `cycle` per product. Nullable columns: `codename`, `latest_version`, `lts`, `support_date`, `extended_support_date`, `release_label`, `raw_json`. `eol_date` and `release_date` are stored as ISO date strings or NULL.

- **GIVEN** API returns Ubuntu 24.04 with codename "Noble Numbat", lts=true, eol="2029-05-31"
- **WHEN** normalized and stored
- **THEN** row has `codename='Noble Numbat'`, `lts=1`, `eol_date='2029-05-31'`

### Requirement: REQ-REL-02 — Idempotent upsert

Same `product_slug` + `cycle` MUST update existing row, never duplicate. `fetched_at` is always updated to current timestamp.

- **GIVEN** a row exists for `(ubuntu, 24.04)` with `fetched_at=T1`
- **WHEN** upsert runs again for the same cycle
- **THEN** row is updated; `fetched_at` > T1; no duplicate row created

### Requirement: REQ-CLI-01 — EndOfLifeClient.fetch_product

`fetch_product(slug)` MUST call `GET https://endoflife.date/api/{slug}.json` via `httpx` with 15s timeout. Returns a list of normalized release dicts. Uses 3 retries with exponential backoff (2^attempt seconds).

- **GIVEN** the API returns 200 with valid JSON array
- **WHEN** `fetch_product("ubuntu")` is called
- **THEN** a list of dicts is returned with normalized fields

- **GIVEN** the API returns 404
- **WHEN** `fetch_product("nonexistent")` is called after 3 retries
- **THEN** `EndOfLifeAPIError(status_code=404)` is raised

- **GIVEN** the API times out 3 times
- **WHEN** `fetch_product("ubuntu")` is called
- **THEN** `EndOfLifeTimeoutError` is raised

### Requirement: REQ-CLI-02 — API response normalization

The client MUST normalize heterogeneous API responses:

| Field | Rule |
|-------|------|
| `eol` | `false` (bool) → `NULL`; string date → string |
| `support` | `false` → `NULL`; string → string |
| `extendedSupport` | `false` → `NULL`; string → string |
| `lts` | absent → `NULL`; present → bool |
| `latest` | absent → `NULL` (Linux Mint) |
| `codename` | absent → `NULL` (Linux kernel, Rocky) |
| `releaseLabel` | store raw string if present, else `NULL` |

- **GIVEN** Linux 7.0 returns `{"eol": false, "codename": null}`
- **WHEN** normalized
- **THEN** `eol_date=NULL`, `codename=NULL`

- **GIVEN** Ubuntu 25.10 returns `{"extendedSupport": false}`
- **WHEN** normalized
- **THEN** `extended_support_date=NULL`

- **GIVEN** Fedora returns `{"releaseLabel": "__RELEASE_CYCLE__ (__CODENAME__)"}` 
- **WHEN** normalized
- **THEN** `release_label='__RELEASE_CYCLE__ (__CODENAME__)'` (raw, no template resolution)

- **GIVEN** Linux Mint response has no `latest` key
- **WHEN** normalized
- **THEN** `latest_version=NULL`

### Requirement: REQ-CLI-03 — Error hierarchy

Custom exceptions: `EndOfLifeAPIError(status_code, body)`, `EndOfLifeTimeoutError`, `EndOfLifeParseError`. HTTP non-200 → API error. Timeout → timeout error. JSON decode failure → parse error.

- **GIVEN** API returns 500 with body "server error"
- **WHEN** parsed
- **THEN** `EndOfLifeAPIError(status_code=500, body="server error")`

- **GIVEN** API returns 200 with invalid JSON
- **WHEN** decoded
- **THEN** `EndOfLifeParseError` is raised

### Requirement: REQ-CLI-04 — Rate limit awareness

No documented rate limit. If response contains `X-RateLimit-Remaining` header with value < 10, the client MUST log a warning.

- **GIVEN** response header `X-RateLimit-Remaining: 5`
- **WHEN** the client processes the response
- **THEN** `logger.warning(...)` is called mentioning low remaining quota

### Requirement: REQ-DB-01 — Database schema

Two tables in `data/plugins/linux-updates.db`:

**products**: `slug` TEXT PK, `display_name` TEXT, `last_check_at` REAL (unix), `last_check_status` TEXT, `last_check_error` TEXT.

**releases**: `id` INTEGER PK AUTOINCREMENT, `product_slug` TEXT FK→products.slug, `cycle` TEXT, `codename` TEXT, `release_date` TEXT, `eol_date` TEXT, `latest_version` TEXT, `lts` INTEGER, `support_date` TEXT, `extended_support_date` TEXT, `release_label` TEXT, `raw_json` TEXT, `fetched_at` REAL.

Index on `(product_slug)` and `(eol_date)`.

- **GIVEN** a fresh DB
- **WHEN** `connect()` completes
- **THEN** both tables exist with correct schema and indexes

### Requirement: REQ-DB-02 — CRUD operations

| Method | Returns |
|--------|---------|
| `get_products()` | `list[dict]` — all products |
| `get_product(slug)` | `dict \| None` |
| `get_releases(slug)` | `list[dict]` sorted by `release_date DESC` |
| `get_active_releases(slug)` | releases where `eol_date >= today` or `eol_date IS NULL` |
| `upsert_releases(slug, releases)` | replaces existing rows for same slug+cycle |
| `get_summary()` | counts per product, expiring soon (<90 days) |

- **GIVEN** Ubuntu has 44 releases, 3 active
- **WHEN** `get_active_releases("ubuntu")` is called
- **THEN** 3 rows returned, each with `eol_date >= today` or `eol_date IS NULL`

- **GIVEN** Ubuntu 20.04 has `eol_date` in 15 days
- **WHEN** `get_summary()` is called
- **THEN** `expiring_soon` list contains `{slug: "ubuntu", cycle: "20.04", days_left: 15}`

### Requirement: REQ-API-01 — GET /products

Mounted at `/api/plugins/linux-updates/products`. Returns 200 with list of products including computed fields: `release_count`, `active_count`, `stale` (no refresh in 2x interval), `updated_at` (humanized relative time).

- **GIVEN** Ubuntu has 44 releases, last refresh 2 hours ago
- **WHEN** `GET /products` is called
- **THEN** response includes `{"slug": "ubuntu", "release_count": 44, "active_count": N, "stale": false, "updated_at": "hace 2 horas"}`

### Requirement: REQ-API-02 — GET /products/{slug}

Returns 200 with product detail and its releases. Each release includes computed `days_until_eol` (int or null) and `status` (`active`|`expired`|`unknown`). Returns 404 if slug not in seeded products.

- **GIVEN** Ubuntu 24.04 has `eol_date` 1095 days from today
- **WHEN** `GET /products/ubuntu` is called
- **THEN** release includes `{"cycle": "24.04", "days_until_eol": 1095, "status": "active"}`

- **GIVEN** slug "nonexistent" is not in products
- **WHEN** `GET /products/nonexistent` is called
- **THEN** 404 with `{detail: "Producto no encontrado"}`

### Requirement: REQ-API-03 — GET /summary (sin endpoints de refresh manual)

Returns aggregated stats: `total_releases`, `active_releases`, `expiring_soon` (<90 days), `expired`, `no_eol_date` (releases with `eol_date IS NULL`).

- **GIVEN** DB has releases with various EOL states
- **WHEN** `GET /summary` is called
- **THEN** response categorizes all releases correctly; `no_eol_date` includes entries like `{"slug": "linux", "cycle": "7.0", "note": "Sin fecha EOL asignada"}`

### Requirement: REQ-API-04 — GET /config

Returns current plugin config: `enabled`, `refresh_interval_hours` (default 12), `eol_warning_days` (default 90), `discord_channel_id`.

- **GIVEN** config has defaults
- **WHEN** `GET /config` is called
- **THEN** 200 with all config keys and their current values

### Requirement: REQ-API-05 — PUT /config

Updates config. MUST validate: `refresh_interval_hours >= 1`, `eol_warning_days >= 7`. Invalid values return 400 with Spanish neutro peruano detail.

- **GIVEN** request with `{"refresh_interval_hours": 0}`
- **WHEN** `PUT /config` is called
- **THEN** 400 `{"detail": "refresh_interval_hours debe ser mayor o igual a 1"}`

- **GIVEN** valid config update
- **WHEN** `PUT /config` is called
- **THEN** 200 with updated config; activity event emitted

### Requirement: REQ-COG-01 — /linux status command

Discord slash command showing embed summary per product. Embed color: green (0x57F287) if all active, yellow (0xFEE75C) if expiring soon, red (0xED4245) if any expired. Each product row: display name, latest active version, days until EOL.

- **GIVEN** Ubuntu 20.04 expires in 15 days, all others active
- **WHEN** `/linux status` is invoked
- **THEN** yellow embed with Ubuntu row showing "20.04 - 15 dias hasta EOL"

- **GIVEN** no releases in DB
- **WHEN** `/linux status` is invoked
- **THEN** embed says "Plugin sin datos. Los datos se descargan automaticamente cada 12 horas"

### Requirement: REQ-COG-02 — /linux check {producto}

Discord slash command with autocomplete for the 6 slugs. Shows detailed embed: active releases, recent historical, dates. If no data, instructs user to refresh.

- **GIVEN** Ubuntu has data with 3 active releases
- **WHEN** `/linux check ubuntu` is invoked
- **THEN** embed lists active releases with cycle, codename, EOL date, days remaining

- **GIVEN** Fedora has no releases yet
- **WHEN** `/linux check fedora` is invoked
- **THEN** embed says "Sin datos. Los datos se descargan automaticamente cada 12 horas"

### Requirement: REQ-SCH-01 — Periodic refresh scheduler

Background asyncio task started in `setup()`. Ticks every 60s. Evaluates per-product whether refresh is needed based on `refresh_interval_hours` config. **Enabled by default** (`enabled=true`). Default `refresh_interval_hours=12` (cada 12 horas, una vez al medio dia cada dia).

- **GIVEN** `enabled=true`, `refresh_interval_hours=12`, product last refreshed 13h ago
- **WHEN** scheduler tick fires
- **THEN** refresh is triggered for that product

- **GIVEN** `enabled=false`
- **WHEN** scheduler tick fires
- **THEN** no refresh is triggered

### Requirement: REQ-SCH-02 — Per-product deduplication

Scheduler MUST skip refresh for a product if `last_check_at` is within the configured interval. Independent per product.

- **GIVEN** Ubuntu refreshed 1 hour ago, interval is 12h
- **WHEN** scheduler tick fires
- **THEN** Ubuntu is skipped; other overdue products are refreshed

### Requirement: REQ-SCH-03 — Automatic EOL notifications

When the scheduler detects releases entering the EOL warning window (`days_until_eol <= eol_warning_days` config, default 90), it MUST publish an embed notification to the configured `discord_channel_id`. Uses the same `embed_publisher` pattern as openrouter_prices. MUST track which releases have already been notified via metadata to avoid duplicate notifications for the same release.

- **GIVEN** Ubuntu 20.04 has `eol_date` 85 days from today, no prior notification sent
- **WHEN** scheduler tick fires
- **THEN** an embed notification is published to the Discord channel; metadata records `notified_eol_ubuntu_20.04`

- **GIVEN** Ubuntu 20.04 already has `notified_eol_ubuntu_20.04` in metadata
- **WHEN** scheduler fires again the next day
- **THEN** no duplicate notification is sent for that release

- **GIVEN** `discord_channel_id` is not configured (empty string)
- **WHEN** notification is triggered
- **THEN** the notification is silently skipped (no crash)

### Requirement: REQ-EDGE-01 — Empty DB first use

All endpoints MUST handle empty state gracefully: `GET /products` returns 6 products with zero counts, `GET /summary` returns zeros, `/linux status` shows "sin datos" message.

- **GIVEN** fresh DB with only seeded products, no releases
- **WHEN** `GET /products` is called
- **THEN** 6 products returned, each with `release_count: 0`, `active_count: 0`, `last_check_at: null`

### Requirement: REQ-EDGE-02 — Plugin setup contract

The plugin MUST follow `setup(bot, config_manager, app)` pattern per plugin-system spec. MUST create `data/plugins/linux-updates.db`, register router at `/api/plugins/linux-updates`, add cog via `bot.add_cog()`, store state on `app.state`, start scheduler.

- **GIVEN** bot is starting
- **WHEN** `setup(bot, config_manager, app)` is called
- **THEN** DB created, router mounted, cog registered, scheduler started, `app.state.linux_updates_db` set

### Requirement: REQ-QUAL-01 — Test coverage

Coverage targets: `database.py` >= 85%, `client.py` >= 85%, `api.py` >= 80%. All tests use mocked httpx (no real API calls). Import check: `from src.bot.plugins.linux_updates import setup` succeeds.

- **GIVEN** all new tests run
- **WHEN** `uv run pytest --cov=src.bot.plugins.linux_updates` executes
- **THEN** coverage meets thresholds; no real HTTP requests made

### Requirement: REQ-QUAL-02 — No regressions

All existing tests MUST remain green. No changes to other plugins or shared code.

- **GIVEN** the plugin is fully integrated
- **WHEN** `uv run pytest` runs the full suite
- **THEN** all pre-existing tests pass unchanged
