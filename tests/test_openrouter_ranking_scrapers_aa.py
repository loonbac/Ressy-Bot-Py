"""Tests para ArtificialAnalysisScraper — API oficial de Artificial Analysis.

TDD: RED primero, luego GREEN implementando artificial_analysis.py.
Inyeccion de dependencia via http_client — sin Playwright en ningun test.

Cubre: exito, extraccion de modelos, mapeo de benchmarks, resolucion de alias,
       modelos desconocidos, datos vacios, errores HTTP, registro en scrape_runs.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from src.bot.plugins.openrouter_prices.database import OpenRouterDatabase
from src.bot.plugins.openrouter_prices.scrapers.artificial_analysis import (
    ArtificialAnalysisScraper,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "openrouter" / "aa"

# A non-empty key so the scraper actually performs the (mocked) HTTP call.
# The mock client ignores the key value entirely.
VALID_KEY = "aa_test_key"


def _load_fixture() -> dict:
    with open(FIXTURES_DIR / "api_response.json") as f:
        return json.load(f)


def _make_model(model_id: str, name: str) -> dict:
    return {
        "id": model_id,
        "name": name,
        "description": "",
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


def _make_mock_response(json_data: dict | None = None, status_code: int = 200) -> MagicMock:
    """Crea un mock de respuesta httpx con .json() y raise_for_status()."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json = MagicMock(return_value=json_data)
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"{status_code} Error",
            request=MagicMock(),
            response=resp,
        )
    return resp


def _make_mock_client(response: MagicMock) -> AsyncMock:
    """Crea un mock de httpx.AsyncClient que retorna la respuesta dada."""
    client = AsyncMock(spec=httpx.AsyncClient)
    client.get = AsyncMock(return_value=response)
    client.aclose = AsyncMock()
    client.is_closed = False
    return client


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def db():
    database = OpenRouterDatabase(":memory:")
    await database.connect()
    yield database
    await database.close()


@pytest.fixture
async def db_with_models(db):
    await db.upsert_models(
        [
            _make_model("anthropic/claude-3-haiku", "Claude 3 Haiku"),
            _make_model("openai/gpt-4o", "GPT-4o"),
            _make_model("deepseek/deepseek-v3", "DeepSeek V3"),
            _make_model("meta/llama-3-1-405b", "Llama 3.1 405B"),
        ],
        int(time.time()),
    )
    return db


# ---------------------------------------------------------------------------
# 1. Success path
# ---------------------------------------------------------------------------

class TestAAScrapeSuccess:
    @pytest.mark.timeout(5)
    async def test_scrape_returns_ok_status(self, db_with_models):
        fixture = _load_fixture()
        resp = _make_mock_response(fixture)
        client = _make_mock_client(resp)

        scraper = ArtificialAnalysisScraper(http_client=client, api_key=VALID_KEY)
        result = await scraper.scrape(db_with_models)

        assert result.status == "ok"
        assert result.source == "artificial_analysis"
        assert result.rows_updated > 0

    @pytest.mark.timeout(5)
    async def test_scrape_upserts_ifbench(self, db_with_models):
        fixture = _load_fixture()
        resp = _make_mock_response(fixture)
        client = _make_mock_client(resp)

        scraper = ArtificialAnalysisScraper(http_client=client, api_key=VALID_KEY)
        await scraper.scrape(db_with_models)

        benchmarks = await db_with_models.list_model_benchmarks(
            benchmark_slug="ifbench"
        )
        assert len(benchmarks) >= 1
        assert benchmarks[0]["source"] == "artificial_analysis"
        assert benchmarks[0]["score"] == 0.785

    @pytest.mark.timeout(5)
    async def test_scrape_upserts_tau2_telecom(self, db_with_models):
        fixture = _load_fixture()
        resp = _make_mock_response(fixture)
        client = _make_mock_client(resp)

        scraper = ArtificialAnalysisScraper(http_client=client, api_key=VALID_KEY)
        await scraper.scrape(db_with_models)

        benchmarks = await db_with_models.list_model_benchmarks(
            benchmark_slug="tau2_telecom"
        )
        assert len(benchmarks) >= 1
        b = benchmarks[0]
        assert b["source"] == "artificial_analysis"
        assert isinstance(b["score"], float)

    @pytest.mark.timeout(5)
    async def test_scrape_upserts_aa_intelligence_index(self, db_with_models):
        fixture = _load_fixture()
        resp = _make_mock_response(fixture)
        client = _make_mock_client(resp)

        scraper = ArtificialAnalysisScraper(http_client=client, api_key=VALID_KEY)
        await scraper.scrape(db_with_models)

        benchmarks = await db_with_models.list_model_benchmarks(
            benchmark_slug="aa_intelligence_index"
        )
        assert len(benchmarks) >= 1
        b = benchmarks[0]
        assert b["source"] == "artificial_analysis"
        assert isinstance(b["score"], float)

    @pytest.mark.timeout(5)
    async def test_scrape_records_scrape_run(self, db_with_models):
        fixture = _load_fixture()
        resp = _make_mock_response(fixture)
        client = _make_mock_client(resp)

        scraper = ArtificialAnalysisScraper(http_client=client, api_key=VALID_KEY)
        await scraper.scrape(db_with_models)

        runs = await db_with_models.list_scrape_runs(source="artificial_analysis")
        assert runs
        assert runs[0]["status"] == "ok"

    @pytest.mark.timeout(5)
    async def test_multiple_rows_processed(self, db_with_models):
        fixture = _load_fixture()
        resp = _make_mock_response(fixture)
        client = _make_mock_client(resp)

        scraper = ArtificialAnalysisScraper(http_client=client, api_key=VALID_KEY)
        result = await scraper.scrape(db_with_models)

        assert result.rows_updated >= 3

    @pytest.mark.timeout(5)
    async def test_client_not_closed_when_injected(self, db_with_models):
        fixture = _load_fixture()
        resp = _make_mock_response(fixture)
        client = _make_mock_client(resp)

        scraper = ArtificialAnalysisScraper(http_client=client, api_key=VALID_KEY)
        await scraper.scrape(db_with_models)

        client.aclose.assert_not_called()


