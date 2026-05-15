"""Tests para scripts/probe_aa.py.

TDD: RED primero. Cubre: --dump-fields lista claves de evaluacion con conteos y ejemplos.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

import httpx

from scripts.probe_aa import probe


class _FakeResponse:
    """Respuesta sincrona compatible con httpx.Response para mocks."""

    def __init__(self, payload: dict) -> None:
        self.status_code = 200
        self._payload = payload

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        pass


@pytest.mark.asyncio
async def test_dump_fields_lists_keys_and_counts():
    """Con --dump-fields debe retornar dict con total_models, fields con count/example."""
    fake_response = _FakeResponse({
        "data": [
            {"name": "Model A", "evaluations": {"ifbench": 0.8, "tau2": 0.7}},
            {"name": "Model B", "evaluations": {"ifbench": 0.9, "artificial_analysis_intelligence_index": 44.0}},
            {"name": "Model C", "evaluations": {}},
        ]
    })
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = fake_response

    result = await probe(dump_fields=True, http_client=mock_client)

    assert result is not None
    assert result["total_models"] == 3
    fields = result["fields"]
    assert "ifbench" in fields
    assert fields["ifbench"]["count"] == 2
    assert fields["ifbench"]["example"] == 0.8
    assert "tau2" in fields
    assert fields["tau2"]["count"] == 1
    assert fields["tau2"]["example"] == 0.7
    assert "artificial_analysis_intelligence_index" in fields
    assert fields["artificial_analysis_intelligence_index"]["count"] == 1
    assert fields["artificial_analysis_intelligence_index"]["example"] == 44.0


@pytest.mark.asyncio
async def test_dump_fields_skips_none_values():
    """Las claves con valor None no deben aparecer en el dump."""
    fake_response = _FakeResponse({
        "data": [
            {"name": "Model A", "evaluations": {"ifbench": 0.8, "ruler": None}},
        ]
    })
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = fake_response

    result = await probe(dump_fields=True, http_client=mock_client)

    assert result is not None
    fields = result["fields"]
    assert "ifbench" in fields
    assert fields["ifbench"]["count"] == 1
    assert "ruler" not in fields
