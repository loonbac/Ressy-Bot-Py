import asyncio
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


class TestHubSubscribedColumns:
    async def test_pending_hub_subscribe_column_exists(self, monitor: YouTubeMonitor):
        """T1: pending_hub_subscribe column must exist after init_db."""
        await monitor.add_subscription("UC_test", "Canal Test")
        row = await monitor._db.execute_fetchall(
            "SELECT pending_hub_subscribe FROM youtube_subscriptions WHERE channel_id = ?",
            ("UC_test",),
        )
        assert len(row) == 1
        assert row[0][0] == 0  # DEFAULT 0

    async def test_hub_subscribed_at_column_exists(self, monitor: YouTubeMonitor):
        """T1: hub_subscribed_at column must exist after init_db."""
        await monitor.add_subscription("UC_test", "Canal Test")
        row = await monitor._db.execute_fetchall(
            "SELECT hub_subscribed_at FROM youtube_subscriptions WHERE channel_id = ?",
            ("UC_test",),
        )
        assert len(row) == 1
        assert row[0][0] is None

    async def test_list_subscriptions_includes_hub_columns(self, monitor: YouTubeMonitor):
        """T1: list_subscriptions must include pending_hub_subscribe and hub_subscribed_at."""
        await monitor.add_subscription("UC_test", "Canal Test")
        subs = await monitor.list_subscriptions()
        assert len(subs) == 1
        assert "pending_hub_subscribe" in subs[0]
        assert "hub_subscribed_at" in subs[0]
        assert subs[0]["pending_hub_subscribe"] == 0
        assert subs[0]["hub_subscribed_at"] is None

    async def test_get_subscription_includes_hub_columns(self, monitor: YouTubeMonitor):
        """T1: get_subscription must include pending_hub_subscribe and hub_subscribed_at."""
        await monitor.add_subscription("UC_test", "Canal Test")
        sub = await monitor.get_subscription("UC_test")
        assert sub is not None
        assert "pending_hub_subscribe" in sub
        assert "hub_subscribed_at" in sub
        assert sub["pending_hub_subscribe"] == 0
        assert sub["hub_subscribed_at"] is None


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
        assert loaded.discord_channel_id == 123456
        assert loaded.callback_url == "https://example.com/callback"
        assert loaded.announcement_message == "Nuevo video!"
        assert loaded.filter_shorts is True
        assert loaded.filter_premieres is True
        assert loaded.filter_min_duration == 300


class TestRSSRemoval:
    async def test_fetch_via_rss_removed(self, monitor: YouTubeMonitor):
        """T3: _fetch_via_rss must not exist after RSS removal."""
        assert not hasattr(monitor, "_fetch_via_rss")

    async def test_check_rss_removed(self, monitor: YouTubeMonitor):
        """T3: check_rss must not exist after RSS removal."""
        assert not hasattr(monitor, "check_rss")

    async def test_poll_channels_removed(self, monitor: YouTubeMonitor):
        """T3: poll_channels must not exist after RSS removal."""
        assert not hasattr(monitor, "poll_channels")

    async def test_fetch_recent_videos_removed(self, monitor: YouTubeMonitor):
        """T3: fetch_recent_videos must not exist after RSS removal."""
        assert not hasattr(monitor, "fetch_recent_videos")

    async def test_start_is_noop_or_removed(self, monitor: YouTubeMonitor):
        """T3: start() should be a no-op or removed."""
        if hasattr(monitor, "start"):
            await monitor.start()
            # Should not raise and should not create a polling task

    async def test_http_headers_no_xml_accept(self, monitor: YouTubeMonitor):
        """T3: httpx client should not send Accept: text/xml."""
        headers = monitor._http.headers
        accept = headers.get("Accept", "")
        assert "text/xml" not in accept


