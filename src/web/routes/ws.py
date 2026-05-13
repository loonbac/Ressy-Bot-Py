from typing import Any, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.shared.models import WSMessage

router = APIRouter()

_active_connections: Set[WebSocket] = set()


def get_connected_count() -> int:
    return len(_active_connections)


async def broadcast(event: str, key: str, value: Any) -> None:
    message = WSMessage(event=event, key=key, value=value)
    disconnected: Set[WebSocket] = set()

    for ws in _active_connections:
        try:
            await ws.send_json(message.model_dump())
        except Exception:
            disconnected.add(ws)

    for ws in disconnected:
        _active_connections.discard(ws)


async def broadcast_config_change(key: str, value: Any) -> None:
    await broadcast("config:updated", key, value)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    _active_connections.add(websocket)
    try:
        while True:
            _ = await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        _active_connections.discard(websocket)
