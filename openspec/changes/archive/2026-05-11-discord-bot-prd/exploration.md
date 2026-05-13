# Exploration: Discord Bot + Web Dashboard — Stack & Architecture

## Current State

Greenfield project. No code exists yet. The only context is:
- **Project**: ressy-korosoft — Discord bot for a software development community
- **Confirmed stack direction**: Python
- **Planned features**: Slash commands, web dashboard for live config, modular plugin system
- **No test infrastructure yet**; `strict_tdd: false`

## Affected Areas

Entire project — this exploration defines the foundational architecture for all subsequent phases.

---

## Approaches

### 1. Discord Library: discord.py vs PyCord vs nextcord

| Library | Pros | Cons | Complexity |
|---------|------|------|------------|
| **discord.py (v2.x)** | Actively maintained by Rapptz (original author), largest community, best docs, 537+ code snippets, native slash commands via `app_commands`, most stable API | Slightly more verbose for slash commands than PyCord | Low |
| **PyCord** | Built-in slash command decorators, simpler bot setup for app commands, good for beginners | Smaller community, fork fragmentation risk, less battle-tested than discord.py | Low |
| **nextcord** | Clean API, good slash command support | Less active development, smaller ecosystem, fewer third-party extensions | Low |

**Recommendation: discord.py v2.x**

Rationale: It's the original, most actively maintained, has the largest community and ecosystem. The `app_commands` module (added in v2.0) provides first-class slash command support. For a community bot that will grow, stability and community support matter more than slightly simpler decorators. PyCord and nextcord are forks that solved problems discord.py already solved.

### 2. Web Framework: FastAPI vs Flask

| Framework | Pros | Cons | Complexity |
|-----------|------|------|------------|
| **FastAPI** | Native async (matches discord.py), built-in WebSocket support, auto OpenAPI docs, Pydantic validation, SSE support (v0.135+), high performance | Slightly steeper learning curve, younger ecosystem than Flask | Medium |
| **Flask** | Mature, huge ecosystem, simple, Flask-SocketIO for real-time | Sync by default (need async workarounds), WebSocket requires Flask-SocketIO (extra dependency), no built-in validation | Low |

**Recommendation: FastAPI**

Rationale: discord.py is async-first. Running Flask (sync) alongside discord.py (async) in the same process creates friction — you'd need to run them in separate threads or processes. FastAPI is async-native, has built-in WebSocket support (no extra deps), and its Pydantic validation is perfect for config schemas. The auto-generated OpenAPI docs are a bonus for the dashboard API.

### 3. Database / Config Store: SQLite vs PostgreSQL vs Redis

| Store | Pros | Cons | Complexity |
|-------|------|------|------------|
| **SQLite** | Zero config, file-based, perfect for single-server, `aiosqlite` for async, good enough for config + small data | No native pub/sub, no horizontal scaling, file locking under concurrent writes | Low |
| **PostgreSQL** | Production-grade, robust, great for scaling | Overkill for a single bot, requires external service, adds ops complexity | High |
| **Redis** | Native pub/sub (perfect for live config), fast, async support | External dependency, in-memory (needs persistence config), overkill for simple config | Medium |

**Recommendation: SQLite (with optional Redis later)**

Rationale: Start simple. SQLite handles config storage perfectly for a single-server bot. For live config reload, use a **shared in-memory state** pattern (see architecture below). If the bot scales to multiple instances later, migrate to Redis for pub/sub. Don't pre-optimize.

### 4. Frontend: Vanilla JS vs Alpine.js vs HTMX vs React/Vue

| Approach | Pros | Cons | Complexity |
|----------|------|------|------------|
| **Vanilla JS (ES Modules)** | Zero deps, full control, native component loading via `import()`, no build step | More boilerplate, manual DOM updates | Low |
| **Alpine.js** | Lightweight (15kb), declarative like Vue, perfect for dashboards, works with HTML fragments | Less ecosystem than React/Vue, not ideal for complex state | Low |
| **HTMX** | Server-driven UI, minimal JS, great with FastAPI, no SPA complexity | Less client-side control, server renders everything | Low |
| **React/Vue** | Full component ecosystem, mature tooling, great for complex UIs | Build step required, heavy for a simple dashboard, overkill | High |

**Recommendation: Alpine.js + ES Modules**

Rationale: Alpine.js gives declarative reactivity (perfect for live config updates via WebSocket) without a build step. Components are HTML files with `x-data` attributes — naturally modular. ES Modules handle lazy loading of component scripts. This keeps the frontend lightweight and matches the "simple first" philosophy. HTMX is a strong alternative if you prefer server-rendered UI, but Alpine gives better real-time feel for live config.

---

## Architecture: Real-Time Config

### Recommended Pattern: Shared State + WebSocket Broadcast

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────┐
│  Discord    │     │   ConfigManager   │     │   FastAPI   │
│  Bot (async)│◄───►│  (in-memory dict  │◄───►│  Dashboard  │
│  discord.py │     │  + SQLite persist)│     │  + WS       │
└─────────────┘     └──────────────────┘     └─────────────┘
                           │
                    ┌──────▼──────┐
                    │   SQLite    │
                    │  (persist)  │
                    └─────────────┘
