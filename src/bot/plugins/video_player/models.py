"""Modelos Pydantic del plugin de reproducción de videos.

IDs Discord (snowflakes 64-bit) SIEMPRE como string en JSON — int pierde
precisión en JS. Los tokens de usuario NUNCA se devuelven completos al frontend.
"""

from __future__ import annotations

from pydantic import BaseModel


class VideoConfig(BaseModel):
    enabled: bool = True
    manager_url: str = "http://video-worker:8081"
    width: int = 1280
    height: int = 720
    fps: int = 30
    bitrate: int = 3000
    bitrate_max: int = 4500
    audio_offset: float = 0.3


class WorkerInfo(BaseModel):
    user_id: str  # snowflake string
    username: str = ""
    tag: str = ""
    avatar_url: str = ""
    status: str = "unknown"  # idle | playing | error | offline | unknown
    busy: bool = False
    token_preview: str = ""  # solo los últimos 4 chars, nunca el token completo


class AddWorkerRequest(BaseModel):
    token: str


class PlayRequest(BaseModel):
    video: str
    guild_id: str
    channel_id: str
    worker_id: str | None = None
