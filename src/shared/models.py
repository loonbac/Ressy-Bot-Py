from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel


class ConfigUpdate(BaseModel):
    key: str
    value: Any


class ConfigResponse(BaseModel):
    key: str
    value: Any
    updated_at: datetime


class WSMessage(BaseModel):
    event: Literal["config:updated", "config:deleted"]
    key: str
    value: Any


class BotStatus(BaseModel):
    online: bool
    uptime_seconds: float
    loaded_cogs: list[str]
    connected_ws_clients: int
    latency_ms: float = 0.0
    memory_mb: float = 0.0
    bot_avatar_url: str = ""
    bot_name: str = ""
