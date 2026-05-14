# Tasks: Discord Music Plugin — `music-player`

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~500–600 |
| 400-line budget risk | Medium |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 (Foundation) → PR 2 (Core + Integration) → PR 3 (API + Tests) |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: Medium

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Foundation: models, queue, config wiring | PR 1 | Independent, no voice deps |
| 2 | Core + Integration: player, cog, setup | PR 2 | Depends on PR 1 models/queue |
| 3 | API + Tests: REST endpoints, test suite | PR 3 | Depends on PR 2 core |

## Phase 1: Foundation

- [x] 1.1 Create `src/bot/plugins/music_player/models.py` — MusicConfig, TrackInfo, QueueResponse, NowPlayingResponse with snowflake-as-string IDs
- [x] 1.2 Create `src/bot/plugins/music_player/queue_manager.py` — Track dataclass + TrackQueue (FIFO deque: enqueue, dequeue, peek, remove, list, clear, total_duration)
- [x] 1.3 Modify `src/bot/core/bot.py` — add `intents.voice_states = True` after `intents.members`
- [x] 1.4 Modify `pyproject.toml` — add `"yt-dlp>=2024.12.1"` to dependencies array
- [x] 1.5 Modify `src/web/routes/activity.py` — add `"music"` to ALLOWED_KINDS set

## Phase 2: Core

- [x] 2.1 Create `src/bot/plugins/music_player/player.py` — GuildPlayer (connect/disconnect, play/pause/resume/skip/stop, after_callback, set_volume) + GuildPlayerManager (get/get_or_create/cleanup dict)

## Phase 3: Integration

- [x] 3.1 Create `src/bot/plugins/music_player/cog.py` — MusicCog with 10 guild-only slash commands (play, pause, resume, skip, stop, queue, nowplaying, volume, join, leave)
- [x] 3.2 Create `src/bot/plugins/music_player/__init__.py` — setup() with DB init, config defaults seeding, cog+router registration, FFmpeg availability check
- [x] 3.3 Modify `src/__main__.py` — import and await setup_music_player() before mount_static_files

## Phase 4: API

- [x] 4.1 Create `src/bot/plugins/music_player/api.py` — GET/PUT config, GET queue, GET nowplaying, POST control/{action} with snowflake-as-string IDs and push_event integration

## Phase 5: Tests

- [x] 5.1 Create `tests/test_music_player_plugin.py` — unit tests for TrackQueue (enqueue/dequeue/peek/clear), Pydantic models (volume bounds, snowflake strings), GuildPlayerManager lifecycle (get/create/cleanup), API endpoints via httpx.AsyncClient + TestClient
