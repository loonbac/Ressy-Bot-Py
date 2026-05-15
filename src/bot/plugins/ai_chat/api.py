from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from .client import DEFAULT_ANALYSIS_MODEL, DEFAULT_CHAT_MODEL
from .models import AnalyzeCodeRequest, ChatRequest, ConfigPayload

router = APIRouter()


def _get_cog(request: Request):
    cog = getattr(request.app.state, "ai_chat_cog", None)
    if cog is None:
        raise HTTPException(status_code=503, detail="AI Chat no inicializado")
    return cog


def _typed_config(raw: dict[str, str]) -> dict[str, Any]:
    return {
        "enabled": raw.get("enabled", "true") == "true",
        "chat_model": raw.get("chat_model", DEFAULT_CHAT_MODEL),
        "analysis_model": raw.get("analysis_model", DEFAULT_ANALYSIS_MODEL),
        "system_prompt": raw.get("system_prompt", ""),
        "max_context_messages": int(raw.get("max_context_messages", "12")),
        "rate_limit_seconds": int(raw.get("rate_limit_seconds", "8")),
    }


@router.get("/config")
async def get_config(request: Request) -> dict[str, Any]:
    return _typed_config(await _get_cog(request).db.get_config())


@router.put("/config")
async def update_config(request: Request, payload: ConfigPayload) -> dict[str, Any]:
    data = payload.model_dump(exclude_none=True)
    if "rate_limit_seconds" in data:
        data["rate_limit_seconds"] = max(1, int(data["rate_limit_seconds"]))
    if "max_context_messages" in data:
        data["max_context_messages"] = max(1, min(50, int(data["max_context_messages"])))
    return _typed_config(await _get_cog(request).db.update_config(data))


@router.get("/status")
async def status(request: Request) -> dict[str, Any]:
    cfg = await _get_cog(request).db.get_config()
    return {"enabled": cfg.get("enabled") == "true", "chat_model": cfg.get("chat_model"), "ready": True}


@router.get("/models")
async def list_models(request: Request) -> dict[str, Any]:
    cog = _get_cog(request)
    models = await cog.client.list_models()
    return {"models": models, "count": len(models)}


@router.post("/chat")
async def chat(request: Request, payload: ChatRequest) -> dict[str, Any]:
    cog = _get_cog(request)
    ok, wait = await cog._check_rate_limit(payload.user_id)
    if not ok:
        raise HTTPException(status_code=429, detail=f"Rate limit activo. Intenta nuevamente en {wait}s.")
    try:
        thinking, reply = await cog.ask_full(
            payload.user_id, payload.channel_id or "api", payload.message, persist=True
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    cfg = await cog.db.get_config()
    return {
        "reply": reply,
        "thinking": thinking,
        "chat_model": cfg.get("chat_model"),
        "conversation_id": f"{payload.user_id}:{payload.channel_id or 'api'}",
    }


@router.post("/analyze-code")
async def analyze_code(request: Request, payload: AnalyzeCodeRequest) -> dict[str, Any]:
    return await _get_cog(request).analyze_code_execution(payload.code, payload.language, payload.stdout, payload.stderr)


@router.delete("/conversations/{user_id}")
async def reset_conversation(request: Request, user_id: str, channel_id: str | None = None) -> dict[str, Any]:
    # TODO: proteger este endpoint con auth admin cuando el dashboard tenga sesión real.
    deleted = await _get_cog(request).db.reset(user_id, channel_id)
    return {"deleted": deleted, "user_id": user_id, "channel_id": channel_id}
