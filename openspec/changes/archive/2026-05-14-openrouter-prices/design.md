# Design: OpenRouter Prices Plugin

## Technical Approach

On-demand fetch with TTL cache + SQLite persistence, mirroring the `blackboard` plugin's
class-based database pattern combined with the `music_player` inline `aiosqlite` setup
style. A dedicated `OpenRouterClient` class owns the `httpx.AsyncClient` lifecycle;
`OpenRouterDatabase` wraps all SQL; `api.py` reads from `app.state`; the cog queries the
same DB layer. No background task: refresh is caller-driven (endpoint or command).

## Architecture Decisions

### Decision: Class-based DB vs inline aiosqlite (music_player pattern)

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Inline `aiosqlite.connect` in `__init__.py` (music_player) | Simpler setup, harder to unit-test DB methods in isolation | Rejected |
| `OpenRouterDatabase` class (blackboard pattern) | Testable methods, clean separation of schema/CRUD from setup | **Chosen** |

**Rationale**: `upsert_models` + stale-marking + metadata CRUD are non-trivial; isolating
them in a class lets tests call them directly without spinning up FastAPI.

### Decision: PUT with partial-body semantics for /config

| Option | Tradeoff | Decision |
|--------|----------|----------|
| PATCH strict RFC 7396 | Correct HTTP semantics, but inconsistent with existing music_player/blackboard which use PUT | Rejected |
| PUT partial (only provided keys updated) | Matches existing pattern in `music_player/api.py`, simpler client code | **Chosen** |

**Rationale**: Every existing plugin uses `PUT /config` with sparse body. Consistency
outweighs HTTP pedantry here.

### Decision: Retry strategy in OpenRouterClient

| Option | Tradeoff | Decision |
|--------|----------|----------|
| tenacity / httpx-retry library | Full backoff policy, more deps | Rejected |
| Manual 1-retry with `await asyncio.sleep(2)` | Zero deps, readable, sufficient for a single external call | **Chosen** |

**Rationale**: The endpoint is public, unauthenticated, and called infrequently (TTL ≥ 1h).
One retry covers transient blips without over-engineering.

### Decision: Price normalization location

| Option | Tradeoff | Decision |
|--------|----------|----------|
| Compute in DB layer, store in extra columns | Redundant storage, migration risk if formula changes | Rejected |
| Compute at serialization time in API response | Single source of truth (raw string in DB), formula lives in one helper | **Chosen** |

`to_per_million(raw: str | None) -> float | None` in `models.py`. Both `_raw` and
`_per_mtok` fields returned so consumers can display either.

### Decision: cache_stale semantics

**Choice**: `cache_stale = True` only when `last_fetched_at` is older than `2 × ttl_seconds`
AND `last_fetch_status != "ok"`. Normal TTL expiry (between 1× and 2× TTL) returns
`cached: False` (triggers client-side refresh prompt) but `cache_stale: False`.

### Decision: Snowflake validation for discord_channel_id

**Choice**: Accept empty string OR a numeric string of length 17–20. No Discord API call.
Validated at PUT time; invalid values return HTTP 422 with a clear Spanish error message.

## Data Flow

```
GET /models (cache hit)
  Request → api.py → OpenRouterDatabase.list_models() → rows → serialize → Response

GET /models (cache miss) / POST /refresh
  Request → api.py → OpenRouterClient.fetch_models()
           → on success
           OpenRouterDatabase.upsert_models(models, fetched_at)
           OpenRouterDatabase.set_metadata("last_fetched_at", ...)
           push_event(kind="openrouter", ...)
           →
           OpenRouterDatabase.list_models() → serialize → Response

/precios-openrouter (Discord slash)
  Interaction → OpenRouterPricesCog
    → config = db.get_config()
    → if not enabled → ephemeral "deshabilitado"
    → check TTL: if stale → client.fetch_models() → db.upsert_models()
    → db.list_models(text_only=True, sort_by="prompt", sort_dir="asc",
                     limit=max_models_command)
    → build embed (≤25 fields) → send ephemeral (or public if flag)
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/bot/plugins/openrouter_prices/__init__.py` | Create | `setup(bot, cm, app)` — DB init, defaults seed, router mount, cog register, `app.state` assignment |
| `src/bot/plugins/openrouter_prices/models.py` | Create | Pydantic models + `to_per_million()` helper |
| `src/bot/plugins/openrouter_prices/client.py` | Create | `OpenRouterClient` with `fetch_models()`, `httpx.AsyncClient`, 1-retry |
| `src/bot/plugins/openrouter_prices/database.py` | Create | `OpenRouterDatabase` — schema creation, config CRUD, model upsert + stale-marking, metadata CRUD |
| `src/bot/plugins/openrouter_prices/api.py` | Create | `APIRouter` at `/api/plugins/openrouter-prices` — 6 endpoints |
| `src/bot/plugins/openrouter_prices/cog.py` | Create | `OpenRouterPricesCog` — `/precios-openrouter` slash command |
| `src/__main__.py` | Modify | Add import + `await setup_openrouter_prices(bot, cm, app)` after music_player block |
| `src/web/routes/activity.py` | Modify | Add `"openrouter"` to `ALLOWED_KINDS` set |
| `tests/plugins/openrouter_prices/__init__.py` | Create | Empty package marker |
| `tests/plugins/openrouter_prices/test_models.py` | Create | `to_per_million` edge cases |
| `tests/plugins/openrouter_prices/test_database.py` | Create | Schema, seed, upsert, stale-marking, list filters, metadata |
| `tests/plugins/openrouter_prices/test_api.py` | Create | FastAPI TestClient for all 6 endpoints, mocked client |

