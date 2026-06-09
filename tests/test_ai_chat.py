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
from src.bot.plugins.ai_chat.conversations import ConversationStore, estimate_tokens
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
    # Con web_enabled por defecto, el cog usa el tool-loop (chat_completion).
    # El mensaje sin tool_calls hace que el loop devuelva content directo.
    client.chat_completion = AsyncMock(
        return_value={"role": "assistant", "content": "Respuesta de prueba"}
    )
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
async def test_mention_without_text_does_not_call_ai(ai_cog):
    """@ sin texto (solo mención, o mención + imagen sin pregunta) no debe
    invocar a la IA: responde pidiendo la petición y no gasta tokens."""
    author = SimpleNamespace(id=123, bot=False)
    channel = SimpleNamespace(id=456)
    message = SimpleNamespace(
        author=author,
        channel=channel,
        content="<@99>",
        mentions=[ai_cog.bot.user],
        reply=AsyncMock(),
    )

    await ai_cog.on_message(message)

    ai_cog.client.chat.assert_not_awaited()
    message.reply.assert_awaited_once()
    assert "pregunta" in message.reply.await_args.args[0].lower()


@pytest.mark.asyncio
async def test_analyze_code_execution(ai_cog):
    result = await ai_cog.analyze_code_execution("print(1+1)", "python", "2", "")
    assert result["purpose"] == "Suma"
    assert result["improvements"] == ["Validar entrada"]
    ai_cog.client.analyze_code_execution.assert_awaited_once()
    assert ai_cog.client.analyze_code_execution.await_args.args[4] == "MiniMax-M3"


@pytest.mark.asyncio
async def test_ai_chat_defaults_are_minimax_m3(ai_db):
    cfg = await ai_db.get_config()

    assert cfg["chat_model"] == "MiniMax-M3"
    assert cfg["analysis_model"] == "MiniMax-M3"
    assert "model" not in cfg


@pytest.mark.asyncio
async def test_ai_chat_drops_legacy_model_key_and_preserves_dashboard_selection(tmp_path):
    db = AIChatDatabase(str(tmp_path / "ai_chat.db"))
    await db.connect()
    # El dashboard selecciona el modelo vía PUT /config; esa es la fuente de verdad.
    await db.update_config({"chat_model": "MiniMax-M2.5"})
    await db._conn().execute(
        "INSERT OR REPLACE INTO ai_chat_config (key, value) VALUES ('model', 'algo-viejo')"
    )
    await db._conn().commit()
    await db.close()

    db = AIChatDatabase(str(tmp_path / "ai_chat.db"))
    await db.connect()
    cfg = await db.get_config()
    await db.close()

    # La key legacy `model` se borra, pero el modelo elegido NO se reescribe.
    assert "model" not in cfg
    assert cfg["chat_model"] == "MiniMax-M2.5"


@pytest.mark.asyncio
async def test_config_api_exposes_m3_defaults_and_memory_fields(ai_cog):
    app = FastAPI()
    app.state.ai_chat_cog = ai_cog
    app.include_router(router, prefix="/api/plugins/ai-chat")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/plugins/ai-chat/config")

    body = response.json()
    assert response.status_code == 200
    assert body["chat_model"] == "MiniMax-M3"
    assert body["analysis_model"] == "MiniMax-M3"
    assert body["summary_enabled"] is True
    assert body["memory_enabled"] is True
    assert body["context_token_budget"] == 200000
    assert "model" not in body


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


# ----- Memoria jerárquica (M3 1M de contexto) -----


@pytest.mark.asyncio
async def test_build_messages_injects_memory_summary_and_recent_window(ai_db):
    store = ConversationStore(ai_db)
    await ai_db.add_memory("global", "", "El servidor es de Korosoft Community.")
    await ai_db.add_memory("user", "u1", "Se llama Kevin y programa en Python.")
    await ai_db.set_summary("u1", "c1", "Hablaron antes sobre despliegues en Coolify.", last_summarized_id=10)
    await ai_db.add_message("u1", "c1", "user", "hola de nuevo")
    await ai_db.add_message("u1", "c1", "assistant", "hola Kevin")

    messages = await store.build_messages(
        user_id="u1",
        channel_id="c1",
        prompt="¿qué hacíamos?",
        system_prompt="Eres Ressy.",
        limit=60,
    )

    assert messages[0] == {"role": "system", "content": "Eres Ressy."}
    joined = "\n".join(m["content"] for m in messages)
    assert "Korosoft Community" in joined
    assert "Kevin" in joined
    assert "Coolify" in joined
    assert messages[-1] == {"role": "user", "content": "¿qué hacíamos?"}
    # El historial reciente verbatim sigue presente.
    assert any(m.get("content") == "hola de nuevo" for m in messages)


