"""Tests para el plugin setup de linux_updates (__init__.py).

TDD estricto: test primero (RED), implementacion despues (GREEN).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_bot():
    bot = MagicMock()
    bot.add_cog = AsyncMock()
    return bot


@pytest.fixture
def mock_config_manager():
    return MagicMock()


@pytest.fixture
def mock_app():
    app = MagicMock()
    app.state = MagicMock()
    app.state.teardown_callbacks = []
    app.include_router = MagicMock()
    return app


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.connect = AsyncMock()
    db.close = AsyncMock()
    return db


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.close = AsyncMock()
    return client


@pytest.fixture
def mock_scheduler():
    sched = AsyncMock()
    sched.start = AsyncMock()
    sched.stop = AsyncMock()
    return sched


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSetup:
    @pytest.mark.asyncio
    async def test_setup_importable(self):
        """El modulo se puede importar sin errores."""
        from src.bot.plugins.linux_updates import setup
        assert callable(setup)

    @pytest.mark.asyncio
    async def test_setup_creates_db(
        self, mock_bot, mock_config_manager, mock_app, mock_db, mock_client, mock_scheduler
    ):
        """setup crea y conecta la base de datos."""
        from src.bot.plugins.linux_updates import setup

        with patch("src.bot.plugins.linux_updates.database.LinuxUpdatesDatabase", return_value=mock_db), \
             patch("src.bot.plugins.linux_updates.client.EndOfLifeClient", return_value=mock_client), \
             patch("src.bot.plugins.linux_updates.scheduler.LinuxUpdatesScheduler", return_value=mock_scheduler):
            await setup(mock_bot, mock_config_manager, mock_app)

        mock_db.connect.assert_awaited_once()
        assert mock_app.state.linux_updates_db is mock_db

    @pytest.mark.asyncio
    async def test_setup_adds_cog(
        self, mock_bot, mock_config_manager, mock_app, mock_db, mock_client, mock_scheduler
    ):
        """setup registra el cog en el bot."""
        from src.bot.plugins.linux_updates import setup
        from src.bot.plugins.linux_updates.cog import LinuxCog

        with patch("src.bot.plugins.linux_updates.database.LinuxUpdatesDatabase", return_value=mock_db), \
             patch("src.bot.plugins.linux_updates.client.EndOfLifeClient", return_value=mock_client), \
             patch("src.bot.plugins.linux_updates.scheduler.LinuxUpdatesScheduler", return_value=mock_scheduler):
            await setup(mock_bot, mock_config_manager, mock_app)

        mock_bot.add_cog.assert_awaited_once()
        cog_arg = mock_bot.add_cog.call_args[0][0]
        assert isinstance(cog_arg, LinuxCog)

    @pytest.mark.asyncio
    async def test_setup_includes_router(
        self, mock_bot, mock_config_manager, mock_app, mock_db, mock_client, mock_scheduler
    ):
        """setup monta el router de API."""
        from src.bot.plugins.linux_updates import setup

        with patch("src.bot.plugins.linux_updates.database.LinuxUpdatesDatabase", return_value=mock_db), \
             patch("src.bot.plugins.linux_updates.client.EndOfLifeClient", return_value=mock_client), \
             patch("src.bot.plugins.linux_updates.scheduler.LinuxUpdatesScheduler", return_value=mock_scheduler):
            await setup(mock_bot, mock_config_manager, mock_app)

        mock_app.include_router.assert_called_once()
        call_kwargs = mock_app.include_router.call_args[1]
        assert call_kwargs.get("prefix") == "/api/plugins/linux-updates"
        assert "linux-updates" in call_kwargs.get("tags", [])

    @pytest.mark.asyncio
    async def test_setup_stores_scheduler(
        self, mock_bot, mock_config_manager, mock_app, mock_db, mock_client, mock_scheduler
    ):
        """setup almacena el scheduler en app.state."""
        from src.bot.plugins.linux_updates import setup

        with patch("src.bot.plugins.linux_updates.database.LinuxUpdatesDatabase", return_value=mock_db), \
             patch("src.bot.plugins.linux_updates.client.EndOfLifeClient", return_value=mock_client), \
             patch("src.bot.plugins.linux_updates.scheduler.LinuxUpdatesScheduler", return_value=mock_scheduler):
            await setup(mock_bot, mock_config_manager, mock_app)

        assert mock_app.state.linux_updates_scheduler is mock_scheduler
        mock_scheduler.start.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_setup_registers_teardown(
        self, mock_bot, mock_config_manager, mock_app, mock_db, mock_client, mock_scheduler
    ):
        """setup registra un teardown callback."""
        from src.bot.plugins.linux_updates import setup

        with patch("src.bot.plugins.linux_updates.database.LinuxUpdatesDatabase", return_value=mock_db), \
             patch("src.bot.plugins.linux_updates.client.EndOfLifeClient", return_value=mock_client), \
             patch("src.bot.plugins.linux_updates.scheduler.LinuxUpdatesScheduler", return_value=mock_scheduler):
            await setup(mock_bot, mock_config_manager, mock_app)

        assert len(mock_app.state.teardown_callbacks) == 1
        teardown = mock_app.state.teardown_callbacks[0]
        assert callable(teardown)

    @pytest.mark.asyncio
    async def test_teardown_closes_resources(
        self, mock_bot, mock_config_manager, mock_app, mock_db, mock_client, mock_scheduler
    ):
        """El teardown callback cierra scheduler, client y db."""
        from src.bot.plugins.linux_updates import setup

        with patch("src.bot.plugins.linux_updates.database.LinuxUpdatesDatabase", return_value=mock_db), \
             patch("src.bot.plugins.linux_updates.client.EndOfLifeClient", return_value=mock_client), \
             patch("src.bot.plugins.linux_updates.scheduler.LinuxUpdatesScheduler", return_value=mock_scheduler):
            await setup(mock_bot, mock_config_manager, mock_app)

        teardown = mock_app.state.teardown_callbacks[0]
        await teardown()

        mock_scheduler.stop.assert_awaited_once()
        mock_client.close.assert_awaited_once()
        mock_db.close.assert_awaited_once()
