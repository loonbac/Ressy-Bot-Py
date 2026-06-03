from __future__ import annotations

import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.bot.plugins.code_runner.cog import CodeRunnerCog
from src.bot.plugins.code_runner.database import CodeRunnerDatabase
from src.bot.plugins.code_runner.exporter import export_transcript
from src.bot.plugins.code_runner.piston import PistonClient, PistonRateLimitError
from src.bot.plugins.code_runner.security import analyze_security_with_ai, structured_security_analysis
from src.bot.plugins.code_runner.events import broadcast, connect, disconnect
from src.bot.plugins.code_runner.session import SessionManager, sanitize_channel_name


class MockDiscordObject:
    def __init__(self, id: int, name: str) -> None:
        self.id = id
        self.name = name


@pytest.fixture
async def runner_db(tmp_path):
    db = CodeRunnerDatabase(str(tmp_path / "code_runner.db"))
    await db.connect()
    yield db
    await db.close()


@pytest.fixture
async def runner_cog(runner_db):
    bot = MagicMock()
    bot.add_view = MagicMock()
    piston = MagicMock()
    piston.execute = AsyncMock(return_value={"stdout": "hola\n", "stderr": "", "code": "0"})
    ai_chat = MagicMock()
    ai_chat.analyze_code_execution = AsyncMock(return_value={"purpose": "Imprime saludo", "improvements": []})
    ai_chat.analyze_code_security = AsyncMock(return_value={"malicious": False, "severity": "low", "reasons": []})
    return CodeRunnerCog(bot, runner_db, piston, ai_chat)


@pytest.mark.asyncio
async def test_session_create_flow(runner_db):
    bot = MagicMock()
    manager = SessionManager(bot, runner_db)
    channel = SimpleNamespace(id=333, delete=AsyncMock())
    guild = SimpleNamespace(id=111, default_role=object(), create_text_channel=AsyncMock(return_value=channel))
    user = SimpleNamespace(id=222, name="loon")

    created = await manager.create_session(guild, user)
    repeated = await manager.create_session(guild, user)

    assert created["created"] is True
    assert str(created["session"]["channel_id"]) == "333"
    assert repeated["created"] is False
    guild.create_text_channel.assert_awaited_once()
    channel_name = guild.create_text_channel.await_args.kwargs["name"]
    assert channel_name.startswith("code-loon-")
    assert channel_name == channel_name.lower()


@pytest.mark.asyncio
async def test_security_block_flow(runner_cog):
    result = await runner_cog.execute_code("1", "2", None, "rm -rf /", "bash")
    assert result["status"] == "blocked"
    assert "bloqueado" in result["stderr"]
    assert result["security"]["severity"] == "critical"
    infraction = await runner_cog.db.infraction_for_user("1")
    assert infraction["count"] == 1


@pytest.mark.asyncio
async def test_security_ai_fail_closed_after_two_bad_parses(runner_cog):
    runner_cog.ai_chat.analyze_code_security = AsyncMock(return_value="no es json")
    result = await runner_cog.execute_code("1", "2", None, "print('hola')", "python")
    assert result["status"] == "blocked"
    assert "fail-closed" in result["stderr"]
    assert runner_cog.ai_chat.analyze_code_security.await_count == 2


@pytest.mark.asyncio
async def test_security_medium_allows_with_warning(runner_cog):
    runner_cog.ai_chat.analyze_code_security = AsyncMock(return_value={"malicious": False, "severity": "medium", "reasons": ["Usa red externa"]})
    result = await runner_cog.execute_code("1", "2", None, "print('hola')", "python")
    assert result["status"] == "success"
    assert result["warnings"] == ["Usa red externa"]


@pytest.mark.asyncio
async def test_exec_success(runner_cog):
    result = await runner_cog.execute_code("1", "2", None, "print('hola')", "python")
    assert result["status"] == "success"
    assert result["stdout"] == "hola\n"
    assert result["analysis"]["purpose"] == "Imprime saludo"
    rows = await runner_cog.db._conn().execute_fetchall("SELECT warnings_json, security_json, analysis_json FROM executions")
    assert rows[0]["security_json"]


@pytest.mark.asyncio
async def test_language_and_output_limits(runner_cog):
    await runner_cog.db.update_config({"allowed_languages": ["python"], "max_output_chars": 4})
    blocked = await runner_cog.execute_code("1", "2", None, "console.log(1)", "javascript")
    assert blocked["status"] == "blocked"
    runner_cog.piston.execute = AsyncMock(return_value={"stdout": "123456", "stderr": "", "code": "0"})
    result = await runner_cog.execute_code("1", "2", None, "print(123456)", "python")
    assert result["stdout"] == "1234"
    assert "recortada" in result["warnings"][-1]


