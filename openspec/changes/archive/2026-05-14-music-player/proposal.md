# Proposal: Discord Music Plugin — `music-player`

## Intent

Enable Discord users to play music in voice channels via slash commands. Addresses demand for entertainment utility in community servers. Requires FFmpeg system dependency and `yt-dlp` library for stream extraction.

## Scope

### In Scope
- Music playback via FFmpegPCMAudio with per-guild player instances
- Queue management (FIFO with metadata tracking)
- 10 slash commands: `/play`, `/pause`, `/resume`, `/skip`, `/stop`, `/queue`, `/nowplaying`, `/volume`, `/join`, `/leave`
- SQLite config: `default_volume` (int, default 50), `enabled` (bool, default true)
- REST API endpoints for queue, nowplaying, playback control
- Activity feed integration for music events

### Out of Scope
- Spotify direct playback (limited to metadata extraction)
- Playlist parsing (YouTube/Spotify playlists)
- Audio effects (bass boost, nightcore)
- Premium platform integrations (SoundCloud, Twitch)

## Capabilities

### New Capabilities
- `music-player`: music playback plugin with voice integration, queue management, and slash commands

### Modified Capabilities
- `bot-commands`: extends with 10 music-related slash commands
- `plugin-system`: adds music_player to plugin loader pattern

## Approach

- `yt-dlp` as Python library via `asyncio.to_thread()` (avoids blocking event loop)
- GuildPlayer manager: dict keyed by `guild_id`, one instance per guild
- Extract stream URLs at play time (not queue time) to avoid expiration
- Pydantic model for config validation
- REST API mirrors cog functionality for dashboard control

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/bot/plugins/music_player/` | New | Plugin package: `__init__.py`, `cog.py`, `api.py`, `models.py`, `player.py`, `queue_manager.py` |
| `src/__main__.py` | Modified | Add `setup_music_player()` call |
| `src/bot/core/bot.py` | Modified | Add `intents.voice_states = True` |
| `pyproject.toml` | Modified | Add `yt-dlp>=2024.12.1` dependency |
| `src/web/routes/activity.py` | Modified | Add `"music"` to `ALLOWED_KINDS` |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| FFmpeg not installed on host | HIGH | Check at init, document as system requirement, fail gracefully |
| YouTube blocking yt-dlp | MEDIUM | Keep yt-dlp updated, use extractor args, fallback to alternate extractors |
| yt-dlp blocking event loop | MEDIUM | Always wrap in `asyncio.to_thread()`, never call sync |
| Spotify URLs limited support | LOW | Document limitation, extract metadata only, no direct playback |

## Rollback Plan

1. Remove `src/bot/plugins/music_player/` directory
2. Remove `yt-dlp` from `pyproject.toml` dependencies
3. Revert `src/__main__.py` setup call
4. Revert `intents.voice_states` in bot.py
5. Restart bot

All changes isolated to plugin pattern — no core bot logic modified.

## Dependencies

- System: FFmpeg binary installed (`ffmpeg` command available)
- Python: `yt-dlp>=2024.12.1`
- Discord intents: `voice_states` (privileged, requires enablement in Developer Portal)

## Success Criteria

- [ ] Bot connects to voice channel and plays audio from YouTube URL
- [ ] Queue persists across multiple track additions
- [ ] Volume control adjusts playback in real-time
- [ ] All 10 slash commands respond within 3 seconds
- [ ] Config persists across bot restarts
- [ ] Activity feed logs music events with correct kind
- [ ] No event loop blocking (>99% of operations async)
