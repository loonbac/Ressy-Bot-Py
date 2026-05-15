"""Tests TDD para EndOfLifeClient.

Estricto RED -> GREEN -> TRIANGULATE -> REFACTOR.
Mock httpx.AsyncClient con AsyncMock + patch.
"""
from __future__ import annotations

import json
import logging
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.bot.plugins.linux_updates.client import (
    BASE_URL,
    EndOfLifeAPIError,
    EndOfLifeClient,
    EndOfLifeParseError,
    EndOfLifeTimeoutError,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_response(
    status_code: int = 200,
    json_data=None,
    text: str = "",
    headers: dict | None = None,
) -> httpx.Response:
    """Fabrica una respuesta httpx con los datos deseados."""
    response = httpx.Response(
        status_code=status_code,
        headers=headers or {},
        text=text if text else (json.dumps(json_data) if json_data is not None else ""),
    )
    return response


# ---------------------------------------------------------------------------
# RED / GREEN / TRIANGULATE
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_product_success():
    """GET ok con JSON array valido devuelve lista normalizada."""
    client = EndOfLifeClient()
    mock_json = [
        {
            "cycle": "24.04",
            "releaseDate": "2024-04-25",
            "eol": "2034-04-01",
            "latest": "24.04.1",
            "latestReleaseDate": "2024-08-15",
            "lts": True,
        }
    ]
    mock_resp = _mock_response(json_data=mock_json)

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        result = await client.fetch_product("ubuntu")

    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["cycle"] == "24.04"
    assert result[0]["eol_date"] == "2034-04-01"
    assert result[0]["lts"] is True


@pytest.mark.asyncio
async def test_fetch_product_normalizes_fields():
    """eol=false -> None, support=false -> None, lts=True -> True."""
    client = EndOfLifeClient()
    mock_json = [
        {
            "cycle": "22.04",
            "eol": False,
            "support": False,
            "extendedSupport": False,
            "lts": True,
        }
    ]
    mock_resp = _mock_response(json_data=mock_json)

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        result = await client.fetch_product("ubuntu")

    assert result[0]["eol_date"] is None
    assert result[0]["support_date"] is None
    assert result[0]["extended_support_date"] is None
    assert result[0]["lts"] is True


@pytest.mark.asyncio
async def test_fetch_product_handles_missing_fields():
    """Campos ausentes (codename, latest, releaseLabel) -> None."""
    client = EndOfLifeClient()
    mock_json = [{"cycle": "rolling"}]
    mock_resp = _mock_response(json_data=mock_json)

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        result = await client.fetch_product("linux")

    assert result[0]["codename"] is None
    assert result[0]["latest_version"] is None
    assert result[0]["release_label"] is None
    assert result[0]["release_date"] is None


@pytest.mark.asyncio
async def test_fetch_product_handles_extended_support_false():
    """extendedSupport=false se normaliza a None."""
    client = EndOfLifeClient()
    mock_json = [{"cycle": "1.0", "extendedSupport": False}]
    mock_resp = _mock_response(json_data=mock_json)

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        result = await client.fetch_product("rocky-linux")

    assert result[0]["extended_support_date"] is None


@pytest.mark.asyncio
async def test_fetch_product_handles_extended_support_string():
    """extendedSupport='2030-06-30' se conserva como string."""
    client = EndOfLifeClient()
    mock_json = [{"cycle": "9.0", "extendedSupport": "2030-06-30"}]
    mock_resp = _mock_response(json_data=mock_json)

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        result = await client.fetch_product("rocky-linux")

    assert result[0]["extended_support_date"] == "2030-06-30"


@pytest.mark.asyncio
async def test_fetch_product_404_raises_api_error():
    """404 -> EndOfLifeAPIError."""
    client = EndOfLifeClient()
    mock_resp = _mock_response(status_code=404, text="Not Found")

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        with pytest.raises(EndOfLifeAPIError) as exc_info:
            await client.fetch_product("no-existe")

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_fetch_product_timeout_retries_then_raises():
    """3 timeouts consecutivos -> EndOfLifeTimeoutError tras 3 intentos."""
    client = EndOfLifeClient(max_retries=3)

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = httpx.TimeoutException("Timeout")
        with pytest.raises(EndOfLifeTimeoutError) as exc_info:
            await client.fetch_product("debian")

    assert mock_get.call_count == 3
    assert "Timeout" in str(exc_info.value)


@pytest.mark.asyncio
async def test_fetch_product_invalid_json_raises_parse():
    """JSON invalido -> EndOfLifeParseError."""
    client = EndOfLifeClient()
    mock_resp = _mock_response(status_code=200, text="not json")

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        with pytest.raises(EndOfLifeParseError) as exc_info:
            await client.fetch_product("ubuntu")

    assert "JSON invalido" in str(exc_info.value)


@pytest.mark.asyncio
async def test_fetch_product_non_list_raises_parse():
    """Respuesta objeto en vez de array -> EndOfLifeParseError."""
    client = EndOfLifeClient()
    mock_resp = _mock_response(json_data={"error": "not a list"})

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
        with pytest.raises(EndOfLifeParseError) as exc_info:
            await client.fetch_product("ubuntu")

    assert "no es un array" in str(exc_info.value)


@pytest.mark.asyncio
async def test_fetch_product_rate_limit_warning(caplog):
    """Header x-ratelimit-remaining: 5 -> log.warning."""
    client = EndOfLifeClient()
    mock_json = [{"cycle": "1"}]
    mock_resp = _mock_response(
        json_data=mock_json,
        headers={"x-ratelimit-remaining": "5"},
    )

    with caplog.at_level(logging.WARNING):
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            await client.fetch_product("ubuntu")

    assert any("Rate limit remaining bajo" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_close_cleans_up():
    """close() llama a aclose() del cliente interno."""
    client = EndOfLifeClient()
    mock_client = AsyncMock()
    client._client = mock_client

    await client.close()

    mock_client.aclose.assert_awaited_once()
    assert client._client is None


@pytest.mark.asyncio
async def test_fetch_multiple_products_reuses_client():
    """Dos llamadas reusan el mismo AsyncClient."""
    client = EndOfLifeClient()
    mock_json = [{"cycle": "1"}]
    mock_resp = _mock_response(json_data=mock_json)

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp) as mock_get:
        await client.fetch_product("ubuntu")
        await client.fetch_product("debian")

    assert mock_get.call_count == 2
    # Solo una instancia de AsyncClient creada (comparten el mismo mock)
    # Verificamos que no se instancio mas de una vez
    with patch("httpx.AsyncClient") as mock_constructor:
        # Ya hay cliente creado, fetch_product no deberia crear otro
        await client.fetch_product("fedora")
        mock_constructor.assert_not_called()
