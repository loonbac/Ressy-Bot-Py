import os

from src.bot.core.bot import Bot
from src.bot.core.config import ConfigManager


DEFAULT_WELCOME_MESSAGE = (
    "Un espacio para desarrollo de software, agentes de IA, automatización, "
    "ciberseguridad e innovación tecnológica.\n\n"
    "📌 Revisa las reglas\n"
    "💬 Preséntate\n"
    "🚀 Comparte proyectos, ideas y aprende con la comunidad.\n\n"
    "Construye. Automatiza. Innova."
)

DEFAULTS = {
    "enabled": "true",
    "welcome_channel_id": "",
    "welcome_message": DEFAULT_WELCOME_MESSAGE,
    "embed_title": "Bienvenid@ {user_name} a Korosoft Community",
    "embed_color": "2326507",
    "welcome_image_url": "",
    "dm_enabled": "false",
    "delete_previous": "false",
}


async def setup(bot: Bot, config_manager: ConfigManager, app):
    """Inicializa el plugin de bienvenida."""
    db_dir = "data/plugins"
    os.makedirs(db_dir, exist_ok=True)
    db_path = f"{db_dir}/welcome.db"

    from .cog import WelcomeCog
    from .api import router as welcome_router

    import aiosqlite
    db = await aiosqlite.connect(db_path)
    await db.execute("CREATE TABLE IF NOT EXISTS welcome_config (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    for key, value in DEFAULTS.items():
        await db.execute("INSERT OR IGNORE INTO welcome_config (key, value) VALUES (?, ?)", (key, value))

    # Migration: replace previous defaults if user never customized them.
    LEGACY_VALUES = {
        "welcome_message": "¡Bienvenido {{user}} al servidor!",
        "embed_title": "BIENVENIDO/A",
    }
    LEGACY_VALUES["welcome_message_v2"] = (
        "¡Bienvenido/a {user} a {server}! 🌸 Esperamos que disfrutes de tu "
        "estancia en nuestra tranquila morada. Eres nuestro miembro número "
        "{member_count}."
    )
    await db.execute(
        "UPDATE welcome_config SET value = ? WHERE key = 'welcome_message' AND value IN (?, ?)",
        (DEFAULTS["welcome_message"], LEGACY_VALUES["welcome_message"], LEGACY_VALUES["welcome_message_v2"]),
    )
    await db.execute(
        "UPDATE welcome_config SET value = ? WHERE key = 'embed_title' AND value = ?",
        (DEFAULTS["embed_title"], LEGACY_VALUES["embed_title"]),
    )
    # Drop legacy keys to avoid stale UI state
    await db.execute("DELETE FROM welcome_config WHERE key = 'mention_user'")
    await db.commit()

    cog = WelcomeCog(db, bot)
    await bot.add_cog(cog)

    app.include_router(welcome_router, prefix="/api/plugins/welcome")
    app.state.welcome_db = db
    app.state.welcome_cog = cog

    return db
