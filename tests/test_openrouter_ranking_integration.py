"""Smoke integration test para el plugin openrouter_prices con PR3.

TDD: RED primero.

Escenarios:
  - setup() construye la app con scheduler (todo mockeado), scheduler inicia,
    los endpoints responden, teardown limpio.
  - GET /rankings/orchestrator → 200 (fase sin datos → lista vacía, no crash)
  - GET /benchmarks → 200
  - GET /aliases → 200
  - GET /scrape-runs → 200
  - POST /scrape/bfcl → 200 (scheduler presente)
  - teardown_callbacks son ejecutados correctamente
"""
from __future__ import annotations

import asyncio
import os
import time
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest
from fastapi.testclient import TestClient

from src.web.app import create_app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_mock_db(tmp_path):
    """Mock de OpenRouterDatabase con las respuestas mínimas."""
    db = AsyncMock()
    db.get_config = AsyncMock(return_value={
        "enabled": "true",
        "ttl_seconds": "3600",
        "max_models_command": "10",
        "discord_channel_id": "",
        "openrouter_refresh_interval_hours": "24",
        "aa_scrape_enabled": "false",  # Deshabilitado para el smoke test
        "aa_scrape_interval_days": "7",
        "bfcl_scrape_enabled": "false",  # Deshabilitado
        "bfcl_scrape_interval_days": "7",
        "weekly_report_enabled": "false",  # Deshabilitado
        "weekly_report_channel_id": "",
        "weekly_report_day": "monday",
        "weekly_report_hour": "9",
        "weekly_report_count": "10",
        "ranking_embed_enabled": "false",  # Deshabilitado
        "ranking_embed_channel_id": "",
        "ranking_embed_cron_days": "14",
        "ranking_phase": "orchestrator",
    })
    db.update_config = AsyncMock()
    db.get_metadata = AsyncMock(return_value={})
    db.set_metadata = AsyncMock()
    db.count_models = AsyncMock(return_value=0)
    db.list_models = AsyncMock(return_value=[])
    db.get_model = AsyncMock(return_value=None)
    db.upsert_models = AsyncMock(return_value=0)
    db.get_phase_profile = AsyncMock(return_value=None)
    db.list_benchmarks = AsyncMock(return_value=[])
    db.list_aliases = AsyncMock(return_value=[])
    db.get_alias = AsyncMock(return_value=None)
    db.upsert_alias = AsyncMock()
    db.list_scrape_runs = AsyncMock(return_value=[])
    db.close = AsyncMock()
    return db


def _build_mock_client():
    client = AsyncMock()
    client.fetch_models = AsyncMock(return_value=[])
    client.close = AsyncMock()
    return client


def _build_mock_scheduler():
    sched = MagicMock()
    sched.start = AsyncMock()
    sched.stop = AsyncMock()
    sched.trigger_scrape = AsyncMock(return_value=True)
    sched.is_scraping = MagicMock(return_value=False)
    return sched


# ---------------------------------------------------------------------------
# Smoke test: setup() wires everything together
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.timeout(5)
async def test_setup_wires_state(tmp_path):
    """setup() inyecta scheduler, db, client en app.state."""
    app = create_app()
    mock_db = _build_mock_db(tmp_path)
    mock_client = _build_mock_client()
    mock_scheduler = _build_mock_scheduler()
    mock_cog = AsyncMock()

    with (
        patch("src.bot.plugins.openrouter_prices.database.OpenRouterDatabase", return_value=mock_db),
        patch("src.bot.plugins.openrouter_prices.client.OpenRouterClient", return_value=mock_client),
        patch("src.bot.plugins.openrouter_prices.cog.OpenRouterPricesCog", return_value=mock_cog),
        patch("src.bot.plugins.openrouter_prices.scheduler.PluginScheduler", return_value=mock_scheduler),
        patch("src.bot.plugins.openrouter_prices.scrapers.bfcl.BFCLScraper", return_value=MagicMock()),
        patch("src.bot.plugins.openrouter_prices.scrapers.artificial_analysis.ArtificialAnalysisScraper", return_value=MagicMock()),
        patch("os.makedirs"),
    ):
        mock_bot = AsyncMock()
        mock_bot.add_cog = AsyncMock()
        mock_cm = MagicMock()

        from src.bot.plugins.openrouter_prices import setup
        await setup(mock_bot, mock_cm, app)

    # Verificar que el estado está en app.state
    assert hasattr(app.state, "openrouter_prices_db")
    assert hasattr(app.state, "openrouter_prices_scheduler")