def test_fit_budget_keeps_most_recent_within_token_budget():
    history = [
        {"role": "user", "content": "a" * 400},      # ~100 tokens viejo
        {"role": "assistant", "content": "b" * 40},   # ~10 tokens
        {"role": "user", "content": "c" * 40},        # ~10 tokens reciente
    ]
    kept = ConversationStore._fit_budget(history, budget=40)
    # Entra solo lo más reciente; lo viejo y caro se descarta.
    assert [m["content"] for m in kept] == ["b" * 40, "c" * 40]


def test_estimate_tokens_is_roughly_chars_over_four():
    assert estimate_tokens("") == 0
    assert estimate_tokens("a" * 400) == 101


@pytest.mark.asyncio
async def test_maybe_summarize_folds_overflow_prunes_and_extracts_facts(ai_db):
    client = MagicMock(spec=AIChatClient)
    client.summarize_and_extract = AsyncMock(
        return_value={"summary": "Resumen acumulado.", "facts": ["Kevin usa fish shell."]}
    )
    store = ConversationStore(ai_db, client)
    for i in range(110):
        await ai_db.add_message("u1", "c1", "user", f"mensaje {i}")

    cfg = {
        "summary_enabled": "true",
        "memory_enabled": "true",
        "max_context_messages": "60",
        "summary_trigger_messages": "40",
        "analysis_model": "MiniMax-M3",
    }
    did = await store.maybe_summarize("u1", "c1", cfg)

    assert did is True
    client.summarize_and_extract.assert_awaited_once()
    # Quedan solo los 60 más recientes (los viejos se podaron).
    assert await ai_db.count_messages("u1", "c1") == 60
    assert await ai_db.get_summary("u1", "c1") == "Resumen acumulado."
    facts = await ai_db.list_memories("user", "u1")
    assert [f["content"] for f in facts] == ["Kevin usa fish shell."]


@pytest.mark.asyncio
async def test_maybe_summarize_does_not_prune_when_model_fails(ai_db):
    client = MagicMock(spec=AIChatClient)
    client.summarize_and_extract = AsyncMock(side_effect=RuntimeError("modelo caído"))
    store = ConversationStore(ai_db, client)
    for i in range(110):
        await ai_db.add_message("u1", "c1", "user", f"mensaje {i}")

    cfg = {"summary_enabled": "true", "max_context_messages": "60", "summary_trigger_messages": "40"}
    did = await store.maybe_summarize("u1", "c1", cfg)

    # Fail-safe: no resume y NO pierde mensajes.
    assert did is False
    assert await ai_db.count_messages("u1", "c1") == 110
    assert await ai_db.get_summary("u1", "c1") is None


@pytest.mark.asyncio
async def test_memory_dedup_and_reset_clears_summary(ai_db):
    assert await ai_db.add_memory("user", "u1", "dato") is True
    assert await ai_db.add_memory("user", "u1", "dato") is False  # dedup
    assert await ai_db.add_memory("user", "u1", "   ") is False    # vacío

    await ai_db.set_summary("u1", "c1", "algo", 5)
    await ai_db.add_message("u1", "c1", "user", "x")
    await ai_db.reset("u1", "c1")
    assert await ai_db.get_summary("u1", "c1") is None


@pytest.mark.asyncio
async def test_input_guard_truncates_long_message(ai_cog):
    # Path real con web_enabled por defecto: el prompt llega vía chat_completion.
    ai_cog.client.chat_completion = AsyncMock(return_value={"role": "assistant", "content": "ok"})
    await ai_cog.db.update_config({"max_input_chars": 50})
    huge = "x" * 5000
    await ai_cog.ask("u1", "c1", huge, persist=False)

    sent = ai_cog.client.chat_completion.await_args.args[0]
    user_msg = sent[-1]["content"]
    assert len(user_msg) == 50


def test_strip_bot_mention_handles_nickname_form():
    assert AIChatCog._strip_bot_mention("<@!99> hola", 99) == "hola"
    assert AIChatCog._strip_bot_mention("<@99> hola", 99) == "hola"


@pytest.mark.asyncio
async def test_memory_endpoints_create_list_delete(ai_cog):
    app = FastAPI()
    app.state.ai_chat_cog = ai_cog
    app.include_router(router, prefix="/api/plugins/ai-chat")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        created = await client.post(
            "/api/plugins/ai-chat/memories",
            json={"scope": "user", "owner_id": "u1", "content": "le gusta el café"},
        )
        assert created.status_code == 200

        dup = await client.post(
            "/api/plugins/ai-chat/memories",
            json={"scope": "user", "owner_id": "u1", "content": "le gusta el café"},
        )
        assert dup.status_code == 409

        listed = await client.get("/api/plugins/ai-chat/memories", params={"scope": "user", "owner_id": "u1"})
        assert listed.status_code == 200
        items = listed.json()["memories"]
        assert len(items) == 1
        mem_id = items[0]["id"]

        deleted = await client.delete(f"/api/plugins/ai-chat/memories/{mem_id}")
        assert deleted.status_code == 200

        empty = await client.get("/api/plugins/ai-chat/memories", params={"scope": "user", "owner_id": "u1"})
        assert empty.json()["count"] == 0