## Interfaces / Contracts

### models.py

```python
class OpenRouterModel(BaseModel):
    id: str
    name: str
    description: str
    context_length: int
    input_modalities: list[str]
    output_modalities: list[str]
    modality: str
    pricing_prompt_raw: str | None
    pricing_completion_raw: str | None
    pricing_image_raw: str | None
    pricing_prompt_per_mtok: float | None
    pricing_completion_per_mtok: float | None
    stale: bool
    fetched_at: int

class ConfigResponse(BaseModel):
    enabled: bool
    ttl_seconds: int
    max_models_command: int
    discord_channel_id: str

class ConfigPayload(BaseModel):
    enabled: bool | None = None
    ttl_seconds: int | None = None
    max_models_command: int | None = None
    discord_channel_id: str | None = None

class ModelsResponse(BaseModel):
    models: list[OpenRouterModel]
    count: int
    cached: bool
    cache_stale: bool
    last_fetched_at: int | None

class RefreshResponse(BaseModel):
    updated: int
    source: Literal["openrouter", "cache_fallback"]
    fetched_at: int

class StatusResponse(BaseModel):
    enabled: bool
    models_count: int
    stale_count: int
    last_fetched_at: int | None
    ttl_seconds: int
    last_fetch_status: str
    last_fetch_error: str | None

def to_per_million(raw: str | None) -> float | None:
    # Returns raw * 1_000_000 as float; None on missing/unparseable
```

### client.py

```python
class OpenRouterClient:
    BASE_URL = "https://openrouter.ai/api/v1/models"
    TIMEOUT = 15.0

    def __init__(self) -> None: ...
    async def fetch_models(self, force: bool = False) -> list[dict]: ...
    async def close(self) -> None: ...
```

### database.py

```python
class OpenRouterDatabase:
    def __init__(self, db_path: str) -> None: ...
    async def connect(self) -> None: ...
    async def close(self) -> None: ...
    async def _create_schema(self) -> None: ...
    async def _seed_defaults(self) -> None: ...
    async def get_config(self) -> dict[str, str]: ...
    async def update_config(self, updates: dict[str, str]) -> None: ...
    async def upsert_models(self, models: list[dict], fetched_at: int) -> int: ...
    async def list_models(
        self,
        text_only: bool = True,
        sort_by: str = "prompt",
        sort_dir: str = "asc",
        limit: int | None = None,
        include_stale: bool = False,
    ) -> list[dict]: ...
    async def get_model(self, model_id: str) -> dict | None: ...
    async def get_metadata(self) -> dict[str, str]: ...
    async def set_metadata(self, key: str, value: str) -> None: ...
    async def count_models(self, stale: bool = False) -> int: ...
```

### DB Schema (DDL)

