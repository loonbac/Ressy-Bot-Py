from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.bot.plugins.ai_chat.api import router
from src.bot.plugins.ai_chat.client import AIChatClient, MINIMAX_CHAT_COMPLETIONS_URL
from src.bot.plugins.ai_chat.cog import AIChatCog
from src.bot.plugins.ai_chat.database import AIChatDatabase


@pytest.fixture
async def ai_db(tmp_path):
    db = AIChatDatabase(str(tmp_path / "ai_chat.db"))
    await db.connect()
    yield db
    await db.close()


@pytest.fixture
async def ai_cog(ai_db):
    bot = MagicMock()
    bot.user = SimpleNamespace(id=99, mention="<@99>")
    client = MagicMock(spec=AIChatClient)
    client.chat = AsyncMock(return_value="Respuesta de prueba")
    client.analyze_code_execution = AsyncMock(return_value={"purpose": "Suma", "improvements": ["Validar entrada"]})
    return AIChatCog(bot, ai_db, client)


@pytest.mark.asyncio
async def test_rate_limit_ai_chat(ai_cog):
    ok, wait = await ai_cog._check_rate_limit(123)
    assert ok is True
    ok, wait = await ai_cog._check_rate_limit(123)
    assert ok is False
    assert wait > 0


@pytest.mark.asyncio
async def test_mention_handler(ai_cog):
    author = SimpleNamespace(id=123, bot=False)
    channel = SimpleNamespace(id=456)
    message = SimpleNamespace(
        author=author,
        channel=channel,
        content="<@99> hola",
        mentions=[ai_cog.bot.user],
        reply=AsyncMock(),
    )

    await ai_cog.on_message(message)

    message.reply.assert_awaited_once()
    assert "Respuesta de prueba" in message.reply.await_args.args[0]


@pytest.mark.asyncio
async def test_analyze_code_execution(ai_cog):
    result = await ai_cog.analyze_code_execution("print(1+1)", "python", "2", "")
    assert result["purpose"] == "Suma"
    assert result["improvements"] == ["Validar entrada"]
    ai_cog.client.analyze_code_execution.assert_awaited_once()
    assert ai_cog.client.analyze_code_execution.await_args.args[4] == "MiniMax-M2.7"


@pytest.mark.asyncio
async def test_ai_chat_defaults_are_minimax_models(ai_db):
    cfg = await ai_db.get_config()

    assert cfg["chat_model"] == "MiniMax-M2.5"
    assert cfg["analysis_model"] == "MiniMax-M2.7"
    assert "model" not in cfg


@pytest.mark.asyncio
async def test_ai_chat_migrates_legacy_default_model_to_minimax_names(tmp_path):
    db = AIChatDatabase(str(tmp_path / "ai_chat.db"))
    await db.connect()
    await db.update_config({"chat_model": "MiniMax-M2.5"})
    await db._conn().execute(
        "INSERT OR REPLACE INTO ai_chat_config (key, value) VALUES ('model', 'openai/gpt-4o-mini')"
    )
    await db._conn().commit()
    await db.close()

    db = AIChatDatabase(str(tmp_path / "ai_chat.db"))
    await db.connect()
    cfg = await db.get_config()
    await db.close()

    assert cfg["chat_model"] == "MiniMax-M2.5"
    assert cfg["analysis_model"] == "MiniMax-M2.7"
    assert "model" not in cfg


@pytest.mark.asyncio
async def test_config_api_uses_clear_minimax_model_names(ai_cog):
    app = FastAPI()
    app.state.ai_chat_cog = ai_cog
    app.include_router(router, prefix="/api/plugins/ai-chat")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/plugins/ai-chat/config")

    assert response.status_code == 200
    assert response.json()["chat_model"] == "MiniMax-M2.5"
    assert response.json()["analysis_model"] == "MiniMax-M2.7"
    assert "model" not in response.json()


