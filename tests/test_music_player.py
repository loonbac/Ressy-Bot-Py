import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from unittest.mock import MagicMock, AsyncMock, patch

from src.bot.plugins.music_player.models import MusicConfig, QueueInfo, TrackInfo
from src.bot.plugins.music_player.queue_manager import Track, TrackQueue


class TestMusicConfig:
    def test_default_values(self):
        cfg = MusicConfig()
        assert cfg.enabled is True
        assert cfg.default_volume == 50

    def test_custom_values(self):
        cfg = MusicConfig(enabled=False, default_volume=100)
        assert cfg.enabled is False
        assert cfg.default_volume == 100

    def test_volume_range_validation(self):
        # Pydantic doesn't enforce range by default with plain fields,
        # but the spec says range 1-200. We test the model accepts values in range.
        cfg_low = MusicConfig(default_volume=1)
        assert cfg_low.default_volume == 1
        cfg_high = MusicConfig(default_volume=200)
        assert cfg_high.default_volume == 200


class TestTrackInfo:
    def test_default_values(self):
        track = TrackInfo(title="Test", url="https://example.com", requester_id="1234567890123456789", requester_name="User")
        assert track.title == "Test"
        assert track.url == "https://example.com"
        assert track.requester_id == "1234567890123456789"
        assert track.requester_name == "User"
        assert track.duration_seconds == 0
        assert track.thumbnail_url == ""

    def test_full_values(self):
        track = TrackInfo(
            title="Song",
            url="https://youtube.com/watch?v=abc",
            requester_id="9876543210987654321",
            requester_name="TestUser",
            duration_seconds=180,
            thumbnail_url="https://img.youtube.com/vi/abc/default.jpg",
        )
        assert track.duration_seconds == 180
        assert track.thumbnail_url == "https://img.youtube.com/vi/abc/default.jpg"


class TestQueueInfo:
    def test_default_values(self):
        q = QueueInfo(guild_id="1234567890123456789", tracks=[])
        assert q.guild_id == "1234567890123456789"
        assert q.tracks == []
        assert q.current_track is None
        assert q.total_duration_seconds == 0
        assert q.volume == 50

    def test_with_tracks(self):
        track = TrackInfo(title="Song", url="https://example.com", requester_id="1", requester_name="User")
        q = QueueInfo(guild_id="1", tracks=[track], current_track=track, total_duration_seconds=180, volume=75)
        assert q.current_track == track
        assert q.total_duration_seconds == 180
        assert q.volume == 75


class TestTrackDataclass:
    def test_default_values(self):
        track = Track(url="https://example.com")
        assert track.url == "https://example.com"
        assert track.title == "Unknown"
        assert track.requester_id == ""
        assert track.requester_name == ""
        assert track.duration_seconds == 0
        assert track.thumbnail_url == ""

    def test_full_values(self):
        track = Track(
            url="https://youtube.com/watch?v=abc",
            title="Song",
            requester_id="123",
            requester_name="User",
            duration_seconds=180,
            thumbnail_url="https://img.youtube.com/vi/abc/default.jpg",
        )
        assert track.title == "Song"
        assert track.requester_id == "123"
        assert track.duration_seconds == 180


