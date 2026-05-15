from datetime import datetime
from typing import Any
from pydantic import BaseModel, field_serializer, field_validator


class YouTubeChannel(BaseModel):
    channel_id: str
    channel_name: str = ""
    added_at: datetime
    last_checked: datetime | None = None
    active: bool = True


class YouTubeVideo(BaseModel):
    video_id: str
    channel_id: str
    title: str
    url: str
    published_at: datetime
    notified: bool = False


class YouTubeSubscription(BaseModel):
    channel_id: str
    channel_name: str
    last_video_title: str | None = None
    last_video_url: str | None = None
    video_count: int = 0


class YouTubePluginConfig(BaseModel):
    enabled: bool = True
    # Discord IDs are 64-bit snowflakes that exceed JS Number.MAX_SAFE_INTEGER.
    # Internally stored as int; serialized as string on the JSON boundary so
    # the frontend never loses precision.
    discord_channel_id: int | None = None
    callback_url: str = ""  # public URL for PubSubHubbub callbacks
    google_api_key: str = ""  # YouTube Data API v3 key
    announcement_message: str = "@everyone ¡Hay un nuevo video en {canal}!"
    filter_shorts: bool = False
    filter_premieres: bool = False
    filter_min_duration: int = 0  # 0 = no filter, in seconds

    @field_validator("discord_channel_id", mode="before")
    @classmethod
    def _parse_discord_channel_id(cls, v: Any) -> int | None:
        if v is None:
            return None
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return None
            return int(v)
        return v

    @field_serializer("discord_channel_id")
    def _serialize_discord_channel_id(self, v: int | None) -> str | None:
        return str(v) if v is not None else None
