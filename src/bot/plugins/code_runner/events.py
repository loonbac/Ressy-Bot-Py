from __future__ import annotations

import asyncio
from typing import Any

from fastapi import WebSocket

from src.web.routes.activity import push_event


_connections: set[WebSocket] = set()


def connected_count() -> int:
    return len(_connections)


async def connect(websocket: WebSocket) -> None:
    await websocket.accept()
    _connections.add(websocket)


def disconnect(websocket: WebSocket) -> None:
    _connections.discard(websocket)


async def broadcast(event: str, payload: dict[str, Any]) -> None:
    message = {"event": event, "payload": payload}
    disconnected: set[WebSocket] = set()
    for websocket in list(_connections):
        try:
            await websocket.send_json(message)
        except Exception:
            disconnected.add(websocket)
    for websocket in disconnected:
        _connections.discard(websocket)


def emit_event(event: str, title: str, *, detail: str = "", meta: dict[str, Any] | None = None) -> None:
    """Emit an activity event and best-effort websocket broadcast.

    This helper deliberately never raises: code execution/session cleanup must not
    fail because a dashboard websocket disappeared.
    """
    payload = meta or {}
    push_event("code_runner", title, detail=detail, meta={"event": event, **payload})
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(broadcast(event, {"title": title, "detail": detail, **payload}))
    except RuntimeError:
        pass
