"""Smoke tests de integración para el plugin openrouter_prices.

Verifica que setup() monta correctamente endpoints + estado en app.
Usa tmp_path para DB aislada y mock del cliente HTTP (no toca httpx real).
Fixture cierra todos los recursos en teardown para evitar hangs.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def smoke_app(tmp_path, monkeypatch):
    """Crea app con plugin montado en directorio temporal, sin httpx real.

    Cleanup: cierra DB, cierra cliente, restaura cwd.
    """
    monkeypatch.chdir(tmp_path)

    fake_httpx_client = MagicMock()
    fake_httpx_client.is_closed = False
    fake_httpx_client.aclose = AsyncMock()

    with patch(
        "src.bot.plugins.openrouter_prices.client.httpx.AsyncClient",
        return_value=fake_httpx_client,
    ), patch(
        "src.bot.plugins.openrouter_prices.client.OpenRouterClient.fetch_models",
        new_callable=AsyncMock,
        return_value=[],
    ):
        from src.bot.plugins.openrouter_prices import setup as setup_openrouter_prices

        app = FastAPI()
        mock_bot = MagicMock()
        mock_bot.add_cog = AsyncMock()
        mock_cm = MagicMock()

        await setup_openrouter_prices(bot=mock_bot, config_manager=mock_cm, app=app)

        try:
            yield app, mock_bot
        finally:
            db = getattr(app.state, "openrouter_prices_db", None)
            if db is not None:
                await db.close()
            client = getattr(app.state, "openrouter_prices_client", None)
            if client is not None and hasattr(client, "close"):
                await client.close()


class TestOpenRouterSmokeEndpoints:
    async def test_status_endpoint_responds(self, smoke_app):
        app, _ = smoke_app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/plugins/openrouter-prices/status")
        assert resp.status_code == 200, f"Endpoint devolvió {resp.status_code}"

    async def test_config_endpoint_responds(self, smoke_app):
        app, _ = smoke_app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/plugins/openrouter-prices/config")
        assert resp.status_code == 200

    async def test_models_endpoint_responds(self, smoke_app):
        app, _ = smoke_app
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/plugins/openrouter-prices/models")
        assert resp.status_code != 404

    async def test_app_state_has_db(self, smoke_app):
        app, _ = smoke_app
        assert hasattr(app.state, "openrouter_prices_db")
        assert app.state.openrouter_prices_db is not None

    async def test_app_state_has_client(self, smoke_app):
        app, _ = smoke_app
        assert hasattr(app.state, "openrouter_prices_client")

    async def test_app_state_has_cog(self, smoke_app):
        app, _ = smoke_app
        assert hasattr(app.state, "openrouter_prices_cog")

    async def test_cog_was_registered_with_bot(self, smoke_app):
        _, mock_bot = smoke_app
        mock_bot.add_cog.assert_awaited_once()

    async def test_setup_closes_db_cleanly(self, smoke_app):
        app, _ = smoke_app
        db = app.state.openrouter_prices_db
        await db.close()
        # Cerrar dos veces no debe lanzar excepción
        await db.close()

    async def test_app_state_has_bfcl_client(self, smoke_app):
        app, _ = smoke_app
        assert hasattr(app.state, "openrouter_prices_bfcl_client")
        assert app.state.openrouter_prices_bfcl_client is not None

    async def test_bfcl_scraper_uses_shared_client(self, smoke_app):
        app, _ = smoke_app
        scraper = app.state.openrouter_prices_bfcl_scraper
        assert scraper._owns_client is False, "BFCLScraper should use the shared injected client"

    async def test_teardown_closes_bfcl_client(self, smoke_app):
        app, _ = smoke_app
        client = app.state.openrouter_prices_bfcl_client
        from unittest.mock import AsyncMock, patch
        with patch.object(client, "aclose", new_callable=AsyncMock) as mock_close:
            for cb in app.state.teardown_callbacks:
                await cb()
            mock_close.assert_awaited()
