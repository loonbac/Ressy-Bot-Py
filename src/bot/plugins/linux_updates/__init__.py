"""Plugin de monitoreo de versiones Linux."""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

DEFAULTS = {
    "enabled": "true",
    "refresh_interval_hours": "12",
    "eol_warning_days": "90",
    "discord_channel_id": "",
}


async def setup(bot, config_manager, app) -> None:
    """Inicializa el plugin linux_updates."""
    from .database import LinuxUpdatesDatabase
    from .client import EndOfLifeClient
    from .api import router as api_router
    from .scheduler import LinuxUpdatesScheduler
    from .cog import LinuxCog
    from .embeds import build_eol_notification_embed
    from src.bot.plugins.openrouter_prices.discord_embeds import publish_embed_to_channel

    # Crear directorio de datos
    db_dir = "data/plugins"
    os.makedirs(db_dir, exist_ok=True)
    db_path = f"{db_dir}/linux-updates.db"

    # Inicializar DB
    db = LinuxUpdatesDatabase(db_path)
    await db.connect()

    # Inicializar cliente HTTP
    client = EndOfLifeClient()

    # Crear e instalar cog
    cog = LinuxCog(bot=bot, db=db)
    await bot.add_cog(cog)

    # Montar router
    app.include_router(
        api_router,
        prefix="/api/plugins/linux-updates",
        tags=["linux-updates"],
    )

    # Embed publisher para notificaciones EOL
    async def _publish(channel_id: str, embed) -> bool:
        try:
            return await publish_embed_to_channel(bot, channel_id, embed)
        except Exception:
            logger.exception("Error publicando embed al canal %s", channel_id)
            return False

    # Scheduler
    scheduler = LinuxUpdatesScheduler(
        db=db,
        client=client,
        embed_publisher=_publish,
    )
    await scheduler.start()

    # Almacenar estado
    app.state.linux_updates_db = db
    app.state.linux_updates_client = client
    app.state.linux_updates_cog = cog
    app.state.linux_updates_scheduler = scheduler

    # Teardown
    async def _teardown() -> None:
        if hasattr(app.state, "linux_updates_scheduler"):
            await app.state.linux_updates_scheduler.stop()
        if hasattr(app.state, "linux_updates_client"):
            await app.state.linux_updates_client.close()
        if hasattr(app.state, "linux_updates_db"):
            await app.state.linux_updates_db.close()

    if not hasattr(app.state, "teardown_callbacks"):
        app.state.teardown_callbacks = []
    app.state.teardown_callbacks.append(_teardown)
