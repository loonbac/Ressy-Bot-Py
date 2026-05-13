"""Pydantic config model for the Blackboard plugin."""

from pydantic import BaseModel


class BlackboardConfig(BaseModel):
    enabled: bool = True
    blackboard_url: str = "https://senati.blackboard.com"
    blackboard_user: str = ""
    blackboard_pass: str = ""
    discord_channel_id: int | None = None
    mention_role_id: int | None = None
    poll_interval_minutes: int = 60
    weekly_digest_day: int = 1  # 1=Monday
    timezone: str = "America/Lima"
    headless: bool = True