@pytest.mark.asyncio
@pytest.mark.timeout(5)
async def test_setup_registers_teardown_callback(tmp_path):
    """setup() registra un teardown callback en app.state.teardown_callbacks."""
    app = create_app()
    mock_db = _build_mock_db(tmp_path)
    mock_client = _build_mock_client()
    mock_scheduler = _build_mock_scheduler()
    mock_cog = AsyncMock()

    with (
        patch("src.bot.plugins.openrouter_prices.database.OpenRouterDatabase", return_value=mock_db),
        patch("src.bot.plugins.openrouter_prices.client.OpenRouterClient", return_value=mock_client),
        patch("src.bot.plugins.openrouter_prices.cog.OpenRouterPricesCog", return_value=mock_cog),
        patch("src.bot.plugins.openrouter_prices.scheduler.PluginScheduler", return_value=mock_scheduler),
        patch("src.bot.plugins.openrouter_prices.scrapers.bfcl.BFCLScraper", return_value=MagicMock()),
        patch("src.bot.plugins.openrouter_prices.scrapers.artificial_analysis.ArtificialAnalysisScraper", return_value=MagicMock()),
        patch("os.makedirs"),
    ):
        mock_bot = AsyncMock()
        mock_bot.add_cog = AsyncMock()
        mock_cm = MagicMock()

        from src.bot.plugins.openrouter_prices import setup
        await setup(mock_bot, mock_cm, app)

    assert len(app.state.teardown_callbacks) >= 1


# ---------------------------------------------------------------------------
# Endpoints smoke test
# ---------------------------------------------------------------------------

@pytest.mark.timeout(5)
def test_rankings_endpoint_with_phase_data():
    """GET /rankings/orchestrator con fase configurada y ranking vacío → 200 con lista vacía."""
    app = create_app()
    mock_db = _build_mock_db(None)
    mock_client = _build_mock_client()
    mock_scheduler = _build_mock_scheduler()

    # La fase existe en DB pero no hay datos de benchmarks → ranking vacío
    mock_db.get_phase_profile = AsyncMock(return_value=[
        {"phase": "orchestrator", "benchmark_slug": "ifbench", "weight": 1.0, "is_feature_factor": False},
    ])

    from src.bot.plugins.openrouter_prices import api as _api
    app.include_router(
        _api.router,
        prefix="/api/plugins/openrouter-prices",
        tags=["openrouter-prices"],
    )

    app.state.openrouter_prices_db = mock_db
    app.state.openrouter_prices_client = mock_client
    app.state.openrouter_prices_scheduler = mock_scheduler

    with patch(
        "src.bot.plugins.openrouter_prices.api.compute_ranking_for_phase",
        new=AsyncMock(return_value=[]),
    ):
        with TestClient(app, raise_server_exceptions=False) as tc:
            response = tc.get("/api/plugins/openrouter-prices/rankings/orchestrator")

    # Con lista vacía el endpoint debe retornar 200 con lista vacía
    assert response.status_code == 200
    data = response.json()
    assert data["models"] == []


@pytest.mark.timeout(5)
def test_rankings_endpoint_unknown_phase():
    """GET /rankings/desconocida con fase no configurada → 404."""
    app = create_app()
    mock_db = _build_mock_db(None)
    mock_client = _build_mock_client()

    from src.bot.plugins.openrouter_prices import api as _api
    app.include_router(_api.router, prefix="/api/plugins/openrouter-prices")

    app.state.openrouter_prices_db = mock_db
    app.state.openrouter_prices_client = mock_client

    with TestClient(app, raise_server_exceptions=False) as tc:
        response = tc.get("/api/plugins/openrouter-prices/rankings/unknownphase")
    assert response.status_code == 404


@pytest.mark.timeout(5)
def test_benchmarks_endpoint():
    """GET /benchmarks → 200."""
    app = create_app()
    mock_db = _build_mock_db(None)
    mock_client = _build_mock_client()

    from src.bot.plugins.openrouter_prices import api as _api
    app.include_router(_api.router, prefix="/api/plugins/openrouter-prices")

    app.state.openrouter_prices_db = mock_db
    app.state.openrouter_prices_client = mock_client

    with TestClient(app, raise_server_exceptions=False) as tc:
        response = tc.get("/api/plugins/openrouter-prices/benchmarks")
    assert response.status_code == 200


@pytest.mark.timeout(5)
def test_aliases_endpoint():
    """GET /aliases → 200."""
    app = create_app()
    mock_db = _build_mock_db(None)
    mock_client = _build_mock_client()

    from src.bot.plugins.openrouter_prices import api as _api
    app.include_router(_api.router, prefix="/api/plugins/openrouter-prices")

    app.state.openrouter_prices_db = mock_db
    app.state.openrouter_prices_client = mock_client

    with TestClient(app, raise_server_exceptions=False) as tc:
        response = tc.get("/api/plugins/openrouter-prices/aliases")
    assert response.status_code == 200