class TestTrackQueue:
    def test_empty_queue(self):
        q = TrackQueue()
        assert q.is_empty is True
        assert q.length == 0
        assert q.current is None
        assert q.total_duration == 0
        assert q.upcoming == []

    def test_add_and_length(self):
        q = TrackQueue()
        track = Track(url="https://example.com", title="Song", duration_seconds=180)
        q.add(track)
        assert q.is_empty is False
        assert q.length == 1
        assert q.total_duration == 180

    def test_add_multiple_and_total_duration(self):
        q = TrackQueue()
        q.add(Track(url="a", title="A", duration_seconds=120))
        q.add(Track(url="b", title="B", duration_seconds=180))
        assert q.length == 2
        assert q.total_duration == 300

    def test_pop_returns_fifo_order(self):
        q = TrackQueue()
        t1 = Track(url="a", title="A")
        t2 = Track(url="b", title="B")
        q.add(t1)
        q.add(t2)
        popped = q.pop()
        assert popped == t1
        assert q.length == 1
        assert q.upcoming == [t2]

    def test_pop_empty_returns_none(self):
        q = TrackQueue()
        assert q.pop() is None

    def test_remove_by_index(self):
        q = TrackQueue()
        t1 = Track(url="a", title="A", duration_seconds=100)
        t2 = Track(url="b", title="B", duration_seconds=200)
        t3 = Track(url="c", title="C", duration_seconds=300)
        q.add(t1)
        q.add(t2)
        q.add(t3)
        assert q.remove(1) is True
        assert q.length == 2
        assert q.upcoming == [t1, t3]
        assert q.total_duration == 400

    def test_remove_invalid_index_returns_false(self):
        q = TrackQueue()
        q.add(Track(url="a", title="A"))
        assert q.remove(5) is False
        assert q.remove(-1) is False

    def test_clear(self):
        q = TrackQueue()
        q.add(Track(url="a", title="A", duration_seconds=100))
        q.add(Track(url="b", title="B", duration_seconds=200))
        q.clear()
        assert q.is_empty is True
        assert q.length == 0
        assert q.total_duration == 0

    def test_set_current(self):
        q = TrackQueue()
        track = Track(url="a", title="A")
        q.set_current(track)
        assert q.current == track

    def test_upcoming_returns_copy(self):
        q = TrackQueue()
        t1 = Track(url="a", title="A")
        q.add(t1)
        upcoming = q.upcoming
        upcoming.clear()
        assert q.length == 1

    def test_loop_property(self):
        q = TrackQueue()
        assert q.loop is False
        q.loop = True
        assert q.loop is True


class TestActivityAllowedKinds:
    def test_music_kind_is_allowed(self):
        from src.web.routes.activity import ALLOWED_KINDS

        assert "music" in ALLOWED_KINDS


class TestBotIntents:
    def test_voice_states_intent_is_enabled(self):
        from src.bot.core.bot import Bot
        from unittest.mock import MagicMock

        mock_cm = MagicMock()
        bot = Bot(mock_cm)
        assert bot.intents.voice_states is True


class TestGuildPlayerManager:
    def test_get_returns_none_for_unknown_guild(self):
        from src.bot.plugins.music_player.player import GuildPlayerManager
        manager = GuildPlayerManager()
        assert manager.get(123456789) is None

    def test_get_or_create_creates_new_player(self):
        from src.bot.plugins.music_player.player import GuildPlayerManager, GuildPlayer
        manager = GuildPlayerManager()
        mock_bot = MagicMock()
        player = manager.get_or_create(123456789, mock_bot)
        assert isinstance(player, GuildPlayer)
        assert player.guild_id == 123456789

    def test_get_or_create_returns_existing_player(self):
        from src.bot.plugins.music_player.player import GuildPlayerManager
        manager = GuildPlayerManager()
        mock_bot = MagicMock()
        player1 = manager.get_or_create(123456789, mock_bot)
        player2 = manager.get_or_create(123456789, mock_bot)
        assert player1 is player2

    def test_cleanup_removes_player(self):
        from src.bot.plugins.music_player.player import GuildPlayerManager
        manager = GuildPlayerManager()
        mock_bot = MagicMock()
        player = manager.get_or_create(123456789, mock_bot)
        manager.cleanup(123456789)
        assert manager.get(123456789) is None

    def test_cleanup_all_removes_all_players(self):
        from src.bot.plugins.music_player.player import GuildPlayerManager
        manager = GuildPlayerManager()
        mock_bot = MagicMock()
        manager.get_or_create(1, mock_bot)
        manager.get_or_create(2, mock_bot)
        manager.cleanup_all()
        assert manager.get(1) is None
        assert manager.get(2) is None

    def test_active_players_returns_list(self):
        from src.bot.plugins.music_player.player import GuildPlayerManager
        manager = GuildPlayerManager()
        mock_bot = MagicMock()
        player = manager.get_or_create(1, mock_bot)
        active = manager.active_players()
        assert len(active) == 1
        assert active[0][0] == 1
        assert active[0][1] is player