# ---------------------------------------------------------------------------
# 2. Benchmark mapping
# ---------------------------------------------------------------------------

class TestAABenchmarkMapping:
    @pytest.mark.timeout(5)
    async def test_ifbench_mapped_correctly(self, db_with_models):
        fixture = _load_fixture()
        resp = _make_mock_response(fixture)
        client = _make_mock_client(resp)

        scraper = ArtificialAnalysisScraper(http_client=client, api_key=VALID_KEY)
        await scraper.scrape(db_with_models)

        benchmarks = await db_with_models.list_model_benchmarks(
            benchmark_slug="ifbench"
        )
        # Claude 3 Haiku in fixture has ifbench=0.785
        claude = [b for b in benchmarks if b["model_id"] == "anthropic/claude-3-haiku"]
        assert len(claude) == 1
        assert claude[0]["score"] == 0.785

    @pytest.mark.timeout(5)
    async def test_tau2_mapped_to_tau2_telecom(self, db_with_models):
        fixture = _load_fixture()
        resp = _make_mock_response(fixture)
        client = _make_mock_client(resp)

        scraper = ArtificialAnalysisScraper(http_client=client, api_key=VALID_KEY)
        await scraper.scrape(db_with_models)

        benchmarks = await db_with_models.list_model_benchmarks(
            benchmark_slug="tau2_telecom"
        )
        claude = [b for b in benchmarks if b["model_id"] == "anthropic/claude-3-haiku"]
        assert len(claude) == 1
        assert claude[0]["score"] == 0.652

    @pytest.mark.timeout(5)
    async def test_intelligence_index_mapped_to_aa_intelligence_index(self, db_with_models):
        fixture = _load_fixture()
        resp = _make_mock_response(fixture)
        client = _make_mock_client(resp)

        scraper = ArtificialAnalysisScraper(http_client=client, api_key=VALID_KEY)
        await scraper.scrape(db_with_models)

        benchmarks = await db_with_models.list_model_benchmarks(
            benchmark_slug="aa_intelligence_index"
        )
        claude = [b for b in benchmarks if b["model_id"] == "anthropic/claude-3-haiku"]
        assert len(claude) == 1
        assert claude[0]["score"] == 44.0


# ---------------------------------------------------------------------------
# 3. Null / edge case evaluations
# ---------------------------------------------------------------------------

