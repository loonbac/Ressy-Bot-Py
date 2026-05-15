from __future__ import annotations

import os


async def setup(bot, config_manager, app):
    from .api import router
    from .client import AIChatClient
    from .cog import AIChatCog
    from .database import AIChatDatabase

    os.makedirs("data/plugins", exist_ok=True)
    db = AIChatDatabase("data/plugins/ai_chat.db")
    await db.connect()
    client = AIChatClient(config_manager=config_manager or getattr(app.state, "config_manager", None))
    cog = AIChatCog(bot=bot, db=db, client=client)
    await bot.add_cog(cog)

    app.include_router(router, prefix="/api/plugins/ai-chat", tags=["ai-chat"])
    app.state.ai_chat_db = db
    app.state.ai_chat_client = client
    app.state.ai_chat_cog = cog

    async def _teardown() -> None:
        await client.close()
        await db.close()

    if not hasattr(app.state, "teardown_callbacks"):
        app.state.teardown_callbacks = []
    app.state.teardown_callbacks.append(_teardown)
    return db
