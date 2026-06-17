"""Live smoke tests for the `web_search` + `fetch_webpage` flow.

CONSTRAINT (project-wide hard rule): never launch a browser (Firefox/Chromium/any)
from agent/test tooling. These live tests use **httpx only** — no Playwright.

- Each test is decorated with `@pytest.mark.live` so it is excluded from the
  default `uv run pytest` run via `addopts = "-m 'not live'"` in `pyproject.toml`.
- They are designed to be OPT-IN and gentle with provider-side blocking:
  if DDG blocks this environment, the test asserts a graceful `{"error": ...}`
  payload rather than hard-failing.
- They DO NOT touch the bot, do NOT commit, and never start a Playwright.
"""
from __future__ import annotations

import pytest

from src.bot.plugins.ai_chat.web import fetch_webpage, web_search


LIVE_USER_ID = "live-pr2-smoke"


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_ddg_web_search_returns_results_or_graceful_error():
    """Smoke real: ejecuta `web_search` contra DuckDuckGo Lite con httpx.

    Acepta EITHER:
      - resultados estructurados no vacíos (`results` con `title`/`url`/`snippet`)
      - o un `{"error": ...}` cortés (DDG bloquea bots, IP, captcha, etc.)

    Nunca propaga excepciones: `web_search` está contratado a fallar cerrado.
    """
    result = await web_search(
        "linux kernel 6.8",
        user_id=LIVE_USER_ID,
        max_per_hour=100,
        safe=True,
        timeout=10,
    )

    assert isinstance(result, dict)
    if "error" in result:
        # Fallo cortés del proveedor — no es regresión de código.
        assert isinstance(result["error"], str)
        assert result["error"]
    else:
        # Camino feliz: payload estructurado, sin HTML crudo.
        assert "results" in result
        assert "query" in result
        assert result["query"] == "linux kernel 6.8"
        assert result["safe"] is True
        assert result["source"] == "duckduckgo_lite"
        assert result["fetched_with"] == "http"
        assert isinstance(result["results"], list)
        assert result["results"], "DDG devolvió 0 resultados sin error"
        for item in result["results"]:
            assert set(item.keys()) >= {"title", "url", "snippet"}
            assert item["title"]
            assert item["url"].startswith(("http://", "https://"))


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_fetch_webpage_via_existing_ssrf_guard():
    """Smoke real: dado un resultado de búsqueda, `fetch_webpage` lo trae con httpx.

    Se fuerza `browser_fallback=False` para CUMPLIR la restricción dura del
    proyecto ("no lanzar navegador desde tooling"). El runtime puede caer
    al fallback de Playwright en producción, pero este test sólo prueba el
    camino httpx.
    """
    search_result = await web_search(
        "linux kernel 6.8",
        user_id=LIVE_USER_ID,
        max_per_hour=100,
        safe=True,
        timeout=10,
    )

    if "error" in search_result or not search_result.get("results"):
        pytest.skip("DDG no devolvió resultados en este entorno; smoke omitido.")

    first_url = search_result["results"][0]["url"]
    assert first_url.startswith(("http://", "https://"))

    page = await fetch_webpage(first_url, timeout=10, browser_fallback=False)

    assert isinstance(page, dict)
    if "error" in page:
        # El SSRF guard o un timeout de red pueden bloquear — es no-regresión.
        assert isinstance(page["error"], str)
        assert page["error"]
    else:
        # Camino feliz: payload estructurado, sin raw HTML.
        assert "url" in page
        assert "content" in page or "text" in page or "title" in page
        # El resultado no debe contener un dump gigante de HTML crudo.
        raw = page.get("content") or page.get("text") or ""
        assert isinstance(raw, str)
        # Si devolvió HTML crudo, fallamos: el extractor debería haberlo reducido.
        assert "<html" not in raw.lower(), "fetch_webpage devolvió HTML crudo"
