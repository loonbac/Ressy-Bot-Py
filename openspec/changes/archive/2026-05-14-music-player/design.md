# Design: Discord Music Plugin — `music-player`

## Technical Approach

A self-contained plugin following the existing `welcome` pattern: `setup(bot, cm, app)` in `__init__.py` opens an aiosqlite DB, registers a Cog with slash commands, and mounts an APIRouter. Playback uses `FFmpegPCMAudio` with stream URLs extracted on-demand by `yt-dlp` via `asyncio.to_thread()`. A `GuildPlayerManager` singleton holds one `GuildPlayer` per guild, each owning a `TrackQueue` and managing voice client lifecycle.

## Architecture Decisions

| Decision | Choice | Rejected | Rationale |
|----------|--------|----------|-----------|
| Stream extraction | `yt-dlp` Python API via `asyncio.to_thread()` | subprocess call, lavaplayer | Library avoids process overhead; `to_thread()` guarantees non-blocking. Matches proposal. |
| Extraction timing | At play time (when track is dequeued) | At enqueue time | Stream URLs expire; extracting early wastes time and may 403 later. |
| Queue structure | In-memory `collections.deque` per guild | SQLite-backed queue | Music queues are ephemeral (lost on restart is acceptable). Simpler, faster. Config only in DB. |
| Player lifecycle | `dict[int, GuildPlayer]` in manager singleton | One global player | Discord voice is per-guild. Each guild needs independent voice client + queue. |
| Voice join strategy | `/play` auto-joins requester's channel; explicit `/join` also available | Require `/join` first | UX: most users expect `/play <url>` to Just Work. |
| Volume | `FFmpegPCMAudio` volume transform (0.0–2.0) | Per-source volume filter | Simpler; applies to current and future sources in the voice client. |

## Data Flow

```
User /play <query>
       │
       ▼
  MusicCog.play()
       │
       ├── asyncio.to_thread(yt_dlp.extract_info)  ← non-blocking
       │         │
       │         ▼
       │    Track(title, url, requester, duration)
       │
       ├── Not in voice? → connect to requester.voice.channel
       │
       ├── Currently playing? → queue.enqueue(track)
       │
       └── Idle? → _play_track(track)
                    │
                    ├── yt-dlp extract stream URL (to_thread)
                    ├── FFmpegPCMAudio(stream_url)
                    ├── voice_client.play(source, after=_on_play_end)
                    └── push_event(kind="music", title="Reproduciendo ...")

_on_play_end()
       │
       ├── queue.dequeue() → next Track → _play_track(next)
       └── queue empty → cleanup voice client
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/bot/plugins/music_player/__init__.py` | Create | Plugin setup: open DB, seed config defaults, register cog + router on app.state |
| `src/bot/plugins/music_player/cog.py` | Create | `MusicCog` with 10 slash commands, delegates to `GuildPlayerManager` |
| `src/bot/plugins/music_player/player.py` | Create | `GuildPlayer` (voice client, play/pause/skip/stop/volume) + `GuildPlayerManager` |
| `src/bot/plugins/music_player/queue_manager.py` | Create | `Track` dataclass + `TrackQueue` (FIFO deque with metadata) |
| `src/bot/plugins/music_player/api.py` | Create | REST endpoints: config GET/PUT, queue, nowplaying, control actions |
| `src/bot/plugins/music_player/models.py` | Create | Pydantic models: `MusicConfig`, `TrackInfo`, `QueueResponse`, `NowPlayingResponse` |
| `src/__main__.py` | Modify | Add `from src.bot.plugins.music_player import setup as setup_music_player` + `await setup_music_player(bot, cm, app)` before `mount_static_files` |
| `src/bot/core/bot.py` | Modify | Add `intents.voice_states = True` after `intents.members = True` |
| `pyproject.toml` | Modify | Add `"yt-dlp>=2024.12.1"` to dependencies |
| `src/web/routes/activity.py` | Modify | Add `"music"` to `ALLOWED_KINDS` set |

