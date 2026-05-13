# Proposal: Discord Bot PRD — Foundation + Live Dashboard

## Intent

Build a modular Discord bot with a real-time web dashboard for the ressy-korosoft community, enabling live configuration changes without bot restarts.

---

## In Scope

| Area | Description |
|------|-------------|
| **Scaffolding** | UV package manager, `src/` layout, `.env` configuration, pyproject.toml |
| **Discord Bot** | discord.py v2 with `/about` slash command using `app_commands` |
| **FastAPI Server** | Async web server with WebSocket support and config endpoints |
| **Frontend** | React 19+ + Tailwind v4+ + Vite SPA dashboard |
| **ConfigManager** | Singleton with Observer pattern, SQLite persistence (WAL mode) |
| **WebSocket** | Real-time config broadcast from FastAPI to dashboard |
| **Testing** | pytest + pytest-asyncio (backend), Vitest + React Testing Library (frontend) |

---

## Out of Scope

- Multi-instance / clustering (postponed)
- Redis or external pub/sub (postponed)
- Advanced community features (welcome messages, moderation, profiles)
- Dashboard user authentication
- Plugin hot-reloading (cogs load at startup only)

---

## Capabilities

| ID | Capability | Description |
|----|------------|-------------|
| `bot-commands` | Discord slash commands | Bot responds to `/about` with version/info |
| `live-config` | Real-time configuration | Dashboard edits reflect in bot instantly |
| `web-dashboard` | React SPA dashboard | View/edit bot config with live updates |
| `plugin-system` | Modular cogs | Dynamic cog loading from `src/bot/cogs/` |

---

## Approach

### Architecture: Single-Process Async

Bot and FastAPI run in the **same asyncio event loop** via `asyncio.gather()`:

```
src/
├── bot/
│   ├── __main__.py       # Entry: asyncio.gather(bot.start(), server.serve())
│   ├── core/
│   │   ├── bot.py        # Discord bot instance
│   │   └── config.py     # ConfigManager singleton
│   └── cogs/
│       └── about.py      # /about command
├── web/
│   ├── app.py            # FastAPI instance
│   ├── routes/
│   │   ├── config.py     # Config CRUD endpoints
│   │   └── ws.py         # WebSocket handler
│   └── static/           # Built React app
└── shared/
    └── models.py         # Pydantic schemas
```

### ConfigManager Pattern

```python
class ConfigManager:
    _instance = None
    def __init__(self):
        self._config: dict = {}
        self._listeners: list[Callable] = []
    
    async def update(self, key: str, value: Any):
        self._config[key] = value
        await self._persist(key, value)  # SQLite WAL
        await self._notify(key, value)   # WebSocket broadcast
```

### Key Decisions

| Decision | Rationale |
|----------|-----------|
| UV over pip | Faster installs, lockfile support, modern Python packaging |
| discord.py v2 | Most stable, largest ecosystem, native `app_commands` |
| FastAPI | Async-native, built-in WebSocket, Pydantic validation |
| SQLite WAL | Enables concurrent reads/writes without locking |
| React 19 + Vite | Fast HMR, modern component architecture |
| Vitest + RTL | Fast, React-native testing with RTL patterns |

---

## Affected Areas

Entire codebase (greenfield). All files created from scratch.

---

## Risks

| Risk | Mitigation |
|------|------------|
| **Single-process coupling** | Bot crash takes down API. Start single-process, split if needed. |
| **SQLite WAL mode required** | Enable `PRAGMA journal_mode=WAL` on init. |
| **Vite dev server + FastAPI coordination** | Run Vite build in watch mode, FastAPI serves built assets. |
| **Discord rate limits** | Use `app_commands.checks`, implement backoff. |
| **WebSocket reconnection** | Implement exponential backoff in React client. |

---

## Rollback Plan

1. `git revert` last commit
2. Remove UV virtual environment: `rm -rf .venv/`
3. Clean generated assets: `rm -rf src/web/static/`
4. Restore previous `.env` backup

---

## Success Criteria

| Criterion | Verification |
|-----------|--------------|
| `/about` responds in Discord | Bot replies with version string |
| Dashboard loads in browser | React app renders at `http://localhost:8000` |
| Live config works | Change `welcome_message` in dashboard → bot uses new value instantly |
| Backend tests pass | `pytest tests/backend/` — 100% coverage on ConfigManager, endpoints |
| Frontend tests pass | `npm run test` — Vitest + RTL covers ConfigPanel, WebSocket hook |

---

## Next Steps

1. ✅ **Proposal approved** → proceed to `sdd-spec` for delta specs
2. Then `sdd-design` for technical architecture details
3. Then `sdd-tasks` for implementation task breakdown
4. Finally `sdd-apply` to execute