class TestHubRenewalLoop:
    async def test_start_hub_renewal_loop_creates_task(self, monitor: YouTubeMonitor):
        """T4: start_hub_renewal_loop must create an asyncio task."""
        await monitor.start_hub_renewal_loop()
        assert monitor._task is not None
        assert not monitor._task.done()
        await monitor.stop()

    async def test_stop_cancels_task(self, monitor: YouTubeMonitor):
        """T4: stop must cancel the hub renewal task."""
        await monitor.start_hub_renewal_loop()
        assert monitor._task is not None
        await monitor.stop()
        assert monitor._task is None

    async def test_hub_renewal_loop_resubscribes_expired(self, monitor: YouTubeMonitor):
        """T4: _hub_renewal_loop re-subscribes channels with hub_subscribed_at >= 4 days old."""
        from src.bot.plugins.youtube_notifier.models import YouTubePluginConfig

        cfg = YouTubePluginConfig(callback_url="https://example.com/callback")
        await monitor.update_config(cfg)

        await monitor.add_subscription("UC_test", "Canal Test")
        # Set hub_subscribed_at to 5 days ago
        await monitor._db.execute(
            "UPDATE youtube_subscriptions SET hub_subscribed_at = datetime('now', '-5 days') WHERE channel_id = ?",
            ("UC_test",),
        )
        await monitor._db.commit()

        call_count = 0
        def _is_set():
            nonlocal call_count
            call_count += 1
            return call_count > 2  # allow one loop iteration

        with patch.object(monitor, "subscribe_to_hub", return_value=True) as mock_sub:
            monitor._stop_event = asyncio.Event()
            monitor._stop_event.is_set = _is_set
            monitor._stop_event.wait = AsyncMock(return_value=None)
            await monitor._hub_renewal_loop()

        mock_sub.assert_awaited_once_with("UC_test", "https://example.com/callback")

    async def test_hub_renewal_loop_skips_fresh_subscriptions(self, monitor: YouTubeMonitor):
        """T4: _hub_renewal_loop skips channels with hub_subscribed_at < 4 days old."""
        await monitor.add_subscription("UC_test", "Canal Test")
        await monitor._db.execute(
            "UPDATE youtube_subscriptions SET hub_subscribed_at = datetime('now', '-1 days') WHERE channel_id = ?",
            ("UC_test",),
        )
        await monitor._db.commit()

        call_count = 0
        def _is_set():
            nonlocal call_count
            call_count += 1
            return call_count > 2

        with patch.object(monitor, "subscribe_to_hub", return_value=True) as mock_sub:
            monitor._stop_event = asyncio.Event()
            monitor._stop_event.is_set = _is_set
            monitor._stop_event.wait = AsyncMock(return_value=None)
            await monitor._hub_renewal_loop()

        mock_sub.assert_not_awaited()

    async def test_execute_ttl_cleanup_deletes_old_videos(self, monitor: YouTubeMonitor):
        """T4: _execute_ttl_cleanup deletes videos older than 30 days."""
        await monitor.add_subscription("UC_test", "Canal Test")
        await monitor._db.execute(
            """
            INSERT INTO youtube_videos (video_id, channel_id, title, url, published_at, notified)
            VALUES (?, ?, ?, ?, datetime('now', '-31 days'), 0)
            """,
            ("v_old", "UC_test", "Old", "https://youtu.be/v_old"),
        )
        await monitor._db.execute(
            """
            INSERT INTO youtube_videos (video_id, channel_id, title, url, published_at, notified)
            VALUES (?, ?, ?, ?, datetime('now', '-1 days'), 0)
            """,
            ("v_new", "UC_test", "New", "https://youtu.be/v_new"),
        )
        await monitor._db.commit()

        await monitor._execute_ttl_cleanup()

        videos = await monitor.get_videos(limit=10)
        assert len(videos) == 1
        assert videos[0]["video_id"] == "v_new"


