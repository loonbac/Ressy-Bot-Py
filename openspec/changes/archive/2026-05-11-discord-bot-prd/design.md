# Design: Discord Bot PRD

## Technical Approach

Single-process asyncio architecture: `asyncio.gather(bot.start(), uvicorn.run(app))` runs both Discord bot and FastAPI on the same event loop. They share a `ConfigManager` singleton as the single source of truth. React SPA (built by Vite to `src/web/static/`) is served by FastAPI as `StaticFiles`. No process boundary — no serialization, no IPC overhead.

## Architecture Decisions

| # | Decision | Choice | Rejected | Rationale |
|---|----------|--------|----------|-----------|
| 1 | Process model | Single-process `asyncio.gather` | Separate bot + API processes | Shared event loop eliminates IPC. Crash risk accepted — split later if needed. |
| 2 | ConfigManager | Singleton + Observer + SQLite WAL | Redis, JSON files, env-only | WAL allows concurrent reads during writes. Observer pattern enables WS broadcast without polling. |
| 3 | Live updates | WebSocket | Polling, SSE | Bidirectional, lower latency, one connection for all events. |
| 4 | Frontend build | Vite → `src/web/static/` → FastAPI `StaticFiles` | Separate CDN, Next.js SSR | Zero infra. `vite build` outputs static files, FastAPI serves them. SPA fallback to `index.html`. |
| 5 | Package manager | UV + `pyproject.toml` | pip + requirements.txt | Lockfile, faster installs, group dev dependencies. |
| 6 | Cog loading | Scan `cogs/` dir, `load_extension()` per file | Manual registration, plugin discovery | Convention over config. Each file = one cog, `setup(bot, config_manager)` entry point. |
| 7 | Frontend architecture | Context + hooks, no global state lib | Redux, Zustand | App is small. `WebSocketProvider` context + `useConfig` hook cover all state needs. |

## Data Flow

```
React Dashboard                    FastAPI                         Discord Bot
─────────────                      ───────                         ───────────
                                   ┌─────────────┐
  GET /api/config ────────────────→│ ConfigManager│←── load() on startup
  ←─ JSON config ─────────────────│    │  │     │
                                   │    │  └────────→ SQLite (WAL)
  PUT /api/config/{key} ─────────→│    │
  ←─ 200 OK ──────────────────────│    └──→ _notify() ──→ observers
                                   │              │
  WS /ws ◄────────────────────────│              └──→ broadcast change
  ← { event, key, value }         │                   to all WS clients
                                   └─────────────┘
  ConfigPanel edit ──→ PUT ──→ ConfigManager.update() ──→ persist + broadcast
                                                      ──→ cog reads on next command
```

**Config update flow**: User edits in dashboard → `PUT /api/config/{key}` → `ConfigManager.update(key, value)` → SQLite persist → notify observers → WS broadcast → connected dashboards update live → cogs read updated config on next command invocation.

