"""Plugin de reproducción de videos (RessyTube).

Permite que cualquier persona reproduzca videos de YouTube como pantalla
compartida (Go Live) en su canal de voz, vía el comando slash `/ver`. El trabajo
pesado lo hace el servicio Node `video-worker` (un pool de cuentas selfbot que
abren Firefox + capturan con ffmpeg). Este plugin:

- Guarda los tokens de usuario (workers) en SQLite y los re-sincroniza con el
  manager al arrancar.
- Expone `/ver` y `/parar` en Discord.
- Expone API REST para el dashboard (alta/baja de workers, estado, config).

Patrón de plugin: setup(bot, config_manager, app). DB en data/plugins/.
Tokens: plaintext en DB local (bot personal), NUNCA devueltos completos al front.
"""

from __future__ import annotations

import asyncio
import json
import os

from src.bot.core.bot import Bot
from src.bot.core.config import ConfigManager

ALL_COMMANDS = ["ver", "parar", "siguiente"]

DEFAULTS = {
    "enabled": "true",
    "manager_url": os.getenv("VIDEO_MANAGER_URL", "http://video-worker:8081"),
    "width": "1280",
    "height": "720",
    "fps": "30",
    "bitrate": "3000",
    "bitrate_max": "4500",
    "audio_offset": "0.3",
    "enabled_commands": json.dumps(ALL_COMMANDS),
}


async def _resync_workers(db, manager) -> None:
    """Re-registra en el manager los workers guardados (best-effort).

    El manager es un contenedor aparte sin estado persistente: al reiniciar
    pierde las sesiones selfbot. Aquí se las devolvemos desde la DB del bot.
    Tolerante a fallos: si el manager está caído, se reintenta perezosamente
    la próxima vez que alguien use `/ver`.
    """
    try:
        rows = await db.execute_fetchall("SELECT user_id, token FROM video_workers")
    except Exception:
        return
    for _user_id, token in rows:
        try:
            await manager.add_worker(token)
        except Exception as exc:
            print(f"[video_player] resync worker falló: {exc}")


async def setup(bot: Bot, config_manager: ConfigManager, app):
    from .cog import VideoCog
    from .api import router as video_router
    from .manager_client import ManagerClient

    db_dir = "data/plugins"
    os.makedirs(db_dir, exist_ok=True)
    db_path = f"{db_dir}/video_player.db"

    import aiosqlite

    db = await aiosqlite.connect(db_path)
    await db.execute(
        "CREATE TABLE IF NOT EXISTS video_config (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
    )
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS video_workers (
            user_id    TEXT PRIMARY KEY,
            token      TEXT NOT NULL,
            username   TEXT DEFAULT '',
            tag        TEXT DEFAULT '',
            avatar_url TEXT DEFAULT '',
            added_at   TEXT DEFAULT (datetime('now'))
        )
        """
    )
    for key, value in DEFAULTS.items():
        await db.execute(
            "INSERT OR IGNORE INTO video_config (key, value) VALUES (?, ?)", (key, value)
        )
    # Migración idempotente: agregar "siguiente" a installs viejos cuyo
    # enabled_commands seguía siendo el default anterior ["ver", "parar"].
    await db.execute(
        "UPDATE video_config SET value = ? WHERE key = 'enabled_commands' AND value = ?",
        (json.dumps(ALL_COMMANDS), json.dumps(["ver", "parar"])),
    )
    await db.commit()

    # URL editable desde config; secret solo por entorno (sensible).
    row = await db.execute_fetchall(
        "SELECT value FROM video_config WHERE key = 'manager_url'"
    )
    manager_url = row[0][0] if row else DEFAULTS["manager_url"]
    manager_secret = os.getenv("VIDEO_MANAGER_SECRET", "")
    manager = ManagerClient(manager_url, manager_secret)

    cog = VideoCog(bot, db, manager, config_manager)
    await bot.add_cog(cog)

    app.include_router(video_router, prefix="/api/plugins/videos")

    app.state.video_db = db
    app.state.video_cog = cog
    app.state.video_manager = manager

    # Re-sincronizar workers guardados en segundo plano (no bloquea arranque).
    asyncio.create_task(_resync_workers(db, manager))

    # Teardown: cerrar la DB al apagar.
    async def _teardown() -> None:
        try:
            await db.close()
        except Exception:
            pass

    if not hasattr(app.state, "teardown_callbacks"):
        app.state.teardown_callbacks = []
    app.state.teardown_callbacks.append(_teardown)

    return db
