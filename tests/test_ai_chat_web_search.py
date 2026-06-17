"""Tests para el slice de búsqueda web (`web_search`) del plugin `ai_chat`.

Estrategia: TDD estricto. Cada bloque de tests cubre una fase del plan en
`openspec/changes/ai-web-search/tasks.md`. La convención `fase_<n>_<m>` en
el nombre del test permite filtrar con `-k` por scope.

Restricciones duras:
- Sin browser: ningún test debe lanzar Firefox/Chromium/Playwright.
- Sin red: la cuota, el parser y el dispatch usan httpx mockeado o
  `WebSearchQuota` inyectado. La única excepción serían los tests
  `@pytest.mark.live` (PR 2).
- `asyncio_mode = "auto"` ya está en `pyproject.toml`; no se usa
  `@pytest.mark.asyncio` explícito.

Convenio de organización: las funciones que importan símbolos aún no
implementados (Phases 2–6) lo hacen localmente. Así la suite puede
coleccionarse y los RED de las primeras fases pueden correr sin que las
siguientes rompan la colección.
"""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from src.bot.plugins.ai_chat import web
from src.bot.plugins.ai_chat.cog import AIChatCog
from src.bot.plugins.ai_chat.database import AIChatDatabase
from src.bot.plugins.ai_chat.tools import run_tool_loop
from src.bot.plugins.ai_chat.web import WEB_TOOL_NAMES, WEB_TOOLS, dispatch_web_tool


# ---------------------------------------------------------------------------
# Phase 1 — Config seeding (DEFAULTS)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fase_1_seeding_inserta_search_defaults_en_db_fresca(tmp_path: Path):
    db = AIChatDatabase(str(tmp_path / "ai_chat.db"))
    await db.connect()
    try:
        cfg = await db.get_config()
    finally:
        await db.close()

    assert cfg["search_enabled"] == "true"
    assert cfg["search_safe"] == "true"
    assert cfg["search_max_per_hour"] == "10"


@pytest.mark.asyncio
async def test_fase_1_seeding_no_pisa_search_safe_personalizado(tmp_path: Path):
    db = AIChatDatabase(str(tmp_path / "ai_chat.db"))
    await db.connect()
    # El admin personaliza search_safe = "false" (admin-only, REQ-SEARCH-05).
    await db.update_config({"search_safe": "false"})
    await db.close()

    # Reabrir y reconectar: el INSERT OR IGNORE debe respetar el valor custom.
    db2 = AIChatDatabase(str(tmp_path / "ai_chat.db"))
    await db2.connect()
    try:
        cfg = await db2.get_config()
    finally:
        await db2.close()

    assert cfg["search_safe"] == "false"
    # El resto de defaults sigue sembrado.
    assert cfg["search_enabled"] == "true"
    assert cfg["search_max_per_hour"] == "10"


# ---------------------------------------------------------------------------
# Phase 2 — WebSearchQuota
# ---------------------------------------------------------------------------


def test_fase_2_quota_permite_hasta_el_maximo_y_devuelve_remaining():
    from src.bot.plugins.ai_chat.web import WebSearchQuota

    clock = {"t": 1000.0}
    quota = WebSearchQuota(clock=lambda: clock["t"])
    assert quota.check_and_consume("u1", 2) == (True, 1)
    assert quota.check_and_consume("u1", 2) == (True, 0)


def test_fase_2_quota_rechaza_tercera_llamada_y_devuelve_retry_positivo():
    from src.bot.plugins.ai_chat.web import WebSearchQuota

    clock = {"t": 1000.0}
    quota = WebSearchQuota(clock=lambda: clock["t"])
    quota.check_and_consume("u1", 2)
    quota.check_and_consume("u1", 2)
    allowed, retry = quota.check_and_consume("u1", 2)
    assert allowed is False
    assert retry > 0
    # El retry debe ser <= window_seconds (3600s por defecto).
    assert retry <= 3600


