import math
import os
from datetime import datetime, timezone
from typing import Any

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
