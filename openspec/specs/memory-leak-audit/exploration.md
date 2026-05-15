# Exploration: Memory Leak Audit

## Current State

The bot runs Discord.py + FastAPI + multiple plugins on a **single shared event loop**. Each plugin manages its own SQLite database, HTTP clients, and background tasks. Shutdown is handled via `asyncio.gather()` on `bot.start()` and `uvicorn.serve()`, with a FastAPI lifespan that runs `teardown_callbacks` registered by some (but not all) plugins.

## Leak Sources Found

---

### Leak #1: YouTube HTTP Client + DB Connection Never Closed on Shutdown

- **Severity**: **CRITICAL**
- **File**: `src/bot/plugins/youtube_notifier/__init__.py` (no teardown), `src/bot/plugins/youtube_notifier/monitor.py` lines 24-31, 111-115
- **Pattern**: `YouTubeMonitor` creates a long-lived `httpx.AsyncClient` at `__init__` (line 24) and an `aiosqlite.Connection` at `init_db()` (line 35). The `close_db()` method exists (line 111) that closes both, but **no teardown callback is registered**.
- **Why it leaks**: The `httpx.AsyncClient` holds connection pools, DNS caches, and SSL contexts. On graceful shutdown, these are never released. Over multiple restarts, connection pool entries accumulate. The aiosqlite connection also holds file descriptors and WAL state.

### Leak #2: YouTube Monitor Background Task Never Stopped on Shutdown

- **Severity**: **CRITICAL**
- **File**: `src/bot/plugins/youtube_notifier/__init__.py` (no teardown), `src/bot/plugins/youtube_notifier/monitor.py` lines 117-129
- **Pattern**: `monitor.start()` creates `asyncio.create_task(self._polling_loop())` at line 119. The `stop()` method exists (line 121) that sets `_stop_event` and cancels the task, but **no teardown callback is registered**.

### Leak #3: Blackboard Polling Task Never Stopped on Shutdown

- **Severity**: **CRITICAL**
- **File**: `src/bot/plugins/blackboard/__init__.py` lines 34-54
- **Pattern**: Creates `asyncio.create_task(_polling_loop())` at line 53, stores `stop_event` at line 35, but **no teardown callback is registered** to set the event and await the task.

### Leak #4: Music Player Guild Dict Grows Unbounded

- **Severity**: **HIGH**
- **File**: `src/bot/plugins/music_player/player.py` lines 289-317
- **Pattern**: `GuildPlayerManager._players: dict[int, GuildPlayer]` creates a player per guild via `get_or_create()` but `cleanup_all()` is **never called**. If the bot is removed from a guild while playing, or a voice connection drops unexpectedly, the player entry remains.

### Leak #5: YouTube `_consecutive_failures` Dict Never Pruned

- **Severity**: **HIGH**
- **File**: `src/bot/plugins/youtube_notifier/monitor.py` line 32
- **Pattern**: Entries are added when a channel fails (line 188), reset to 0 on success (line 186), but **never removed** even when the channel is deleted from subscriptions.

### Leak #6: YouTube `youtube_videos` Table Grows Indefinitely (Disk + Memory on Query)

- **Severity**: **MEDIUM**
- **File**: `src/bot/plugins/youtube_notifier/monitor.py` lines 69-81, 553-560
- **Pattern**: Every video ever detected is inserted with `INSERT OR IGNORE`. **No cleanup job, no TTL, no max row count**. API endpoint loads ALL videos per channel (`limit=9999`).

### Leak #7: Music Player `cleanup()` Creates Fire-and-Forget Tasks

- **Severity**: **MEDIUM**
- **File**: `src/bot/plugins/music_player/player.py` lines 303-309
- **Pattern**: `cleanup(guild_id)` calls `asyncio.create_task(player.stop())` inside `try/except RuntimeError`. Tasks are **not tracked** — if `stop()` hangs, the task remains pending indefinitely.

### Leak #8: No Graceful Shutdown for Uvicorn Server Task

- **Severity**: **MEDIUM**
- **File**: `src/__main__.py` lines 66-76
- **Pattern**: `server_task = asyncio.create_task(server.serve())` — when `asyncio.gather()` completes, the server task is cancelled without `server.shutdown()`. Conversely, bot task is cancelled without `bot.close()`.

## Non-Issues Reviewed (areas checked and found OK)

| Area | Verdict | Reason |
|------|---------|--------|
| ActivityLog (`activity.py`) | OK | `collections.deque(maxlen=80)` — bounded ring buffer |
| WebSocket connections (`ws.py`) | OK | Cleanup in `finally` block |
| Frontend intervals | OK | All `setInterval` have `clearInterval` in `useEffect` cleanup |
| Frontend event listeners | OK | All `addEventListener` have `removeEventListener` cleanup |
| Frontend WebSocket | OK | Proper cleanup: clears timeout, nulls ref, closes socket |
| ConfigManager listeners | OK | Singleton pattern; registered once at startup |
| Pillow images (`banner.py`) | OK | In-memory BytesIO, GC handles cleanup |
| httpx per-request clients | OK | Most use `async with httpx.AsyncClient()` context manager |
| Blackboard scraper cleanup | OK | `scraper.close()` called in `finally` blocks |
| OpenRouter scheduler | OK | Has teardown callback registered |
| Linux Updates scheduler | OK | Has teardown callback registered |

## Approaches for Each Fix

**Leak #1-3 (Missing teardown callbacks):**
Register teardown callbacks following the pattern used by `openrouter_prices` and `linux_updates`:
```python
async def _teardown() -> None:
    await monitor.stop()
    await monitor.close_db()
app.state.teardown_callbacks.append(_teardown)
```

**Leak #4 (Music player unbounded dict):**
Add teardown callback calling `cleanup_all()`. Add `on_guild_remove` listener.

**Leak #5 (YouTube failures dict):**
Prune entry from `_consecutive_failures` when channel is removed from subscriptions.

**Leak #6 (YouTube videos table):**
Add periodic cleanup job deleting videos older than N days, or cap at max N rows.

**Leak #7 (Music fire-and-forget tasks):**
Track cleanup tasks in a set and await them via `asyncio.wait()` with timeout.

**Leak #8 (No graceful shutdown):**
Wrap `asyncio.gather()` in try/finally calling `bot.close()`.

## Recommendation

Priority order:
1. **P1** — Add teardown callbacks for YouTube + Blackboard (Leaks #1, #2, #3)
2. **P1** — Add graceful shutdown for bot (Leak #8)
3. **P2** — Add teardown for Music player (Leak #4)
4. **P2** — Prune YouTube `_consecutive_failures` (Leak #5)
5. **P3** — Add YouTube video cleanup job (Leak #6)
6. **P3** — Track music cleanup tasks (Leak #7)

## Risks

- Teardown order matters: FastAPI lifespan teardown runs *after* uvicorn stops serving
- `bot.close()` must check `bot.is_closed()` first
- Deleting old YouTube videos may break dashboard history feature
- Blackboard stop during scrape needs `scraper.close()` protection

## Ready for Proposal

**Yes**
