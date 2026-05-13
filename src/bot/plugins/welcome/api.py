from typing import Any

import discord
from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


ALLOWED_KEYS = {
    "enabled",
    "welcome_channel_id",
    "welcome_message",
    "embed_title",
    "embed_color",
    "welcome_image_url",
    "dm_enabled",
    "delete_previous",
}

BOOL_KEYS = {"enabled", "dm_enabled", "delete_previous"}
INT_KEYS = {"embed_color"}


def _get_db(request: Request):
    db = getattr(request.app.state, "welcome_db", None)
    if db is None:
        raise HTTPException(status_code=500, detail="Welcome plugin no inicializado")
    return db


def _normalize(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    return str(value)


def _serialize_config(rows: list[tuple[str, str]]) -> dict[str, Any]:
    raw = {r[0]: r[1] for r in rows}
    out: dict[str, Any] = {}
    for key, val in raw.items():
        if key in BOOL_KEYS:
            out[key] = val == "true"
        elif key in INT_KEYS:
            try:
                out[key] = int(val)
            except (TypeError, ValueError):
                out[key] = 0
        else:
            out[key] = val
    return out


@router.get("/config")
async def get_config(request: Request) -> dict[str, Any]:
    db = _get_db(request)
    rows = await db.execute_fetchall("SELECT key, value FROM welcome_config")
    return _serialize_config(list(rows))


@router.put("/config")
async def update_config(request: Request, body: dict[str, Any]) -> dict[str, Any]:
    db = _get_db(request)
    for key, value in body.items():
        if key in ALLOWED_KEYS:
            await db.execute(
                "INSERT OR REPLACE INTO welcome_config (key, value) VALUES (?, ?)",
                (key, _normalize(value)),
            )
    await db.commit()
    rows = await db.execute_fetchall("SELECT key, value FROM welcome_config")
    return _serialize_config(list(rows))


@router.get("/discord-channels")
async def list_discord_channels(request: Request) -> dict[str, Any]:
    bot = getattr(request.app.state, "bot", None)
    if bot is None:
        return {"channels": []}

    cm = getattr(request.app.state, "config_manager", None)
    guild_id_str = cm.get("guild_id") if cm else None
    guild_id = int(guild_id_str) if guild_id_str else None

    channels: list[dict[str, str]] = []
    for guild in bot.guilds:
        if guild_id is not None and guild.id != guild_id:
            continue
        for channel in guild.text_channels:
            channels.append({
                "id": str(channel.id),
                "name": f"#{channel.name}",
                "guild_name": guild.name,
            })
    return {"channels": channels}


async def _resolve_channel(bot: Any, channel_id: int):
    """Resolve channel via cache then fall back to Discord API fetch."""
    channel = bot.get_channel(channel_id)
    if channel is not None:
        return channel
    try:
        return await bot.fetch_channel(channel_id)
    except discord.NotFound:
        raise HTTPException(status_code=404, detail=f"Canal {channel_id} no encontrado en Discord")
    except discord.Forbidden:
        raise HTTPException(
            status_code=403,
            detail=f"Bot sin acceso al canal {channel_id} (¿perdió permisos o salió del servidor?)",
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Discord API error al buscar canal: {exc}")


async def _resolve_bot_member(channel: Any, bot: Any):
    """Resolve the bot's Member object in the channel's guild."""
    guild = getattr(channel, "guild", None)
    if guild is None:
        raise HTTPException(status_code=400, detail="El canal no pertenece a un servidor (¿es DM?)")
    me = guild.me
    if me is None and bot.user is not None:
        try:
            me = await guild.fetch_member(bot.user.id)
        except Exception:
            me = None
    if me is None:
        raise HTTPException(
            status_code=400,
            detail=f"Bot no es miembro del servidor '{guild.name}'",
        )
    return me, guild


@router.post("/test")
async def send_test_welcome(request: Request) -> dict[str, Any]:
    """Send a sample welcome message using the bot itself as the fake new member.

    Bypasses the enabled toggle so the user can preview even while disabled.
    """
    db = _get_db(request)
    cog = getattr(request.app.state, "welcome_cog", None)
    bot = getattr(request.app.state, "bot", None)
    if cog is None or bot is None:
        raise HTTPException(status_code=503, detail="Bot no disponible")

    rows = await db.execute_fetchall(
        "SELECT value FROM welcome_config WHERE key = 'welcome_channel_id'"
    )
    channel_id_raw = rows[0][0] if rows else ""
    if not channel_id_raw:
        raise HTTPException(
            status_code=400,
            detail="No hay canal configurado. Selecciona uno en el editor.",
        )

    try:
        channel_id_int = int(channel_id_raw)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"ID de canal inválido: {channel_id_raw!r}")

    channel = await _resolve_channel(bot, channel_id_int)

    if not hasattr(channel, "send"):
        raise HTTPException(
            status_code=400,
            detail=f"El canal no soporta mensajes (tipo: {type(channel).__name__})",
        )

    me, guild = await _resolve_bot_member(channel, bot)

    # Permission preflight to give clear errors before attempting send
    try:
        perms = channel.permissions_for(me)
    except Exception:
        perms = None
    if perms is not None:
        missing = []
        if not perms.send_messages:
            missing.append("Enviar mensajes")
        if not perms.embed_links:
            missing.append("Insertar enlaces")
        if not perms.attach_files:
            missing.append("Adjuntar archivos")
        if missing:
            raise HTTPException(
                status_code=403,
                detail=f"Bot sin permisos en #{getattr(channel, 'name', channel_id_int)}: {', '.join(missing)}",
            )

    try:
        result = await cog.send_welcome(me, force=True)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error inesperado: {type(exc).__name__}: {exc}")

    if not result.get("sent_channel"):
        channel_error = result.get("channel_error") or "Discord rechazó el envío"
        raise HTTPException(status_code=400, detail=str(channel_error))

    return {
        "sent": True,
        "channel_id": str(channel.id),
        "channel_name": getattr(channel, "name", ""),
        "guild_name": getattr(guild, "name", ""),
        "sent_dm": bool(result.get("sent_dm")),
    }
