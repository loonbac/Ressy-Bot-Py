import json
import os

from src.bot.core.bot import Bot
from src.bot.core.config import ConfigManager

# Comandos de música disponibles (espejo de ALL_COMMANDS en el frontend).
ALL_COMMANDS = ["play", "stop", "queue", "nowplaying"]

DEFAULTS = {
    "enabled": "true",
    "default_volume": "50",
    "audio_quality": "high",
    "allowed_channel_ids": json.dumps([]),
    "enabled_commands": json.dumps(ALL_COMMANDS),
}


async def setup(bot: Bot, config_manager: ConfigManager, app):
    """Inicializa el plugin de música."""
    from .cog import MusicCog
    from .api import router as music_router
    from .player import GuildPlayerManager

    db_dir = "data/plugins"
    os.makedirs(db_dir, exist_ok=True)
    db_path = f"{db_dir}/music_player.db"

    import aiosqlite
    db = await aiosqlite.connect(db_path)
    await db.execute(
        "CREATE TABLE IF NOT EXISTS music_config (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
    )
    for key, value in DEFAULTS.items():
        await db.execute(
            "INSERT OR IGNORE INTO music_config (key, value) VALUES (?, ?)", (key, value)
        )
    await db.commit()

    # Check FFmpeg availability
    import shutil
    ffmpeg_available = shutil.which("ffmpeg") is not None
    if not ffmpeg_available:
        print("WARNING: FFmpeg no encontrado. El plugin de música no funcionará sin FFmpeg.")

    # Create player manager
    player_manager = GuildPlayerManager()

    # Register cog
    cog = MusicCog(bot, player_manager, db, config_manager)
    await bot.add_cog(cog)

    # Register API routes
    app.include_router(music_router, prefix="/api/plugins/music")

    # Store state
    app.state.music_db = db
    app.state.music_cog = cog
    app.state.music_player_manager = player_manager
    app.state.ffmpeg_available = ffmpeg_available

    return db
