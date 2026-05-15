"""Pruebas de integración para la REST API del plugin openrouter_prices.

Usa FastAPI TestClient con una DB en memoria y un cliente HTTP mockeado.
Sigue el patrón de test_music_player.py (ASGITransport + AsyncClient).
"""
from __future__ import annotations

import json
import time
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FIXTURE_MODELS = [
    {
        "id": "openai/gpt-4o",
        "name": "GPT-4o",
        "description": "Modelo multimodal de OpenAI.",
        "created": 1715000000,
        "context_length": 128000,
        "architecture": {
            "modality": "text+image->text",
            "input_modalities": ["text", "image"],
            "output_modalities": ["text"],
        },
        "pricing": {
            "prompt": "0.000005",
            "completion": "0.000015",
            "image": "0.001",
        },
        "top_provider": {
            "context_length": 128000,
            "max_completion_tokens": 4096,
            "is_moderated": True,
        },
    },
    {
        "id": "anthropic/claude-3-haiku",
        "name": "Claude 3 Haiku",
        "description": "Modelo rápido de Anthropic.",
        "created": 1710000000,
        "context_length": 200000,
        "architecture": {
            "modality": "text->text",
            "input_modalities": ["text"],
            "output_modalities": ["text"],
        },
        "pricing": {
            "prompt": "0.00000025",
            "completion": "0.00000125",
        },
        "top_provider": {
            "context_length": 200000,
            "max_completion_tokens": 4096,
            "is_moderated": False,
        },
    },
    {
        "id": "openai/dall-e-3",
        "name": "DALL-E 3",
        "description": "Modelo de imagen de OpenAI.",
        "created": 1700000000,
        "context_length": 0,
        "architecture": {
            "modality": "text->image",
            "input_modalities": ["text"],
            "output_modalities": ["image"],
        },
        "pricing": {
            "prompt": "0.0",
            "image": "0.04",
        },
        "top_provider": {},
    },
]


@pytest.fixture
async def or_db():
    """Base de datos de openrouter_prices en memoria."""
    from src.bot.plugins.openrouter_prices.database import OpenRouterDatabase

    db = OpenRouterDatabase(":memory:")
    await db.connect()
    yield db
    await db.close()


@pytest.fixture
async def or_api_client(or_db):
    """Cliente HTTPX para la API de openrouter_prices con mock de OpenRouterClient."""
    from src.bot.plugins.openrouter_prices.api import router as or_router
    from src.bot.plugins.openrouter_prices.client import OpenRouterClient

    mock_client = AsyncMock(spec=OpenRouterClient)
    mock_client.fetch_models = AsyncMock(return_value=FIXTURE_MODELS)

    app = FastAPI()
    app.state.openrouter_prices_db = or_db
    app.state.openrouter_prices_client = mock_client

    app.include_router(or_router, prefix="/api/plugins/openrouter-prices")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# ---------------------------------------------------------------------------
# GET /models — cold start, cache hit, filters
# ---------------------------------------------------------------------------


