from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    user_id: str = Field(..., description="Snowflake Discord serializado como string")
    channel_id: str | None = None
    message: str
    system_prompt: str | None = None


class ChatResponse(BaseModel):
    reply: str
    model: str
    conversation_id: str | None = None


class AnalyzeCodeRequest(BaseModel):
    code: str
    language: str
    stdout: str = ""
    stderr: str = ""


class AnalyzeCodeResponse(BaseModel):
    purpose: str
    improvements: list[str]


class ConfigPayload(BaseModel):
    enabled: bool | None = None
    chat_model: str | None = None
    analysis_model: str | None = None
    system_prompt: str | None = None
    max_context_messages: int | None = None
    rate_limit_seconds: int | None = None
