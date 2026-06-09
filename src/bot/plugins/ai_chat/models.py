from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    user_id: str = Field(..., description="Snowflake Discord serializado como string")
    channel_id: str | None = None
    message: str
    system_prompt: str | None = None
    user_name: str | None = Field(None, description="Nombre visible del usuario para que la IA sepa con quién habla")


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
    context_token_budget: int | None = None
    summary_enabled: bool | None = None
    summary_trigger_messages: int | None = None
    memory_enabled: bool | None = None
    max_input_chars: int | None = None
    tools_enabled: bool | None = None
    tools_search_scan_limit: int | None = None
    web_enabled: bool | None = None
    web_max_chars: int | None = None
    web_timeout_seconds: int | None = None


class MemoryCreate(BaseModel):
    content: str = Field(..., description="Hecho duradero a recordar")
    scope: str = Field("user", description="'user' o 'global'")
    owner_id: str | None = Field(None, description="user_id para scope user; vacío para global")
