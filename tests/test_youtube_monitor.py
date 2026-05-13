from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.bot.plugins.youtube_notifier.monitor import YouTubeMonitor


@pytest.fixture
async def youtube_client(monitor: YouTubeMonitor):
    from src.bot.plugins.youtube_notifier.api import router as youtube_router

    app = FastAPI()
    app.state.youtube_monitor = monitor
    app.include_router(youtube_router, prefix="/api/plugins/youtube")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
async def monitor():
    mock_bot = MagicMock()
    mock_cm = MagicMock()
    mon = YouTubeMonitor(":memory:", mock_cm, mock_bot)
    await mon.init_db()
    yield mon
    await mon.close_db()


class TestDatabaseOperations:
    async def test_add_subscription(self, monitor: YouTubeMonitor):
        success = await monitor.add_subscription("UC_test_123", "Canal Test")
        assert success is True

        sub = await monitor.get_subscription("UC_test_123")
        assert sub is not None
        assert sub["channel_id"] == "UC_test_123"
        assert sub["channel_name"] == "Canal Test"
        assert sub["thumbnail_url"] == ""
        assert sub["active"] is True
        assert sub["notifications_enabled"] is True

    async def test_add_subscription_with_thumbnail(self, monitor: YouTubeMonitor):
        success = await monitor.add_subscription("UC_test_123", "Canal Test", "https://example.com/thumb.jpg")
        assert success is True

        sub = await monitor.get_subscription("UC_test_123")
        assert sub is not None
        assert sub["thumbnail_url"] == "https://example.com/thumb.jpg"

    async def test_remove_subscription(self, monitor: YouTubeMonitor):
        await monitor.add_subscription("UC_test_123", "Canal Test")
        await monitor.remove_subscription("UC_test_123")

        subs = await monitor.list_subscriptions()
        assert len(subs) == 0

    async def test_list_subscriptions(self, monitor: YouTubeMonitor):
        await monitor.add_subscription("UC_a", "Canal A")
        await monitor.add_subscription("UC_b", "Canal B")

        subs = await monitor.list_subscriptions()
        assert len(subs) == 2
        ids = {s["channel_id"] for s in subs}
        assert ids == {"UC_a", "UC_b"}

    async def test_get_config_defaults(self, monitor: YouTubeMonitor):
        cfg = await monitor.get_config()
        assert cfg.enabled is True
        assert cfg.poll_interval_minutes == 30
        assert cfg.discord_channel_id is None
        assert cfg.callback_url == ""
        assert cfg.announcement_message == "@everyone ¡Hay un nuevo video en {canal}!"
        assert cfg.filter_shorts is False
        assert cfg.filter_premieres is False
        assert cfg.filter_min_duration == 0

    async def test_update_config(self, monitor: YouTubeMonitor):
        from src.bot.plugins.youtube_notifier.models import YouTubePluginConfig

        cfg = YouTubePluginConfig(
            enabled=False,
            poll_interval_minutes=5,
            discord_channel_id=123456,
            callback_url="https://example.com/callback",
            announcement_message="Nuevo video!",
            filter_shorts=True,
            filter_premieres=True,
            filter_min_duration=300,
        )
        await monitor.update_config(cfg)

        loaded = await monitor.get_config()
        assert loaded.enabled is False
        assert loaded.poll_interval_minutes == 5
        assert loaded.discord_channel_id == 123456
        assert loaded.callback_url == "https://example.com/callback"
        assert loaded.announcement_message == "Nuevo video!"
        assert loaded.filter_shorts is True
        assert loaded.filter_premieres is True
        assert loaded.filter_min_duration == 300