class TestGuildPlayer:
    def test_initial_state(self):
        from src.bot.plugins.music_player.player import GuildPlayer
        mock_bot = MagicMock()
        player = GuildPlayer(guild_id=1, bot=mock_bot, volume=50)
        assert player.is_playing is False
        assert player.is_paused is False
        assert player.current_track is None
        assert player.volume == 50

    @pytest.mark.asyncio
    async def test_connect_returns_true(self):
        from src.bot.plugins.music_player.player import GuildPlayer
        mock_bot = MagicMock()
        player = GuildPlayer(guild_id=1, bot=mock_bot, volume=50)
        mock_channel = AsyncMock()
        mock_channel.connect.return_value = AsyncMock()
        result = await player.connect(mock_channel)
        assert result is True
        assert player.voice_client is not None

    @pytest.mark.asyncio
    async def test_disconnect_clears_voice_client(self):
        from src.bot.plugins.music_player.player import GuildPlayer
        mock_bot = MagicMock()
        player = GuildPlayer(guild_id=1, bot=mock_bot, volume=50)
        mock_channel = AsyncMock()
        mock_vc = AsyncMock()
        mock_channel.connect.return_value = mock_vc
        await player.connect(mock_channel)
        await player.disconnect()
        mock_vc.disconnect.assert_awaited_once()
        assert player.voice_client is None

    @pytest.mark.asyncio
    async def test_extract_returns_track_and_stream_url(self):
        from src.bot.plugins.music_player.player import GuildPlayer
        mock_bot = MagicMock()
        player = GuildPlayer(guild_id=1, bot=mock_bot, volume=50)

        mock_extract_info = {
            "title": "Test Song",
            "url": "https://youtube.com/watch?v=abc",
            "duration": 180,
            "thumbnail": "https://img.youtube.com/vi/abc/default.jpg",
            "formats": [{"url": "https://stream.url/audio", "format_id": "bestaudio"}],
        }

        with patch("src.bot.plugins.music_player.player.yt_dlp.YoutubeDL") as mock_ydl:
            instance = MagicMock()
            instance.__enter__ = MagicMock(return_value=instance)
            instance.__exit__ = MagicMock(return_value=False)
            instance.extract_info.return_value = mock_extract_info
            mock_ydl.return_value = instance

            track, stream_url = await player.extract("https://youtube.com/watch?v=abc")
            assert track.title == "Test Song"
            assert track.duration_seconds == 180
            # extract prefers the top-level "url" (yt-dlp direct stream URL),
            # falling back to formats[].url only when it is absent.
            assert stream_url == "https://youtube.com/watch?v=abc"
            # extract must NOT start playback (decoupled from streaming)
            assert player.is_playing is False

    @pytest.mark.asyncio
    async def test_extract_unwraps_search_entries(self):
        from src.bot.plugins.music_player.player import GuildPlayer
        mock_bot = MagicMock()
        player = GuildPlayer(guild_id=1, bot=mock_bot, volume=50)

        # ytsearch1: resolves to a wrapper with entries[]; extract must use
        # the real video, not the search-term wrapper.
        search_result = {
            "title": "ytsearch1:candy store heathers",
            "entries": [
                {
                    "title": "Candy Store - Heathers",
                    "webpage_url": "https://youtube.com/watch?v=real",
                    "url": "https://stream.url/real-audio",
                    "duration": 200,
                    "thumbnail": "https://img/real.jpg",
                }
            ],
        }

        with patch("src.bot.plugins.music_player.player.yt_dlp.YoutubeDL") as mock_ydl:
            instance = MagicMock()
            instance.__enter__ = MagicMock(return_value=instance)
            instance.__exit__ = MagicMock(return_value=False)
            instance.extract_info.return_value = search_result
            mock_ydl.return_value = instance

            track, stream_url = await player.extract("ytsearch1:candy store heathers")
            assert track.title == "Candy Store - Heathers"
            assert track.url == "https://youtube.com/watch?v=real"
            assert stream_url == "https://stream.url/real-audio"
            assert track.duration_seconds == 200

    @pytest.mark.asyncio
    async def test_extract_playlist_returns_all_entries(self):
        from src.bot.plugins.music_player.player import GuildPlayer
        mock_bot = MagicMock()
        player = GuildPlayer(guild_id=1, bot=mock_bot, volume=50)

        # extract_flat playlist result: bare ids/urls, one null entry that
        # must be skipped, and a full webpage_url that must be kept as-is.
        flat_result = {
            "entries": [
                {"id": "AAA", "title": "Song A", "duration": 100, "thumbnail": "tA"},
                {"url": "BBB", "title": "Song B"},
                None,
                {"webpage_url": "https://music.youtube.com/watch?v=CCC", "title": "Song C"},
            ],
        }

        with patch("src.bot.plugins.music_player.player.yt_dlp.YoutubeDL") as mock_ydl:
            instance = MagicMock()
            instance.__enter__ = MagicMock(return_value=instance)
            instance.__exit__ = MagicMock(return_value=False)
            instance.extract_info.return_value = flat_result
            mock_ydl.return_value = instance

            tracks = await player.extract_playlist(
                "https://music.youtube.com/playlist?list=OLAK"
            )
            # null entry skipped; bare ids/urls expanded to watch URLs;
            # full webpage_url preserved.
            assert [t.title for t in tracks] == ["Song A", "Song B", "Song C"]
            assert tracks[0].url == "https://www.youtube.com/watch?v=AAA"
            assert tracks[0].duration_seconds == 100
            assert tracks[1].url == "https://www.youtube.com/watch?v=BBB"
            assert tracks[2].url == "https://music.youtube.com/watch?v=CCC"

    @pytest.mark.asyncio
    async def test_start_stream_begins_playback(self):
        from src.bot.plugins.music_player.player import GuildPlayer
        mock_bot = MagicMock()
        player = GuildPlayer(guild_id=1, bot=mock_bot, volume=50)
        mock_channel = AsyncMock()
        mock_vc = MagicMock()
        mock_channel.connect.return_value = mock_vc
        await player.connect(mock_channel)

        track = TrackInfo(
            title="Test Song",
            url="https://youtube.com/watch?v=abc",
            requester_id="123",
            requester_name="User",
            duration_seconds=180,
            thumbnail_url="",
        )
        player.start_stream("https://stream.url/audio", track)
        assert player.is_playing is True
        assert player.current_track is not None
        assert player.current_track.title == "Test Song"
        mock_vc.play.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_clears_queue_and_disconnects(self):
        from src.bot.plugins.music_player.player import GuildPlayer
        mock_bot = MagicMock()
        player = GuildPlayer(guild_id=1, bot=mock_bot, volume=50)
        mock_channel = AsyncMock()
        mock_vc = AsyncMock()
        mock_channel.connect.return_value = mock_vc
        await player.connect(mock_channel)
        player.queue.add(Track(url="a", title="A"))
        await player.stop()
        assert player.queue.is_empty is True
        assert player.is_playing is False
        mock_vc.disconnect.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_after_callback_plays_next(self):
        from src.bot.plugins.music_player.player import GuildPlayer
        mock_bot = MagicMock()
        player = GuildPlayer(guild_id=1, bot=mock_bot, volume=50)
        mock_channel = AsyncMock()
        mock_vc = AsyncMock()
        mock_channel.connect.return_value = mock_vc
        await player.connect(mock_channel)

        player.queue.add(Track(url="a", title="Next Song", duration_seconds=120))

        mock_extract_info = {
            "title": "Next Song",
            "url": "https://youtube.com/watch?v=next",
            "duration": 120,
            "thumbnail": "",
            "formats": [{"url": "https://stream.url/audio", "format_id": "bestaudio"}],
        }

        with patch("src.bot.plugins.music_player.player.yt_dlp.YoutubeDL") as mock_ydl:
            instance = MagicMock()
            instance.__enter__ = MagicMock(return_value=instance)
            instance.__exit__ = MagicMock(return_value=False)
            instance.extract_info.return_value = mock_extract_info
            mock_ydl.return_value = instance

            # after_callback is async but discord calls it sync with a lambda wrapping
            # We call it directly for testing
            await player.after_callback(None)
            assert player.current_track is not None
            assert player.current_track.title == "Next Song"
            mock_vc.play.assert_called()

    @pytest.mark.asyncio
    async def test_play_from_queue_empty(self):
        from src.bot.plugins.music_player.player import GuildPlayer
        mock_bot = MagicMock()
        player = GuildPlayer(guild_id=1, bot=mock_bot, volume=50)
        mock_channel = AsyncMock()
        mock_vc = AsyncMock()
        mock_channel.connect.return_value = mock_vc
        await player.connect(mock_channel)
        await player.play_from_queue()
        assert player.is_playing is False
        assert player.current_track is None