def test_fase_2_quota_poda_eventos_pasada_la_ventana():
    from src.bot.plugins.ai_chat.web import WebSearchQuota

    clock = {"t": 1000.0}
    quota = WebSearchQuota(clock=lambda: clock["t"])
    quota.check_and_consume("u1", 1)  # consume el único slot
    # Avanzamos el reloj más allá de la ventana: la entrada vieja debe podarse.
    clock["t"] = 1000.0 + 3600.0 + 5
    allowed, remaining = quota.check_and_consume("u1", 1)
    assert allowed is True
    assert remaining == 0  # 1 - 1


def test_fase_2_quota_usuarios_independientes():
    from src.bot.plugins.ai_chat.web import WebSearchQuota

    clock = {"t": 1000.0}
    quota = WebSearchQuota(clock=lambda: clock["t"])
    quota.check_and_consume("u1", 1)
    # u1 está bloqueado…
    assert quota.check_and_consume("u1", 1)[0] is False
    # …pero u2 todavía tiene su slot completo.
    allowed, remaining = quota.check_and_consume("u2", 1)
    assert allowed is True
    assert remaining == 0


def test_fase_2_quota_max_per_hour_uno_rechaza_segunda_llamada_de_inmediato():
    from src.bot.plugins.ai_chat.web import WebSearchQuota

    clock = {"t": 1000.0}
    quota = WebSearchQuota(clock=lambda: clock["t"])
    assert quota.check_and_consume("u1", 1)[0] is True
    assert quota.check_and_consume("u1", 1)[0] is False


def test_fase_2_quota_poda_en_frontera_inclusiva_menor_o_igual():
    """El parser debe podar timestamps donde events[0] <= cutoff (inclusivo)."""
    from src.bot.plugins.ai_chat.web import WebSearchQuota

    clock = {"t": 1000.0}
    quota = WebSearchQuota(clock=lambda: clock["t"])
    quota.check_and_consume("u1", 1)  # evento en t=1000
    # Justo en el borde (now == events[0] + window): el evento se considera viejo.
    clock["t"] = 1000.0 + 3600.0
    allowed, _ = quota.check_and_consume("u1", 1)
    assert allowed is True


# ---------------------------------------------------------------------------
# Phase 3 — _parse_ddg_lite
# ---------------------------------------------------------------------------


def _fixture_path() -> Path:
    return Path(__file__).parent / "fixtures" / "ai_chat" / "ddg_lite_search.html"


def test_fase_3_parse_ddg_lite_devuelve_resultados_del_fixture():
    from src.bot.plugins.ai_chat.web import _parse_ddg_lite

    html = _fixture_path().read_text(encoding="utf-8")
    results = _parse_ddg_lite(html)
    assert len(results) >= 2


def test_fase_3_parse_ddg_lite_cada_resultado_tiene_title_url_snippet():
    from src.bot.plugins.ai_chat.web import _parse_ddg_lite

    html = _fixture_path().read_text(encoding="utf-8")
    results = _parse_ddg_lite(html)
    assert results  # no vacío
    for item in results:
        assert set(item.keys()) == {"title", "url", "snippet"}
        assert item["title"]
        assert item["url"]


def test_fase_3_parse_ddg_lite_decodifica_enlaces_envueltos_uddg_absoluto():
    from src.bot.plugins.ai_chat.web import _parse_ddg_lite

    html = _fixture_path().read_text(encoding="utf-8")
    results = _parse_ddg_lite(html)
    urls = {r["url"] for r in results}
    assert "https://kernel.org/" in urls


def test_fase_3_parse_ddg_lite_decodifica_enlaces_envueltos_uddg_relativo():
    from src.bot.plugins.ai_chat.web import _parse_ddg_lite

    html = _fixture_path().read_text(encoding="utf-8")
    results = _parse_ddg_lite(html)
    urls = {r["url"] for r in results}
    assert "https://www.phoronix.com/" in urls


def test_fase_3_parse_ddg_lite_acepta_enlaces_directos_http_s():
    from src.bot.plugins.ai_chat.web import _parse_ddg_lite

    html = _fixture_path().read_text(encoding="utf-8")
    results = _parse_ddg_lite(html)
    urls = {r["url"] for r in results}
    assert "https://lwn.net/Articles/950000/" in urls


