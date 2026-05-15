from __future__ import annotations

import os


async def setup(bot, config_manager, app):
    from .api import router
    from .cog import CodeRunnerCog
    from .database import CodeRunnerDatabase
    from .piston import PistonClient

    os.makedirs("data/plugins", exist_ok=True)
    db = CodeRunnerDatabase("data/plugins/code_runner.db")
    await db.connect()
    cfg = await db.get_config()
    # Precedencia: env PISTON_URL (Coolify) > config DB > default público.
    # El público emkc.org es whitelist-only desde 2026-02-15; self-host recomendado.
    piston_url = os.getenv("PISTON_URL", "").strip() or cfg.get("piston_url", "https://emkc.org/api/v2/piston")
    piston = PistonClient(piston_url)
    ai_chat = getattr(app.state, "ai_chat_cog", None)
    cog = CodeRunnerCog(bot=bot, db=db, piston=piston, ai_chat=ai_chat)
    await bot.add_cog(cog)
    await cog.sessions.start()
    await cog.startup_republish_lobby()

    app.include_router(router, prefix="/api/plugins/code-runner", tags=["code-runner"])
    app.state.code_runner_db = db
    app.state.code_runner_cog = cog
    app.state.code_runner_piston = piston

    async def _teardown() -> None:
        await cog.stop_workers()
        await cog.sessions.stop()
        await piston.close()
        await db.close()

    if not hasattr(app.state, "teardown_callbacks"):
        app.state.teardown_callbacks = []
    app.state.teardown_callbacks.append(_teardown)
    return db
