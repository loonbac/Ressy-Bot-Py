import math
import os
from datetime import datetime, timezone
from typing import Any

import discord
from fastapi import APIRouter, HTTPException, Request

from src.shared.models import BotStatus, ConfigResponse

router = APIRouter()


def _get_memory_mb() -> float:
    """Lee memoria RAM del proceso actual en MB (Linux)."""
    try:
        with open(f"/proc/{os.getpid()}/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return round(int(line.split()[1]) / 1024, 1)
    except Exception:
        pass
    return 0.0


@router.get("/config")
async def get_config(request: Request) -> dict[str, list[ConfigResponse]]:
    cm = request.app.state.config_manager
    if cm is None:
        raise HTTPException(status_code=500, detail="ConfigManager not initialized")

    all_config = cm.get_all()
    configs = [
        ConfigResponse(key=k, value=v, updated_at=datetime.now(timezone.utc))
        for k, v in all_config.items()
    ]
    return {"configs": configs}


@router.put("/config/{key}")
async def update_config(
    request: Request, key: str, body: dict[str, Any]
) -> ConfigResponse:
    cm = request.app.state.config_manager
    if cm is None:
        raise HTTPException(status_code=500, detail="ConfigManager not initialized")

    if key not in cm._schema:
        raise HTTPException(status_code=400, detail=f"Invalid config key: {key}")

    if "value" not in body:
        raise HTTPException(status_code=400, detail="Missing 'value' in request body")

    value = body["value"]

    try:
        await cm.update(key, value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return ConfigResponse(key=key, value=value, updated_at=datetime.now(timezone.utc))


@router.get("/guilds")
async def list_guilds(request: Request) -> dict:
    """List Discord guilds the bot is connected to."""
    bot = request.app.state.bot
    if bot is None:
        return {"guilds": []}

    guilds = []
    for guild in bot.guilds:
        guilds.append({
            "id": str(guild.id),
            "name": guild.name,
            "member_count": guild.member_count,
            "icon_url": guild.icon.url if guild.icon else None,
        })

    return {"guilds": sorted(guilds, key=lambda g: g["name"])}


@router.get("/status")
async def get_status(request: Request) -> BotStatus:
    bot = request.app.state.bot
    from src.web.routes.ws import get_connected_count

    connected_ws_clients = get_connected_count()

    latency_ms = 0.0

    bot_avatar_url = ""
    bot_name = ""

    if bot is None:
        return BotStatus(
            online=False,
            uptime_seconds=0.0,
            loaded_cogs=[],
            connected_ws_clients=connected_ws_clients,
            latency_ms=latency_ms,
            memory_mb=_get_memory_mb(),
            bot_avatar_url=bot_avatar_url,
            bot_name=bot_name,
        )

    if hasattr(bot, "user") and bot.user is not None:
        raw_name = bot.user.name
        if isinstance(raw_name, str):
            bot_name = raw_name
        if hasattr(bot.user, "display_avatar") and bot.user.display_avatar:
            raw_url = bot.user.display_avatar.url
            if isinstance(raw_url, str):
                bot_avatar_url = raw_url

    online = False
    if hasattr(bot, "is_ready"):
        try:
            result = bot.is_ready()
            if hasattr(result, "__await__"):
                online = await result
            else:
                online = result
        except Exception:
            online = False

    uptime_seconds = 0.0
    if hasattr(bot, "start_time") and bot.start_time is not None:
        uptime_seconds = (
            datetime.now(timezone.utc) - bot.start_time
        ).total_seconds()

    loaded_cogs = []
    if hasattr(bot, "cogs"):
        loaded_cogs = list(bot.cogs.keys())

    if hasattr(bot, "latency"):
        raw = bot.latency
        if isinstance(raw, (int, float)) and math.isfinite(raw) and raw >= 0:
            latency_ms = round(raw * 1000, 1)

    return BotStatus(
        online=online,
        uptime_seconds=uptime_seconds,
        loaded_cogs=loaded_cogs,
        connected_ws_clients=connected_ws_clients,
        latency_ms=latency_ms,
        memory_mb=_get_memory_mb(),
        bot_avatar_url=bot_avatar_url,
        bot_name=bot_name,
    )


@router.post("/presence")
async def update_presence(request: Request) -> dict:
    """Apply the configured status and activity to the bot."""
    cm = request.app.state.config_manager
    bot = request.app.state.bot

    if cm is None or bot is None:
        raise HTTPException(status_code=500, detail="Bot no disponible")

    status_map = {
        "online": discord.Status.online,
        "idle": discord.Status.idle,
        "dnd": discord.Status.dnd,
        "invisible": discord.Status.invisible,
    }
    activity_map = {
        "playing": lambda t: discord.Game(name=t),
        "watching": lambda t: discord.Activity(type=discord.ActivityType.watching, name=t),
        "listening": lambda t: discord.Activity(type=discord.ActivityType.listening, name=t),
        "competing": lambda t: discord.Activity(type=discord.ActivityType.competing, name=t),
    }

    status_str = cm.get("bot_status") or "online"
    activity_type = cm.get("bot_activity_type") or "playing"
    activity_text = cm.get("bot_activity_text") or ""

    status = status_map.get(status_str, discord.Status.online)
    activity_fn = activity_map.get(activity_type, activity_map["playing"])
    activity = activity_fn(activity_text) if activity_text else None

    try:
        await bot.change_presence(status=status, activity=activity)
        return {"status": status_str, "activity_type": activity_type, "activity_text": activity_text}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
