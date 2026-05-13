from datetime import datetime
from pydantic import BaseModel


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
    poll_interval_minutes: int = 30  # reduce polling since PubSubHubbub is primary
    discord_channel_id: int | None = None
    callback_url: str = ""  # public URL for PubSubHubbub callbacks
    google_api_key: str = ""  # YouTube Data API v3 key
    announcement_message: str = "@everyone ¡Hay un nuevo video en {canal}!"
    filter_shorts: bool = False
    filter_premieres: bool = False
    filter_min_duration: int = 0  # 0 = no filter, in seconds