def test_fase_3_parse_ddg_lite_no_filtra_html_crudo_ni_enlaces_duckduckgo_com():
    from src.bot.plugins.ai_chat.web import _parse_ddg_lite

    html = _fixture_path().read_text(encoding="utf-8")
    results = _parse_ddg_lite(html)
    for r in results:
        assert "duckduckgo.com" not in r["url"]
        assert "<" not in r["url"] and ">" not in r["url"]
        assert "<" not in r["title"] and ">" not in r["title"]


def test_fase_3_parse_ddg_lite_ignora_enlaces_internos_y_ads():
    from src.bot.plugins.ai_chat.web import _parse_ddg_lite

    html = _fixture_path().read_text(encoding="utf-8")
    results = _parse_ddg_lite(html)
    urls = {r["url"] for r in results}
    # El nav de DDG y los links de ads/footer no son resultados.
    for bad in ("/html/", "/images/", "/video/", "/about-our-ads", "/about", "/settings"):
        assert bad not in urls
    # El ad dentro de la fila sponsored no debe filtrarse como resultado.
    assert "https://ads.example/" not in urls


def test_fase_3_parse_ddg_lite_devuelve_lista_vacia_con_input_vacio_o_basura():
    from src.bot.plugins.ai_chat.web import _parse_ddg_lite

    assert _parse_ddg_lite("") == []
    assert _parse_ddg_lite("<<>>>???") == []
    # Sin hrefs no hay nada que extraer.
    assert _parse_ddg_lite("<html><body><p>sin enlaces</p></body></html>") == []


def test_fase_3_parse_ddg_lite_snippet_no_contiene_etiquetas_y_esta_acotado():
    from src.bot.plugins.ai_chat.web import _parse_ddg_lite

    # HTML con un anchor de resultado válido + un snippet gigante.
    huge = "palabra " * 1000
    html = (
        "<html><body><table class='result'>"
        "<tr><td class='result-link'><a href='https://kernel.org/'>Kernel</a></td></tr>"
        f"<tr><td class='result-snippet'>{huge}</td></tr>"
        "</table></body></html>"
    )
    results = _parse_ddg_lite(html)
    assert len(results) == 1
    assert results[0]["url"] == "https://kernel.org/"
    # Snippet acotado: <= 500 chars y sin HTML residual.
    assert len(results[0]["snippet"]) <= 500
    assert "<" not in results[0]["snippet"]


# ---------------------------------------------------------------------------
# Phase 4 — web_search (httpx + cuota)
# ---------------------------------------------------------------------------


def _make_quota(allowed_remaining: int = 5, retry: int = 0):
    """Quota falsa: consume siempre y devuelve el remaining/retry configurados."""

    class _FakeQuota:
        def check_and_consume(self, user_id: str, max_per_hour: int) -> tuple[bool, int]:
            del user_id, max_per_hour
            if allowed_remaining < 0:
                return (False, retry)
            return (True, allowed_remaining)

    return _FakeQuota()


