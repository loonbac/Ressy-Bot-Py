"""Tests para OpenRouterClient.

Usa mocks de httpx.AsyncClient para no hacer llamadas reales a la API.
Cubre: happy path, retry en 5xx, timeout/error de red, JSON malformado,
fallo final tras reintentos.
"""
from __future__ import annotations

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Fixtures y helpers
# ---------------------------------------------------------------------------

def _make_fixture_models(n: int = 3) -> list[dict]:
    """Genera una lista mínima de modelos al estilo OpenRouter API."""
    return [
        {
            "id": f"vendor/model-{i}",
            "name": f"Model {i}",
            "description": "Test",
            "created": 1_700_000_000,
            "context_length": 4096,
            "architecture": {
                "input_modalities": ["text"],
                "output_modalities": ["text"],
                "modality": "text->text",
            },
            "pricing": {
                "prompt": "0.000001",
                "completion": "0.000002",
                "image": "0",
                "request": "0",
                "web_search": "0",
                "input_cache_read": "0",
                "input_cache_write": "0",
            },
            "top_provider": {
                "context_length": 4096,
                "max_completion_tokens": 2048,
                "is_moderated": False,
            },
        }
        for i in range(n)
    ]


def _make_ok_response(models: list[dict]) -> MagicMock:
    """Mock de respuesta httpx 200 OK con lista de modelos."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"data": models}
    return resp


def _make_error_response(status_code: int = 503) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = f"Error {status_code}"
    return resp


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestFetchModelsHappyPath:
    async def test_returns_list_of_dicts(self):
        from src.bot.plugins.openrouter_prices.client import OpenRouterClient

        models = _make_fixture_models(5)

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = _make_ok_response(models)
            client = OpenRouterClient()
            result = await client.fetch_models()
            await client.close()

        assert isinstance(result, list)
        assert len(result) == 5

    async def test_preserves_model_structure(self):
        from src.bot.plugins.openrouter_prices.client import OpenRouterClient

        models = _make_fixture_models(2)

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = _make_ok_response(models)
            client = OpenRouterClient()
            result = await client.fetch_models()
            await client.close()

        assert result[0]["id"] == "vendor/model-0"
        assert "architecture" in result[0]
        assert "pricing" in result[0]

    async def test_calls_correct_url(self):
        from src.bot.plugins.openrouter_prices.client import OpenRouterClient, BASE_URL

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = _make_ok_response([])
            client = OpenRouterClient()
            await client.fetch_models()
            await client.close()

        mock_get.assert_called_once()
        call_url = mock_get.call_args[0][0]
        assert call_url == BASE_URL


class TestFetchModelsRetry:
    async def test_retries_once_on_5xx(self):
        """Un 503 en el primer intento debe resultar en un segundo intento exitoso."""
        from src.bot.plugins.openrouter_prices.client import OpenRouterClient

        models = _make_fixture_models(2)
        ok_resp = _make_ok_response(models)
        err_resp = _make_error_response(503)

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            # Primer intento falla, segundo tiene éxito
            mock_get.side_effect = [err_resp, ok_resp]
            with patch("asyncio.sleep", new_callable=AsyncMock):
                client = OpenRouterClient()
                result = await client.fetch_models()
                await client.close()

        assert len(result) == 2
        assert mock_get.call_count == 2

    async def test_raises_after_max_retries_on_5xx(self):
        """Si ambos intentos fallan con 5xx, debe lanzar excepción."""
        from src.bot.plugins.openrouter_prices.client import OpenRouterClient

        err_resp = _make_error_response(503)

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = err_resp
            with patch("asyncio.sleep", new_callable=AsyncMock):
                client = OpenRouterClient()
                with pytest.raises(Exception):
                    await client.fetch_models()
                await client.close()

        # 2 intentos (original + 1 retry)
        assert mock_get.call_count == 2

    async def test_raises_on_non_200_final(self):
        """Un 404 no debe reintentarse — es un error no recuperable."""
        from src.bot.plugins.openrouter_prices.client import OpenRouterClient

        err_resp = _make_error_response(404)

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = err_resp
            client = OpenRouterClient()
            with pytest.raises(Exception):
                await client.fetch_models()
            await client.close()


class TestFetchModelsNetworkErrors:
    async def test_raises_on_timeout(self):
        """Un timeout de red debe propagarse como excepción."""
        import httpx
        from src.bot.plugins.openrouter_prices.client import OpenRouterClient

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.TimeoutException("timeout")
            with patch("asyncio.sleep", new_callable=AsyncMock):
                client = OpenRouterClient()
                with pytest.raises(Exception):
                    await client.fetch_models()
                await client.close()

    async def test_raises_on_connect_error(self):
        """Un error de conexión debe propagarse como excepción."""
        import httpx
        from src.bot.plugins.openrouter_prices.client import OpenRouterClient

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = httpx.ConnectError("unreachable")
            with patch("asyncio.sleep", new_callable=AsyncMock):
                client = OpenRouterClient()
                with pytest.raises(Exception):
                    await client.fetch_models()
                await client.close()


class TestFetchModelsMalformedJSON:
    async def test_raises_on_missing_data_key(self):
        """Si la respuesta 200 no tiene la clave 'data', debe lanzar excepción."""
        from src.bot.plugins.openrouter_prices.client import OpenRouterClient

        bad_resp = MagicMock()
        bad_resp.status_code = 200
        bad_resp.json.return_value = {"unexpected": "structure"}

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = bad_resp
            client = OpenRouterClient()
            with pytest.raises(Exception):
                await client.fetch_models()
            await client.close()

    async def test_raises_on_json_decode_error(self):
        """Si json() lanza, debe propagarse como excepción."""
        import httpx
        from src.bot.plugins.openrouter_prices.client import OpenRouterClient

        bad_resp = MagicMock()
        bad_resp.status_code = 200
        bad_resp.json.side_effect = Exception("JSON decode error")

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = bad_resp
            client = OpenRouterClient()
            with pytest.raises(Exception):
                await client.fetch_models()
            await client.close()


class TestClientLifecycle:
    async def test_close_is_idempotent(self):
        """Llamar close() dos veces no debe lanzar."""
        from src.bot.plugins.openrouter_prices.client import OpenRouterClient

        client = OpenRouterClient()
        await client.close()
        await client.close()  # segunda llamada no debe explotar

    async def test_base_url_constant(self):
        from src.bot.plugins.openrouter_prices.client import BASE_URL
        assert BASE_URL == "https://openrouter.ai/api/v1/models"

    async def test_timeout_constant(self):
        from src.bot.plugins.openrouter_prices.client import TIMEOUT
        assert TIMEOUT == 15.0