@pytest.mark.asyncio
async def test_exec_timeout_or_rate_limited_does_not_persist_success(runner_cog):
    runner_cog.piston.execute = AsyncMock(side_effect=PistonRateLimitError("Piston 429"))
    result = await runner_cog.execute_code("1", "2", None, "print(1)", "python")
    rows = await runner_cog.db._conn().execute_fetchall("SELECT * FROM executions")
    assert result["status"] == "rate_limited"
    assert rows == []


@pytest.mark.asyncio
async def test_analyze_security_with_ai_local_block():
    ok, reason = await analyze_security_with_ai(None, "cat /etc/passwd", "bash")
    assert ok is False
    assert "bloqueado" in reason


@pytest.mark.asyncio
async def test_structured_security_analysis_parse_fenced_json():
    ai_chat = MagicMock()
    ai_chat.analyze_code_security = AsyncMock(return_value='```json\n{"malicious": false, "severity": "low", "reasons": []}\n```')
    analysis = await structured_security_analysis(ai_chat, "print(1)", "python", enabled=True, model="MiniMax-M2.7")
    assert analysis == {"malicious": False, "severity": "low", "reasons": []}


def test_sanitize_channel_name():
    assert sanitize_channel_name("Loon Bac!!!") == "loon-bac"


def test_sanitize_channel_name_safe_lowercase():
    assert sanitize_channel_name("Ñandú USER../$$$") == "and-user"


@pytest.mark.asyncio
async def test_transcript_generation(tmp_path):
    class HistoryChannel:
        id = 999

        async def history(self, limit=None, oldest_first=True):
            yield SimpleNamespace(author=SimpleNamespace(display_name="Ana"), content="```python\nprint(1)\n```")

    path = await export_transcript(HistoryChannel(), str(tmp_path))
    assert Path(path).exists()
    assert "print(1)" in Path(path).read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_mod_session_is_exempt_from_expiry(runner_db):
    # Sesión normal expirada → aparece en expired_sessions.
    await runner_db.create_session("1", "2", "333", ttl_minutes=1, exempt_expiry=False)
    # Sesión de moderador expirada → NO aparece (exempt_expiry = 1).
    await runner_db.create_session("9", "2", "444", ttl_minutes=1, exempt_expiry=True)
    past = int(time.time()) - 1
    await runner_db._conn().execute("UPDATE sessions SET expires_at = ?", (past,))
    await runner_db._conn().commit()

    expired = await runner_db.expired_sessions()

    channel_ids = {str(s["channel_id"]) for s in expired}
    assert channel_ids == {"333"}
    mod_session = await runner_db.session_by_channel("444")
    assert mod_session["exempt_expiry"] == 1


@pytest.mark.asyncio
async def test_create_session_flags_mod_role_as_exempt(runner_db):
    bot = MagicMock()
    manager = SessionManager(bot, runner_db)
    await runner_db.update_config({"mod_role_names": ["Moderador"]})
    channel = SimpleNamespace(id=555, delete=AsyncMock())
    mod_role = MockDiscordObject(2, "Moderador")
    guild = SimpleNamespace(id=111, default_role=object(), roles=[mod_role], create_text_channel=AsyncMock(return_value=channel))
    user = SimpleNamespace(id=222, name="mod", roles=[mod_role])

    await manager.create_session(guild, user)
    session = await runner_db.session_by_channel("555")

    assert session["exempt_expiry"] == 1


@pytest.mark.asyncio
async def test_chat_history_is_scoped_per_channel(runner_db):
    await runner_db.add_chat_message("100", "user", "hola")
    await runner_db.add_chat_message("100", "assistant", "qué tal")
    await runner_db.add_chat_message("200", "user", "otro canal")

    history_100 = await runner_db.recent_chat_messages("100", limit=12)
    history_200 = await runner_db.recent_chat_messages("200", limit=12)

    assert [m["content"] for m in history_100] == ["hola", "qué tal"]
    assert [m["content"] for m in history_200] == ["otro canal"]


@pytest.mark.asyncio
async def test_ai_chat_reply_includes_history_and_persists(runner_cog):
    captured: dict[str, Any] = {}

    async def fake_chat(messages, model):
        captured["messages"] = messages
        return "respuesta IA"

    runner_cog.ai_chat.client = SimpleNamespace(chat=fake_chat)
    await runner_cog.db.add_chat_message("777", "user", "pregunta vieja")
    await runner_cog.db.add_chat_message("777", "assistant", "respuesta vieja")

    reply = await runner_cog._ai_chat_reply("1", "777", "nueva pregunta")

    assert reply == "respuesta IA"
    roles = [m["role"] for m in captured["messages"]]
    contents = [m["content"] for m in captured["messages"]]
    assert roles[0] == "system"
    assert "pregunta vieja" in contents
    assert "respuesta vieja" in contents
    assert contents[-1] == "nueva pregunta"
    # El intercambio nuevo quedó persistido para el siguiente turno.
    history = await runner_cog.db.recent_chat_messages("777", limit=12)
    assert history[-2:] == [
        {"role": "user", "content": "nueva pregunta"},
        {"role": "assistant", "content": "respuesta IA"},
    ]