```sql
CREATE TABLE IF NOT EXISTS config (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS models (
    id                              TEXT PRIMARY KEY,
    name                            TEXT,
    description                     TEXT,
    created_at                      INTEGER,
    context_length                  INTEGER,
    input_modalities                TEXT,   -- JSON array
    output_modalities               TEXT,   -- JSON array
    modality                        TEXT,
    pricing_prompt                  TEXT,
    pricing_completion              TEXT,
    pricing_image                   TEXT,
    pricing_request                 TEXT,
    pricing_web_search              TEXT,
    pricing_input_cache_read        TEXT,
    pricing_input_cache_write       TEXT,
    top_provider_context_length     INTEGER,
    top_provider_max_completion_tokens INTEGER,
    top_provider_is_moderated       INTEGER,
    raw_json                        TEXT NOT NULL,
    stale                           INTEGER NOT NULL DEFAULT 0,
    fetched_at                      INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS metadata (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE INDEX IF NOT EXISTS idx_models_stale ON models(stale);
CREATE INDEX IF NOT EXISTS idx_models_pricing_prompt ON models(pricing_prompt);
```

### Default config seeds

```python
DEFAULTS = {
    "enabled": "true",
    "ttl_seconds": "3600",
    "max_models_command": "10",
    "discord_channel_id": "",
}
```

### __main__.py diff snippet

```python
    # Cargar plugin de música
    from src.bot.plugins.music_player import setup as setup_music_player
    await setup_music_player(bot, cm, app)

    # Cargar plugin de precios OpenRouter         ← ADD
    from src.bot.plugins.openrouter_prices import setup as setup_openrouter_prices  # ← ADD
    await setup_openrouter_prices(bot, cm, app)   # ← ADD

    # Mount SPA static files *after* all API routes are registered
    mount_static_files(app)
```

### API Endpoints

| Method | Path | Response model |
|--------|------|----------------|
| GET | `/models` | `ModelsResponse` |
| GET | `/models/{model_id}` | `OpenRouterModel` or 404 |
| GET | `/config` | `ConfigResponse` |
| PUT | `/config` | `ConfigResponse` |
| POST | `/refresh` | `RefreshResponse` |
| GET | `/status` | `StatusResponse` |

Query params for `GET /models`: `text_only: bool = True`, `sort: str = "prompt"`,
`direction: str = "asc"`, `limit: int | None = None`.

`sort` maps to DB column: `"prompt"` → `pricing_prompt`, `"completion"` → `pricing_completion`,
`"context"` → `context_length`, `"name"` → `name`. Unknown values silently fall back to `"prompt"`.

## Testing Strategy

| Layer | What | Approach |
|-------|------|----------|
| Unit | `to_per_million` — None, "0", negative, overflow | Pure function, no fixtures |
| Unit | `OpenRouterDatabase._create_schema` | Spin up `:memory:` DB, assert tables exist |
| Unit | `_seed_defaults` | Assert config keys present; re-run is idempotent |
| Unit | `upsert_models` stale-marking | Insert 3 models, upsert 2 different ones, assert 1 stale |
| Unit | `list_models` filters + sort | `:memory:` DB, assert text_only excludes image-only entries |
| Unit | `get_metadata` + `set_metadata` | CRUD round-trip |
| Integration | `GET /models` cold start | Mock `OpenRouterClient.fetch_models` returning fixture data |
| Integration | `GET /models` cache hit | Call twice; assert client called once |
| Integration | `POST /refresh` | Assert `updated` count, activity event emitted |
| Integration | `PUT /config` invalid snowflake | Assert 422 |
| Integration | `GET /status` | Assert all fields present |
| Integration | `GET /models/{id}` missing | Assert 404 |

Test runner: `uv run pytest tests/plugins/openrouter_prices/`. Coverage target ≥70%.
`OpenRouterClient` is always mocked via `unittest.mock.AsyncMock` — live API never called.

## Migration / Rollout

No migration required. Plugin is purely additive. DB file `data/plugins/openrouter_prices.db`
is created on first run. Rollback: remove the three lines in `__main__.py`, delete the plugin
directory and the DB file.

## Extensibility Hooks (deferred — do NOT implement now)

- `OpenRouterClient.fetch_models()` returns raw `list[dict]` → future ranking module
  consumes the same source without re-fetch
- `models` table stores all OpenRouter fields (via `raw_json` fallback) → ranking scores
  can be computed in-DB without schema changes
- Activity kind `"openrouter"` already reserved in `ALLOWED_KINDS` for both refresh events
  and future scheduled channel embed events
- `discord_channel_id` config key already present → future scheduled embed reads from it;
  the `OpenRouterPricesCog` structure mirrors `YouTubeMonitor`'s pattern and can be extended
  with a `start()` / `stop()` polling loop without touching `api.py`

## Open Questions

- None. All questions from the scope brief have been resolved in the Architecture Decisions
  section above (PUT semantics, `cache_stale` formula, snowflake validation).