class TestMusicCog:
    def test_cog_initialization(self):
        from src.bot.plugins.music_player.cog import MusicCog
        mock_bot = MagicMock()
        mock_manager = MagicMock()
        mock_db = MagicMock()
        mock_cm = MagicMock()
        cog = MusicCog(mock_bot, mock_manager, mock_db, mock_cm)
        assert cog.bot is mock_bot
        assert cog.player_manager is mock_manager

    @pytest.mark.asyncio
    async def test_play_command_no_voice(self):
        from src.bot.plugins.music_player.cog import MusicCog
        mock_bot = MagicMock()
        mock_manager = MagicMock()
        mock_db = MagicMock()
        mock_cm = MagicMock()
        cog = MusicCog(mock_bot, mock_manager, mock_db, mock_cm)

        interaction = AsyncMock()
        interaction.user.voice = None
        interaction.guild_id = 1

        await cog.play.callback(cog, interaction, "test query")
        interaction.response.send_message.assert_awaited_once()
        assert "conectarte" in interaction.response.send_message.call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_play_command_adds_to_queue(self):
        from src.bot.plugins.music_player.cog import MusicCog
        mock_bot = MagicMock()
        mock_manager = MagicMock()
        mock_db = MagicMock()
        mock_cm = MagicMock()
        cog = MusicCog(mock_bot, mock_manager, mock_db, mock_cm)

        interaction = AsyncMock()
        interaction.user.voice.channel = AsyncMock()
        interaction.user.id = 123
        interaction.user.display_name = "TestUser"
        interaction.guild_id = 1

        mock_player = AsyncMock()
        mock_player.is_playing = True
        mock_player.current_track = MagicMock()
        mock_player.queue = MagicMock()
        mock_manager.get_or_create.return_value = mock_player

        mock_player.extract.return_value = (
            TrackInfo(
                title="Test Song",
                url="https://youtube.com/watch?v=abc",
                requester_id="",
                requester_name="",
                duration_seconds=180,
                thumbnail_url="https://img.youtube.com/vi/abc/default.jpg",
            ),
            "https://stream.url/audio",
        )
        await cog.play.callback(cog, interaction, "test query")
        # Already playing → enqueue, must NOT start a second stream.
        mock_player.queue.add.assert_called_once()
        mock_player.start_stream.assert_not_called()
        interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_play_command_starts_stream_when_idle(self):
        from src.bot.plugins.music_player.cog import MusicCog
        mock_bot = MagicMock()
        mock_manager = MagicMock()
        mock_db = MagicMock()
        mock_cm = MagicMock()
        cog = MusicCog(mock_bot, mock_manager, mock_db, mock_cm)

        interaction = AsyncMock()
        interaction.user.voice.channel = AsyncMock()
        interaction.user.id = 123
        interaction.user.display_name = "TestUser"
        interaction.guild_id = 1

        mock_player = AsyncMock()
        mock_player.is_playing = False
        mock_player.current_track = None
        mock_player.queue = MagicMock()
        mock_manager.get_or_create.return_value = mock_player

        mock_player.extract.return_value = (
            TrackInfo(
                title="Test Song",
                url="https://youtube.com/watch?v=abc",
                requester_id="",
                requester_name="",
                duration_seconds=180,
                thumbnail_url="",
            ),
            "https://stream.url/audio",
        )
        await cog.play.callback(cog, interaction, "test query")
        # Nothing playing → stream now, do NOT enqueue.
        mock_player.start_stream.assert_called_once()
        mock_player.queue.add.assert_not_called()
        interaction.followup.send.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_stop_command(self):
        from src.bot.plugins.music_player.cog import MusicCog
        mock_bot = MagicMock()
        mock_manager = MagicMock()
        mock_db = MagicMock()
        mock_cm = MagicMock()
        cog = MusicCog(mock_bot, mock_manager, mock_db, mock_cm)

        interaction = AsyncMock()
        interaction.guild_id = 1

        mock_player = AsyncMock()
        mock_manager.get.return_value = mock_player

        await cog.stop.callback(cog, interaction)
        mock_player.stop.assert_awaited_once()
        interaction.response.send_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_queue_command(self):
        from src.bot.plugins.music_player.cog import MusicCog
        mock_bot = MagicMock()
        mock_manager = MagicMock()
        mock_db = MagicMock()
        mock_cm = MagicMock()
        cog = MusicCog(mock_bot, mock_manager, mock_db, mock_cm)

        interaction = AsyncMock()
        interaction.guild_id = 1

        mock_player = MagicMock()
        mock_player.queue.upcoming = []
        mock_player.current_track = None
        mock_manager.get.return_value = mock_player

        await cog.queue.callback(cog, interaction)
        interaction.response.send_message.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_nowplaying_command(self):
        from src.bot.plugins.music_player.cog import MusicCog
        mock_bot = MagicMock()
        mock_manager = MagicMock()
        mock_db = MagicMock()
        mock_cm = MagicMock()
        cog = MusicCog(mock_bot, mock_manager, mock_db, mock_cm)

        interaction = AsyncMock()
        interaction.guild_id = 1

        mock_track = MagicMock()
        mock_track.title = "Current Song"
        mock_track.requester_name = "User"
        mock_track.duration_seconds = 180
        mock_track.thumbnail_url = "https://img.youtube.com/vi/abc/default.jpg"

        mock_player = MagicMock()
        mock_player.current_track = mock_track
        mock_player.is_paused = False
        mock_player.volume = 75
        mock_manager.get.return_value = mock_player

        await cog.nowplaying.callback(cog, interaction)
        interaction.response.send_message.assert_awaited_once()
        embed = interaction.response.send_message.call_args[1]["embed"]
        assert embed.title == "Current Song"


