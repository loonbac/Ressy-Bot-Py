from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.bot.plugins.ai_chat.api import _typed_config, router
from src.bot.plugins.ai_chat.client import AIChatClient
from src.bot.plugins.ai_chat.cog import AIChatCog
from src.bot.plugins.ai_chat.database import AIChatDatabase


# ---------- fixtures (mirror test_ai_chat.py style) ----------


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
    client.chat_completion = AsyncMock(
        return_value={"role": "assistant", "content": "Respuesta de prueba"}
    )
    return AIChatCog(bot, ai_db, client)


@pytest.fixture
async def app(ai_cog):
    app = FastAPI()
    app.state.ai_chat_cog = ai_cog
    app.include_router(router, prefix="/api/plugins/ai-chat")
    return app


# ---------- _typed_config pure unit tests ----------


def test_typed_config_includes_search_enabled_as_bool():
    out = _typed_config(
        {
            "search_enabled": "true",
            "search_safe": "true",
            "search_max_per_hour": "10",
        }
    )
    assert out["search_enabled"] is True
    assert isinstance(out["search_enabled"], bool)


def test_typed_config_includes_search_safe_as_bool():
    out = _typed_config({"search_enabled": "true", "search_safe": "false", "search_max_per_hour": "10"})
    assert out["search_safe"] is False
    assert isinstance(out["search_safe"], bool)


def test_typed_config_includes_search_max_per_hour_as_int():
    out = _typed_config(
        {"search_enabled": "true", "search_safe": "true", "search_max_per_hour": "25"}
    )
    assert out["search_max_per_hour"] == 25
    assert isinstance(out["search_max_per_hour"], int)


def test_typed_config_search_keys_default_when_missing_from_raw():
    """Si la DB no trae las claves, _typed_config usa defaults razonables.
    No se inventa: defaults literales 'true'/'true'/'10'."""
    out = _typed_config({})
    # Si los defaults están, deben ser bool/int (no string) — PR 2 hace el cast.
    assert out.get("search_enabled") is True
    assert out.get("search_safe") is True
    assert out.get("search_max_per_hour") == 10


# ---------- API surface: GET includes typed search_* keys ----------


@pytest.mark.asyncio
async def test_get_config_includes_typed_search_keys(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/plugins/ai-chat/config")

    assert response.status_code == 200
    body = response.json()
    assert body["search_enabled"] is True
    assert body["search_safe"] is True
    assert body["search_max_per_hour"] == 10
    assert isinstance(body["search_enabled"], bool)
    assert isinstance(body["search_safe"], bool)
    assert isinstance(body["search_max_per_hour"], int)


# ---------- API surface: PUT validation REJECTS out-of-bounds ----------


@pytest.mark.asyncio
async def test_put_config_rejects_search_max_per_hour_zero(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.put(
            "/api/plugins/ai-chat/config", json={"search_max_per_hour": 0}
        )

    assert response.status_code == 422
    detail = response.json().get("detail", "")
    # Mensaje en español neutro y menciona la clave.
    assert "search_max_per_hour" in detail
    assert "1" in detail and "100" in detail


@pytest.mark.asyncio
async def test_put_config_rejects_search_max_per_hour_too_high(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.put(
            "/api/plugins/ai-chat/config", json={"search_max_per_hour": 101}
        )

    assert response.status_code == 422
    detail = response.json().get("detail", "")
    assert "search_max_per_hour" in detail


@pytest.mark.asyncio
async def test_put_config_rejects_search_max_per_hour_negative(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.put(
            "/api/plugins/ai-chat/config", json={"search_max_per_hour": -3}
        )

    assert response.status_code == 422


# ---------- API surface: PUT persists valid values ----------


@pytest.mark.asyncio
async def test_put_config_persists_search_max_per_hour_25(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        put_resp = await client.put(
            "/api/plugins/ai-chat/config", json={"search_max_per_hour": 25}
        )
        assert put_resp.status_code == 200
        get_resp = await client.get("/api/plugins/ai-chat/config")

    body = get_resp.json()
    assert body["search_max_per_hour"] == 25
    assert isinstance(body["search_max_per_hour"], int)


@pytest.mark.asyncio
async def test_put_config_persists_search_enabled_false(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        put_resp = await client.put(
            "/api/plugins/ai-chat/config", json={"search_enabled": False}
        )
        assert put_resp.status_code == 200
        get_resp = await client.get("/api/plugins/ai-chat/config")

    body = get_resp.json()
    assert body["search_enabled"] is False


@pytest.mark.asyncio
async def test_put_config_persists_search_safe_false(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        put_resp = await client.put(
            "/api/plugins/ai-chat/config", json={"search_safe": False}
        )
        assert put_resp.status_code == 200
        get_resp = await client.get("/api/plugins/ai-chat/config")

    body = get_resp.json()
    assert body["search_safe"] is False


@pytest.mark.asyncio
async def test_put_config_search_boundary_values_accepted(app):
    """Los extremos 1 y 100 son válidos y NO deben clamp ni 422."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for value in (1, 100):
            r = await client.put(
                "/api/plugins/ai-chat/config", json={"search_max_per_hour": value}
            )
            assert r.status_code == 200, f"value={value} devolvió {r.status_code}"
            g = await client.get("/api/plugins/ai-chat/config")
            assert g.json()["search_max_per_hour"] == value


# ---------- Regression: otros campos siguen funcionando ----------


@pytest.mark.asyncio
async def test_put_config_other_fields_still_clamped(app):
    """REGRESIÓN: la nueva rama de validación search_max_per_hour no rompe
    el clamp existente de context_token_budget ni de max_input_chars."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.put(
            "/api/plugins/ai-chat/config",
            json={"context_token_budget": 5, "max_input_chars": 50},
        )
        assert r.status_code == 200
        body = r.json()
        # Clamp a piso 1000/100 respectivamente.
        assert body["context_token_budget"] == 1000
        assert body["max_input_chars"] == 100