class TestAANullEvaluations:
    @pytest.mark.timeout(5)
    async def test_null_benchmark_values_skipped(self, db_with_models):
        """Gemini 1.5 Pro tiene todos los evals en null → no debe upsertar."""
        fixture = _load_fixture()
        resp = _make_mock_response(fixture)
        client = _make_mock_client(resp)

        scraper = ArtificialAnalysisScraper(http_client=client, api_key=VALID_KEY)
        await scraper.scrape(db_with_models)

        # Gemini no esta en db_with_models, pero si estuviera, nulls se saltan.
        # Verificamos que no hay crash y el status es ok.
        benchmarks = await db_with_models.list_model_benchmarks(
            benchmark_slug="ifbench"
        )
        # Solo Claude, GPT-4o, Llama tienen ifbench no-null
        assert len(benchmarks) == 3

    @pytest.mark.timeout(5)
    async def test_empty_evaluations_object_skipped(self, db_with_models):
        """DeepSeek V3 tiene evaluations={} → no debe upsertar benchmarks."""
        fixture = _load_fixture()
        resp = _make_mock_response(fixture)
        client = _make_mock_client(resp)

        scraper = ArtificialAnalysisScraper(http_client=client, api_key=VALID_KEY)
        result = await scraper.scrape(db_with_models)

        assert result.status == "ok"
        # DeepSeek esta en db pero sin evals → no aporta rows
        deepseek = await db_with_models.list_model_benchmarks(
            benchmark_slug="ifbench"
        )
        ids = {b["model_id"] for b in deepseek}
        assert "deepseek/deepseek-v3" not in ids

    @pytest.mark.timeout(5)
    async def test_empty_response_data_returns_zero_rows(self, db):
        resp = _make_mock_response({"data": []})
        client = _make_mock_client(resp)

        scraper = ArtificialAnalysisScraper(http_client=client, api_key=VALID_KEY)
        result = await scraper.scrape(db)

        assert result.status == "ok"
        assert result.rows_updated == 0

    @pytest.mark.timeout(5)
    async def test_null_pricing_still_processes_benchmarks(self, db_with_models):
        """DeepSeek V3 tiene pricing=null pero evaluations vacio;
        usamos Llama 3.1 que tiene evals y pricing normal."""
        fixture = _load_fixture()
        resp = _make_mock_response(fixture)
        client = _make_mock_client(resp)

        scraper = ArtificialAnalysisScraper(http_client=client, api_key=VALID_KEY)
        result = await scraper.scrape(db_with_models)

        assert result.status == "ok"
        assert result.rows_updated > 0


# ---------------------------------------------------------------------------
# 4. Alias resolution
# ---------------------------------------------------------------------------

class TestAAAliasResolution:
    @pytest.mark.timeout(5)
    async def test_known_model_resolves_via_fuzzy_match(self, db_with_models):
        fixture = _load_fixture()
        resp = _make_mock_response(fixture)
        client = _make_mock_client(resp)

        scraper = ArtificialAnalysisScraper(http_client=client, api_key=VALID_KEY)
        result = await scraper.scrape(db_with_models)

        assert result.status == "ok"
        assert result.rows_updated >= 1

    @pytest.mark.timeout(5)
    async def test_unknown_model_no_benchmark_upsert(self, db):
        await db.upsert_models(
            [_make_model("vendor/model-a", "Model A")],
            int(time.time()),
        )
        fixture = _load_fixture()
        resp = _make_mock_response(fixture)
        client = _make_mock_client(resp)

        scraper = ArtificialAnalysisScraper(http_client=client, api_key=VALID_KEY)
        result = await scraper.scrape(db)

        assert result.status == "ok"
        benchmarks = await db.list_model_benchmarks(benchmark_slug="ifbench")
        assert len(benchmarks) == 0


# ---------------------------------------------------------------------------
# 5. HTTP errors
# ---------------------------------------------------------------------------

class TestAAHTTPError:
    @pytest.mark.timeout(5)
    async def test_http_401_returns_error(self, db):
        resp = _make_mock_response(status_code=401)
        client = _make_mock_client(resp)

        scraper = ArtificialAnalysisScraper(http_client=client, api_key=VALID_KEY)
        result = await scraper.scrape(db)

        assert result.status == "error"
        # 401 is normalized to the canonical token the dashboard warning
        # logic (api.py) matches against to surface "Clave API de AA faltante".
        assert result.error == "unauthorized"

    @pytest.mark.timeout(5)
    async def test_http_403_normalized_to_unauthorized(self, db):
        resp = _make_mock_response(status_code=403)
        client = _make_mock_client(resp)

        scraper = ArtificialAnalysisScraper(http_client=client, api_key=VALID_KEY)
        result = await scraper.scrape(db)

        assert result.status == "error"
        assert result.error == "unauthorized"

    @pytest.mark.timeout(5)
    async def test_http_429_returns_error_with_message(self, db):
        resp = _make_mock_response(status_code=429)
        client = _make_mock_client(resp)

        scraper = ArtificialAnalysisScraper(http_client=client, api_key=VALID_KEY)
        result = await scraper.scrape(db)

        assert result.status == "error"
        assert "429" in result.error or "rate" in result.error.lower() or "Too Many Requests" in result.error

    @pytest.mark.timeout(5)
    async def test_http_500_returns_error(self, db):
        resp = _make_mock_response(status_code=500)
        client = _make_mock_client(resp)

        scraper = ArtificialAnalysisScraper(http_client=client, api_key=VALID_KEY)
        result = await scraper.scrape(db)

        assert result.status == "error"