class TestVideoDetection:
    async def test_new_video_detected(self, monitor: YouTubeMonitor):
        await monitor.add_subscription("UC_test", "Canal Test")

        # Simular inserción manual de un video existente
        await monitor._db.execute(
            """
            INSERT INTO youtube_videos (video_id, channel_id, title, url, published_at, notified)
            VALUES (?, ?, ?, ?, ?, 0)
            """,
            ("video_old", "UC_test", "Old Video", "https://youtu.be/video_old", datetime.now(timezone.utc).isoformat()),
        )
        await monitor._db.commit()

        # Simular fetch_rss que devuelve un video nuevo y uno viejo
        new_video = MagicMock()
        new_video.video_id = "video_new"
        new_video.channel_id = "UC_test"
        new_video.title = "New Video"
        new_video.url = "https://youtu.be/video_new"
        new_video.published_at = datetime.now(timezone.utc)
        new_video.notified = False

        old_video = MagicMock()
        old_video.video_id = "video_old"
        old_video.channel_id = "UC_test"
        old_video.title = "Old Video"
        old_video.url = "https://youtu.be/video_old"
        old_video.published_at = datetime.now(timezone.utc)
        old_video.notified = False

        with patch.object(monitor, "fetch_recent_videos", return_value=[new_video, old_video]):
            with patch.object(monitor, "notify_new_video", new_callable=AsyncMock):
                new_videos = await monitor.poll_channels()

        assert len(new_videos) == 1
        assert new_videos[0].video_id == "video_new"

    async def test_no_duplicate_videos(self, monitor: YouTubeMonitor):
        await monitor.add_subscription("UC_test", "Canal Test")

        video = MagicMock()
        video.video_id = "video_1"
        video.channel_id = "UC_test"
        video.title = "Video 1"
        video.url = "https://youtu.be/video_1"
        video.published_at = datetime.now(timezone.utc)
        video.notified = False

        with patch.object(monitor, "fetch_recent_videos", return_value=[video]):
            with patch.object(monitor, "notify_new_video", new_callable=AsyncMock):
                new_videos = await monitor.poll_channels()
        assert len(new_videos) == 1

        # Segunda poll con el mismo video
        with patch.object(monitor, "fetch_recent_videos", return_value=[video]):
            with patch.object(monitor, "notify_new_video", new_callable=AsyncMock):
                new_videos = await monitor.poll_channels()
        assert len(new_videos) == 0


class TestRSSParsing:
    async def test_fetch_rss_parses_xml(self, monitor: YouTubeMonitor):
        rss_xml = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:yt="http://www.youtube.com/xml/schemas/2015">
  <title>Canal Test</title>
  <entry>
    <id>yt:video:ABC123:UC_test</id>
    <yt:videoId>ABC123</yt:videoId>
    <yt:channelId>UC_test</yt:channelId>
    <title>Video de prueba</title>
    <link rel="alternate" href="https://www.youtube.com/watch?v=ABC123"/>
    <published>2024-01-15T10:30:00+00:00</published>
  </entry>
</feed>
"""
        mock_response = MagicMock()
        mock_response.text = rss_xml
        mock_response.raise_for_status = MagicMock()

        with patch.object(monitor._http, "get", return_value=mock_response):
            videos = await monitor._fetch_via_rss("UC_test")

        assert len(videos) == 1
        assert videos[0].video_id == "ABC123"
        assert videos[0].title == "Video de prueba"
        assert videos[0].url == "https://www.youtube.com/watch?v=ABC123"
        assert videos[0].channel_id == "UC_test"

    async def test_fetch_rss_empty_feed(self, monitor: YouTubeMonitor):
        rss_xml = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Canal Vacio</title>
</feed>
"""
        mock_response = MagicMock()
        mock_response.text = rss_xml
        mock_response.raise_for_status = MagicMock()

        with patch.object(monitor._http, "get", return_value=mock_response):
            videos = await monitor._fetch_via_rss("UC_empty")

        assert len(videos) == 0


class TestAPIIntegration:
    async def test_status_endpoint_data(self, monitor: YouTubeMonitor):
        status = await monitor.get_status()
        assert "enabled" in status
        assert "channels_count" in status
        assert "videos_count" in status
        assert "last_poll" in status
        assert status["channels_count"] == 0
        assert status["videos_count"] == 0

    async def test_get_videos_empty(self, monitor: YouTubeMonitor):
        videos = await monitor.get_videos(limit=10)
        assert videos == []

    async def test_get_videos_with_data(self, monitor: YouTubeMonitor):
        await monitor.add_subscription("UC_test", "Canal Test")
        await monitor._db.execute(
            """
            INSERT INTO youtube_videos (video_id, channel_id, title, url, published_at, notified)
            VALUES (?, ?, ?, ?, ?, 0)
            """,
            ("v1", "UC_test", "Video 1", "https://youtu.be/v1", datetime.now(timezone.utc).isoformat()),
        )
        await monitor._db.commit()

        videos = await monitor.get_videos(limit=10)
        assert len(videos) == 1
        assert videos[0]["video_id"] == "v1"


class TestStoreVideo:
    async def test_store_video_inserts_new(self, monitor: YouTubeMonitor):
        from src.bot.plugins.youtube_notifier.models import YouTubeVideo

        video = YouTubeVideo(
            video_id="v_new",
            channel_id="UC_test",
            title="New Video",
            url="https://youtu.be/v_new",
            published_at=datetime.now(timezone.utc),
        )
        await monitor._store_video(video)

        videos = await monitor.get_videos(limit=10)
        assert len(videos) == 1
        assert videos[0]["video_id"] == "v_new"

    async def test_store_video_ignores_duplicate(self, monitor: YouTubeMonitor):
        from src.bot.plugins.youtube_notifier.models import YouTubeVideo

        video = YouTubeVideo(
            video_id="v_dup",
            channel_id="UC_test",
            title="Duplicate",
            url="https://youtu.be/v_dup",
            published_at=datetime.now(timezone.utc),
        )
        await monitor._store_video(video)
        await monitor._store_video(video)

        videos = await monitor.get_videos(limit=10)
        assert len(videos) == 1


