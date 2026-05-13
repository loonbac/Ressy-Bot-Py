# Tasks: Discord Bot PRD

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~1800 (37 files created) |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 → PR 2 → PR 3 → PR 4 |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Foundation + Bot | PR 1 | Scaffolding, ConfigManager, /about, bot tests |
| 2 | API | PR 2 | FastAPI routes, WebSocket, API tests |
| 3 | Frontend | PR 3 | React + Tailwind + Vite, components, frontend tests |
| 4 | Integration | PR 4 | Entry point, wiring, integration tests, coverage |

## Phase 1: Foundation (10 tasks)

- [x] 1.1 Create `pyproject.toml` with UV deps (discord.py, fastapi, uvicorn, aiosqlite, pytest-asyncio, httpx)
- [x] 1.2 Create `.env.example` with DISCORD_TOKEN, DATABASE_PATH, HOST, PORT
- [x] 1.3 Create `src/__init__.py`, `src/shared/__init__.py` as package markers
- [x] 1.4 Create `src/shared/models.py` — Pydantic schemas: ConfigUpdate, ConfigResponse, WSMessage, BotStatus
- [x] 1.5 Create `src/bot/core/__init__.py` — package marker
- [x] 1.6 Create `src/bot/core/config.py` — ConfigManager singleton with get/get_all/update/on_change/load/_persist/_notify
- [x] 1.7 Create `tests/__init__.py`, `tests/conftest.py` — shared fixtures: async client, test CM, mock bot
- [x] 1.8 Write `tests/test_config_manager.py` — CRUD, persistence, listeners, WAL mode, invalid key rejection

## Phase 2: Bot Core (5 tasks)

- [x] 2.1 Create `src/bot/__init__.py`, `src/bot/cogs/__init__.py` — package markers
- [x] 2.2 Create `src/bot/core/bot.py` — Bot subclass, on_ready with tree.sync() + retry
- [x] 2.3 Create `src/bot/loader.py` — scan cogs/ dir, load_extension per file, error resilience
- [x] 2.4 Create `src/bot/cogs/about.py` — /about command with embed (name, version, uptime)
- [x] 2.5 Write `tests/test_bot_commands.py` — mock Interaction, verify /about response

## Phase 3: API (5 tasks)

- [x] 3.1 Create `src/web/__init__.py`, `src/web/routes/__init__.py` — package markers
- [x] 3.2 Create `src/web/app.py` — FastAPI app, CORS, lifespan with WS observer registration
- [x] 3.3 Create `src/web/routes/config.py` — GET /api/config, PUT /api/config/{key} with schema validation, GET /api/status
- [x] 3.4 Create `src/web/routes/ws.py` — WS /ws handler, connection set, broadcast on config change, cleanup on disconnect
- [x] 3.5 Write `tests/test_api_endpoints.py` + `tests/test_websocket.py` — 9 tests: CRUD, WS broadcast, multiple clients, disconnect

## Phase 4: Frontend (12 tasks)

- [x] 4.1 Create `frontend/package.json` — React 19, Tailwind v4, Vite, Vitest, RTL
- [x] 4.2 Create `frontend/vite.config.ts` — build → ../src/web/static, proxy /api and /ws in dev
- [x] 4.3 Create `frontend/tsconfig.json` — strict TS config
- [x] 4.4 Create `frontend/index.html` — SPA entry
- [x] 4.5 Create `frontend/src/main.tsx` — React root with WebSocketProvider
- [x] 4.6 Create `frontend/src/App.tsx` — DashboardLayout shell with route placeholders
- [x] 4.7 Create `frontend/src/types/index.ts` — TS types mirroring Pydantic schemas
- [x] 4.8 Create `frontend/src/api/config.ts` — fetchConfig(), updateConfig() helpers
- [x] 4.9 Create `frontend/src/hooks/useWebSocket.ts` — WS auto-reconnect with exponential backoff
- [x] 4.10 Create components: `DashboardLayout`, `ConfigPanel`, `PluginList`, `SystemStatus`
- [x] 4.11 Write `frontend/src/__tests__/ConfigPanel.test.tsx` — render, edit, save, error state
- [x] 4.12 Write `frontend/src/__tests__/useWebSocket.test.ts` — connection, message, reconnect, backoff

## Phase 5: Integration (3 tasks)

- [x] 5.1 Create `src/__main__.py` — asyncio.gather(bot.start(), uvicorn.run(app))
- [x] 5.2 Wire WebSocket broadcast in app.py: register ConfigManager observer → WS broadcast
- [x] 5.3 Write integration tests — verify bot ↔ API ↔ WS ↔ frontend static serving

## Phase 6: Coverage (2 tasks)

- [x] 6.1 Run pytest --cov, verify backend coverage >80%
- [x] 6.2 Run vitest --coverage, verify frontend coverage >70%
