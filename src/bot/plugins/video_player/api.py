"""Endpoints REST del plugin de videos (dashboard).

Monta en /api/plugins/videos. Gestiona config, alta/baja de workers (tokens de
usuario) y estado del worker-manager. Los tokens NUNCA se devuelven completos:
solo un preview de los últimos 4 caracteres.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from .manager_client import ManagerError

router = APIRouter()

ALLOWED_KEYS = {
    "enabled",
    "manager_url",
    "width",
    "height",
    "fps",
    "bitrate",
    "bitrate_max",
    "audio_offset",
    "enabled_commands",
}
BOOL_KEYS = {"enabled"}
INT_KEYS = {"width", "height", "fps", "bitrate", "bitrate_max"}
FLOAT_KEYS = {"audio_offset"}
LIST_KEYS = {"enabled_commands"}
QUALITY_KEYS = {"width", "height", "fps", "bitrate", "bitrate_max", "audio_offset"}
ALL_COMMANDS = ["ver", "parar", "siguiente"]


def _get_db(request: Request):
    db = getattr(request.app.state, "video_db", None)
    if db is None:
        raise HTTPException(status_code=500, detail="Plugin de videos no inicializado")
    return db


def _get_manager(request: Request):
    manager = getattr(request.app.state, "video_manager", None)
    if manager is None:
        raise HTTPException(status_code=500, detail="Worker-manager no inicializado")
    return manager


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
        elif key in FLOAT_KEYS:
            try:
                out[key] = float(val)
            except (TypeError, ValueError):
                out[key] = 0.0
        elif key in LIST_KEYS:
            try:
                parsed = json.loads(val)
                out[key] = parsed if isinstance(parsed, list) else []
            except (TypeError, ValueError):
                out[key] = []
        else:
            out[key] = val
    return out


def _token_preview(token: str) -> str:
    token = token or ""
    return f"…{token[-4:]}" if len(token) >= 4 else "…"


@router.get("/config")
async def get_config(request: Request) -> dict[str, Any]:
    db = _get_db(request)
    rows = await db.execute_fetchall("SELECT key, value FROM video_config")
    return _serialize_config(list(rows))


@router.put("/config")
async def update_config(request: Request, body: dict[str, Any]) -> dict[str, Any]:
    db = _get_db(request)
    manager = getattr(request.app.state, "video_manager", None)
    quality_changed = False
    for key, value in body.items():
        if key not in ALLOWED_KEYS:
            continue
        if key in INT_KEYS:
            try:
                value = int(value)
            except (TypeError, ValueError):
                continue
            quality_changed = quality_changed or key in QUALITY_KEYS
            stored = str(value)
        elif key in FLOAT_KEYS:
            try:
                value = max(0.0, min(3.0, float(value)))
            except (TypeError, ValueError):
                continue
            quality_changed = True
            stored = str(value)
        elif key in BOOL_KEYS:
            stored = "true" if value else "false"
        elif key in LIST_KEYS:
            items = value if isinstance(value, list) else []
            stored = json.dumps([str(v) for v in items if str(v) in ALL_COMMANDS])
        elif key == "manager_url":
            stored = str(value).strip()
            if manager is not None:
                manager.update(base_url=stored)
        else:
            stored = str(value)
        await db.execute(
            "INSERT OR REPLACE INTO video_config (key, value) VALUES (?, ?)", (key, stored)
        )
    await db.commit()

    rows = await db.execute_fetchall("SELECT key, value FROM video_config")
    cfg = _serialize_config(list(rows))

    # Propagar calidad al manager (best-effort: si está caído, no rompe el guardado).
    if quality_changed and manager is not None:
        try:
            await manager.set_quality({
                "width": cfg.get("width", 1280),
                "height": cfg.get("height", 720),
                "fps": cfg.get("fps", 30),
                "bitrate": cfg.get("bitrate", 3000),
                "bitrateMax": cfg.get("bitrate_max", 4500),
                "audioOffset": cfg.get("audio_offset", 0.3),
            })
        except ManagerError:
            pass
    return cfg


@router.get("/workers")
async def list_workers(request: Request) -> dict[str, Any]:
    """Workers guardados en DB enriquecidos con estado en vivo del manager."""
    db = _get_db(request)
    manager = _get_manager(request)
    rows = await db.execute_fetchall(
        "SELECT user_id, token, username, tag, avatar_url, added_at FROM video_workers"
    )

    live: dict[str, dict[str, Any]] = {}
    manager_online = True
    try:
        for w in await manager.list_workers():
            live[str(w.get("user_id") or w.get("id"))] = w
    except ManagerError:
        manager_online = False

    workers = []
    for user_id, token, username, tag, avatar_url, added_at in rows:
        lw = live.get(str(user_id))
        workers.append({
            "user_id": str(user_id),
            "username": (lw or {}).get("username") or username,
            "tag": (lw or {}).get("tag") or tag,
            "avatar_url": (lw or {}).get("avatar_url") or avatar_url,
            "status": (lw or {}).get("status") if lw else ("offline" if manager_online else "unknown"),
            "busy": bool((lw or {}).get("busy", False)),
            "token_preview": _token_preview(token),
            "added_at": added_at,
        })
    return {"workers": workers, "manager_online": manager_online}


@router.post("/workers")
async def add_worker(request: Request, body: dict[str, Any]) -> dict[str, Any]:
    db = _get_db(request)
    manager = _get_manager(request)
    token = (body or {}).get("token", "")
    if not isinstance(token, str) or not token.strip():
        raise HTTPException(status_code=400, detail="Token requerido")
    token = token.strip()

    try:
        info = await manager.add_worker(token)
    except ManagerError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.detail)

    user_id = str(info.get("user_id") or info.get("id"))
    if not user_id or user_id == "None":
        raise HTTPException(status_code=502, detail="El worker no devolvió un usuario válido")

    await db.execute(
        """
        INSERT INTO video_workers (user_id, token, username, tag, avatar_url)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            token=excluded.token,
            username=excluded.username,
            tag=excluded.tag,
            avatar_url=excluded.avatar_url
        """,
        (
            user_id,
            token,
            info.get("username", ""),
            info.get("tag", ""),
            info.get("avatar_url", ""),
        ),
    )
    await db.commit()

    try:
        from src.web.routes.activity import push_event

        push_event(
            kind="videos",
            title=f"Worker agregado: {info.get('tag') or info.get('username') or user_id}",
            meta={"user_id": user_id},
        )
    except Exception:
        pass

    return {
        "user_id": user_id,
        "username": info.get("username", ""),
        "tag": info.get("tag", ""),
        "avatar_url": info.get("avatar_url", ""),
        "status": info.get("status", "idle"),
        "busy": bool(info.get("busy", False)),
        "token_preview": _token_preview(token),
    }


@router.delete("/workers/{worker_id}")
async def delete_worker(request: Request, worker_id: str) -> dict[str, Any]:
    db = _get_db(request)
    manager = _get_manager(request)
    # Quitar del manager (best-effort) y de la DB siempre.
    try:
        await manager.remove_worker(worker_id)
    except ManagerError as exc:
        if exc.status != 404:
            raise HTTPException(status_code=exc.status, detail=exc.detail)
    await db.execute("DELETE FROM video_workers WHERE user_id = ?", (str(worker_id),))
    await db.commit()
    return {"removed": str(worker_id)}


@router.post("/workers/{worker_id}/stop")
async def stop_worker(request: Request, worker_id: str) -> dict[str, Any]:
    manager = _get_manager(request)
    try:
        return await manager.stop_worker(worker_id)
    except ManagerError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.detail)


@router.get("/status")
async def status(request: Request) -> dict[str, Any]:
    manager = _get_manager(request)
    try:
        health = await manager.health()
        return {"online": True, **health}
    except ManagerError as exc:
        return {"online": False, "detail": exc.detail}


@router.post("/play")
async def play(request: Request, body: dict[str, Any]) -> dict[str, Any]:
    """Reproducción de prueba desde el dashboard (sin pasar por Discord)."""
    manager = _get_manager(request)
    video = (body or {}).get("video", "")
    guild_id = (body or {}).get("guild_id", "")
    channel_id = (body or {}).get("channel_id", "")
    worker_id = (body or {}).get("worker_id") or None
    if not video or not guild_id or not channel_id:
        raise HTTPException(status_code=400, detail="video, guild_id y channel_id requeridos")
    try:
        return await manager.play(
            guild_id=str(guild_id), channel_id=str(channel_id), video=video, worker_id=worker_id
        )
    except ManagerError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.detail)


@router.post("/stop")
async def stop(request: Request, body: dict[str, Any] | None = None) -> dict[str, Any]:
    manager = _get_manager(request)
    channel_id = (body or {}).get("channel_id") if body else None
    try:
        return await manager.stop(channel_id=channel_id)
    except ManagerError as exc:
        raise HTTPException(status_code=exc.status, detail=exc.detail)


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
        for channel in guild.voice_channels:
            channels.append({
                "id": str(channel.id),
                "name": channel.name,
                "guild_name": guild.name,
            })
    return {"channels": channels}