@pytest.mark.asyncio
async def test_fase_4_web_search_query_vacia_devuelve_error_sin_http():
    from src.bot.plugins.ai_chat.web import web_search

    called = {"n": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        called["n"] += 1
        return httpx.Response(200, text="unused")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await web_search("   ", user_id="u1", quota=_make_quota(), client=client)

    assert "error" in result
    assert called["n"] == 0


@pytest.mark.asyncio
async def test_fase_4_web_search_cuota_agotada_devuelve_error_y_no_llama_http():
    from src.bot.plugins.ai_chat.web import web_search

    class _BlockedQuota:
        def check_and_consume(self, user_id: str, max_per_hour: int) -> tuple[bool, int]:
            return (False, 120)

    called = {"n": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        called["n"] += 1
        return httpx.Response(200, text="unused")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await web_search(
            "linux kernel", user_id="u1", quota=_BlockedQuota(), client=client
        )

    assert "error" in result
    # Mensaje en español neutro, mencionando el límite.
    assert "límite" in result["error"].lower() or "limite" in result["error"].lower()
    assert called["n"] == 0  # ninguna request salió


@pytest.mark.asyncio
async def test_fase_4_web_search_user_id_none_falla_cerrado_sin_http():
    from src.bot.plugins.ai_chat.web import web_search

    called = {"n": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        called["n"] += 1
        return httpx.Response(200, text="unused")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await web_search(
            "linux kernel", user_id=None, quota=_make_quota(), client=client
        )

    assert "error" in result
    assert "usuario" in result["error"].lower() or "identif" in result["error"].lower()
    assert called["n"] == 0


@pytest.mark.asyncio
async def test_fase_4_web_search_timeout_devuelve_error_sin_propagar():
    from src.bot.plugins.ai_chat.web import web_search

    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("boom")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await web_search(
            "linux kernel", user_id="u1", quota=_make_quota(), client=client
        )

    assert "error" in result
    assert "tiempo" in result["error"].lower() or "timeout" in result["error"].lower()


@pytest.mark.asyncio
async def test_fase_4_web_search_happy_path_devuelve_payload_estructurado():
    from src.bot.plugins.ai_chat.web import web_search

    captured: dict[str, object] = {}
    fixture = _fixture_path().read_text(encoding="utf-8")

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers.get("Authorization")
        return httpx.Response(200, text=fixture, headers={"content-type": "text/html"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await web_search(
            "linux kernel 6.8",
            user_id="u1",
            max_per_hour=5,
            safe=True,
            quota=_make_quota(),
            client=client,
        )

    assert "error" not in result
    assert result["query"] == "linux kernel 6.8"
    assert result["safe"] is True
    assert isinstance(result["results"], list)
    assert result["count"] == len(result["results"])
    assert result["source"] == "duckduckgo_lite"
    assert result["fetched_with"] == "http"
    # No debe filtrarse HTML crudo al payload.
    for r in result["results"]:
        assert "<" not in r["title"] and "<" not in r["url"] and "<" not in r["snippet"]
    # Endpoint correcto y SIN Authorization.
    assert captured["url"].startswith("https://lite.duckduckgo.com/lite/")
    assert captured["authorization"] is None


@pytest.mark.asyncio
async def test_fase_4_web_search_envia_q_y_kp_segun_safe():
    from src.bot.plugins.ai_chat.web import web_search

    captured: list[httpx.Request] = []
    fixture = _fixture_path().read_text(encoding="utf-8")

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, text=fixture, headers={"content-type": "text/html"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await web_search("x", user_id="u1", safe=True, quota=_make_quota(), client=client)
        await web_search("x", user_id="u1", safe=False, quota=_make_quota(), client=client)

    assert len(captured) == 2
    safe_url = str(captured[0].url)
    unsafe_url = str(captured[1].url)
    assert "q=x" in safe_url
    assert "kp=1" in safe_url
    assert "kp=-1" in unsafe_url


@pytest.mark.asyncio
async def test_fase_4_web_search_503_devuelve_error_dict_sin_propagar():
    from src.bot.plugins.ai_chat.web import web_search

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="Service Unavailable")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await web_search(
            "x", user_id="u1", quota=_make_quota(), client=client
        )

    assert "error" in result
    assert "503" in result["error"] or "disponible" in result["error"].lower()


@pytest.mark.asyncio
async def test_fase_4_web_search_max_results_se_acota_a_diez():
    from src.bot.plugins.ai_chat.web import web_search

    fixture = _fixture_path().read_text(encoding="utf-8")

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=fixture, headers={"content-type": "text/html"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await web_search(
            "x", user_id="u1", max_results=20, quota=_make_quota(), client=client
        )

    assert "error" not in result
    assert len(result["results"]) <= 10


# ---------------------------------------------------------------------------
# Phase 5 — dispatch_web_tool + run_tool_loop signature threading
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fase_5_dispatch_rutea_web_search_y_forwardea_contexto(monkeypatch):
    captured: dict[str, object] = {}

    async def fake_web_search(query, **kwargs):
        captured["query"] = query
        captured.update(kwargs)
        return {"query": query, "results": [], "count": 0}

    monkeypatch.setattr(web, "web_search", fake_web_search)

    result = await dispatch_web_tool(
        "web_search",
        {"query": "linux"},
        user_id="u1",
        search_enabled=True,
        search_safe=False,
        search_max_per_hour=15,
    )

    assert "error" not in result
    calls = captured
    assert calls["query"] == "linux"
    assert calls["user_id"] == "u1"
    assert calls["safe"] is False  # viene de search_safe
    assert calls["max_per_hour"] == 15
    # max_results default 5 cuando el LLM no lo envía.
    assert calls["max_results"] == 5


@pytest.mark.asyncio
async def test_fase_5_dispatch_search_enabled_false_no_invoca_web_search(monkeypatch):
    called = {"n": 0}

    async def fake_web_search(*args, **kwargs):
        called["n"] += 1
        return {"results": []}

    monkeypatch.setattr(web, "web_search", fake_web_search)

    result = await dispatch_web_tool(
        "web_search",
        {"query": "linux"},
        user_id="u1",
        search_enabled=False,
    )

    assert "error" in result
    assert called["n"] == 0


@pytest.mark.asyncio
async def test_fase_5_dispatch_fetch_webpage_no_se_rompe_por_nuevos_kwargs(monkeypatch):
    captured: dict[str, object] = {}

    async def fake_fetch(url, **kwargs):
        captured["url"] = url
        captured["timeout"] = kwargs.get("timeout")
        return {"url": url, "title": "T", "content": "ok"}

    monkeypatch.setattr(web, "fetch_webpage", fake_fetch)

    result = await dispatch_web_tool(
        "fetch_webpage",
        {"url": "https://x.example"},
        user_id="u1",
        search_enabled=True,
        search_safe=True,
        search_max_per_hour=10,
        timeout=7.5,
    )

    assert "error" not in result
    assert captured["url"] == "https://x.example"
    assert captured["timeout"] == 7.5


@pytest.mark.asyncio
async def test_fase_5_dispatch_nombre_desconocido_devuelve_error():
    result = await dispatch_web_tool("no_existe", {})
    assert "error" in result


@pytest.mark.asyncio
async def test_fase_5_run_tool_loop_forwardea_user_id_y_search_kwargs_a_dispatch(monkeypatch):
    captured: dict[str, object] = {}

    async def fake_dispatch(name, args, **kwargs):
        captured["name"] = name
        captured["args"] = args
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(web, "dispatch_web_tool", fake_dispatch)

    class FakeClient:
        def __init__(self):
            self.n = 0

        async def chat_completion(self, messages, model, **kw):
            self.n += 1
            if self.n == 1:
                return {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "c1",
                            "function": {
                                "name": "web_search",
                                "arguments": json.dumps({"query": "linux"}),
                            },
                        }
                    ],
                }
            return {"role": "assistant", "content": "listo"}

    out = await run_tool_loop(
        FakeClient(),
        [{"role": "user", "content": "busca linux"}],
        "MiniMax-M3",
        None,
        tools=list(WEB_TOOL_NAMES),
        user_id="discord-user-42",
        search_enabled=True,
        search_safe=False,
        search_max_per_hour=7,
    )

    assert out == "listo"
    assert captured["name"] == "web_search"
    assert captured["args"] == {"query": "linux"}
    assert captured["user_id"] == "discord-user-42"
    assert captured["search_enabled"] is True
    assert captured["search_safe"] is False
    assert captured["search_max_per_hour"] == 7


@pytest.mark.asyncio
async def test_fase_5_run_tool_loop_sin_search_kwargs_sigue_funcionando(monkeypatch):
    """Compatibilidad: run_tool_loop sin los nuevos kwargs sigue rutando fetch_webpage."""
    calls: dict[str, object] = {}

    async def fake_fetch(url, **kwargs):
        calls["url"] = url
        return {"url": url, "title": "T", "content": "ok"}

    monkeypatch.setattr(web, "fetch_webpage", fake_fetch)

    class FakeClient:
        def __init__(self):
            self.n = 0

        async def chat_completion(self, messages, model, **kw):
            self.n += 1
            if self.n == 1:
                return {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "c1",
                            "function": {
                                "name": "fetch_webpage",
                                "arguments": json.dumps({"url": "https://x.example"}),
                            },
                        }
                    ],
                }
            return {"role": "assistant", "content": "fin"}

    out = await run_tool_loop(
        FakeClient(),
        [{"role": "user", "content": "hola"}],
        "MiniMax-M3",
        None,
        tools=list(WEB_TOOL_NAMES),
    )

    assert out == "fin"
    assert calls["url"] == "https://x.example"


# ---------------------------------------------------------------------------
# Phase 6 — ask_full tool gating + search-first hint + caller threading
# ---------------------------------------------------------------------------


@pytest.fixture
async def ai_cog_with_capture(tmp_path: Path):
    """Cog con `chat_completion` capturando tools + system messages inyectados."""
    db = AIChatDatabase(str(tmp_path / "ai_chat.db"))
    await db.connect()
    bot = MagicMock()
    bot.user = SimpleNamespace(id=99, mention="<@99>")
    client = MagicMock()
    captured: dict[str, object] = {}

    async def fake_chat_completion(messages, model, **kw):
        captured.setdefault("calls", []).append(
            {"messages": list(messages), "tools": kw.get("tools")}
        )
        # Sin tool_calls → el loop devuelve el content directamente.
        return {"role": "assistant", "content": "ok"}

    client.chat_completion = AsyncMock(side_effect=fake_chat_completion)
    client.chat = AsyncMock(return_value="ok")
    client.analyze_code_execution = AsyncMock(return_value={"purpose": "x", "improvements": []})
    cog = AIChatCog(bot, db, client, config_manager=None)
    yield cog, captured, db
    await db.close()


@pytest.mark.asyncio
async def test_fase_6_ask_full_expone_ambas_tools_y_pasa_user_id_con_search(ai_cog_with_capture):
    """REQ-SEARCH-01/07/11: con search_enabled, expone web_search + hint + user_id."""
    cog, captured, db = ai_cog_with_capture
    await db.update_config({"web_enabled": "true", "search_enabled": "true",
                            "search_safe": "true", "search_max_per_hour": "12"})

    await cog.ask_full("u-42", "c-1", "busca linux", persist=False)

    assert len(captured["calls"]) == 1
    tools = captured["calls"][0]["tools"]
    names = {t["function"]["name"] for t in tools}
    assert "fetch_webpage" in names
    assert "web_search" in names

    messages = captured["calls"][0]["messages"]
    # El system hint insertado en messages[1] debe mencionar el flujo search-first.
    system_msg = messages[1]["content"].lower()
    assert "web_search" in system_msg or "busca" in system_msg
    # El hint debe sugerir search-first cuando no hay URL.
    assert "url" in system_msg


@pytest.mark.asyncio
async def test_fase_6_ask_full_con_search_false_omite_web_search_y_hint(ai_cog_with_capture):
    """REQ-SEARCH-01/11: search deshabilitado → solo fetch_webpage, sin hint de search."""
    cog, captured, db = ai_cog_with_capture
    await db.update_config({"web_enabled": "true", "search_enabled": "false"})

    await cog.ask_full("u-1", "c-1", "hola", persist=False)

    assert len(captured["calls"]) == 1
    tools = captured["calls"][0]["tools"]
    names = {t["function"]["name"] for t in tools}
    assert "fetch_webpage" in names
    assert "web_search" not in names

    messages = captured["calls"][0]["messages"]
    system_msg = messages[1]["content"].lower()
    # El hint de search-first NO debe estar presente.
    assert "web_search" not in system_msg
    # El hint legacy de fetch_webpage sí.
    assert "página" in system_msg or "url" in system_msg


@pytest.mark.asyncio
async def test_fase_6_ask_full_con_web_false_no_expone_ninguna_herramienta_web(ai_cog_with_capture):
    """REQ-SEARCH-01: web deshabilitado → ninguna tool web expuesta.

    Con `web_enabled=false` el cog evita el tool-loop entero y va por el
    `client.chat` directo. Verificamos que `chat_completion` (tool-loop) NO se
    invoque y que `chat` SÍ se invoque, lo que es la garantía real de que
    ninguna tool web queda expuesta al modelo en ese path.
    """
    cog, captured, db = ai_cog_with_capture
    await db.update_config({"web_enabled": "false", "search_enabled": "true"})

    await cog.ask_full("u-1", "c-1", "hola", persist=False)

    # chat_completion (tool-loop) no debe llamarse cuando no hay tools web.
    assert "calls" not in captured
    # El fallback a chat directo debe haber ocurrido.
    assert cog.client.chat.await_count == 1


@pytest.mark.asyncio
async def test_fase_6_ask_full_pasa_search_max_per_hour_clampado(ai_cog_with_capture):
    """El clamp 1..100 se aplica antes de pasar al tool loop."""
    cog, captured, db = ai_cog_with_capture
    # 250 → debe clampsearse a 100.
    await db.update_config(
        {"web_enabled": "true", "search_enabled": "true", "search_max_per_hour": "250"}
    )

    captured_dispatch: dict[str, object] = {}
    original_dispatch = web.dispatch_web_tool

    async def fake_dispatch(name, args, **kw):
        captured_dispatch["name"] = name
        captured_dispatch["args"] = args
        captured_dispatch.update(kw)
        return await original_dispatch(name, args, **kw)

    web.dispatch_web_tool = fake_dispatch  # type: ignore[assignment]
    try:
        class FakeClient2:
            def __init__(self):
                self.n = 0

            async def chat_completion(self, messages, model, **kw):
                self.n += 1
                if self.n == 1:
                    return {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "c1",
                                "function": {
                                    "name": "web_search",
                                    "arguments": json.dumps({"query": "x"}),
                                },
                            }
                        ],
                    }
                return {"role": "assistant", "content": "fin"}

        cog.client.chat_completion = FakeClient2().chat_completion
        await cog.ask_full("u-1", "c-1", "hola", persist=False)
    finally:
        web.dispatch_web_tool = original_dispatch  # type: ignore[assignment]

    assert captured_dispatch["name"] == "web_search"
    assert captured_dispatch["search_max_per_hour"] == 100