class TestGetModels:
    async def test_cold_start_fetches_and_returns_models(self, or_api_client: AsyncClient):
        """Cold start: DB vacía → cliente llamado → modelos devueltos."""
        resp = await or_api_client.get("/api/plugins/openrouter-prices/models")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] > 0
        assert isinstance(data["models"], list)
        assert data["cached"] is False
        assert "cache_stale" in data
        assert "last_fetched_at" in data

    async def test_cold_start_client_called_exactly_once(self, or_api_client: AsyncClient):
        """Client.fetch_models debe llamarse exactamente una vez en cold start."""
        client_mock = or_api_client._transport.app.state.openrouter_prices_client
        client_mock.fetch_models.reset_mock()
        await or_api_client.get("/api/plugins/openrouter-prices/models")
        client_mock.fetch_models.assert_awaited_once()

    async def test_cache_hit_does_not_call_client(self, or_api_client: AsyncClient):
        """Cache válida → cliente NO debe llamarse en la segunda petición."""
        client_mock = or_api_client._transport.app.state.openrouter_prices_client
        # Primera llamada puebla la caché
        await or_api_client.get("/api/plugins/openrouter-prices/models")
        client_mock.fetch_models.reset_mock()
        # Segunda llamada dentro del TTL
        resp = await or_api_client.get("/api/plugins/openrouter-prices/models")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cached"] is True
        client_mock.fetch_models.assert_not_awaited()

    async def test_text_only_filter_excludes_image_only_models(self, or_api_client: AsyncClient):
        """text_only=true excluye modelos sin 'text' en input_modalities."""
        # Cold start para poblar
        await or_api_client.get("/api/plugins/openrouter-prices/models")
        resp = await or_api_client.get(
            "/api/plugins/openrouter-prices/models?text_only=true"
        )
        assert resp.status_code == 200
        data = resp.json()
        # DALL-E 3 tiene output_modalities=["image"] pero input=["text"] → debe aparecer
        # Los fixtures actuales todos tienen text en input — verificamos que no hay modelos raros
        for model in data["models"]:
            assert "text" in model["input_modalities"]

    async def test_sort_by_prompt_asc(self, or_api_client: AsyncClient):
        """sort=prompt&direction=asc → modelos ordenados de menor a mayor precio de prompt."""
        await or_api_client.get("/api/plugins/openrouter-prices/models")
        resp = await or_api_client.get(
            "/api/plugins/openrouter-prices/models?sort=prompt&direction=asc&text_only=false"
        )
        assert resp.status_code == 200
        data = resp.json()
        prices = [m["pricing_prompt_per_mtok"] for m in data["models"] if m["pricing_prompt_per_mtok"] is not None]
        assert prices == sorted(prices)

    async def test_sort_by_unknown_falls_back_silently(self, or_api_client: AsyncClient):
        """Sort desconocido → no lanza 400; usa fallback silencioso."""
        await or_api_client.get("/api/plugins/openrouter-prices/models")
        resp = await or_api_client.get(
            "/api/plugins/openrouter-prices/models?sort=UNKNOWN_SORT"
        )
        assert resp.status_code == 200

    async def test_limit_parameter_restricts_count(self, or_api_client: AsyncClient):
        """limit=1 → máximo 1 modelo en la respuesta."""
        await or_api_client.get("/api/plugins/openrouter-prices/models")
        resp = await or_api_client.get(
            "/api/plugins/openrouter-prices/models?limit=1&text_only=false"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["models"]) <= 1

    async def test_cache_stale_flag_is_false_on_fresh_fetch(self, or_api_client: AsyncClient):
        """cache_stale debe ser False justo tras un fetch exitoso."""
        resp = await or_api_client.get("/api/plugins/openrouter-prices/models")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cache_stale"] is False


# ---------------------------------------------------------------------------
# GET /models/{model_id}
# ---------------------------------------------------------------------------