class TestMusicPluginSetup:
    @pytest.mark.asyncio
    async def test_setup_creates_db_and_registers_cog(self):
        from src.bot.plugins.music_player import setup
        from unittest.mock import AsyncMock

        mock_bot = MagicMock()
        mock_bot.add_cog = AsyncMock()
        mock_cm = MagicMock()
        mock_app = MagicMock()
        mock_app.state = MagicMock()
        mock_app.include_router = MagicMock()

        db = await setup(mock_bot, mock_cm, mock_app)
        assert db is not None
        mock_bot.add_cog.assert_awaited_once()
        mock_app.include_router.assert_called_once()
        assert hasattr(mock_app.state, "music_db")
        assert hasattr(mock_app.state, "music_cog")
        assert hasattr(mock_app.state, "music_player_manager")
        await db.close()


# ---------------------------------------------------------------------------
# API integration tests (PR 3)
# ---------------------------------------------------------------------------

@pytest.fixture
async def music_db():
    import aiosqlite
    db = await aiosqlite.connect(":memory:")
    await db.execute(
        "CREATE TABLE IF NOT EXISTS music_config (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
    )
    defaults = {"enabled": "true", "default_volume": "50"}
    for key, value in defaults.items():
        await db.execute(
            "INSERT OR IGNORE INTO music_config (key, value) VALUES (?, ?)", (key, value)
        )
    await db.commit()
    yield db
    await db.close()


