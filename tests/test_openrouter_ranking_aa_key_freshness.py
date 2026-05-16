"""Regresion: la API key de Artificial Analysis configurada DESPUES del
arranque del bot debe llegar al scraper sin reiniciar.

Bug original (src/bot/plugins/openrouter_prices/__init__.py):
    config = await db.get_config()          # snapshot UNA vez en setup()
    aa_scraper_factory=lambda: ArtificialAnalysisScraper(
        api_key=config.get("aa_api_key", ""),   # closure sobre snapshot viejo
    )

El lambda capturaba el dict `config` leido una sola vez al arrancar el bot.
Cuando el usuario configuraba `aa_api_key` despues via el dashboard
(PUT /config -> db.update_config), el snapshot en memoria nunca se refrescaba,
asi que el factory seguia construyendo el scraper con api_key="" y el scrape
fallaba con error="unauthorized" pese a estar la key en la DB.

Estos tests son copias del comportamiento real esperado:
  1. El scheduler debe soportar un factory async (awaitable) y await-earlo.
  2. setup() debe cablear un factory que relee la key de la DB en cada
     invocacion, no un snapshot del arranque.
"""
from __future__ import annotations

import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.bot.plugins.openrouter_prices.database import OpenRouterDatabase
from src.bot.plugins.openrouter_prices.scheduler import PluginScheduler
from src.bot.plugins.openrouter_prices.scrapers.base import ScrapeResult


# ---------------------------------------------------------------------------
# 1. Scheduler soporta factory async
# ---------------------------------------------------------------------------

@pytest.fixture
async def db():
    database = OpenRouterDatabase(":memory:")
    await database.connect()
    yield database
    await database.close()


@pytest.mark.asyncio
@pytest.mark.timeout(5)
async def test_job_aa_scrape_awaits_async_factory(db):
    """_job_aa_scrape debe await-ear un factory async y llamar scrape()."""
    aa_scraper = MagicMock()
    aa_scraper.scrape = AsyncMock(
        return_value=ScrapeResult(
            source="artificial_analysis",
            rows_updated=0,
            started_at=1,
            finished_at=2,
            status="ok",
        )
    )

    async def _async_factory():
        return aa_scraper

    sched = PluginScheduler(
        bot=MagicMock(),
        db=db,
        openrouter_client=MagicMock(),
        aa_scraper_factory=_async_factory,
        bfcl_scraper=MagicMock(),
        embed_publisher=AsyncMock(return_value=True),
        time_provider=lambda: 1_000_000,
    )

    await sched._job_aa_scrape()

    aa_scraper.scrape.assert_awaited_once_with(db)


@pytest.mark.asyncio
@pytest.mark.timeout(5)
async def test_job_aa_scrape_still_supports_sync_factory(db):
    """Backward-compat: un factory sincrono sigue funcionando."""
    aa_scraper = MagicMock()
    aa_scraper.scrape = AsyncMock(
        return_value=ScrapeResult(
            source="artificial_analysis",
            rows_updated=0,
            started_at=1,
            finished_at=2,
            status="ok",
        )
    )

    sched = PluginScheduler(
        bot=MagicMock(),
        db=db,
        openrouter_client=MagicMock(),
        aa_scraper_factory=lambda: aa_scraper,
        bfcl_scraper=MagicMock(),
        embed_publisher=AsyncMock(return_value=True),
        time_provider=lambda: 1_000_000,
    )

    await sched._job_aa_scrape()

    aa_scraper.scrape.assert_awaited_once_with(db)


# ---------------------------------------------------------------------------
# 2. Regresion end-to-end: setup() relee la key de la DB en cada scrape
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.timeout(10)
async def test_aa_key_set_after_setup_reaches_scraper(tmp_path):
    """Replica el bug del usuario: key configurada DESPUES del arranque.

    Flujo:
      1. setup() corre con la DB sin aa_api_key (snapshot vacio).
      2. El usuario configura aa_api_key via db.update_config (como PUT /config).
      3. El factory cableado por setup() se invoca (como en un scrape).
      4. El scraper resultante DEBE llevar la key nueva, no "".
    """
    from src.web.app import create_app

    real_db = OpenRouterDatabase(":memory:")

    captured: dict = {}

    class _StubScheduler:
        def __init__(self, *, aa_scraper_factory, **kwargs):
            captured["factory"] = aa_scraper_factory

        async def start(self):
            return None

        async def stop(self):
            return None

    app = create_app()

    with (
        patch(
            "src.bot.plugins.openrouter_prices.database.OpenRouterDatabase",
            return_value=real_db,
        ),
        patch(
            "src.bot.plugins.openrouter_prices.client.OpenRouterClient",
            return_value=MagicMock(close=AsyncMock()),
        ),
        patch(
            "src.bot.plugins.openrouter_prices.cog.OpenRouterPricesCog",
            return_value=AsyncMock(),
        ),
        patch(
            "src.bot.plugins.openrouter_prices.scheduler.PluginScheduler",
            _StubScheduler,
        ),
        patch(
            "src.bot.plugins.openrouter_prices.scrapers.bfcl.BFCLScraper",
            return_value=MagicMock(),
        ),
        patch("os.makedirs"),
    ):
        mock_bot = AsyncMock()
        mock_bot.add_cog = AsyncMock()

        from src.bot.plugins.openrouter_prices import setup

        # 1. Arranque: aa_api_key NO configurada todavia.
        await setup(mock_bot, MagicMock(), app)

    factory = captured["factory"]
    assert factory is not None, "setup() no cableo aa_scraper_factory"

    # 2. El usuario configura la key DESPUES del arranque (PUT /config).
    await real_db.update_config({"aa_api_key": "aa-live-key-xyz"})

    # 3. Un scrape posterior invoca el factory.
    scraper = factory()
    if inspect.isawaitable(scraper):
        scraper = await scraper

    # 4. El scraper debe llevar la key actual de la DB, no el snapshot vacio.
    assert scraper._api_key == "aa-live-key-xyz", (
        "El factory uso un snapshot viejo de config; la key configurada "
        "post-arranque no llego al scraper (causa del error 'unauthorized')."
    )

    await real_db.close()