@pytest.mark.asyncio
async def test_minimax_client_posts_openai_compatible_payload_and_parses_message():
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers.get("Authorization")
        captured["content_type"] = request.headers.get("Content-Type")
        captured["payload"] = json.loads(request.content.decode())
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "Respuesta MiniMax", "role": "assistant"}}],
                "base_resp": {"status_code": 0, "status_msg": ""},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = AIChatClient(api_key="sk-test", http_client=http_client)
        reply = await client.chat(
            [{"role": "user", "content": "hola"}],
            "MiniMax-M2.5",
            temperature=0.3,
            max_completion_tokens=128,
        )

    assert reply == "Respuesta MiniMax"
    assert captured["url"] == MINIMAX_CHAT_COMPLETIONS_URL
    assert captured["authorization"] == "Bearer sk-test"
    assert captured["content_type"] == "application/json"
    assert captured["payload"] == {
        "model": "MiniMax-M2.5",
        "messages": [{"role": "user", "content": "hola"}],
        "temperature": 0.3,
        "max_completion_tokens": 128,
    }


@pytest.mark.asyncio
async def test_minimax_client_prefers_global_config_api_key(monkeypatch):
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers.get("Authorization")
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "ok", "role": "assistant"}}], "base_resp": {"status_code": 0}},
        )

    config_manager = SimpleNamespace(get=lambda key, default=None: "sk-global" if key == "minimax_api_key" else default)
    monkeypatch.setenv("MINIMAX_API_KEY", "sk-env")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = AIChatClient(config_manager=config_manager, http_client=http_client)
        reply = await client.chat([{"role": "user", "content": "hola"}], "MiniMax-M2.5")

    assert reply == "ok"
    assert captured["authorization"] == "Bearer sk-global"


@pytest.mark.asyncio
async def test_minimax_client_falls_back_to_env_when_global_config_empty(monkeypatch):
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers.get("Authorization")
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "ok", "role": "assistant"}}], "base_resp": {"status_code": 0}},
        )

    config_manager = SimpleNamespace(get=lambda key, default=None: "" if key == "minimax_api_key" else default)
    monkeypatch.setenv("MINIMAX_API_KEY", "sk-env")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = AIChatClient(config_manager=config_manager, http_client=http_client)
        await client.chat([{"role": "user", "content": "hola"}], "MiniMax-M2.5")

    assert captured["authorization"] == "Bearer sk-env"


@pytest.mark.asyncio
async def test_minimax_client_reports_base_resp_errors():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"base_resp": {"status_code": 1008, "status_msg": "modelo inválido"}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = AIChatClient(api_key="sk-test", http_client=http_client)
        with pytest.raises(RuntimeError, match="MiniMax rechazó la solicitud: modelo inválido"):
            await client.chat([{"role": "user", "content": "hola"}], "MiniMax-M2.5")


@pytest.mark.asyncio
async def test_minimax_client_reports_auth_and_rate_limit_errors():
    statuses = iter([401, 429, 503])

    async def handler(request: httpx.Request) -> httpx.Response:
        status = next(statuses)
        return httpx.Response(status, json={"error": {"message": "detalle externo"}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = AIChatClient(api_key="sk-test", http_client=http_client)
        with pytest.raises(RuntimeError, match="credenciales de MiniMax"):
            await client.chat([{"role": "user", "content": "hola"}], "MiniMax-M2.5")
        with pytest.raises(RuntimeError, match="límite de uso"):
            await client.chat([{"role": "user", "content": "hola"}], "MiniMax-M2.5")
        with pytest.raises(RuntimeError, match="servicio de MiniMax no está disponible"):
            await client.chat([{"role": "user", "content": "hola"}], "MiniMax-M2.5")


@pytest.mark.asyncio
async def test_chat_api_rate_limit(ai_cog):
    app = FastAPI()
    app.state.ai_chat_cog = ai_cog
    app.include_router(router, prefix="/api/plugins/ai-chat")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {"user_id": "123", "channel_id": "456", "message": "hola"}
        first = await client.post("/api/plugins/ai-chat/chat", json=payload)
        second = await client.post("/api/plugins/ai-chat/chat", json=payload)

    assert first.status_code == 200
    assert second.status_code == 429
