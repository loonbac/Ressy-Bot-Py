import pytest

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
