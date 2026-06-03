from __future__ import annotations

import json
from typing import Any

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from .events import connect, disconnect
from .models import ConfigPayload, ExecuteRequest, SessionCreateRequest
from .piston import DEFAULT_PISTON_URL

router = APIRouter()


def _get_cog(request: Request):
    cog = getattr(request.app.state, "code_runner_cog", None)
    if cog is None:
        raise HTTPException(status_code=503, detail="Code Runner no inicializado")
    return cog


def _typed_config(raw: dict[str, str]) -> dict[str, Any]:
    def _list(key: str) -> list[str]:
        return [item.strip() for item in raw.get(key, "").split(",") if item.strip()]

    return {
        "trigger_channel_id": raw.get("trigger_channel_id") or None,
        "lobby_message_id": raw.get("lobby_message_id") or None,
        "enabled": raw.get("enabled", "true") == "true",
        "allowed_languages": _list("allowed_languages"),
        "max_code_chars": int(raw.get("max_code_chars", "4000")),
        "max_output_chars": int(raw.get("max_output_chars", "4000")),
        "exec_timeout_seconds": int(raw.get("exec_timeout_seconds", "10")),
        "session_timeout_minutes": int(raw.get("session_timeout_minutes", raw.get("session_ttl_minutes", "30"))),
        "cooldown_seconds": int(raw.get("cooldown_seconds", raw.get("rate_limit_seconds", "10"))),
        "max_infractions": int(raw.get("max_infractions", "3")),
        "security_model": raw.get("security_model", "MiniMax-M2.7"),
        "security_enabled": raw.get("security_enabled", "true") == "true",
        "mod_role_names": _list("mod_role_names"),
        "category_id": raw.get("category_id") or None,
        "piston_url": raw.get("piston_url", DEFAULT_PISTON_URL),
    }


def _serialize_session(session: dict[str, Any]) -> dict[str, Any]:
    data = dict(session)
    for key in ("user_id", "guild_id", "channel_id"):
        if data.get(key) is not None:
            data[key] = str(data[key])
    return data


def _decode_execution(row: dict[str, Any]) -> dict[str, Any]:
    data = dict(row)
    data["user_id"] = str(data.get("user_id"))
    for key, default in (("warnings_json", []), ("security_json", {}), ("analysis_json", {})):
        try:
            data[key.removesuffix("_json")] = json.loads(data.get(key) or json.dumps(default))
        except json.JSONDecodeError:
            data[key.removesuffix("_json")] = default
        data.pop(key, None)
    return data


@router.get("/config")
async def get_config(request: Request) -> dict[str, Any]:
    return _typed_config(await _get_cog(request).db.get_config())


@router.put("/config")
async def update_config(request: Request, payload: ConfigPayload) -> dict[str, Any]:
    data = payload.model_dump(exclude_none=True)
    if "session_ttl_minutes" in data and "session_timeout_minutes" not in data:
        data["session_timeout_minutes"] = data.pop("session_ttl_minutes")
    if "rate_limit_seconds" in data and "cooldown_seconds" not in data:
        data["cooldown_seconds"] = data.pop("rate_limit_seconds")
    for key in ("session_timeout_minutes", "cooldown_seconds", "exec_timeout_seconds"):
        if key in data:
            data[key] = max(1, int(data[key]))
    if "max_code_chars" in data:
        data["max_code_chars"] = max(100, int(data["max_code_chars"]))
    if "max_output_chars" in data:
        data["max_output_chars"] = max(100, int(data["max_output_chars"]))
    if "max_infractions" in data:
        data["max_infractions"] = max(1, int(data["max_infractions"]))
    return _typed_config(await _get_cog(request).db.update_config(data))


@router.get("/status")
async def status(request: Request) -> dict[str, Any]:
    cog = _get_cog(request)
    cfg = await cog.db.get_config()
    expired = await cog.db.expired_sessions()
    return {"enabled": cfg.get("enabled") == "true", "ready": True, "expired_pending": len(expired)}


@router.get("/sessions")
async def list_sessions(request: Request, status: str | None = None, limit: int = 50) -> dict[str, Any]:
    sessions = await _get_cog(request).db.list_sessions(status=status, limit=limit)
    return {"sessions": [_serialize_session(s) for s in sessions]}


