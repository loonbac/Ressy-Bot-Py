from __future__ import annotations

import httpx
import pytest

from src.bot.plugins.ai_chat import web
from src.bot.plugins.ai_chat.web import (
    WEB_TOOL_NAMES,
    _ip_is_blocked,
    _normalize_url,
    _resolve_safe,
    dispatch_web_tool,
    fetch_webpage,
    html_to_text,
)


# ----- Extracción de texto -----

def test_html_to_text_extracts_title_and_strips_noise():
    html = """
    <html><head><title>Mi Página</title>
    <style>.x{color:red}</style></head>
    <body>
      <nav>Menú</nav>
      <h1>Hola</h1>
      <p>Primer párrafo con <b>negrita</b> y <a href="#">enlace</a>.</p>
      <script>console.log('no')</script>
      <p>Segundo párrafo.</p>
    </body></html>
    """
    title, text, _ = html_to_text(html)
    assert title == "Mi Página"
    assert "Hola" in text
    assert "Primer párrafo con negrita y enlace." in text
    assert "Segundo párrafo." in text
    assert "console.log" not in text  # script descartado
    assert "color:red" not in text  # style descartado


def test_html_to_text_captures_meta_description():
    html = '<html><head><meta name="description" content="Resumen SEO"></head><body><p>x</p></body></html>'
    _, _, meta = html_to_text(html)
    assert meta == "Resumen SEO"


def test_html_to_text_handles_broken_html():
    title, text, _ = html_to_text("<p>texto sin cerrar <b>roto")
    assert "texto sin cerrar" in text


# ----- Normalización y SSRF -----

def test_normalize_url_assumes_https_and_rejects_bad_scheme():
    assert _normalize_url("example.com").startswith("https://")
    assert _normalize_url("https://a.com/x").startswith("https://")
    assert _normalize_url("ftp://a.com") is None
    assert _normalize_url("file:///etc/passwd") is None
    assert _normalize_url("") is None


@pytest.mark.parametrize(
    "ip,blocked",
    [
        ("127.0.0.1", True),
        ("10.0.0.5", True),
        ("192.168.1.1", True),
        ("169.254.169.254", True),  # metadata cloud
        ("::1", True),
        ("0.0.0.0", True),
        ("8.8.8.8", False),
        ("1.1.1.1", False),
    ],
)
def test_ip_is_blocked(ip, blocked):
    assert _ip_is_blocked(ip) is blocked


def test_resolve_safe_blocks_literal_private_ip_without_dns():
    ok, reason = _resolve_safe("169.254.169.254")
    assert ok is False
    assert reason


def test_resolve_safe_allows_literal_public_ip():
    ok, _ = _resolve_safe("8.8.8.8")
    assert ok is True


# ----- fetch_webpage (red mockeada) -----

@pytest.fixture(autouse=True)
def _allow_dns(monkeypatch):
    # Evita DNS real en tests de fetch: el host se considera público.
    monkeypatch.setattr(web, "_resolve_safe", lambda host: (True, ""))


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True)


@pytest.mark.asyncio
async def test_fetch_webpage_returns_readable_content():
    def handler(request):
        return httpx.Response(
            200,
            html="<html><head><title>Noticia</title></head><body><p>Cuerpo de la noticia aquí, con suficiente texto para no parecer vacío y pasar el umbral de longitud sin problemas.</p></body></html>",
            headers={"content-type": "text/html; charset=utf-8"},
        )

    async with _client(handler) as c:
        r = await fetch_webpage("https://news.example/post", client=c)
    assert "error" not in r
    assert r["title"] == "Noticia"
    assert "Cuerpo de la noticia" in r["content"]
    assert r["fetched_with"] == "http"
    assert r["status"] == 200


@pytest.mark.asyncio
async def test_fetch_webpage_404_returns_clean_error_without_browser():
    def handler(request):
        return httpx.Response(404, html="<h1>Not Found</h1>", headers={"content-type": "text/html"})

    async with _client(handler) as c:
        r = await fetch_webpage("https://x.example/missing", client=c, browser_fallback=False)
    assert r["status"] == 404
    assert "error" in r
    assert "Not Found" not in r.get("content", "")  # no pasa la página de error como contenido