@pytest.mark.asyncio
async def test_fase_6_ask_full_sin_red_invoca_run_tool_loop_con_user_id_string(ai_cog_with_capture):
    """REQ-SEARCH-07: ask_full pasa user_id como string a run_tool_loop (y al dispatch)."""
    cog, captured, db = ai_cog_with_capture
    await db.update_config({"web_enabled": "true", "search_enabled": "true"})

    captured_dispatch: dict[str, object] = {}
    original_dispatch = web.dispatch_web_tool

    async def fake_dispatch(name, args, **kw):
        captured_dispatch.update(kw)
        return await original_dispatch(name, args, **kw)

    web.dispatch_web_tool = fake_dispatch  # type: ignore[assignment]
    try:
        class FakeClient3:
            def __init__(self):
                self.n = 0

            async def chat_completion(self, messages, model, **kw):
                self.n += 1
                if self.n == 1:
                    return {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "c1",
                                "function": {
                                    "name": "web_search",
                                    "arguments": json.dumps({"query": "x"}),
                                },
                            }
                        ],
                    }
                return {"role": "assistant", "content": "fin"}

        cog.client.chat_completion = FakeClient3().chat_completion
        await cog.ask_full("u-42", "c-1", "hola", persist=False)
    finally:
        web.dispatch_web_tool = original_dispatch  # type: ignore[assignment]

    assert captured_dispatch["user_id"] == "u-42"


# ---------------------------------------------------------------------------
# Smoke: WEB_TOOLS/WEB_TOOL_NAMES consistentes con el contrato
# ---------------------------------------------------------------------------


def test_schemas_publicos_consistentes_con_web_tool_names():
    schema_names = {t["function"]["name"] for t in WEB_TOOLS}
    assert "web_search" in schema_names
    assert "fetch_webpage" in schema_names
    assert schema_names == WEB_TOOL_NAMES
    # La schema de web_search no expone `safe` (admin-only, REQ-SEARCH-05).
    ws = next(t for t in WEB_TOOLS if t["function"]["name"] == "web_search")
    props = ws["function"]["parameters"]["properties"]
    assert "safe" not in props
    assert set(ws["function"]["parameters"]["required"]) == {"query"}