class TestPubSubHubbub:
    async def test_subscribe_to_hub_success(self, monitor: YouTubeMonitor):
        mock_response = MagicMock()
        mock_response.status_code = 202

        with patch.object(monitor._http, "post", return_value=mock_response):
            result = await monitor.subscribe_to_hub("UC_test", "https://example.com")

        assert result is True

    async def test_subscribe_to_hub_no_callback(self, monitor: YouTubeMonitor):
        result = await monitor.subscribe_to_hub("UC_test", "")
        assert result is False

    async def test_unsubscribe_from_hub_success(self, monitor: YouTubeMonitor):
        mock_response = MagicMock()
        mock_response.status_code = 204

        with patch.object(monitor._http, "post", return_value=mock_response):
            result = await monitor.unsubscribe_from_hub("UC_test", "https://example.com")

        assert result is True

    async def test_process_pubsub_notification_new_video(self, monitor: YouTubeMonitor):
        await monitor.add_subscription("UC_test", "Canal Test")

        atom_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:yt="http://www.youtube.com/xml/schemas/2015">
  <entry>
    <yt:videoId>NEW123</yt:videoId>
    <yt:channelId>UC_test</yt:channelId>
    <title>Video PubSub</title>
    <published>2024-06-01T12:00:00+00:00</published>
  </entry>
</feed>
"""
        with patch.object(monitor, "notify_new_video", new_callable=AsyncMock):
            await monitor.process_pubsub_notification(atom_xml)

        videos = await monitor.get_videos(limit=10)
        assert len(videos) == 1
        assert videos[0]["video_id"] == "NEW123"
        assert videos[0]["title"] == "Video PubSub"

    async def test_process_pubsub_notification_skips_existing(self, monitor: YouTubeMonitor):
        await monitor.add_subscription("UC_test", "Canal Test")
        await monitor._db.execute(
            """
            INSERT INTO youtube_videos (video_id, channel_id, title, url, published_at, notified)
            VALUES (?, ?, ?, ?, ?, 0)
            """,
            ("OLD123", "UC_test", "Old", "https://youtu.be/OLD123", datetime.now(timezone.utc).isoformat()),
        )
        await monitor._db.commit()

        atom_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:yt="http://www.youtube.com/xml/schemas/2015">
  <entry>
    <yt:videoId>OLD123</yt:videoId>
    <yt:channelId>UC_test</yt:channelId>
    <title>Old</title>
    <published>2024-06-01T12:00:00+00:00</published>
  </entry>
</feed>
"""
        with patch.object(monitor, "notify_new_video", new_callable=AsyncMock) as mock_notify:
            await monitor.process_pubsub_notification(atom_xml)

        # notify_new_video should not be called for existing video
        mock_notify.assert_not_awaited()

    async def test_process_pubsub_notification_no_entries(self, monitor: YouTubeMonitor):
        atom_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Empty</title>
</feed>
"""
        await monitor.process_pubsub_notification(atom_xml)
        videos = await monitor.get_videos(limit=10)
        assert len(videos) == 0


class TestCallbackAPI:
    async def test_callback_verification_returns_challenge(self, youtube_client: AsyncClient):
        response = await youtube_client.get(
            "/api/plugins/youtube/callback?hub.challenge=abc123&hub.mode=subscribe&hub.topic=https://example.com/topic"
        )
        assert response.status_code == 200
        assert response.text == "abc123"

    async def test_callback_verification_no_challenge(self, youtube_client: AsyncClient):
        response = await youtube_client.get("/api/plugins/youtube/callback")
        assert response.status_code == 200
        assert response.text == "OK"

    async def test_callback_notification_posts_to_monitor(self, youtube_client: AsyncClient, monitor: YouTubeMonitor):
        atom_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:yt="http://www.youtube.com/xml/schemas/2015">
  <entry>
    <yt:videoId>API123</yt:videoId>
    <yt:channelId>UC_api</yt:channelId>
    <title>API Video</title>
    <published>2024-06-01T12:00:00+00:00</published>
  </entry>
</feed>
"""
        with patch.object(monitor, "process_pubsub_notification", new_callable=AsyncMock) as mock_process:
            response = await youtube_client.post("/api/plugins/youtube/callback", content=atom_xml)

        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        mock_process.assert_awaited_once()