@router.get("/sessions/{session_id}")
async def get_session(request: Request, session_id: int) -> dict[str, Any]:
    cog = _get_cog(request)
    session = await cog.db.session_by_id(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    executions = await cog.db.list_executions_for_session(session_id)
    data = _serialize_session(session)
    data["executions"] = [_decode_execution(r) for r in executions]
    return data


@router.get("/sessions/{session_id}/transcript", response_class=HTMLResponse)
async def get_session_transcript(request: Request, session_id: int) -> HTMLResponse:
    session = await _get_cog(request).db.session_by_id(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Sesión no encontrada")
    transcript_path = str(session.get("transcript_path") or "")
    if not transcript_path:
        raise HTTPException(status_code=404, detail="La sesión aún no tiene transcript")
    path = Path(transcript_path)
    try:
        resolved = path.resolve()
        allowed = Path("data/plugins/code_runner_transcripts").resolve()
        if allowed not in resolved.parents and resolved != allowed:
            raise HTTPException(status_code=403, detail="Ruta de transcript no permitida")
        return HTMLResponse(resolved.read_text(encoding="utf-8"))
    except HTTPException:
        raise
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Archivo de transcript no encontrado") from None


@router.get("/executions")
async def list_executions(request: Request, limit: int = 50) -> dict[str, Any]:
    rows = await _get_cog(request).db.list_executions(limit=limit)
    return {"executions": [_decode_execution(r) for r in rows]}


@router.get("/executions/{execution_id}")
async def get_execution(request: Request, execution_id: int) -> dict[str, Any]:
    row = await _get_cog(request).db.execution_by_id(execution_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Ejecución no encontrada")
    return _decode_execution(row)


@router.get("/stats")
async def stats(request: Request) -> dict[str, Any]:
    return await _get_cog(request).db.stats()


@router.get("/discord-channels")
async def discord_channels(request: Request) -> dict[str, Any]:
    bot = getattr(request.app.state, "bot", None)
    if bot is None:
        return {"channels": []}
    cm = getattr(request.app.state, "config_manager", None)
    guild_id_str = cm.get("guild_id") if cm else None
    guild_id = int(guild_id_str) if guild_id_str else None
    channels: list[dict[str, str]] = []
    for guild in getattr(bot, "guilds", []) or []:
        if guild_id is not None and int(guild.id) != guild_id:
            continue
        for channel in getattr(guild, "text_channels", []) or []:
            channels.append({"id": str(channel.id), "name": f"#{channel.name}", "guild_name": str(guild.name)})
    return {"channels": channels}


@router.get("/discord-roles")
async def discord_roles(request: Request) -> dict[str, Any]:
    bot = getattr(request.app.state, "bot", None)
    if bot is None:
        return {"roles": []}
    cm = getattr(request.app.state, "config_manager", None)
    guild_id_str = cm.get("guild_id") if cm else None
    guild_id = int(guild_id_str) if guild_id_str else None
    roles: list[dict[str, str]] = []
    for guild in getattr(bot, "guilds", []) or []:
        if guild_id is not None and int(guild.id) != guild_id:
            continue
        for role in getattr(guild, "roles", []) or []:
            name = str(getattr(role, "name", ""))
            # @everyone no sirve como rol moderador.
            if name == "@everyone" or getattr(role, "is_default", lambda: False)():
                continue
            roles.append({"id": str(role.id), "name": name, "guild_name": str(guild.name)})
    return {"roles": roles}


@router.get("/trigger-channel/republish")
async def republish_trigger_channel(request: Request) -> dict[str, Any]:
    cog = _get_cog(request)
    result = await cog.republish_lobby()
    if not result.get("published"):
        reason = str(result.get("reason") or "No se pudo republicar el lobby")
        raise HTTPException(status_code=400 if "configurado" in reason else 404, detail=reason)
    return result


@router.post("/execute")
async def execute(request: Request, payload: ExecuteRequest) -> dict[str, Any]:
    cog = _get_cog(request)
    ok, wait = await cog._check_rate_limit(int(payload.user_id))
    if not ok:
        raise HTTPException(status_code=429, detail=f"Rate limit activo. Intenta nuevamente en {wait}s.")
    result = await cog.execute_code(payload.user_id, payload.guild_id, payload.channel_id, payload.code, payload.language)
    if result["status"] == "blocked":
        raise HTTPException(status_code=400, detail=result["stderr"])
    if result["status"] == "rate_limited":
        raise HTTPException(status_code=429, detail=result["stderr"])
    return result


@router.post("/sessions")
async def create_session(request: Request, payload: SessionCreateRequest) -> dict[str, Any]:
    bot = getattr(request.app.state, "bot", None)
    if bot is None:
        raise HTTPException(status_code=503, detail="Bot Discord no disponible")
    guild = bot.get_guild(int(payload.guild_id)) if hasattr(bot, "get_guild") else None
    if guild is None:
        raise HTTPException(status_code=404, detail="Servidor no encontrado")
    user = guild.get_member(int(payload.user_id)) if hasattr(guild, "get_member") else None
    if user is None:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    result = await _get_cog(request).sessions.create_session(guild, user, None)
    session = result["session"]
    return {"created": bool(result.get("created")), "session": _serialize_session(session)}


@router.delete("/sessions/{session_id}")
async def close_session(request: Request, session_id: int) -> dict[str, Any]:
    # TODO: proteger este endpoint con auth admin cuando el dashboard tenga sesión real.
    cog = _get_cog(request)
    session = await cog.db.session_by_id(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="La sesión no existe o no fue creada por code_runner")
    channel_id = str(session["channel_id"])
    channel = cog.bot.get_channel(int(channel_id)) if hasattr(cog.bot, "get_channel") else None
    if channel is None:
        closed = await cog.db.close_session(channel_id, "")
        return {"closed": closed, "deleted": False}
    closed = await cog.sessions.close_session_channel(channel, reason="manual")
    return {"closed": closed, "deleted": closed}


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        disconnect(websocket)