**WebSocket flow**: Client connects to `WS /ws` → server keeps connection in set → on config change, server iterates all connections and sends `{ event, key, value }` → client hook parses and updates React state → reconnection with exponential backoff (1s→2s→4s→max 30s).

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `pyproject.toml` | Create | UV project config: deps (discord.py, fastapi, uvicorn, aiosqlite), dev deps (pytest, pytest-asyncio, httpx), scripts |
| `.env.example` | Create | Template: `DISCORD_TOKEN`, `DATABASE_PATH`, `HOST`, `PORT` |
| `src/__init__.py` | Create | Package marker |
| `src/__main__.py` | Create | Entry point: `asyncio.gather(bot.start(token), uvicorn.run(app))` |
| `src/bot/__init__.py` | Create | Package marker |
| `src/bot/core/__init__.py` | Create | Package marker |
| `src/bot/core/bot.py` | Create | `discord.ext.commands.Bot` setup, `on_ready` handler, `tree.sync()` with retry |
| `src/bot/core/config.py` | Create | `ConfigManager` singleton: `get()`, `get_all()`, `update()`, `on_change()`, `load()`, `_persist()` |
| `src/bot/cogs/__init__.py` | Create | Package marker |
| `src/bot/cogs/about.py` | Create | `/about` slash command: embed with name, version, uptime |
| `src/bot/loader.py` | Create | Scan `cogs/` dir, `load_extension()` per file, error resilience |
| `src/web/__init__.py` | Create | Package marker |
| `src/web/app.py` | Create | FastAPI app: CORS, mount routes, `StaticFiles` for React build, SPA fallback |
| `src/web/routes/__init__.py` | Create | Package marker |
| `src/web/routes/config.py` | Create | `GET /api/config`, `PUT /api/config/{key}`, `GET /api/status` |
| `src/web/routes/ws.py` | Create | `WS /ws` handler: connection set, broadcast on config change |
| `src/shared/__init__.py` | Create | Package marker |
| `src/shared/models.py` | Create | Pydantic schemas: `ConfigUpdate`, `ConfigResponse`, `WSMessage`, `BotStatus` |
| `frontend/package.json` | Create | React 19, Tailwind v4, Vite, Vitest, RTL |
| `frontend/vite.config.ts` | Create | Build output: `../src/web/static`, proxy `/api` and `/ws` to FastAPI in dev |
| `frontend/tailwind.config.ts` | Create | Tailwind v4 config |
| `frontend/tsconfig.json` | Create | TypeScript strict mode |
| `frontend/index.html` | Create | SPA entry HTML |
| `frontend/src/main.tsx` | Create | React root, `WebSocketProvider` wrapper |
| `frontend/src/App.tsx` | Create | `DashboardLayout` shell with route placeholders |
| `frontend/src/components/DashboardLayout.tsx` | Create | Layout: sidebar nav + main content area |
| `frontend/src/components/ConfigPanel.tsx` | Create | Config key-value list, editable fields, save button |
| `frontend/src/components/PluginList.tsx` | Create | Loaded cogs list with status |
| `frontend/src/components/SystemStatus.tsx` | Create | Bot online status, uptime, WS connection indicator |
| `frontend/src/hooks/useWebSocket.ts` | Create | WS connection with auto-reconnect, exponential backoff |
| `frontend/src/api/config.ts` | Create | `fetchConfig()`, `updateConfig(key, value)` API helpers |
| `frontend/src/types/index.ts` | Create | TypeScript types mirroring Pydantic schemas |
| `frontend/tests/ConfigPanel.test.tsx` | Create | Renders config, edit flow, save flow, error state |
| `frontend/tests/useWebSocket.test.ts` | Create | Connection, message receive, reconnection, backoff |
| `tests/__init__.py` | Create | Package marker |
| `tests/conftest.py` | Create | Shared fixtures: async client, test ConfigManager, mock bot |
| `tests/test_config_manager.py` | Create | CRUD, persistence, listeners, atomicity, WAL mode |
| `tests/test_bot_commands.py` | Create | `/about` command mock test |
| `tests/test_api_endpoints.py` | Create | FastAPI TestClient: config CRUD, status endpoint |
| `tests/test_websocket.py` | Create | WS connect, receive broadcast, multiple clients |
| `README.md` | Create | Setup, run, test, build instructions |

## Interfaces / Contracts

**Pydantic models** (`src/shared/models.py`):
```python
class ConfigUpdate(BaseModel):
    key: str
    value: Any

class ConfigResponse(BaseModel):
    key: str
    value: Any
    updated_at: datetime

class WSMessage(BaseModel):
    event: Literal["config:updated", "config:deleted"]
    key: str
    value: Any

class BotStatus(BaseModel):
    online: bool
    uptime_seconds: float
    loaded_cogs: list[str]
    connected_ws_clients: int
```

**ConfigManager public API** (`src/bot/core/config.py`):
```python
class ConfigManager:
    _instance: ClassVar["ConfigManager | None"] = None
    async def load(self, db_path: str) -> None: ...
    def get(self, key: str) -> Any: ...
    def get_all(self) -> dict[str, Any]: ...
    async def update(self, key: str, value: Any) -> None: ...
    def on_change(self, callback: Callable[[str, Any], Awaitable[None]]) -> None: ...
    async def _persist(self, key: str, value: Any) -> None: ...
    async def _notify(self, key: str, value: Any) -> None: ...
```

**Cog contract**: Each cog file MUST define:
```python
async def setup(bot: commands.Bot, config_manager: ConfigManager) -> None:
    await bot.add_cog(MyCog(bot, config_manager))
```

**FastAPI endpoints**:
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/config` | Return all config as `{ configs: [ConfigResponse] }` |
| PUT | `/api/config/{key}` | Update config key, body `ConfigUpdate` |
| GET | `/api/status` | Return `BotStatus` |
| WS | `/ws` | Real-time config change stream |

**WS message format**: `{ "event": "config:updated" | "config:deleted", "key": "str", "value": any }`

## Testing Strategy

| Layer | What | How |
|-------|------|-----|
| Unit | ConfigManager CRUD, persistence, listeners, atomicity | pytest-asyncio, in-memory SQLite |
| Unit | Bot commands (`/about`) | Mock `discord.Interaction`, verify embed response |
| Integration | FastAPI endpoints | `httpx.AsyncClient` via `TestClient`, assert status codes + JSON |
| Integration | WebSocket | `TestClient` websocket connect, verify broadcast to multiple clients |
| Frontend | ConfigPanel render, edit, save, error | Vitest + RTL, mock `useWebSocket` and API calls |
| Frontend | useWebSocket hook | Vitest, mock WS, verify reconnect with backoff |
| Coverage | Backend >80%, Frontend >70% | pytest-cov, Vitest coverage |

## Migration / Rollout

No migration required — greenfield project. First deployment is the initial commit.

## Open Questions

- [ ] Should `ConfigManager.update()` validate keys against a known schema, or accept any key? (Spec says "invalid key rejected" but schema is undefined)
- [ ] Dashboard authentication is out of scope — confirm this is acceptable for initial release (anyone with URL can edit config)
