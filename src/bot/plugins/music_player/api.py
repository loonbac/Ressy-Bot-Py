from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from src.web.routes.activity import push_event

router = APIRouter()

ALLOWED_KEYS = {"enabled", "default_volume"}
BOOL_KEYS = {"enabled"}
INT_KEYS = {"default_volume"}

VALID_ACTIONS = {"pause", "resume", "skip", "stop"}


def _get_db(request: Request):
    db = getattr(request.app.state, "music_db", None)
    if db is None:
        raise HTTPException(status_code=500, detail="Music player plugin no inicializado")
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


def _push_activity(kind: str, title: str, detail: str = "", meta: dict[str, Any] | None = None) -> None:
    try:
        push_event(kind=kind, title=title, detail=detail, meta=meta or {})
    except Exception:
        pass


def _track_to_dict(track: Any) -> dict[str, Any]:
    """Convert a Track dataclass or TrackInfo to a plain dict."""
    return {
        "title": getattr(track, "title", ""),
        "url": getattr(track, "url", ""),
        "requester_id": getattr(track, "requester_id", ""),
        "requester_name": getattr(track, "requester_name", ""),
        "duration_seconds": getattr(track, "duration_seconds", 0),
        "thumbnail_url": getattr(track, "thumbnail_url", ""),
    }


@router.get("/config")
async def get_config(request: Request) -> dict[str, Any]:
    db = _get_db(request)
    rows = await db.execute_fetchall("SELECT key, value FROM music_config")
    return _serialize_config(list(rows))


@router.put("/config")
async def update_config(request: Request, body: dict[str, Any]) -> dict[str, Any]:
    db = _get_db(request)
    for key, value in body.items():
        if key not in ALLOWED_KEYS:
            continue
        if key == "default_volume":
            try:
                value = max(1, min(200, int(value)))
            except (TypeError, ValueError):
                value = 50
        await db.execute(
            "INSERT OR REPLACE INTO music_config (key, value) VALUES (?, ?)",
            (key, _normalize(value)),
        )
    await db.commit()
    rows = await db.execute_fetchall("SELECT key, value FROM music_config")
    return _serialize_config(list(rows))


@router.get("/queue")
async def get_queue(
    request: Request,
    guild_id: str = Query(...),
) -> dict[str, Any]:
    manager = getattr(request.app.state, "music_player_manager", None)
    if manager is None:
        return {
            "guild_id": guild_id,
            "tracks": [],
            "current_track": None,
            "length": 0,
            "total_duration_seconds": 0,
            "volume": 50,
        }

    try:
        guild_id_int = int(guild_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="guild_id invalido")

    player = manager.get(guild_id_int)
    if player is None:
        return {
            "guild_id": guild_id,
            "tracks": [],
            "current_track": None,
            "length": 0,
            "total_duration_seconds": 0,
            "volume": 50,
        }

    tracks = [_track_to_dict(t) for t in player.queue.upcoming]
    current = _track_to_dict(player.queue.current) if player.queue.current else None

    return {
        "guild_id": guild_id,
        "tracks": tracks,
        "current_track": current,
        "length": len(tracks),
        "total_duration_seconds": player.queue.total_duration,
        "volume": player.volume,
    }


@router.get("/nowplaying")
async def get_nowplaying(
    request: Request,
    guild_id: str = Query(...),
) -> dict[str, Any]:
    manager = getattr(request.app.state, "music_player_manager", None)
    if manager is None:
        return {
            "current_track": None,
            "is_playing": False,
            "is_paused": False,
            "volume": 50,
        }

    try:
        guild_id_int = int(guild_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="guild_id invalido")

    player = manager.get(guild_id_int)
    if player is None:
        return {
            "current_track": None,
            "is_playing": False,
            "is_paused": False,
            "volume": 50,
        }

    current = None
    if player.current_track is not None:
        try:
            current = player.current_track.model_dump()
        except AttributeError:
            current = _track_to_dict(player.current_track)

    return {
        "current_track": current,
        "is_playing": player.is_playing,
        "is_paused": player.is_paused,
        "volume": player.volume,
    }


@router.post("/control/{action}")
async def post_control(
    request: Request,
    action: str,
    body: dict[str, Any],
) -> dict[str, Any]:
    if action not in VALID_ACTIONS:
        raise HTTPException(status_code=400, detail=f"Accion invalida: {action}")

    guild_id_raw = body.get("guild_id")
    if not guild_id_raw:
        raise HTTPException(status_code=400, detail="guild_id es requerido")

    try:
        guild_id = int(guild_id_raw)
    except ValueError:
        raise HTTPException(status_code=400, detail="guild_id invalido")

    manager = getattr(request.app.state, "music_player_manager", None)
    if manager is None:
        raise HTTPException(status_code=503, detail="Music player no disponible")

    player = manager.get(guild_id)
    if player is None:
        raise HTTPException(status_code=404, detail="No hay reproductor activo para este servidor")

    if action == "pause":
        player.pause()
    elif action == "resume":
        player.resume()
    elif action == "skip":
        player.skip()
        _push_activity(
            kind="music",
            title="Cancion saltada",
            detail=f"Saltada en servidor {guild_id}",
            meta={"guild_id": str(guild_id), "action": "skip"},
        )
    elif action == "stop":
        await player.stop()
        _push_activity(
            kind="music",
            title="Reproduccion detenida",
            detail=f"Detenida en servidor {guild_id}",
            meta={"guild_id": str(guild_id), "action": "stop"},
        )

    return {"ok": True, "action": action}


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
