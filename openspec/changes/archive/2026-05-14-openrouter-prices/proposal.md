# Proposal: OpenRouter Prices Plugin

## Intent

The bot currently has no way to inspect AI model pricing. The user wants to query
OpenRouter model prices from the dashboard and from Discord, and later surface
ranking statistics ("best models") with scheduled channel embeds. This iteration
builds the full backend foundation — data layer, HTTP client, REST API, and a
minimal slash command — so that the ranking logic and scheduled delivery can be
added incrementally without reworking the plumbing.

## Scope

### In Scope

- New plugin `src/bot/plugins/openrouter_prices/` (6 modules: `__init__`, `models`,
  `client`, `database`, `api`, `cog`)
- SQLite schema at `data/plugins/openrouter_prices.db`: `config` (key/value) +
  `or_models` (one row per model, refreshed on fetch)
- REST endpoints under `/api/plugins/openrouter-prices/`:
  - `GET /models` — returns stored models with normalized $/Mtok prices
  - `GET /models/{model_id}` — single model detail
  - `POST /refresh` — force-refresh from OpenRouter, bypass TTL
  - `GET /config` + `PATCH /config` — manage plugin config
  - `GET /status` — last fetch time, model count, TTL state
- Discord slash command `/precios-openrouter` — ephemeral embed, top N cheapest
  text-input models (prompt + completion combined), N from config
- Activity feed: add `"openrouter"` to `ALLOWED_KINDS` in `src/web/routes/activity.py`
- Plugin wired in `src/__main__.py` (import + `await setup_openrouter(bot, cm, app)`)

### Out of Scope

- Frontend / React dashboard UI (user will provide a template later)
- Ranking heuristics for "best models" (criteria not yet defined)
- Scheduled embed delivery to a specific Discord channel (channel + format pending)
- `PluginList.tsx` card entry (frontend iteration)

## Capabilities

### New Capabilities

- `openrouter-prices`: Fetch, persist, cache, and expose OpenRouter model prices via
  REST API and Discord slash command; foundation for future ranking + embed delivery.

### Modified Capabilities

- `plugin-system`: New plugin follows existing `setup(bot, config_manager, app)` contract;
  no spec-level behavior change, purely additive.
- `bot-commands`: New slash command `/precios-openrouter` added; no existing command
  modified.

## Approach

**Approach B — on-demand fetch with TTL cache + DB persistence** (recommended by
exploration).

Flow:
1. `GET /models` hits `OpenRouterDatabase` first — returns cached rows if
   `last_fetched_at + ttl_seconds > now`.
2. On cache miss, `OpenRouterClient.fetch_models()` calls
   `https://openrouter.ai/api/v1/models` via `httpx.AsyncClient` (existing dep).
3. Raw pricing strings stored in DB; `prompt_usd_mtok` / `completion_usd_mtok`
   computed columns (×1 000 000) returned in API responses.
4. `POST /refresh` forces fetch unconditionally and emits `"openrouter"` activity event.
5. Slash command calls the same DB read + fetch path, returns top-N ephemeral embed.

Rationale over Approach A (background task): no autonomous push yet; background task
justified only when scheduled delivery lands (migration path is straightforward: extract
`client.py` + `database.py` into a poller class mirroring `YouTubeMonitor`).

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/bot/plugins/openrouter_prices/` | New | All plugin files (6 modules) |
| `data/plugins/openrouter_prices.db` | New | SQLite DB created on first run |
| `src/__main__.py` | Modified | Import + await setup_openrouter |
| `src/web/routes/activity.py` | Modified | Add `"openrouter"` to ALLOWED_KINDS |
| `tests/plugins/openrouter_prices/` | New | pytest test suite (TDD, strict mode) |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Undocumented rate limits on public `/api/v1/models` | Low | 1h TTL + exponential backoff on 429 |
| OpenRouter schema drift (field removal/rename) | Med | All model fields use `.get()` / `Optional`; never assert presence |
| Pricing unit confusion (per-token vs $/Mtok) | Low | Store raw strings; compute display columns at read time |
| Payload growth (200-400 models → more) | Low | Filter non-text modalities early; SQLite handles thousands of rows fine |
| `__main__.py` manual wiring | n/a | Existing pattern, not a risk — just a constraint |

## Rollback Plan

Plugin is purely additive:
1. Remove the `setup_openrouter` import + call from `src/__main__.py`.
2. Delete `src/bot/plugins/openrouter_prices/` and `data/plugins/openrouter_prices.db`.
3. Remove `"openrouter"` from `ALLOWED_KINDS` (reverts to `"system"` fallback).
No existing plugin is modified. No migration needed for other DBs.

## Dependencies

- `httpx` — already a production dependency (used by `youtube_notifier`)
- `aiosqlite` — already a production dependency
- OpenRouter public API — no auth, no API key required for `/api/v1/models`

## Success Criteria

- [ ] `GET /api/plugins/openrouter-prices/models` returns ≥10 models with
  `prompt_usd_mtok` and `completion_usd_mtok` as floats, `id` as string
- [ ] First call after cold start fetches from OpenRouter and populates the DB;
  second call within TTL window returns cached data without HTTP request
- [ ] `POST /api/plugins/openrouter-prices/refresh` forces a new fetch, updates
  `last_fetched_at`, and emits an `"openrouter"` activity event
- [ ] `GET /api/plugins/openrouter-prices/status` returns `model_count`,
  `last_fetched_at`, and `cache_valid` boolean
- [ ] `/precios-openrouter` slash command returns an ephemeral embed listing top 10
  cheapest text-input models (sorted by `prompt_usd_mtok + completion_usd_mtok`)
- [ ] `uv run pytest tests/plugins/openrouter_prices/` passes with ≥70% coverage
  (Strict TDD: tests written before implementation)
- [ ] Activity feed registers `"openrouter"` events (no silent fallback to `"system"`)
- [ ] Plugin removal from `__main__.py` leaves all other plugins unaffected
