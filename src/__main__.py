"""Entry point del bot.

Arranca el bot de Discord y el servidor FastAPI en el mismo event loop.
Usar:
  uv run ressy-bot
  python -m src
"""

import asyncio
import os
import signal

from dotenv import load_dotenv

load_dotenv()


async def _run_teardowns(app, bot, callback_timeout: float = 10.0) -> None:
    """Ejecuta los teardown callbacks registrados por los plugins y cierra el bot."""
    callbacks = getattr(app.state, "teardown_callbacks", [])
    for cb in callbacks:
        try:
            await asyncio.wait_for(cb(), timeout=callback_timeout)
        except asyncio.TimeoutError:
            print(f"[Shutdown] Teardown callback excedio timeout de {callback_timeout}s")
        except Exception as exc:
            print(f"[Shutdown] Error en teardown callback: {exc}")
    try:
        await bot.close()
    except Exception as exc:
        print(f"[Shutdown] Error cerrando bot: {exc}")


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

    await setup_youtube(bot, cm, app)

    # Cargar plugin de blackboard
    from src.bot.plugins.blackboard import setup as setup_blackboard
    await setup_blackboard(bot, cm, app)

    # Cargar plugin de bienvenida
    from src.bot.plugins.welcome import setup as setup_welcome
    await setup_welcome(bot, cm, app)

    # Cargar plugin de música
    from src.bot.plugins.music_player import setup as setup_music_player
    await setup_music_player(bot, cm, app)

    # Cargar plugin de precios OpenRouter
    from src.bot.plugins.openrouter_prices import setup as setup_openrouter_prices
    await setup_openrouter_prices(bot, cm, app)

    # Cargar plugin de monitoreo de versiones Linux
    from src.bot.plugins.linux_updates import setup as setup_linux_updates
    await setup_linux_updates(bot, cm, app)

    # Cargar plugin de chat IA (MiniMax)
    from src.bot.plugins.ai_chat import setup as setup_ai_chat
    await setup_ai_chat(bot, cm, app)

    # Cargar plugin de Code Runner (depende de ai_chat para análisis de seguridad)
    from src.bot.plugins.code_runner import setup as setup_code_runner
    await setup_code_runner(bot, cm, app)

    # Mount SPA static files *after* all API routes are registered
    mount_static_files(app)

    # Arrancar Uvicorn como tarea asíncrona (NO uvicorn.run que es sync)
    config = uvicorn.Config(app, host=os.getenv("HOST", "0.0.0.0"),
                            port=int(os.getenv("PORT", "8000")), log_level="info")
    server = uvicorn.Server(config)

    # Shutdown event
    _shutdown_event = asyncio.Event()

    def _signal_handler() -> None:
        print("[Shutdown] Senal recibida, iniciando apagado ordenado...")
        _shutdown_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _signal_handler)

    bot_task = asyncio.create_task(bot.start(os.getenv("DISCORD_TOKEN", "")))
    server_task = asyncio.create_task(server.serve())
    shutdown_task = asyncio.create_task(_shutdown_event.wait())

    try:
        done, pending = await asyncio.wait(
            [bot_task, server_task, shutdown_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    finally:
        await _run_teardowns(app, bot, callback_timeout=10.0)


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
