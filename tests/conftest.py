import asyncio
import os
import sys
import threading
import time
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.bot.core.config import ConfigManager


_EXIT_STATE: dict[str, object] = {"code": 0, "armed": False}


def _arm_hard_exit(grace: float = 1.5) -> None:
    if _EXIT_STATE["armed"]:
        return
    _EXIT_STATE["armed"] = True

    def _killer() -> None:
        time.sleep(grace)
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        except Exception:
            pass
        os._exit(int(_EXIT_STATE["code"]))

    threading.Thread(
        target=_killer,
        daemon=True,
        name="pytest-exit-watchdog",
    ).start()


@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session, exitstatus):
    _EXIT_STATE["code"] = int(exitstatus) if exitstatus is not None else 0


@pytest.hookimpl(trylast=True, hookwrapper=True)
def pytest_terminal_summary(terminalreporter, exitstatus, config):
    yield
    _arm_hard_exit(grace=1.5)


@pytest.hookimpl(trylast=True)
def pytest_unconfigure(config):
    _arm_hard_exit(grace=1.5)


@pytest.fixture(autouse=True)
async def _cancel_pending_tasks() -> AsyncGenerator[None, None]:
    yield
    current = asyncio.current_task()
    pending = [t for t in asyncio.all_tasks() if t is not current and not t.done()]
    for task in pending:
        task.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)


@pytest.fixture
async def config_manager() -> AsyncGenerator[ConfigManager, None]:
    ConfigManager.reset_instance()
    cm = ConfigManager()
    await cm.load(":memory:")
    try:
        yield cm
    finally:
        try:
            if cm._db is not None:
                await cm._db.close()
        except Exception:
            pass
        ConfigManager.reset_instance()


@pytest.fixture
async def app(config_manager: ConfigManager) -> FastAPI:
    from src.web.app import create_app

    return create_app(config_manager=config_manager)


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
