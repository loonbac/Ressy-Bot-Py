from typing import Any

import pytest
from httpx import AsyncClient


class TestGetConfig:
    async def test_returns_200_with_configs(self, async_client: AsyncClient):
        response = await async_client.get("/api/config")
        assert response.status_code == 200
        data = response.json()
        assert "configs" in data
        assert isinstance(data["configs"], list)
        keys = [c["key"] for c in data["configs"]]
        assert "bot_prefix" in keys
        assert "version" in keys

    async def test_config_values_match_defaults(self, async_client: AsyncClient):
        response = await async_client.get("/api/config")
        data = response.json()
        bot_prefix = next(c for c in data["configs"] if c["key"] == "bot_prefix")
        assert bot_prefix["value"] == "/"


class TestPutConfig:
    async def test_update_existing_key_returns_200(
        self, async_client: AsyncClient, config_manager: Any
    ):
        response = await async_client.put(
            "/api/config/bot_prefix",
            json={"value": "!"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["key"] == "bot_prefix"
        assert data["value"] == "!"

    async def test_update_persists_value(
        self, async_client: AsyncClient, config_manager: Any
    ):
        await async_client.put(
            "/api/config/bot_prefix",
            json={"value": "!"},
        )
        assert config_manager.get("bot_prefix") == "!"

    async def test_invalid_key_returns_400(self, async_client: AsyncClient):
        response = await async_client.put(
            "/api/config/invalid_key",
            json={"value": "test"},
        )
        assert response.status_code == 400
        assert "Invalid config key" in response.json()["detail"]

    async def test_wrong_type_returns_400(self, async_client: AsyncClient):
        response = await async_client.put(
            "/api/config/bot_prefix",
            json={"value": 123},
        )
        assert response.status_code == 400
        assert "expects type" in response.json()["detail"]

    async def test_missing_value_field_returns_400(self, async_client: AsyncClient):
        response = await async_client.put(
            "/api/config/bot_prefix",
            json={},
        )
        assert response.status_code == 400
        assert "Missing 'value'" in response.json()["detail"]


class TestGetStatus:
    async def test_returns_200_with_bot_status(self, async_client: AsyncClient):
        response = await async_client.get("/api/status")
        assert response.status_code == 200
        data = response.json()
        assert "online" in data
        assert "uptime_seconds" in data
        assert "loaded_cogs" in data
        assert "connected_ws_clients" in data
        assert "latency_ms" in data
        assert "memory_mb" in data
        assert isinstance(data["online"], bool)
        assert isinstance(data["uptime_seconds"], (int, float))
        assert isinstance(data["loaded_cogs"], list)
        assert isinstance(data["connected_ws_clients"], int)
        assert isinstance(data["latency_ms"], (int, float))
        assert isinstance(data["memory_mb"], (int, float))

    async def test_status_without_bot_returns_defaults(self, async_client: AsyncClient):
        response = await async_client.get("/api/status")
        data = response.json()
        assert data["online"] is False
        assert data["uptime_seconds"] == 0.0
        assert data["loaded_cogs"] == []
        assert data["latency_ms"] == 0.0
        assert "memory_mb" in data
        assert isinstance(data["memory_mb"], (int, float))
        assert "bot_avatar_url" in data
        assert "bot_name" in data
        assert isinstance(data["bot_avatar_url"], str)
        assert isinstance(data["bot_name"], str)


class TestPostPresence:
    async def test_presence_without_bot_returns_500(self, async_client: AsyncClient):
        response = await async_client.post("/api/presence")
        assert response.status_code == 500
        assert "Bot no disponible" in response.json()["detail"]

    async def test_presence_with_bot_applies_and_returns_config(
        self, async_client: AsyncClient, config_manager: Any
    ):
        from unittest.mock import AsyncMock, MagicMock
        from src.web.app import create_app
        from httpx import ASGITransport, AsyncClient

        await config_manager.update("bot_status", "dnd")
        await config_manager.update("bot_activity_type", "watching")
        await config_manager.update("bot_activity_text", "el dashboard")

        bot = MagicMock()
        bot.change_presence = AsyncMock()

        app = create_app(config_manager=config_manager, bot=bot)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/presence")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "dnd"
        assert data["activity_type"] == "watching"
        assert data["activity_text"] == "el dashboard"
        bot.change_presence.assert_awaited_once()

    async def test_presence_with_bot_error_returns_500(
        self, async_client: AsyncClient, config_manager: Any
    ):
        from unittest.mock import AsyncMock, MagicMock
        from src.web.app import create_app
        from httpx import ASGITransport, AsyncClient

        bot = MagicMock()
        bot.change_presence = AsyncMock(side_effect=RuntimeError("Discord error"))

        app = create_app(config_manager=config_manager, bot=bot)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/presence")

        assert response.status_code == 500
        assert "Discord error" in response.json()["detail"]