@pytest.mark.asyncio
async def test_memory_endpoint_requires_owner_for_user_scope(ai_cog):
    app = FastAPI()
    app.state.ai_chat_cog = ai_cog
    app.include_router(router, prefix="/api/plugins/ai-chat")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/plugins/ai-chat/memories", json={"scope": "user", "content": "sin dueño"}
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_summarize_and_extract_parses_json_and_facts():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": '```json\n{"summary": "S", "facts": ["f1", "f2"]}\n```'}}
                ],
                "base_resp": {"status_code": 0},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = AIChatClient(api_key="sk-test", http_client=http_client)
        result = await client.summarize_and_extract("prev", [{"role": "user", "content": "hola"}], "MiniMax-M3")

    assert result["summary"] == "S"
    assert result["facts"] == ["f1", "f2"]


@pytest.mark.asyncio
async def test_summarize_and_extract_raises_on_bad_json():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "no soy json"}}], "base_resp": {"status_code": 0}},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = AIChatClient(api_key="sk-test", http_client=http_client)
        with pytest.raises(RuntimeError):
            await client.summarize_and_extract(None, [{"role": "user", "content": "hola"}], "MiniMax-M3")


@pytest.mark.asyncio
async def test_build_messages_injects_user_identity(ai_db):
    store = ConversationStore(ai_db)
    messages = await store.build_messages(
        user_id="123",
        channel_id="c1",
        prompt="¿quién soy?",
        system_prompt="Eres Ressy.",
        limit=60,
        user_name="Kevin",
    )
    joined = "\n".join(m["content"] for m in messages)
    assert "Kevin" in joined
    assert "123" in joined


@pytest.mark.asyncio
async def test_build_messages_identity_falls_back_to_id(ai_db):
    store = ConversationStore(ai_db)
    messages = await store.build_messages(
        user_id="555", channel_id="c1", prompt="hola", system_prompt="Eres Ressy.", limit=60
    )
    joined = "\n".join(m["content"] for m in messages)
    assert "555" in joined


@pytest.mark.asyncio
async def test_mention_handler_passes_display_name_to_ask(ai_cog):
    ai_cog.ask_full = AsyncMock(return_value=(None, "ok"))
    author = SimpleNamespace(id=123, bot=False, display_name="Kevin", name="kevin99")
    channel = SimpleNamespace(id=456)
    message = SimpleNamespace(
        author=author, channel=channel, content="<@99> hola", mentions=[ai_cog.bot.user], reply=AsyncMock()
    )

    await ai_cog.on_message(message)

    assert ai_cog.ask_full.await_args.kwargs["user_name"] == "Kevin"


# ----- Tools de lectura del servidor Discord -----

from datetime import datetime, timezone

from src.bot.plugins.ai_chat.tools import DiscordTools, run_tool_loop, TOOLS


def _msg(author_name, author_id, content, channel, jump="https://discord.com/x"):
    author = SimpleNamespace(id=author_id, name=author_name, display_name=author_name, global_name=author_name)
    return SimpleNamespace(
        author=author,
        channel=channel,
        content=content,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        jump_url=jump,
    )


def _channel(name, cid, msgs, can_read=True):
    ch = SimpleNamespace(id=cid, name=name, topic=None)

    async def _hist(limit=None, after=None):
        for m in msgs:
            yield m

    ch.history = lambda limit=None, after=None: _hist(limit=limit, after=after)
    ch.permissions_for = lambda me: SimpleNamespace(read_message_history=can_read)
    return ch