@pytest.mark.asyncio
async def test_fetch_webpage_returns_raw_json():
    def handler(request):
        return httpx.Response(200, json={"a": 1, "b": "dos"}, headers={"content-type": "application/json"})

    async with _client(handler) as c:
        r = await fetch_webpage("https://api.example/data", client=c)
    assert "error" not in r
    assert '"a": 1' in r["content"] or '"a":1' in r["content"]


@pytest.mark.asyncio
async def test_fetch_webpage_truncates_to_max_chars():
    big = "palabra " * 5000
    def handler(request):
        return httpx.Response(200, html=f"<body><p>{big}</p></body>", headers={"content-type": "text/html"})

    async with _client(handler) as c:
        r = await fetch_webpage("https://big.example/", client=c, max_chars=1000)
    assert r["truncated"] is True
    assert len(r["content"]) <= 1000


@pytest.mark.asyncio
async def test_fetch_webpage_rejects_bad_scheme():
    r = await fetch_webpage("ftp://example.com/file")
    assert "error" in r


@pytest.mark.asyncio
async def test_fetch_webpage_blocks_redirect_to_internal_ip(monkeypatch):
    # Resolver real: IP pública literal pasa el chequeo inicial, pero el server
    # redirige a la IP de metadata → debe bloquear el salto (SSRF vía redirect).
    monkeypatch.setattr(web, "_resolve_safe", _resolve_safe)

    def handler(request):
        if request.url.host == "8.8.8.8":
            return httpx.Response(302, headers={"location": "http://169.254.169.254/latest/meta-data/"})
        return httpx.Response(200, html="<p>interno</p>", headers={"content-type": "text/html"})

    async with _client(handler) as c:
        r = await fetch_webpage("https://8.8.8.8/", client=c, browser_fallback=True)
    assert "error" in r
    assert "seguridad" in r["error"].lower() or "interna" in r["error"].lower()
    assert "interno" not in r.get("content", "")


@pytest.mark.asyncio
async def test_fetch_webpage_follows_public_redirect(monkeypatch):
    # Resolver real: redirect entre dos IPs públicas literales se sigue normal.
    monkeypatch.setattr(web, "_resolve_safe", _resolve_safe)

    def handler(request):
        if request.url.host == "8.8.8.8":
            return httpx.Response(302, headers={"location": "https://1.1.1.1/final"})
        return httpx.Response(
            200,
            html="<html><head><title>Destino</title></head><body><p>Contenido final tras la redirección, con bastante texto adicional de sobra para superar con holgura el umbral mínimo de longitud y no parecer una página vacía renderizada por JavaScript.</p></body></html>",
            headers={"content-type": "text/html"},
        )

    async with _client(handler) as c:
        r = await fetch_webpage("https://8.8.8.8/start", client=c, browser_fallback=False)
    assert "error" not in r
    assert r["title"] == "Destino"
    assert "Contenido final" in r["content"]


@pytest.mark.asyncio
async def test_fetch_webpage_blocks_ssrf(monkeypatch):
    # Restaura el resolver real (la autouse fixture lo había neutralizado) y
    # apunta a IP interna: debe bloquear sin tocar la red.
    monkeypatch.setattr(web, "_resolve_safe", _resolve_safe)
    r = await fetch_webpage("http://169.254.169.254/latest/meta-data/")
    assert "error" in r


# ----- Routing en el tool-loop -----

@pytest.mark.asyncio
async def test_dispatch_web_tool_unknown_name():
    r = await dispatch_web_tool("no_existe", {})
    assert "error" in r


@pytest.mark.asyncio
async def test_run_tool_loop_routes_web_tool(monkeypatch):
    from src.bot.plugins.ai_chat.tools import run_tool_loop

    calls = {}

    async def fake_fetch(url, **kw):
        calls["url"] = url
        return {"title": "T", "content": "contenido web"}

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
                            "function": {"name": "fetch_webpage", "arguments": '{"url": "https://x.example"}'},
                        }
                    ],
                }
            return {"role": "assistant", "content": "Resumen final"}

    out = await run_tool_loop(
        FakeClient(),
        [{"role": "user", "content": "lee https://x.example"}],
        "MiniMax-M3",
        None,  # sin executor de Discord: la tool web igual debe funcionar
        tools=list(WEB_TOOL_NAMES),
    )
    assert out == "Resumen final"
    assert calls["url"] == "https://x.example"
