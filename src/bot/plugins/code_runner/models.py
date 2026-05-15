from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ExecuteRequest(BaseModel):
    user_id: str = Field(..., description="Snowflake Discord como string")
    guild_id: str
    channel_id: str | None = None
    code: str
    language: str = "python"


class ExecuteResponse(BaseModel):
    status: str
    stdout: str = ""
    stderr: str = ""
    analysis: dict | None = None
    warnings: list[str] = []
    security: dict | None = None


class SessionCreateRequest(BaseModel):
    user_id: str
    guild_id: str
    parent_channel_id: str | None = None


class ConfigPayload(BaseModel):
    trigger_channel_id: str | None = None
    lobby_message_id: str | None = None
    enabled: bool | None = None
    allowed_languages: list[str] | None = None
    max_code_chars: int | None = None
    max_output_chars: int | None = None
    exec_timeout_seconds: int | None = None
    session_timeout_minutes: int | None = None
    cooldown_seconds: int | None = None
    max_infractions: int | None = None
    security_model: str | None = None
    security_enabled: bool | None = None
    mod_role_names: list[str] | None = None
    category_id: str | None = None

    # Compatibilidad con la versión simplificada anterior.
    session_ttl_minutes: int | None = None
    rate_limit_seconds: int | None = None
    piston_url: str | None = None


class SecurityAnalysis(BaseModel):
    malicious: bool = False
    severity: Literal["low", "medium", "high", "critical"] = "low"
    reasons: list[str] = Field(default_factory=list)
