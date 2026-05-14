import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from src.bot.plugins.youtube_notifier.monitor import YouTubeMonitor
from src.bot.plugins.youtube_notifier.api import router as youtube_router
from unittest.mock import MagicMock


@pytest.fixture
async def real_monitor():
    """Monitor backed by the real on-disk DB."""
    mock_bot = MagicMock()
    mock_cm = MagicMock()
    mon = YouTubeMonitor("data/plugins/youtube.db", mock_cm, mock_bot)
    await mon.init_db()
    yield mon
    await mon.close_db()


@pytest.fixture
async def real_client(real_monitor: YouTubeMonitor):
    app = FastAPI()
    app.state.youtube_monitor = real_monitor
    app.include_router(youtube_router, prefix="/api/plugins/youtube")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


class TestRealDBIntegration:
    async def test_get_config_returns_api_key(self, real_client: AsyncClient):
        resp = await real_client.get("/api/plugins/youtube/config")
        assert resp.status_code == 200
        data = resp.json()
        print(f"Config google_api_key from endpoint: '{data.get('google_api_key')}'")
        assert data.get("google_api_key"), f"API key missing or empty in endpoint response: {data}"

    async def test_poll_returns_has_api_key_true(self, real_client: AsyncClient):
        resp = await real_client.post("/api/plugins/youtube/poll")
        assert resp.status_code == 200
        data = resp.json()
        print(f"Poll response: {data}")
        assert data["has_api_key"] is True, f"has_api_key should be True, got: {data}"