class TestSeedViaAPI:
    async def test_seed_via_api_exists(self, monitor: YouTubeMonitor):
        """T8: _seed_via_api must exist (renamed from _fetch_via_api)."""
        assert hasattr(monitor, "_seed_via_api")

    async def test_seed_via_api_returns_videos(self, monitor: YouTubeMonitor):
        """T8: _seed_via_api fetches videos via YouTube Data API."""
        import json
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [
                {
                    "id": {"kind": "youtube#video", "videoId": "API123"},
                    "snippet": {
                        "title": "API Video",
                        "publishedAt": "2024-01-15T10:30:00+00:00",
                    },
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient.get", return_value=mock_response):
            videos = await monitor._seed_via_api("UC_test", "test_api_key")

        assert len(videos) == 1
        assert videos[0].video_id == "API123"
        assert videos[0].title == "API Video"


class TestAPIIntegration:
    async def test_status_endpoint_data(self, monitor: YouTubeMonitor):
        status = await monitor.get_status()
        assert "enabled" in status
        assert "channels_count" in status
        assert "videos_count" in status
        assert "poll_interval_minutes" not in status
        assert "last_poll" not in status
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


class TestGoogleAPIKeyPersistence:
    """Test that google_api_key is correctly saved and loaded."""

    async def test_save_and_load_api_key(self, monitor: YouTubeMonitor):
        """Save a config with google_api_key, then load it back."""
        config = await monitor.get_config()
        assert config.google_api_key == "", "Should start empty"

        config.google_api_key = "AIzaSyTestKey123"
        await monitor.update_config(config)

        loaded = await monitor.get_config()
        assert loaded.google_api_key == "AIzaSyTestKey123", f"Expected key, got: '{loaded.google_api_key}'"

    async def test_api_key_via_endpoint(self, youtube_client):
        """Test that PUT /config saves google_api_key and GET /config returns it."""
        # Save via endpoint
        resp = await youtube_client.put("/api/plugins/youtube/config", json={
            "google_api_key": "AIzaSyEndpointKey",
            "enabled": True,
            "discord_channel_id": None,
            "callback_url": "",
            "announcement_message": "",
            "filter_shorts": False,
            "filter_premieres": False,
            "filter_min_duration": 0,
        })
        assert resp.status_code == 200

        # Read back via endpoint
        resp = await youtube_client.get("/api/plugins/youtube/config")
        data = resp.json()
        assert data["google_api_key"] == "AIzaSyEndpointKey", f"Expected key, got: '{data.get('google_api_key')}'"


class TestCallbackServer:
    """Test the standalone callback server endpoints."""

    async def test_health_endpoint(self):
        from src.bot.plugins.youtube_notifier.callback_server import app
        from httpx import ASGITransport, AsyncClient
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health")
            assert resp.status_code == 200
            assert resp.json()["status"] == "ok"

    async def test_verification_returns_challenge(self):
        from src.bot.plugins.youtube_notifier.callback_server import app
        from httpx import ASGITransport, AsyncClient
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/plugins/youtube/callback?hub.challenge=test123")
            assert resp.status_code == 200
            assert resp.text == "test123"

    async def test_verification_no_challenge(self):
        from src.bot.plugins.youtube_notifier.callback_server import app
        from httpx import ASGITransport, AsyncClient
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/plugins/youtube/callback")
            assert resp.status_code == 200
            assert resp.text == "OK"

    async def test_notification_stores_video(self, tmp_path):
        import src.bot.plugins.youtube_notifier.callback_server as cs
        from src.bot.plugins.youtube_notifier.callback_server import app
        from httpx import ASGITransport, AsyncClient

        # Point callback server to a temp DB
        db_path = str(tmp_path / "test_cb.db")
        cs.DB_PATH = db_path

        # Initialise schema manually (ASGITransport does not trigger lifespan)
        await cs._init_db()

        transport = ASGITransport(app=app, client=("127.0.0.1", 50000))
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            atom_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:yt="http://www.youtube.com/xml/schemas/2015">
  <entry>
    <yt:videoId>CB123</yt:videoId>
    <yt:channelId>UC_cb</yt:channelId>
    <title>Callback Video</title>
    <published>2024-06-01T12:00:00+00:00</published>
  </entry>
</feed>
"""
            resp = await client.post("/api/plugins/youtube/callback", content=atom_xml)
            assert resp.status_code == 200
            assert resp.json()["status"] == "ok"

        # Verify DB contents
        import aiosqlite
        db = await aiosqlite.connect(db_path)
        db.row_factory = aiosqlite.Row
        rows = await db.execute_fetchall("SELECT * FROM youtube_videos")
        await db.close()
        assert len(rows) == 1
        assert rows[0]["video_id"] == "CB123"
        assert rows[0]["title"] == "Callback Video"
        assert rows[0]["notified"] == 0