# ---------------------------------------------------------------------------
# 6. Regression — old interface removed
# ---------------------------------------------------------------------------

class TestAARegression:
    @pytest.mark.timeout(5)
    def test_old_page_factory_interface_removed(self):
        with pytest.raises(TypeError):
            ArtificialAnalysisScraper(page_factory=lambda: None)

    @pytest.mark.timeout(5)
    def test_no_hardcoded_api_key_constant(self):
        """The leaked/revoked hardcoded key must not live in the source.

        Regression for prod 401: API_KEY = "aa_Pau..." was committed and
        later revoked by Artificial Analysis. There must be NO class-level
        credential fallback — the key comes only from config.
        """
        assert not hasattr(ArtificialAnalysisScraper, "API_KEY")


# ---------------------------------------------------------------------------
# 8. Missing / blank API key — no doomed network call, clear error token
# ---------------------------------------------------------------------------

class TestAAMissingKey:
    @pytest.mark.timeout(5)
    async def test_no_api_key_returns_unauthorized_without_http_call(self, db):
        """No key configured → short-circuit before any HTTP request."""
        resp = _make_mock_response({"data": []})
        client = _make_mock_client(resp)

        scraper = ArtificialAnalysisScraper(http_client=client)
        result = await scraper.scrape(db)

        assert result.status == "error"
        assert result.error == "unauthorized"
        client.get.assert_not_called()

    @pytest.mark.timeout(5)
    async def test_empty_string_key_treated_as_missing(self, db):
        resp = _make_mock_response({"data": []})
        client = _make_mock_client(resp)

        scraper = ArtificialAnalysisScraper(http_client=client, api_key="")
        result = await scraper.scrape(db)

        assert result.status == "error"
        assert result.error == "unauthorized"
        client.get.assert_not_called()

    @pytest.mark.timeout(5)
    async def test_whitespace_key_treated_as_missing(self, db):
        resp = _make_mock_response({"data": []})
        client = _make_mock_client(resp)

        scraper = ArtificialAnalysisScraper(http_client=client, api_key="   ")
        result = await scraper.scrape(db)

        assert result.status == "error"
        assert result.error == "unauthorized"
        client.get.assert_not_called()

    @pytest.mark.timeout(5)
    async def test_missing_key_still_records_scrape_run(self, db):
        """The failed run must be persisted so the dashboard health/warning
        logic (api.py) can surface 'aa_api_key_missing'."""
        scraper = ArtificialAnalysisScraper(api_key="")
        await scraper.scrape(db)

        runs = await db.list_scrape_runs(source="artificial_analysis")
        assert runs
        assert runs[0]["status"] == "error"
        assert runs[0]["error"] == "unauthorized"


# ---------------------------------------------------------------------------
# 7. Alias miss counting (PR2 observability)
# ---------------------------------------------------------------------------

class TestAAAliasesMissed:
    @pytest.mark.timeout(5)
    async def test_aa_scraper_counts_aliases_missed(self, db_with_models):
        """AA scraper records aliases_missed count."""
        fixture = _load_fixture()
        # Add some models with names that won't resolve
        fixture["data"].extend([
            {"id": "u1", "name": "UnknownModelXYZ1", "evaluations": {"ifbench": 0.5}},
            {"id": "u2", "name": "UnknownModelXYZ2", "evaluations": {"ifbench": 0.6}},
            {"id": "u3", "name": "UnknownModelXYZ3", "evaluations": {"ifbench": 0.7}},
        ])

        resp = _make_mock_response(fixture)
        client = _make_mock_client(resp)

        scraper = ArtificialAnalysisScraper(http_client=client, api_key=VALID_KEY)
        result = await scraper.scrape(db_with_models)

        # Should have aliases_missed > 0 (the 3 unknown models)
        runs = await db_with_models.list_scrape_runs(source="artificial_analysis")
        assert runs[0]["aliases_missed"] >= 3
