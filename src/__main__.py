"""Entry point del bot.

Arranca el bot de Discord y el servidor FastAPI en el mismo event loop.
Usar:
  uv run ressy-bot
  python -m src
"""

import asyncio
import os

from dotenv import load_dotenv

load_dotenv()


async def main_async() -> None:
    from src.bot.core.config import ConfigManager
    from src.bot.core.bot import Bot
    from src.bot.loader import load_cogs
    from src.web.app import create_app
    import uvicorn

    # Asegurar que el directorio de datos existe
    db_path = os.getenv("DATABASE_PATH", "data/bot.db")
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)

    # Inicializar config
    cm = ConfigManager()
    await cm.load(db_path)

    # Inicializar bot
    bot = Bot(cm)
    await load_cogs(bot, cm)

    # Inicializar FastAPI
    from src.web.app import mount_static_files

    app = create_app(config_manager=cm, bot=bot)

    # Cargar plugins (must happen BEFORE mounting static files)
    from src.bot.plugins.youtube_notifier import setup as setup_youtube

    monitor = await setup_youtube(bot, cm, app)
    await monitor.start()  # Iniciar polling de YouTube

    # Mount SPA static files *after* all API routes are registered
    mount_static_files(app)

    # Arrancar Uvicorn como tarea asíncrona (NO uvicorn.run que es sync)
    config = uvicorn.Config(app, host=os.getenv("HOST", "0.0.0.0"),
                            port=int(os.getenv("PORT", "8000")), log_level="info")
    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve())

    # Correr ambos en el mismo event loop
    await asyncio.gather(
        bot.start(os.getenv("DISCORD_TOKEN", "")),
        server_task,
    )


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