@pytest.mark.asyncio
async def test_close_session_purges_chat_history(runner_db):
    await runner_db.create_session("1", "2", "333", ttl_minutes=1)
    await runner_db.add_chat_message("333", "user", "hola")
    await runner_db.close_session("333", "")

    history = await runner_db.recent_chat_messages("333", limit=12)
    assert history == []


@pytest.mark.asyncio
async def test_reaper_loop_closes_only_db_channels(runner_db):
    await runner_db.create_session("1", "2", "333", ttl_minutes=1)
    await runner_db._conn().execute("UPDATE sessions SET expires_at = ? WHERE channel_id = '333'", (int(time.time()) - 1,))
    await runner_db._conn().commit()
    channel = SimpleNamespace(id=333, delete=AsyncMock())
    bot = MagicMock()
    bot.get_channel.return_value = channel
    bot.get_user.return_value = SimpleNamespace(send=AsyncMock())
    manager = SessionManager(bot, runner_db)

    count = await manager.reap_once()
    session = await runner_db.session_by_channel("333")

    assert count == 1
    assert session["status"] == "closed"
    channel.delete.assert_awaited_once()


@pytest.mark.asyncio
async def test_listing_stats_and_session_by_id(runner_db):
    session = await runner_db.create_session("123456789012345678", "2", "333", ttl_minutes=1)
    await runner_db.add_execution(session["id"], "123456789012345678", "python", "print(1)", "1", "", "success", security={"severity": "low"})
    sessions = await runner_db.list_sessions(status="active", limit=10)
    executions = await runner_db.list_executions(limit=10)
    stats = await runner_db.stats()
    assert str(sessions[0]["user_id"]) == "123456789012345678"
    assert executions[0]["status"] == "success"
    assert stats["executions_by_status"] == {"success": 1}
    assert stats["totals"]["executions_total"] == 1
    assert stats["most_used_language"] == "python"
    assert stats["top_users"][0]["user_id"] == "123456789012345678"


@pytest.mark.asyncio
async def test_session_by_id_includes_executions(runner_db):
    session = await runner_db.create_session("1", "2", "333", ttl_minutes=1)
    await runner_db.add_execution(session["id"], "1", "python", "print(1)", "1", "", "success")
    executions = await runner_db.list_executions_for_session(session["id"])
    assert len(executions) == 1
    assert executions[0]["session_id"] == session["id"]


@pytest.mark.asyncio
async def test_overwrites_include_creator_bot_and_mod_roles(runner_db):
    bot_user = MockDiscordObject(999, "Ressy")
    bot = SimpleNamespace(user=bot_user)
    manager = SessionManager(bot, runner_db)
    await runner_db.update_config({"mod_role_names": ["Moderador"]})
    channel = SimpleNamespace(id=333, delete=AsyncMock())
    default_role = MockDiscordObject(1, "@everyone")
    mod_role = MockDiscordObject(2, "Moderador")
    guild = SimpleNamespace(id=111, default_role=default_role, roles=[mod_role], create_text_channel=AsyncMock(return_value=channel))
    user = MockDiscordObject(222, "Loon Bac")

    await manager.create_session(guild, user)

    overwrites = guild.create_text_channel.await_args.kwargs["overwrites"]
    assert default_role in overwrites or "1" in overwrites
    assert user in overwrites or "222" in overwrites
    assert bot_user in overwrites or "999" in overwrites
    assert mod_role in overwrites or "2" in overwrites


@pytest.mark.asyncio
async def test_republish_lobby_sends_embed_with_stable_button_and_persists_message_id(runner_cog):
    await runner_cog.db.update_config({"trigger_channel_id": "444"})
    message = SimpleNamespace(id=555)
    channel = SimpleNamespace(id=444, send=AsyncMock(return_value=message))
    runner_cog.bot.get_channel.return_value = channel

    result = await runner_cog.republish_lobby()
    cfg = await runner_cog.db.get_config()

    assert result["published"] is True
    assert result["action"] == "created"
    assert result["message_id"] == "555"
    assert cfg["lobby_message_id"] == "555"
    assert result["custom_id"] == "code_runner:create_session"
    channel.send.assert_awaited_once()
    assert channel.send.await_args.kwargs["view"] is not None