def _guild_bot_cm(guild_id=123):
    general = _channel("general", 1, [])
    chat = _channel("chat", 2, [])
    general_msgs = [
        _msg("Kevin", 555, "hola a todos", general),
        _msg("Ana", 777, "el deploy está listo", general),
    ]
    general.history = lambda limit=None, after=None: _aiter_list(general_msgs)
    kevin = SimpleNamespace(id=555, name="kevin99", display_name="Kevin", bot=False,
                            joined_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
                            roles=[SimpleNamespace(name="@everyone"), SimpleNamespace(name="Mod")])
    guild = SimpleNamespace(
        id=guild_id, name="Korosoft", text_channels=[general, chat], voice_channels=[],
        members=[kevin], me=SimpleNamespace(), member_count=2, owner=kevin,
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    bot = SimpleNamespace(get_guild=lambda gid: guild if gid == guild_id else None, guilds=[guild])
    cm = SimpleNamespace(get=lambda k, default=None: str(guild_id) if k == "guild_id" else default)
    return guild, bot, cm


def _aiter_list(items):
    async def _gen(limit=None, after=None):
        for i in items:
            yield i
    return _gen()


@pytest.mark.asyncio
async def test_tools_dispatch_errors_when_no_guild_selected():
    cm = SimpleNamespace(get=lambda k, default=None: "")  # sin guild
    tools = DiscordTools(SimpleNamespace(get_guild=lambda gid: None, guilds=[]), cm)
    result = await tools.dispatch("server_info", {})
    assert "error" in result


@pytest.mark.asyncio
async def test_search_messages_filters_by_query_and_author():
    _guild, bot, cm = _guild_bot_cm()
    tools = DiscordTools(bot, cm)
    result = await tools.dispatch("search_messages", {"query": "deploy", "author": "Ana"})
    assert result["count"] == 1
    assert result["matches"][0]["author"] == "Ana"
    assert result["matches"][0]["jump_url"] == "https://discord.com/x"

    none = await tools.dispatch("search_messages", {"query": "deploy", "author": "Kevin"})
    assert none["count"] == 0


@pytest.mark.asyncio
async def test_find_member_and_server_info_and_list_channels():
    _guild, bot, cm = _guild_bot_cm()
    tools = DiscordTools(bot, cm)

    member = await tools.dispatch("find_member", {"query": "Kevin"})
    assert member["found"] is True
    assert member["display_name"] == "Kevin"
    assert "Mod" in member["roles"] and "@everyone" not in member["roles"]

    info = await tools.dispatch("server_info", {})
    assert info["name"] == "Korosoft"
    assert info["text_channels"] == 2

    channels = await tools.dispatch("list_channels", {})
    assert channels["count"] == 2


@pytest.mark.asyncio
async def test_search_skips_unreadable_channels():
    secret = _channel("secreto", 9, [_msg("X", 1, "deploy aquí", None)], can_read=False)
    guild = SimpleNamespace(id=123, name="G", text_channels=[secret], voice_channels=[], members=[], me=SimpleNamespace())
    bot = SimpleNamespace(get_guild=lambda gid: guild, guilds=[guild])
    cm = SimpleNamespace(get=lambda k, default=None: "123" if k == "guild_id" else default)
    tools = DiscordTools(bot, cm)
    result = await tools.dispatch("search_messages", {"query": "deploy"})
    assert result["count"] == 0
    assert result["channels_searched"] == 0


@pytest.mark.asyncio
async def test_run_tool_loop_executes_tool_then_returns_final():
    _guild, bot, cm = _guild_bot_cm()
    tools = DiscordTools(bot, cm)

    responses = [
        {"role": "assistant", "content": None,
         "tool_calls": [{"id": "t1", "type": "function",
                         "function": {"name": "server_info", "arguments": "{}"}}]},
        {"role": "assistant", "content": "El server se llama Korosoft."},
    ]
    calls = []

    class FakeClient:
        async def chat_completion(self, messages, model, **kw):
            calls.append(kw)
            return responses.pop(0)

    out = await run_tool_loop(FakeClient(), [{"role": "user", "content": "info"}], "MiniMax-M3", tools)
    assert out == "El server se llama Korosoft."
    assert len(calls) == 2  # una con tool_call, otra final


@pytest.mark.asyncio
async def test_run_tool_loop_returns_content_without_tool_calls():
    class FakeClient:
        async def chat_completion(self, messages, model, **kw):
            return {"role": "assistant", "content": "respuesta directa"}

    _guild, bot, cm = _guild_bot_cm()
    out = await run_tool_loop(FakeClient(), [{"role": "user", "content": "hola"}], "MiniMax-M3", DiscordTools(bot, cm))
    assert out == "respuesta directa"


@pytest.mark.asyncio
async def test_chat_completion_parses_tool_calls():
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"role": "assistant", "content": None,
                                          "tool_calls": [{"id": "t1", "function": {"name": "list_channels", "arguments": "{}"}}]}}],
                "base_resp": {"status_code": 0},
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        client = AIChatClient(api_key="sk-test", http_client=http_client)
        message = await client.chat_completion([{"role": "user", "content": "x"}], "MiniMax-M3", tools=TOOLS)

    assert message["tool_calls"][0]["function"]["name"] == "list_channels"


@pytest.mark.asyncio
async def test_tools_config_defaults_exposed(ai_db):
    cfg = await ai_db.get_config()
    assert cfg["tools_enabled"] == "true"
    assert cfg["tools_search_scan_limit"] == "300"