class TestGetModelById:
    async def test_found_returns_200(self, or_api_client: AsyncClient):
        """Modelo existente → 200 con datos del modelo."""
        await or_api_client.get("/api/plugins/openrouter-prices/models")
        resp = await or_api_client.get(
            "/api/plugins/openrouter-prices/models/anthropic%2Fclaude-3-haiku"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "anthropic/claude-3-haiku"
        assert data["name"] == "Claude 3 Haiku"

    async def test_not_found_returns_404(self, or_api_client: AsyncClient):
        """Modelo inexistente → 404 con detail en español."""
        await or_api_client.get("/api/plugins/openrouter-prices/models")
        resp = await or_api_client.get(
            "/api/plugins/openrouter-prices/models/does-not-exist"
        )
        assert resp.status_code == 404
        data = resp.json()
        assert "detail" in data
        assert "no encontrado" in data["detail"].lower()


# ---------------------------------------------------------------------------
# GET /config
# ---------------------------------------------------------------------------


class TestGetConfig:
    async def test_returns_default_config(self, or_api_client: AsyncClient):
        """GET /config devuelve la configuración por defecto."""
        resp = await or_api_client.get("/api/plugins/openrouter-prices/config")
        assert resp.status_code == 200
        data = resp.json()
        assert data["enabled"] is True
        assert data["ttl_seconds"] == 3600
        assert data["max_models_command"] == 10
        assert "discord_channel_id" in data


# ---------------------------------------------------------------------------
# PUT /config
# ---------------------------------------------------------------------------


class TestPutConfig:
    async def test_valid_ttl_update(self, or_api_client: AsyncClient):
        """ttl_seconds válido → 200 con nuevo valor."""
        resp = await or_api_client.put(
            "/api/plugins/openrouter-prices/config",
            json={"ttl_seconds": 7200},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ttl_seconds"] == 7200

    async def test_invalid_ttl_negative(self, or_api_client: AsyncClient):
        """ttl_seconds <= 0 → 422 con detail en español."""
        resp = await or_api_client.put(
            "/api/plugins/openrouter-prices/config",
            json={"ttl_seconds": -1},
        )
        assert resp.status_code == 422
        data = resp.json()
        assert "detail" in data
        assert "ttl_seconds" in data["detail"]

    async def test_invalid_ttl_zero(self, or_api_client: AsyncClient):
        """ttl_seconds = 0 → 422."""
        resp = await or_api_client.put(
            "/api/plugins/openrouter-prices/config",
            json={"ttl_seconds": 0},
        )
        assert resp.status_code == 422

    async def test_invalid_max_models_command_too_high(self, or_api_client: AsyncClient):
        """max_models_command > 25 → 422."""
        resp = await or_api_client.put(
            "/api/plugins/openrouter-prices/config",
            json={"max_models_command": 30},
        )
        assert resp.status_code == 422

    async def test_invalid_max_models_command_zero(self, or_api_client: AsyncClient):
        """max_models_command < 1 → 422."""
        resp = await or_api_client.put(
            "/api/plugins/openrouter-prices/config",
            json={"max_models_command": 0},
        )
        assert resp.status_code == 422

    async def test_valid_enabled_false(self, or_api_client: AsyncClient):
        """enabled=false → 200."""
        resp = await or_api_client.put(
            "/api/plugins/openrouter-prices/config",
            json={"enabled": False},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["enabled"] is False

    async def test_partial_update_preserves_other_fields(self, or_api_client: AsyncClient):
        """Actualización parcial → otros campos no cambian."""
        resp = await or_api_client.put(
            "/api/plugins/openrouter-prices/config",
            json={"enabled": False},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ttl_seconds"] == 3600  # no debe cambiar

    async def test_invalid_discord_channel_id_too_short(self, or_api_client: AsyncClient):
        """discord_channel_id con longitud < 17 → 400."""
        resp = await or_api_client.put(
            "/api/plugins/openrouter-prices/config",
            json={"discord_channel_id": "1234"},
        )
        assert resp.status_code == 400

    async def test_valid_discord_channel_id_empty_string(self, or_api_client: AsyncClient):
        """discord_channel_id = '' (vacío) → 200 (deseleccionar canal)."""
        resp = await or_api_client.put(
            "/api/plugins/openrouter-prices/config",
            json={"discord_channel_id": ""},
        )
        assert resp.status_code == 200

    async def test_valid_discord_channel_id_numeric_string(self, or_api_client: AsyncClient):
        """discord_channel_id numérico de 18 dígitos → 200."""
        resp = await or_api_client.put(
            "/api/plugins/openrouter-prices/config",
            json={"discord_channel_id": "123456789012345678"},
        )
        assert resp.status_code == 200

    async def test_invalid_discord_channel_id_non_numeric(self, or_api_client: AsyncClient):
        """discord_channel_id no numérico → 400."""
        resp = await or_api_client.put(
            "/api/plugins/openrouter-prices/config",
            json={"discord_channel_id": "not-a-snowflake!"},
        )
        assert resp.status_code == 400


class TestPutConfigPhasesEnabled:
    async def test_put_phases_enabled_validates_list_of_strings(self, or_api_client: AsyncClient):
        resp = await or_api_client.put(
            "/api/plugins/openrouter-prices/config",
            json={"phases_enabled": ["orchestrator", 123]},
        )

        assert resp.status_code == 422
        assert "lista" in resp.json()["detail"].lower()

    async def test_put_phases_enabled_accepts_valid_json_array(self, or_api_client: AsyncClient):
        resp = await or_api_client.put(
            "/api/plugins/openrouter-prices/config",
            json={"phases_enabled": ["orchestrator", "sdd_init"]},
        )

        assert resp.status_code == 200
        db = or_api_client._transport.app.state.openrouter_prices_db
        config = await db.get_config()
        assert json.loads(config["phases_enabled"]) == ["orchestrator", "sdd_init"]

    async def test_put_phases_enabled_rejects_csv_string(self, or_api_client: AsyncClient):
        resp = await or_api_client.put(
            "/api/plugins/openrouter-prices/config",
            json={"phases_enabled": "orchestrator,sdd_init"},
        )

        assert resp.status_code == 422
        assert "lista de fases" in resp.json()["detail"].lower()

    async def test_put_phases_enabled_rejects_unknown_phase(self, or_api_client: AsyncClient):
        resp = await or_api_client.put(
            "/api/plugins/openrouter-prices/config",
            json={"phases_enabled": ["orchestrator", "fantasma"]},
        )

        assert resp.status_code == 422
        assert "fantasma" in resp.json()["detail"]


class TestGetPhases:
    async def test_get_phases_returns_objects_not_strings(self, or_api_client: AsyncClient):
        resp = await or_api_client.get("/api/plugins/openrouter-prices/phases")

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert data
        assert isinstance(data[0], dict)
        assert set(data[0]) == {
            "slug",
            "label",
            "description",
            "weights_count",
            "active_benchmarks_count",
            "reserved_benchmarks_count",
            "feature_factors_count",
            "last_ranking_computed_at",
        }

    async def test_get_phases_label_orchestrator_es(self, or_api_client: AsyncClient):
        resp = await or_api_client.get("/api/plugins/openrouter-prices/phases")

        phase = next(item for item in resp.json() if item["slug"] == "orchestrator")
        assert phase["label"] == "Orquestador"

    async def test_get_phases_label_sdd_init(self, or_api_client: AsyncClient):
        resp = await or_api_client.get("/api/plugins/openrouter-prices/phases")

        phase = next(item for item in resp.json() if item["slug"] == "sdd_init")
        assert phase["label"] == "SDD Init"

    async def test_get_phases_counts_correct(self, or_api_client: AsyncClient):
        resp = await or_api_client.get("/api/plugins/openrouter-prices/phases")

        phases = {item["slug"]: item for item in resp.json()}
        orchestrator = phases["orchestrator"]
        assert orchestrator["weights_count"] == 11
        assert orchestrator["active_benchmarks_count"] == 8
        assert orchestrator["reserved_benchmarks_count"] == 3
        assert orchestrator["feature_factors_count"] == 3

    async def test_get_phases_last_ranking_null_when_no_scrapes(self, or_api_client: AsyncClient):
        resp = await or_api_client.get("/api/plugins/openrouter-prices/phases")

        assert all(item["last_ranking_computed_at"] is None for item in resp.json())


# ---------------------------------------------------------------------------
# POST /refresh
# ---------------------------------------------------------------------------


class TestPostRefresh:
    async def test_successful_refresh_returns_updated_count(self, or_api_client: AsyncClient):
        """Refresh exitoso → 200 con updated_count y source='openrouter'."""
        resp = await or_api_client.post("/api/plugins/openrouter-prices/refresh")
        assert resp.status_code == 200
        data = resp.json()
        assert data["updated"] == len(FIXTURE_MODELS)
        assert data["source"] == "openrouter"
        assert "fetched_at" in data

    async def test_refresh_calls_client(self, or_api_client: AsyncClient):
        """POST /refresh siempre llama al cliente HTTP."""
        client_mock = or_api_client._transport.app.state.openrouter_prices_client
        client_mock.fetch_models.reset_mock()
        await or_api_client.post("/api/plugins/openrouter-prices/refresh")
        client_mock.fetch_models.assert_awaited_once()

    async def test_refresh_on_http_failure_returns_cache_fallback(self, or_api_client: AsyncClient):
        """Fallo HTTP → 200 con source='cache_fallback' (graceful degradation)."""
        client_mock = or_api_client._transport.app.state.openrouter_prices_client

        # Primero poblar el caché
        await or_api_client.post("/api/plugins/openrouter-prices/refresh")

        # Simular fallo en el siguiente refresh
        client_mock.fetch_models.side_effect = RuntimeError("HTTP 503")

        resp = await or_api_client.post("/api/plugins/openrouter-prices/refresh")
        assert resp.status_code == 200
        data = resp.json()
        assert data["source"] == "cache_fallback"
        assert data["updated"] == 0

        # Resetear side_effect
        client_mock.fetch_models.side_effect = None
        client_mock.fetch_models.return_value = FIXTURE_MODELS


# ---------------------------------------------------------------------------
# GET /status
# ---------------------------------------------------------------------------


class TestGetStatus:
    async def test_status_all_fields_present(self, or_api_client: AsyncClient):
        """GET /status devuelve todos los campos requeridos."""
        resp = await or_api_client.get("/api/plugins/openrouter-prices/status")
        assert resp.status_code == 200
        data = resp.json()
        required_fields = {
            "enabled",
            "models_count",
            "stale_count",
            "last_fetched_at",
            "ttl_seconds",
            "last_fetch_status",
            "last_fetch_error",
        }
        for field in required_fields:
            assert field in data, f"Campo '{field}' no encontrado en /status"

    async def test_status_after_fetch_shows_model_count(self, or_api_client: AsyncClient):
        """Tras un fetch, /status muestra el conteo correcto de modelos."""
        await or_api_client.post("/api/plugins/openrouter-prices/refresh")
        resp = await or_api_client.get("/api/plugins/openrouter-prices/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["models_count"] == len(FIXTURE_MODELS)
        assert data["last_fetch_status"] == "ok"
        assert data["last_fetched_at"] is not None

    async def test_status_fresh_db_shows_zero_models(self, or_api_client: AsyncClient):
        """DB vacía → models_count = 0, last_fetched_at = None."""
        resp = await or_api_client.get("/api/plugins/openrouter-prices/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["models_count"] == 0
        assert data["last_fetched_at"] is None
