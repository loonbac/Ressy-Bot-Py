from pydantic import BaseModel
from typing import Optional


class MusicConfig(BaseModel):
    enabled: bool = True
    default_volume: int = 50  # Range 1-200


class TrackInfo(BaseModel):
    title: str
    url: str
    requester_id: str  # Snowflake as string
    requester_name: str
    duration_seconds: int = 0
    thumbnail_url: str = ""


class QueueInfo(BaseModel):
    guild_id: str  # Snowflake as string
    tracks: list[TrackInfo]
    current_track: Optional[TrackInfo] = None
    total_duration_seconds: int = 0
    volume: int = 50