@pytest.mark.timeout(5)
def test_scrape_runs_endpoint():
    """GET /scrape-runs → 200."""
    app = create_app()
    mock_db = _build_mock_db(None)
    mock_client = _build_mock_client()
    mock_scheduler = _build_mock_scheduler()

    from src.bot.plugins.openrouter_prices import api as _api
    app.include_router(_api.router, prefix="/api/plugins/openrouter-prices")

    app.state.openrouter_prices_db = mock_db
    app.state.openrouter_prices_client = mock_client
    app.state.openrouter_prices_scheduler = mock_scheduler

    with TestClient(app, raise_server_exceptions=False) as tc:
        response = tc.get("/api/plugins/openrouter-prices/scrape-runs")
    assert response.status_code == 200


@pytest.mark.timeout(5)
def test_scrape_trigger_endpoint():
    """POST /scrape/bfcl con scheduler presente → 200."""
    app = create_app()
    mock_db = _build_mock_db(None)
    mock_client = _build_mock_client()
    mock_scheduler = _build_mock_scheduler()

    from src.bot.plugins.openrouter_prices import api as _api
    app.include_router(_api.router, prefix="/api/plugins/openrouter-prices")

    app.state.openrouter_prices_db = mock_db
    app.state.openrouter_prices_client = mock_client
    app.state.openrouter_prices_scheduler = mock_scheduler

    with TestClient(app, raise_server_exceptions=False) as tc:
        response = tc.post("/api/plugins/openrouter-prices/scrape/bfcl")
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Teardown callbacks test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.timeout(5)
async def test_teardown_callbacks_are_called():
    """Los callbacks en app.state.teardown_callbacks son ejecutados al tear down."""
    app = create_app()
    if not hasattr(app.state, "teardown_callbacks"):
        app.state.teardown_callbacks = []

    callback_called = []
    async def mock_callback():
        callback_called.append(True)

    app.state.teardown_callbacks.append(mock_callback)

    # Simular la ejecución de los callbacks como lo haría el lifespan
    for cb in app.state.teardown_callbacks:
        await cb()

    assert len(callback_called) == 1


# ---------------------------------------------------------------------------
# Live scraper integration test
# ---------------------------------------------------------------------------

@pytest.mark.live
@pytest.mark.skipif(
    not os.environ.get("RUN_LIVE_SCRAPER_TESTS"),
    reason="set RUN_LIVE_SCRAPER_TESTS=1",
)
@pytest.mark.asyncio
@pytest.mark.timeout(60)
async def test_aa_scraper_live():
    """Llamada HTTP real a la API de AA; espera rows_updated > 0."""
    from src.bot.plugins.openrouter_prices.database import OpenRouterDatabase
    from src.bot.plugins.openrouter_prices.scrapers.artificial_analysis import (
        ArtificialAnalysisScraper,
    )

    db = OpenRouterDatabase(":memory:")
    await db.connect()

    # Seed modelos conocidos para que alias matching funcione
    await db.upsert_models(
        [
            {
                "id": "openai/gpt-4o",
                "name": "GPT-4o",
                "description": "",
                "created": 1_700_000_000,
                "context_length": 128_000,
                "architecture": {
                    "input_modalities": ["text"],
                    "output_modalities": ["text"],
                    "modality": "text->text",
                },
                "pricing": {
                    "prompt": "0.000005",
                    "completion": "0.000015",
                    "image": "0",
                    "request": "0",
                    "web_search": "0",
                    "input_cache_read": "0",
                    "input_cache_write": "0",
                },
                "top_provider": {
                    "context_length": 128_000,
                    "max_completion_tokens": 4096,
                    "is_moderated": False,
                },
            },
            {
                "id": "anthropic/claude-3-opus",
                "name": "Claude 3 Opus",
                "description": "",
                "created": 1_700_000_000,
                "context_length": 200_000,
                "architecture": {
                    "input_modalities": ["text"],
                    "output_modalities": ["text"],
                    "modality": "text->text",
                },
                "pricing": {
                    "prompt": "0.000015",
                    "completion": "0.000075",
                    "image": "0",
                    "request": "0",
                    "web_search": "0",
                    "input_cache_read": "0",
                    "input_cache_write": "0",
                },
                "top_provider": {
                    "context_length": 200_000,
                    "max_completion_tokens": 4096,
                    "is_moderated": False,
                },
            },
        ],
        int(time.time()),
    )

    scraper = ArtificialAnalysisScraper()
    result = await scraper.scrape(db)

    assert result.status == "ok"
    assert result.rows_updated > 0

    runs = await db.list_scrape_runs(source="artificial_analysis")
    assert runs
    assert runs[0]["status"] == "ok"

    await db.close()