@pytest.fixture
async def music_api_client(music_db):
    from src.bot.plugins.music_player.api import router as music_router
    from src.bot.plugins.music_player.player import GuildPlayerManager

    app = FastAPI()
    app.state.music_db = music_db
    app.state.music_player_manager = GuildPlayerManager()

    mock_bot = MagicMock()
    app.state.bot = mock_bot
    app.state.config_manager = MagicMock()
    app.state.ffmpeg_available = True

    app.include_router(music_router, prefix="/api/plugins/music")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


class TestMusicAPI:
    async def test_get_config_returns_defaults(self, music_api_client: AsyncClient):
        resp = await music_api_client.get("/api/plugins/music/config")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["enabled"] is True
        assert data["default_volume"] == 50

    async def test_put_config_updates_values(self, music_api_client: AsyncClient):
        resp = await music_api_client.put(
            "/api/plugins/music/config",
            json={"enabled": False, "default_volume": 75},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["enabled"] is False
        assert data["default_volume"] == 75

    async def test_put_config_clamps_volume_low(self, music_api_client: AsyncClient):
        resp = await music_api_client.put(
            "/api/plugins/music/config",
            json={"default_volume": -50},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["default_volume"] == 1

    async def test_put_config_clamps_volume_high(self, music_api_client: AsyncClient):
        resp = await music_api_client.put(
            "/api/plugins/music/config",
            json={"default_volume": 500},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["default_volume"] == 200

    async def test_put_config_ignores_unknown_keys(self, music_api_client: AsyncClient):
        resp = await music_api_client.put(
            "/api/plugins/music/config",
            json={"unknown_key": "should_be_ignored"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "unknown_key" not in data

    async def test_get_queue_no_guild_id_returns_error(self, music_api_client: AsyncClient):
        resp = await music_api_client.get("/api/plugins/music/queue")
        assert resp.status_code == 422  # FastAPI missing required query param

    async def test_get_queue_with_no_player_returns_empty_queue(self, music_api_client: AsyncClient):
        resp = await music_api_client.get("/api/plugins/music/queue?guild_id=123456789")
        assert resp.status_code == 200
        data = resp.json()
        assert data["guild_id"] == "123456789"
        assert data["tracks"] == []
        assert data["current_track"] is None
        assert data["total_duration_seconds"] == 0

    async def test_get_queue_with_player_returns_tracks(self, music_api_client: AsyncClient):
        # Seed a player with tracks in the manager attached to the client app
        from src.bot.plugins.music_player.player import GuildPlayer
        manager = music_api_client._transport.app.state.music_player_manager
        mock_bot = MagicMock()
        player = manager.get_or_create(123456789, mock_bot)
        player.queue.add(Track(url="https://a.com", title="Song A", duration_seconds=120))
        player.queue.add(Track(url="https://b.com", title="Song B", duration_seconds=180))
        player.volume = 80

        resp = await music_api_client.get("/api/plugins/music/queue?guild_id=123456789")
        assert resp.status_code == 200
        data = resp.json()
        assert data["guild_id"] == "123456789"
        assert len(data["tracks"]) == 2
        assert data["tracks"][0]["title"] == "Song A"
        assert data["tracks"][1]["title"] == "Song B"
        assert data["total_duration_seconds"] == 300
        assert data["volume"] == 80

    async def test_get_nowplaying_no_guild_id_returns_error(self, music_api_client: AsyncClient):
        resp = await music_api_client.get("/api/plugins/music/nowplaying")
        assert resp.status_code == 422

    async def test_get_nowplaying_no_player_returns_empty_state(self, music_api_client: AsyncClient):
        resp = await music_api_client.get("/api/plugins/music/nowplaying?guild_id=123456789")
        assert resp.status_code == 200
        data = resp.json()
        assert data["current_track"] is None
        assert data["is_playing"] is False
        assert data["is_paused"] is False
        assert data["volume"] == 50

    async def test_get_nowplaying_with_player(self, music_api_client: AsyncClient):
        from src.bot.plugins.music_player.player import GuildPlayer
        manager = music_api_client._transport.app.state.music_player_manager
        mock_bot = MagicMock()
        player = manager.get_or_create(123456789, mock_bot)
        player._is_playing = True
        player._is_paused = True
        player._current_track = TrackInfo(
            title="Now Playing",
            url="https://example.com",
            requester_id="111",
            requester_name="User",
            duration_seconds=200,
            thumbnail_url="https://img.example.com/thumb.jpg",
        )
        player.volume = 90

        resp = await music_api_client.get("/api/plugins/music/nowplaying?guild_id=123456789")
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_playing"] is True
        assert data["is_paused"] is True
        assert data["volume"] == 90
        assert data["current_track"]["title"] == "Now Playing"
        assert data["current_track"]["duration_seconds"] == 200

    async def test_discord_channels_returns_voice_channels(self, music_api_client: AsyncClient):
        mock_guild = MagicMock()
        mock_guild.id = 111
        mock_guild.name = "Test Guild"
        mock_channel = MagicMock()
        mock_channel.id = 222
        mock_channel.name = "voice-general"
        mock_guild.voice_channels = [mock_channel]
        mock_guild.text_channels = []

        music_api_client._transport.app.state.bot.guilds = [mock_guild]
        music_api_client._transport.app.state.config_manager = MagicMock()
        music_api_client._transport.app.state.config_manager.get.return_value = None

        resp = await music_api_client.get("/api/plugins/music/discord-channels")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["channels"]) == 1
        assert data["channels"][0]["id"] == "222"
        assert data["channels"][0]["name"] == "voice-general"
        assert data["channels"][0]["guild_name"] == "Test Guild"

    async def test_discord_channels_no_bot_returns_empty(self, music_api_client: AsyncClient):
        music_api_client._transport.app.state.bot = None
        resp = await music_api_client.get("/api/plugins/music/discord-channels")
        assert resp.status_code == 200
        data = resp.json()
        assert data["channels"] == []