## Interfaces / Contracts

### Track dataclass (`queue_manager.py`)

```python
from dataclasses import dataclass, field

@dataclass
class Track:
    query: str            # original user input (URL or search term)
    title: str
    webpage_url: str      # canonical YouTube URL
    stream_url: str = ""  # resolved at play time, empty in queue
    requester_id: int
    duration: int | None = None   # seconds
    thumbnail: str = ""
```

### GuildPlayerManager (`player.py`)

```python
class GuildPlayerManager:
    def __init__(self, bot: commands.Bot): ...
    def get(self, guild_id: int) -> GuildPlayer | None: ...
    def get_or_create(self, guild_id: int) -> GuildPlayer: ...
    async def cleanup(self, guild_id: int) -> None: ...

class GuildPlayer:
    def __init__(self, guild_id: int, bot: commands.Bot): ...
    queue: TrackQueue
    voice_client: discord.VoiceClient | None
    current_track: Track | None
    volume: float  # 0.0–2.0
    async def connect(self, channel: discord.VoiceChannel) -> None: ...
    async def disconnect(self) -> None: ...
    async def play(self, track: Track) -> None: ...   # extract + start playback
    async def pause(self) -> None: ...
    async def resume(self) -> None: ...
    async def skip(self) -> None: ...
    async def stop(self) -> None: ...      # clear queue + disconnect
    def set_volume(self, vol: int) -> None: ...  # 1-200 → 0.005–2.0
```

### Config DB schema (`music_config` table)

```sql
CREATE TABLE IF NOT EXISTS music_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
-- Seeded: enabled=true, default_volume=50
```

### REST API (`api.py`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/plugins/music/config` | GET | Returns config (enabled, default_volume) |
| `/api/plugins/music/config` | PUT | Updates config |
| `/api/plugins/music/queue` | GET | Returns queued tracks (title, url, requester, duration) |
| `/api/plugins/music/nowplaying` | GET | Returns current track or `null` |
| `/api/plugins/music/control/{action}` | POST | Actions: `pause`, `resume`, `skip`, `stop`. Requires `guild_id` in body |

### Pydantic models (`models.py`)

```python
class MusicConfig(BaseModel):
    enabled: bool = True
    default_volume: int = Field(default=50, ge=1, le=200)

class TrackInfo(BaseModel):
    title: str
    webpage_url: str
    requester_id: str  # snowflake as string
    duration: int | None = None
    thumbnail: str = ""

class QueueResponse(BaseModel):
    tracks: list[TrackInfo]
    length: int

class NowPlayingResponse(BaseModel):
    track: TrackInfo | None = None
    is_paused: bool = False
    volume: int = 50
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | `TrackQueue` (enqueue, dequeue, peek, clear, ordering) | Pure deque tests, no Discord mocks |
| Unit | `GuildPlayerManager` (get/create/cleanup lifecycle) | Mock `discord.VoiceClient` |
| Unit | `models.py` validation (volume bounds, snowflake strings) | Pydantic validation tests |
| Integration | `api.py` endpoints via `httpx.AsyncClient` + fake app.state | TestClient against FastAPI app |
| E2E | Slash commands against test bot | Manual (requires voice channel + FFmpeg) |

## Migration / Rollout

No data migration required — plugin is new. DB table created on first `setup()` via `CREATE TABLE IF NOT EXISTS`.

System prerequisite: **FFmpeg must be installed**. `setup()` should check `shutil.which("ffmpeg")` and log a warning if missing, but not crash — commands will fail gracefully with a user-facing error message.

## Open Questions

- [ ] Should `/play` support searching by keyword (yt-dlp `ytsearch:` prefix) or only direct URLs? Proposal implies both. Recommend `ytsearch1:<query>` for non-URL inputs.
- [ ] Auto-disconnect timeout when bot is alone in voice channel? Not in proposal but standard UX. Recommend 5-minute idle timer as optional follow-up.
