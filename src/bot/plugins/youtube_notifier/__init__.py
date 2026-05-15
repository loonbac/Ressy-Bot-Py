import os

from src.bot.core.bot import Bot
from src.bot.core.config import ConfigManager
from src.web.app import create_app


async def setup(bot: Bot, config_manager: ConfigManager, app):
    """Inicializa el plugin de notificaciones de YouTube."""
    db_dir = "data/plugins"
    os.makedirs(db_dir, exist_ok=True)
    db_path = f"{db_dir}/youtube.db"

    from .monitor import YouTubeMonitor
    from .api import router as youtube_router

    # Crear monitor
    monitor = YouTubeMonitor(db_path, config_manager, bot)
    await monitor.init_db()
    await monitor.start_hub_renewal_loop()

    # Montar rutas API
    app.include_router(youtube_router, prefix="/api/plugins/youtube")

    # Guardar monitor en app.state para acceso desde la API
    app.state.youtube_monitor = monitor

    # Teardown callback
    async def _teardown() -> None:
        await monitor.stop()
        await monitor.close_db()

    if not hasattr(app.state, "teardown_callbacks"):
        app.state.teardown_callbacks = []
    app.state.teardown_callbacks.append(_teardown)

    return monitor
