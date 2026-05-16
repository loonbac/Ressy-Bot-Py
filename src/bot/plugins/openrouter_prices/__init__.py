"""Plugin de precios de modelos OpenRouter.

Expone precios del catálogo de OpenRouter mediante REST API y un comando
Discord slash. Se inicializa con setup(bot, config_manager, app).
"""
from __future__ import annotations

import os


DEFAULTS = {
    "enabled": "true",
    "ttl_seconds": "3600",
    "max_models_command": "10",
    "discord_channel_id": "",
}


async def setup(bot, config_manager, app) -> None:
    """Inicializa el plugin openrouter_prices.

    Abre la DB, siembra defaults, registra el router FastAPI, añade el cog,
    inicia el scheduler de scraping/embeds y registra el teardown callback.

    Args:
        bot: Instancia de commands.Bot.
        config_manager: ConfigManager global del bot.
        app: Instancia de FastAPI.
    """
    from .database import OpenRouterDatabase
    from .client import OpenRouterClient
    from .cog import OpenRouterPricesCog
    from .api import router
    from .scrapers.bfcl import BFCLScraper
    from .scrapers.artificial_analysis import ArtificialAnalysisScraper
    from .scheduler import PluginScheduler
    from .discord_embeds import publish_embed_to_channel

    # Crear directorio de datos si no existe
    db_dir = "data/plugins"
    os.makedirs(db_dir, exist_ok=True)
    db_path = f"{db_dir}/openrouter_prices.db"

    # Inicializar DB
    db = OpenRouterDatabase(db_path)
    await db.connect()

    # Inicializar cliente HTTP
    client = OpenRouterClient()

    # Crear e instalar cog
    cog = OpenRouterPricesCog(bot=bot, db=db, client=client)
    await bot.add_cog(cog)

    # Montar router
    app.include_router(
        router,
        prefix="/api/plugins/openrouter-prices",
        tags=["openrouter-prices"],
    )

    # Almacenar estado en app.state
    app.state.openrouter_prices_db = db
    app.state.openrouter_prices_client = client
    app.state.openrouter_prices_cog = cog

    # ------------------------------------------------------------------
    # Scrapers + Scheduler (PR 3)
    # ------------------------------------------------------------------

    import httpx

    bfcl_http_client = httpx.AsyncClient(timeout=30.0)
    config = await db.get_config()
    bfcl_scraper = BFCLScraper(
        http_client=bfcl_http_client,
        github_token=config.get("github_token", ""),
        max_models=int(config.get("bfcl_scrape_max_models", "200")),
    )

    async def _publish(channel_id: str, embed) -> bool:
        return await publish_embed_to_channel(bot, channel_id, embed)

    async def _aa_scraper_factory() -> ArtificialAnalysisScraper:
        # Releer la config en CADA scrape: la aa_api_key puede configurarse
        # desde el dashboard despues del arranque del bot. Un snapshot tomado
        # aqui en setup() quedaria viejo y el scrape fallaria con
        # error="unauthorized" pese a estar la key persistida en la DB.
        current = await db.get_config()
        return ArtificialAnalysisScraper(
            api_key=current.get("aa_api_key", ""),
        )

    scheduler = PluginScheduler(
        bot=bot,
        db=db,
        openrouter_client=client,
        aa_scraper_factory=_aa_scraper_factory,
        bfcl_scraper=bfcl_scraper,
        embed_publisher=_publish,
    )
    await scheduler.start()

    app.state.openrouter_prices_scheduler = scheduler
    app.state.openrouter_prices_bfcl_scraper = bfcl_scraper
    app.state.openrouter_prices_bfcl_client = bfcl_http_client

    # ------------------------------------------------------------------
    # Teardown callback (ADR-LIFECYCLE)
    # ------------------------------------------------------------------

    async def _teardown() -> None:
        await scheduler.stop()
        await client.close()
        await bfcl_http_client.aclose()
        await db.close()

    # Asegurar que teardown_callbacks existe
    if not hasattr(app.state, "teardown_callbacks"):
        app.state.teardown_callbacks = []
    app.state.teardown_callbacks.append(_teardown)
