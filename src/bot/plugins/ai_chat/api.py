from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from .client import DEFAULT_ANALYSIS_MODEL, DEFAULT_CHAT_MODEL
from .models import AnalyzeCodeRequest, ChatRequest, ConfigPayload, MemoryCreate

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
        "max_context_messages": int(raw.get("max_context_messages", "60")),
        "rate_limit_seconds": int(raw.get("rate_limit_seconds", "8")),
        "context_token_budget": int(raw.get("context_token_budget", "200000")),
        "summary_enabled": raw.get("summary_enabled", "true") == "true",
        "summary_trigger_messages": int(raw.get("summary_trigger_messages", "40")),
        "memory_enabled": raw.get("memory_enabled", "true") == "true",
        "max_input_chars": int(raw.get("max_input_chars", "8000")),
        "tools_enabled": raw.get("tools_enabled", "true") == "true",
        "tools_search_scan_limit": int(raw.get("tools_search_scan_limit", "300")),
        "web_enabled": raw.get("web_enabled", "true") == "true",
        "web_max_chars": int(raw.get("web_max_chars", "8000")),
        "web_timeout_seconds": int(raw.get("web_timeout_seconds", "20")),
        # Búsqueda web (DuckDuckGo Lite) — REQ-SEARCH-10.
        # Tipos nativos para que el dashboard no tenga que castear strings.
        "search_enabled": raw.get("search_enabled", "true") == "true",
        "search_safe": raw.get("search_safe", "true") == "true",
        "search_max_per_hour": int(raw.get("search_max_per_hour", "10")),
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
        data["max_context_messages"] = max(1, min(500, int(data["max_context_messages"])))
    if "context_token_budget" in data:
        # Acota a la ventana de MiniMax-M3 (1M), con piso razonable.
        data["context_token_budget"] = max(1000, min(900_000, int(data["context_token_budget"])))
    if "summary_trigger_messages" in data:
        data["summary_trigger_messages"] = max(1, min(500, int(data["summary_trigger_messages"])))
    if "max_input_chars" in data:
        data["max_input_chars"] = max(100, min(100_000, int(data["max_input_chars"])))
    if "tools_search_scan_limit" in data:
        data["tools_search_scan_limit"] = max(50, min(2000, int(data["tools_search_scan_limit"])))
    if "web_max_chars" in data:
        data["web_max_chars"] = max(1000, min(20000, int(data["web_max_chars"])))
    if "web_timeout_seconds" in data:
        data["web_timeout_seconds"] = max(5, min(60, int(data["web_timeout_seconds"])))
    # REQ-SEARCH-10: la búsqueda web rechaza valores fuera de 1..100.
    # Se valida ANTES de cualquier clamp: el dashboard debe saber que el valor
    # es inválido en vez de recibir un silencio.
    if "search_max_per_hour" in data:
        value = int(data["search_max_per_hour"])
        if value < 1 or value > 100:
            raise HTTPException(
                status_code=422,
                detail="search_max_per_hour debe estar entre 1 y 100.",
            )
        data["search_max_per_hour"] = value
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
            payload.user_id, payload.channel_id or "api", payload.message, persist=True, user_name=payload.user_name
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


@router.get("/conversations/{user_id}/summary")
async def conversation_summary(request: Request, user_id: str, channel_id: str = "api") -> dict[str, Any]:
    summary = await _get_cog(request).db.get_summary(user_id, channel_id)
    return {"user_id": user_id, "channel_id": channel_id, "summary": summary}


def _resolve_owner(scope: str, owner_id: str | None) -> str:
    return "" if scope == "global" else str(owner_id or "")


@router.get("/memories")
async def list_memories(request: Request, scope: str = "user", owner_id: str | None = None) -> dict[str, Any]:
    if scope not in {"user", "global"}:
        raise HTTPException(status_code=422, detail="scope debe ser 'user' o 'global'")
    owner = _resolve_owner(scope, owner_id)
    if scope == "user" and not owner:
        raise HTTPException(status_code=422, detail="owner_id es obligatorio para scope 'user'")
    items = await _get_cog(request).db.list_memories(scope, owner)
    return {"memories": items, "count": len(items), "scope": scope, "owner_id": owner}


@router.post("/memories")
async def create_memory(request: Request, payload: MemoryCreate) -> dict[str, Any]:
    if payload.scope not in {"user", "global"}:
        raise HTTPException(status_code=422, detail="scope debe ser 'user' o 'global'")
    owner = _resolve_owner(payload.scope, payload.owner_id)
    if payload.scope == "user" and not owner:
        raise HTTPException(status_code=422, detail="owner_id es obligatorio para scope 'user'")
    added = await _get_cog(request).db.add_memory(payload.scope, owner, payload.content, source="manual")
    if not added:
        raise HTTPException(status_code=409, detail="Ese dato ya estaba guardado o está vacío.")
    return {"added": True, "scope": payload.scope, "owner_id": owner, "content": payload.content.strip()}


@router.delete("/memories/{memory_id}")
async def delete_memory(request: Request, memory_id: int) -> dict[str, Any]:
    deleted = await _get_cog(request).db.delete_memory(memory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memoria no encontrada")
    return {"deleted": True, "id": memory_id}