```

**How it works:**

1. **ConfigManager** is a shared singleton (or injected dependency) holding config in memory
2. **FastAPI** receives config changes via HTTP POST → updates ConfigManager → persists to SQLite → broadcasts to WebSocket clients
3. **Discord Bot** reads from ConfigManager on every command execution (no restart needed)
4. **Dashboard** connects via WebSocket to receive live updates when config changes

**Why this over alternatives:**

| Pattern | Verdict |
|---------|---------|
| Shared in-memory state | ✅ Simple, fast, works for single process |
| SQLite polling | ❌ Latency, unnecessary I/O |
| File watching | ❌ Race conditions, platform-specific |
| Redis pub/sub | ⏭️ Future: only needed for multi-instance |
| SQLite WAL mode | ✅ Enables safe concurrent reads/writes |

### Live Config Reload Pattern

```python
class ConfigManager:
    def __init__(self):
        self._config: dict = {}
        self._listeners: list[Callable] = []

    async def update(self, key: str, value: Any):
        self._config[key] = value
        await self._persist(key, value)
        await self._notify(key, value)

    def get(self, key: str, default=None):
        return self._config.get(key, default)

    def on_change(self, callback: Callable):
        self._listeners.append(callback)
```

This is the **Observer pattern** — simple, effective, no external dependencies.

---

## Modular Structure

### Bot Modules (discord.py Cogs)

```
src/
├── bot/
│   ├── __main__.py          # Entry point
│   ├── core/
│   │   ├── bot.py           # Bot instance + ConfigManager
│   │   └── config.py        # ConfigManager class
│   ├── cogs/
│   │   ├── about.py         # /about command
│   │   ├── config.py        # /config admin commands
│   │   └── moderation.py    # Future: moderation features
│   └── utils/
│       └── helpers.py
├── web/
│   ├── app.py               # FastAPI app
│   ├── routes/
│   │   ├── config.py        # Config CRUD endpoints
│   │   └── ws.py            # WebSocket handler
│   └── static/
│       ├── index.html       # Dashboard shell
│       ├── components/      # Alpine.js components
│       │   ├── config-panel.html
│       │   └── status-panel.html
│       └── js/
│           ├── app.js       # Alpine app init
│           └── modules/     # ES Module components
└── shared/
    └── models.py            # Pydantic config schemas
```

### Plugin System Pattern

Each cog is a plugin:
```python
# src/bot/cogs/about.py
from discord.ext import commands

class AboutCog(commands.Cog, name="about"):
    """Plugin: /about command showing bot info."""

    def __init__(self, bot, config_manager):
        self.bot = bot
        self.config = config_manager

    @discord.app_commands.command(name="about")
    async def about(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            f"Bot v{self.config.get('version', '1.0.0')}"
        )

async def setup(bot, config_manager):
    await bot.add_cog(AboutCog(bot, config_manager))
```

**Convention**: Each cog file exports a `setup(bot, config_manager)` coroutine. The bot loads cogs dynamically from the `cogs/` directory.

### Frontend Component Loading

```html
<!-- index.html: Dashboard shell -->
<div id="app" x-data="dashboard()">
  <!-- Components loaded dynamically -->
  <template x-for="comp in components" :key="comp.name">
    <div x-html="comp.html"></div>
  </template>
</div>

<script type="module">
  // Lazy load components
  const modules = await Promise.all([
    import('./js/modules/config-panel.js'),
    import('./js/modules/status-panel.js'),
  ]);
  // Each module registers itself
</script>
```

---

## PRD — Features & Roadmap

### Phase 1: Foundation (Week 1)
- [ ] Project scaffolding (src layout, pyproject.toml, .env)
- [ ] Discord bot with `/about` slash command
- [ ] FastAPI health endpoint
- [ ] ConfigManager with SQLite persistence
- [ ] Bot + FastAPI running in same process (asyncio.gather)

### Phase 2: Dashboard (Week 2)
- [ ] FastAPI serves static dashboard
- [ ] Alpine.js dashboard shell
- [ ] Config panel (view/edit settings)
- [ ] WebSocket live updates
- [ ] Config changes reflect in bot without restart

### Phase 3: Plugin System (Week 3)
- [ ] Dynamic cog loading from directory
- [ ] Cog registration convention
- [ ] Dashboard shows active plugins
- [ ] Enable/disable plugins from dashboard

### Phase 4: Community Features (Week 4+)
- [ ] Welcome messages
- [ ] Role management
- [ ] Code snippet sharing
- [ ] Database-backed user profiles

---

## Risks

1. **Single-process limitation**: Running discord.py + FastAPI in the same asyncio loop works but couples them. If one crashes, both go down. **Mitigation**: Start single-process, split later if needed.
2. **SQLite concurrent writes**: Under heavy config changes, SQLite may lock. **Mitigation**: Use WAL mode, serialize writes through ConfigManager.
3. **Alpine.js limits**: If the dashboard grows complex, Alpine may feel limiting. **Mitigation**: The component architecture makes migration to Vue/React possible later.
4. **discord.py rate limits**: Slash commands have global/per-guild rate limits. **Mitigation**: Use `app_commands.checks` and proper error handling.
5. **Hot-reload config consistency**: If a config change happens mid-command execution, the command may see partial state. **Mitigation**: Use atomic config updates (replace entire dict, not mutate).

---

## Tradeoffs Summary

| Decision | Chosen | Rejected | Why |
|----------|--------|----------|-----|
| Discord lib | discord.py v2 | PyCord, nextcord | Stability, community, native app_commands |
| Web framework | FastAPI | Flask | Async-native, built-in WS, Pydantic |
| Config store | SQLite | PostgreSQL, Redis | Simplicity, zero ops, good enough |
| Frontend | Alpine.js + ES Modules | React/Vue, HTMX | Lightweight, no build, reactive |
| Config pattern | Shared state + Observer | Redis pub/sub, polling | Simple, no external deps |

---

## Ready for Proposal

**Yes.** The exploration is complete with clear recommendations for every major decision. The next step is `sdd-propose` to create a formal change proposal with scope, intent, and approach, followed by `sdd-spec` for delta specs and `sdd-design` for the technical design.