class TestSubscriptionNotifications:
    async def test_update_subscription_notifications(self, monitor: YouTubeMonitor):
        await monitor.add_subscription("UC_test", "Canal Test")
        await monitor.update_subscription_notifications("UC_test", False)

        sub = await monitor.get_subscription("UC_test")
        assert sub is not None
        assert sub["notifications_enabled"] is False

        await monitor.update_subscription_notifications("UC_test", True)
        sub = await monitor.get_subscription("UC_test")
        assert sub["notifications_enabled"] is True

    async def test_list_subscriptions_includes_notifications(self, monitor: YouTubeMonitor):
        await monitor.add_subscription("UC_a", "Canal A")
        await monitor.update_subscription_notifications("UC_a", False)

        subs = await monitor.list_subscriptions()
        assert len(subs) == 1
        assert subs[0]["notifications_enabled"] is False


class TestContentFilters:
    async def test_is_short_detects_shorts(self, monitor: YouTubeMonitor):
        from src.bot.plugins.youtube_notifier.models import YouTubeVideo

        short_video = YouTubeVideo(
            video_id="v1",
            channel_id="UC_test",
            title="My #Shorts video",
            url="https://youtu.be/v1",
            published_at=datetime.now(timezone.utc),
        )
        assert monitor._is_short(short_video) is True

        normal_video = YouTubeVideo(
            video_id="v2",
            channel_id="UC_test",
            title="Normal video",
            url="https://youtu.be/v2",
            published_at=datetime.now(timezone.utc),
        )
        assert monitor._is_short(normal_video) is False

    async def test_is_premiere_detects_premieres(self, monitor: YouTubeMonitor):
        from src.bot.plugins.youtube_notifier.models import YouTubeVideo

        premiere_video = YouTubeVideo(
            video_id="v1",
            channel_id="UC_test",
            title="Estreno del nuevo álbum",
            url="https://youtu.be/v1",
            published_at=datetime.now(timezone.utc),
        )
        assert monitor._is_premiere(premiere_video) is True

        normal_video = YouTubeVideo(
            video_id="v2",
            channel_id="UC_test",
            title="Normal video",
            url="https://youtu.be/v2",
            published_at=datetime.now(timezone.utc),
        )
        assert monitor._is_premiere(normal_video) is False


class TestToggleNotificationsAPI:
    async def test_toggle_notifications_endpoint(self, youtube_client: AsyncClient, monitor: YouTubeMonitor):
        await monitor.add_subscription("UC_toggle", "Canal Toggle")
        response = await youtube_client.put(
            "/api/plugins/youtube/subscriptions/UC_toggle/notifications",
            json={"enabled": False},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["channel_id"] == "UC_toggle"
        assert data["notifications_enabled"] is False

        sub = await monitor.get_subscription("UC_toggle")
        assert sub["notifications_enabled"] is False


class TestDiscordChannelsAPI:
    async def test_discord_channels_no_bot(self, youtube_client: AsyncClient):
        response = await youtube_client.get("/api/plugins/youtube/discord-channels")
        assert response.status_code == 200
        data = response.json()
        assert data["channels"] == []


class TestYouTubePluginIntegration:
    """Test que los endpoints del plugin responden (sin polling)."""

    @pytest.fixture
    async def app_with_plugin(self):
        """Crea app y carga el plugin IGUAL que en produccion, pero sin polling."""
        from src.web.app import create_app
        from src.bot.core.config import ConfigManager
        from unittest.mock import MagicMock

        ConfigManager.reset_instance()
        cm = ConfigManager()
        await cm.load(":memory:")

        app = create_app(config_manager=cm, bot=MagicMock())

        from src.bot.plugins.youtube_notifier import setup as setup_youtube
        await setup_youtube(MagicMock(), cm, app)
        return app

    async def test_subscriptions_returns_200(self, app_with_plugin):
        from httpx import ASGITransport, AsyncClient
        transport = ASGITransport(app=app_with_plugin)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/plugins/youtube/subscriptions")
            assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    async def test_config_returns_200(self, app_with_plugin):
        from httpx import ASGITransport, AsyncClient
        transport = ASGITransport(app=app_with_plugin)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/plugins/youtube/config")
            assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    async def test_discord_channels_returns_200(self, app_with_plugin):
        from httpx import ASGITransport, AsyncClient
        transport = ASGITransport(app=app_with_plugin)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/plugins/youtube/discord-channels")
            assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
