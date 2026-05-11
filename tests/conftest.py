import asyncio
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.bot.core.config import ConfigManager


@pytest.fixture
async def config_manager() -> AsyncGenerator[ConfigManager, None]:
    ConfigManager.reset_instance()
    cm = ConfigManager()
    await cm.load(":memory:")
    yield cm
    await cm._db.close()
    ConfigManager.reset_instance()


@pytest.fixture
def app() -> FastAPI:
    from src.web.app import create_app

    return create_app()


@pytest.fixture
async def async_client(app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def mock_bot() -> MagicMock:
    bot = MagicMock()
    bot.user = MagicMock()
    bot.user.name = "TestBot"
    bot.tree = MagicMock()
    bot.tree.sync = AsyncMock()
    return bot