@pytest.mark.asyncio
async def test_lobby_embed_shows_current_allowed_languages(runner_cog):
    await runner_cog.db.update_config({"allowed_languages": ["python", "bash"]})

    payload = await runner_cog._lobby_payload()
    embed = payload["embed"]

    assert embed is not None
    fields = {field.name: field.value for field in embed.fields}
    assert fields["🛠 Lenguajes soportados"] == "`🐍 python` `💻 bash`"


@pytest.mark.asyncio
async def test_republish_lobby_reuses_existing_message_when_edit_succeeds(runner_cog):
    await runner_cog.db.update_config({"trigger_channel_id": "444", "lobby_message_id": "555"})
    message = SimpleNamespace(id=555, edit=AsyncMock())
    channel = SimpleNamespace(id=444, send=AsyncMock(), fetch_message=AsyncMock(return_value=message))
    runner_cog.bot.get_channel.return_value = channel

    result = await runner_cog.republish_lobby()

    assert result["published"] is True
    assert result["action"] == "updated"
    assert result["message_id"] == "555"
    channel.fetch_message.assert_awaited_once_with(555)
    message.edit.assert_awaited_once()
    channel.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_republish_lobby_falls_back_to_new_message_when_existing_edit_fails(runner_cog):
    await runner_cog.db.update_config({"trigger_channel_id": "444", "lobby_message_id": "555"})
    replacement = SimpleNamespace(id=777)
    channel = SimpleNamespace(
        id=444,
        fetch_message=AsyncMock(side_effect=RuntimeError("mensaje no disponible")),
        send=AsyncMock(return_value=replacement),
    )
    runner_cog.bot.get_channel.return_value = channel

    result = await runner_cog.republish_lobby()
    cfg = await runner_cog.db.get_config()

    assert result["published"] is True
    assert result["action"] == "created"
    assert result["message_id"] == "777"
    assert cfg["lobby_message_id"] == "777"
    channel.fetch_message.assert_awaited_once_with(555)
    channel.send.assert_awaited_once()


@pytest.mark.asyncio
async def test_infraction_extends_cooldown_after_max(runner_db):
    first = await runner_db.record_infraction("1", "bloqueado", max_infractions=2, base_cooldown_seconds=10)
    second = await runner_db.record_infraction("1", "bloqueado", max_infractions=2, base_cooldown_seconds=10)
    third = await runner_db.record_infraction("1", "bloqueado", max_infractions=2, base_cooldown_seconds=10)
    assert first["penalized"] is False
    assert second["penalized"] is True
    assert third["count"] == 3
    assert third["cooldown_until"] >= second["cooldown_until"]


@pytest.mark.asyncio
async def test_close_session_notifies_dm_and_stores_transcript(runner_db):
    session = await runner_db.create_session("1", "2", "333", ttl_minutes=1)
    await runner_db.add_execution(session["id"], "1", "python", "print(1)", "1", "", "success")
    await runner_db.add_execution(session["id"], "1", "javascript", "console.log(2)", "2", "", "success")
    sent = AsyncMock()
    bot = MagicMock()
    bot.get_user.return_value = SimpleNamespace(send=sent)
    manager = SessionManager(bot, runner_db)
    channel = SimpleNamespace(id=333, delete=AsyncMock())

    closed = await manager.close_session_channel(channel, reason="manual")
    session = await runner_db.session_by_channel("333")

    assert closed is True
    assert session["transcript_path"]
    sent.assert_awaited_once()
    message = sent.await_args.args[0]
    assert "Tu sesión de Code Runner fue archivada" in message
    assert "Motivo: manual" in message
    assert "Ejecuciones registradas: 2" in message
    assert "Lenguajes usados: javascript, python" in message
    assert session["transcript_path"] in message


@pytest.mark.asyncio
async def test_code_runner_websocket_broadcast_basic_event():
    websocket = MagicMock()
    websocket.accept = AsyncMock()
    websocket.send_json = AsyncMock()
    await connect(websocket)
    await broadcast("session_created", {"session_id": 1})
    disconnect(websocket)
    websocket.accept.assert_awaited_once()
    websocket.send_json.assert_awaited_once_with({"event": "session_created", "payload": {"session_id": 1}})


@pytest.mark.parametrize(
    "given,expected",
    [
        ("http://piston:2000", "http://piston:2000/api/v2"),
        ("http://piston:2000/", "http://piston:2000/api/v2"),
        ("http://piston:2000/api/v2", "http://piston:2000/api/v2"),
        ("http://piston:2000/api/v2/", "http://piston:2000/api/v2"),
        ("https://emkc.org/api/v2/piston", "https://emkc.org/api/v2/piston"),
    ],
)
def test_piston_client_normalizes_base_url(given, expected):
    assert PistonClient(given).base_url == expected
