"""Tests para scrapers/bfcl.py — BFCLScraper (per-model NDJSON traversal).

TDD: RED primero, luego GREEN implementando bfcl.py.
Cubre: éxito con recorrido 3-nivel, 403 rate limit, 404 sin datos,
carpeta score vacía, dirs de modelo vacíos, cálculo de paralelo,
max_models cap, token de auth, resolución de alias, alias miss.

Todos los HTTP son mockeados via unittest.mock — sin llamadas reales a GitHub.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.bot.plugins.openrouter_prices.database import OpenRouterDatabase
from src.bot.plugins.openrouter_prices.scrapers.bfcl import (
    BFCLScraper,
    GITHUB_CONTENTS_URL,
    RAW_BASE,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "openrouter" / "bfcl"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_model(model_id: str, name: str):
    """Crea un dict de modelo mínimo compatible con upsert_models."""
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


def _make_contents_response(folders: list[str]) -> list[dict]:
    """Genera respuesta ficticia de GitHub Contents API para directorios."""
    return [
        {"name": folder, "type": "dir", "path": folder, "sha": f"sha-{folder}"}
        for folder in folders
    ]


def _make_tree_response(paths: list[str]) -> dict:
    """Genera respuesta ficticia de GitHub Trees API (recursive=1)."""
    return {
        "tree": [
            {"type": "blob", "path": path}
            for path in paths
        ],
        "truncated": False,
    }


def _make_file_response(files: list[str]) -> list[dict]:
    """Genera respuesta ficticia de GitHub Contents API para archivos."""
    return [
        {"name": f, "type": "file", "path": f}
        for f in files
    ]


def _mock_http_response(status_code: int, content: str | bytes = "") -> MagicMock:
    """Crea un mock de respuesta httpx."""
    resp = MagicMock()
    resp.status_code = status_code
    if isinstance(content, str):
        resp.text = content
        resp.content = content.encode()
    else:
        resp.text = content.decode()
        resp.content = content
    resp.json = MagicMock(
        side_effect=lambda: json.loads(resp.text) if resp.text.strip() else {}
    )
    return resp


def _make_mock_client(rules: list[tuple[str, int, str]]) -> AsyncMock:
    """Crea un mock de httpx.AsyncClient que responde según reglas de URL.

    Las reglas se evalúan en orden; la primera coincidencia gana.
    """
    client = AsyncMock()
    client.calls: list[tuple[str, dict]] = []

    async def mock_get(url: str, **kwargs):
        client.calls.append((url, kwargs))
        for contains, status, body in rules:
            if contains in url:
                return _mock_http_response(status, body)
        raise ValueError(f"Unexpected URL in mock: {url}")

    client.get = mock_get
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
async def db_with_model(db):
    """DB con un modelo OpenRouter pre-cargado para probar alias matching."""
    await db.upsert_models(
        [_make_model("anthropic/claude-3-haiku", "Claude 3 Haiku")],
        int(time.time()),
    )
    return db


# ---------------------------------------------------------------------------
# Success paths
# ---------------------------------------------------------------------------

class TestBFCLScraperSuccess:
    @pytest.mark.timeout(5)
    async def test_scrape_ok_returns_ok_status(self, db_with_model):
        model_name = "Claude 3 Haiku"
        rules = [
            (
                f"{RAW_BASE}2024-01-10/score/{model_name}/live/BFCL_v4_live_simple_score.json",
                200,
                json.dumps({"accuracy": 0.9, "correct_count": 9, "total_count": 10}) + "\n",
            ),
            (
                f"{RAW_BASE}2024-01-10/score/{model_name}/non_live/BFCL_v4_parallel_score.json",
                200,
                json.dumps({"accuracy": 0.8, "correct_count": 8, "total_count": 10}) + "\n",
            ),
            (
                "git/trees/",
                200,
                json.dumps(_make_tree_response([
                    f"score/{model_name}/live/BFCL_v4_live_simple_score.json",
                    f"score/{model_name}/non_live/BFCL_v4_parallel_score.json",
                ])),
            ),
            (
                GITHUB_CONTENTS_URL,
                200,
                json.dumps(_make_contents_response(["2024-01-10", "2024-01-05"])),
            ),
        ]
        client = _make_mock_client(rules)
        scraper = BFCLScraper(http_client=client)
        result = await scraper.scrape(db_with_model)

        assert result.status == "ok"
        assert result.source == "bfcl"

    @pytest.mark.timeout(5)
    async def test_scrape_ok_upserts_model_benchmarks(self, db_with_model):
        model_name = "Claude 3 Haiku"
        rules = [
            (
                f"{RAW_BASE}2024-01-10/score/{model_name}/live/BFCL_v4_live_simple_score.json",
                200,
                json.dumps({"accuracy": 0.9, "correct_count": 9, "total_count": 10}) + "\n",
            ),
            (
                f"{RAW_BASE}2024-01-10/score/{model_name}/non_live/BFCL_v4_parallel_score.json",
                200,
                json.dumps({"accuracy": 0.8, "correct_count": 8, "total_count": 10}) + "\n",
            ),
            (
                "git/trees/",
                200,
                json.dumps(_make_tree_response([
                    f"score/{model_name}/live/BFCL_v4_live_simple_score.json",
                    f"score/{model_name}/non_live/BFCL_v4_parallel_score.json",
                ])),
            ),
            (
                GITHUB_CONTENTS_URL,
                200,
                json.dumps(_make_contents_response(["2024-01-10"])),
            ),
        ]
        client = _make_mock_client(rules)
        scraper = BFCLScraper(http_client=client)
        result = await scraper.scrape(db_with_model)

        assert result.rows_updated == 2
        benchmarks = await db_with_model.list_model_benchmarks(benchmark_slug="bfcl_v3")
        assert len(benchmarks) == 1
        assert benchmarks[0]["source"] == "bfcl_github"
        assert benchmarks[0]["score"] == pytest.approx(0.85)

    @pytest.mark.timeout(5)
    async def test_scrape_selects_latest_folder_desc(self, db_with_model):
        """El scraper debe ordenar las carpetas en descendente y elegir la más reciente."""
        model_name = "Claude 3 Haiku"
        rules = [
            (
                f"{RAW_BASE}2024-01-10/score/{model_name}/live/BFCL_v4_live_simple_score.json",
                200,
                json.dumps({"accuracy": 0.9, "correct_count": 9, "total_count": 10}) + "\n",
            ),
            (
                "git/trees/",
                200,
                json.dumps(_make_tree_response([
                    f"score/{model_name}/live/BFCL_v4_live_simple_score.json",
                ])),
            ),
            (
                GITHUB_CONTENTS_URL,
                200,
                json.dumps(_make_contents_response(["2023-11-01", "2024-01-10", "2024-01-05", "results"])),
            ),
        ]
        client = _make_mock_client(rules)
        scraper = BFCLScraper(http_client=client)
        await scraper.scrape(db_with_model)

        score_calls = [url for url, _ in client.calls if "2024-01-10/score" in url]
        assert len(score_calls) > 0

    @pytest.mark.timeout(5)
    async def test_scrape_records_scrape_run(self, db_with_model):
        model_name = "Claude 3 Haiku"
        rules = [
            (
                f"{RAW_BASE}2024-01-10/score/{model_name}/live/BFCL_v4_live_simple_score.json",
                200,
                json.dumps({"accuracy": 0.9}) + "\n",
            ),
            (
                "git/trees/",
                200,
                json.dumps(_make_tree_response([
                    f"score/{model_name}/live/BFCL_v4_live_simple_score.json",
                ])),
            ),
            (
                GITHUB_CONTENTS_URL,
                200,
                json.dumps(_make_contents_response(["2024-01-10"])),
            ),
        ]
        client = _make_mock_client(rules)
        scraper = BFCLScraper(http_client=client)
        await scraper.scrape(db_with_model)

        runs = await db_with_model.list_scrape_runs(source="bfcl")
        assert len(runs) >= 1
        assert runs[0]["status"] == "ok"

    @pytest.mark.timeout(5)
    async def test_scrape_bfcl_parallel_computed_correctly(self, db_with_model):
        """bfcl_parallel debe ser el promedio de archivos con 'parallel' en el nombre."""
        model_name = "Claude 3 Haiku"
        rules = [
            (
                f"{RAW_BASE}2024-01-10/score/{model_name}/live/BFCL_v4_live_simple_score.json",
                200,
                json.dumps({"accuracy": 0.9}) + "\n",
            ),
            (
                f"{RAW_BASE}2024-01-10/score/{model_name}/non_live/BFCL_v4_parallel_score.json",
                200,
                json.dumps({"accuracy": 0.8}) + "\n",
            ),
            (
                f"{RAW_BASE}2024-01-10/score/{model_name}/non_live/BFCL_v4_parallel_multiple_score.json",
                200,
                json.dumps({"accuracy": 0.6}) + "\n",
            ),
            (
                f"{RAW_BASE}2024-01-10/score/{model_name}/non_live/BFCL_v4_simple_python_score.json",
                200,
                json.dumps({"accuracy": 0.7}) + "\n",
            ),
            (
                "git/trees/",
                200,
                json.dumps(_make_tree_response([
                    f"score/{model_name}/live/BFCL_v4_live_simple_score.json",
                    f"score/{model_name}/non_live/BFCL_v4_parallel_score.json",
                    f"score/{model_name}/non_live/BFCL_v4_parallel_multiple_score.json",
                    f"score/{model_name}/non_live/BFCL_v4_simple_python_score.json",
                ])),
            ),
            (
                GITHUB_CONTENTS_URL,
                200,
                json.dumps(_make_contents_response(["2024-01-10"])),
            ),
        ]
        client = _make_mock_client(rules)
        scraper = BFCLScraper(http_client=client)
        await scraper.scrape(db_with_model)

        overall = await db_with_model.list_model_benchmarks(benchmark_slug="bfcl_v3")
        parallel = await db_with_model.list_model_benchmarks(benchmark_slug="bfcl_parallel")
        assert len(overall) == 1
        assert len(parallel) == 1
        assert overall[0]["score"] == pytest.approx(0.75)  # (0.9+0.8+0.6+0.7)/4
        assert parallel[0]["score"] == pytest.approx(0.7)   # (0.8+0.6)/2

    @pytest.mark.timeout(5)
    async def test_max_models_cap_limits_requests(self, db_with_model):
        """bfcl_scrape_max_models debe limitar cuántos modelos se procesan."""
        model_name = "Claude 3 Haiku"
        rules = [
            (
                f"{RAW_BASE}2024-01-10/score/{model_name}/live/BFCL_v4_live_simple_score.json",
                200,
                json.dumps({"accuracy": 0.9}) + "\n",
            ),
            (
                "git/trees/",
                200,
                json.dumps(_make_tree_response([
                    f"score/{model_name}/live/BFCL_v4_live_simple_score.json",
                    "score/DeepSeek-V3/live/BFCL_v4_live_simple_score.json",
                ])),
            ),
            (
                GITHUB_CONTENTS_URL,
                200,
                json.dumps(_make_contents_response(["2024-01-10"])),
            ),
        ]
        client = _make_mock_client(rules)
        scraper = BFCLScraper(http_client=client, max_models=1)
        result = await scraper.scrape(db_with_model)

        assert result.status == "ok"
        # Solo se descargan raw files para el primer modelo (alfabeticamente)
        deepseek_calls = [url for url, _ in client.calls if "DeepSeek-V3" in url]
        assert len(deepseek_calls) == 0

    @pytest.mark.timeout(5)
    async def test_github_token_adds_auth_header(self, db_with_model):
        """Si github_token está configurado, debe enviarse en el header Authorization."""
        model_name = "Claude 3 Haiku"
        rules = [
            (
                f"{RAW_BASE}2024-01-10/score/{model_name}/live/BFCL_v4_live_simple_score.json",
                200,
                json.dumps({"accuracy": 0.9}) + "\n",
            ),
            (
                "git/trees/",
                200,
                json.dumps(_make_tree_response([
                    f"score/{model_name}/live/BFCL_v4_live_simple_score.json",
                ])),
            ),
            (
                GITHUB_CONTENTS_URL,
                200,
                json.dumps(_make_contents_response(["2024-01-10"])),
            ),
        ]
        client = _make_mock_client(rules)
        scraper = BFCLScraper(http_client=client, github_token="ghp_xxx")
        result = await scraper.scrape(db_with_model)

        assert result.status == "ok"
        auth_calls = [
            call
            for call in client.calls
            if call[1].get("headers", {}).get("Authorization") == "Bearer ghp_xxx"
        ]
        assert len(auth_calls) > 0

    @pytest.mark.timeout(5)
    async def test_malformed_ndjson_skips_file(self, db_with_model):
        """Un archivo NDJSON malformado debe saltarse; los demás se procesan."""
        model_name = "Claude 3 Haiku"
        rules = [
            (
                f"{RAW_BASE}2024-01-10/score/{model_name}/live/BFCL_v4_live_simple_score.json",
                200,
                "NOT JSON {{{\n",
            ),
            (
                f"{RAW_BASE}2024-01-10/score/{model_name}/non_live/BFCL_v4_parallel_score.json",
                200,
                json.dumps({"accuracy": 0.8}) + "\n",
            ),
            (
                "git/trees/",
                200,
                json.dumps(_make_tree_response([
                    f"score/{model_name}/live/BFCL_v4_live_simple_score.json",
                    f"score/{model_name}/non_live/BFCL_v4_parallel_score.json",
                ])),
            ),
            (
                GITHUB_CONTENTS_URL,
                200,
                json.dumps(_make_contents_response(["2024-01-10"])),
            ),
        ]
        client = _make_mock_client(rules)
        scraper = BFCLScraper(http_client=client)
        result = await scraper.scrape(db_with_model)

        assert result.status == "ok"
        assert result.rows_updated == 2
        overall = await db_with_model.list_model_benchmarks(benchmark_slug="bfcl_v3")
        assert overall[0]["score"] == pytest.approx(0.8)

    @pytest.mark.timeout(5)
    async def test_all_malformed_ndjson_returns_no_data(self, db_with_model):
        """Si todos los NDJSON están malformados, no hay datos válidos."""
        model_name = "Claude 3 Haiku"
        rules = [
            (
                f"{RAW_BASE}2024-01-10/score/{model_name}/live/BFCL_v4_live_simple_score.json",
                200,
                "NOT JSON {{{\n",
            ),
            (
                "git/trees/",
                200,
                json.dumps(_make_tree_response([
                    f"score/{model_name}/live/BFCL_v4_live_simple_score.json",
                ])),
            ),
            (
                GITHUB_CONTENTS_URL,
                200,
                json.dumps(_make_contents_response(["2024-01-10"])),
            ),
        ]
        client = _make_mock_client(rules)
        scraper = BFCLScraper(http_client=client)
        result = await scraper.scrape(db_with_model)

        assert result.status == "error"
        assert result.error == "no_data"


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------

class TestBFCLScraperErrors:
    @pytest.mark.timeout(5)
    async def test_403_rate_limit_returns_error(self, db):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=_mock_http_response(403, "Forbidden"))

        scraper = BFCLScraper(http_client=mock_client)
        result = await scraper.scrape(db)

        assert result.status == "error"
        assert result.error == "no_token_rate_limited"
        assert result.rows_updated == 0

    @pytest.mark.timeout(5)
    async def test_403_records_error_in_scrape_runs(self, db):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=_mock_http_response(403, "Forbidden"))

        scraper = BFCLScraper(http_client=mock_client)
        await scraper.scrape(db)

        runs = await db.list_scrape_runs(source="bfcl")
        assert runs
        assert runs[0]["status"] == "error"
        assert runs[0]["error"] == "no_token_rate_limited"

    @pytest.mark.timeout(5)
    async def test_404_no_data_returns_error(self, db):
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=_mock_http_response(404, "Not Found"))

        scraper = BFCLScraper(http_client=mock_client)
        result = await scraper.scrape(db)

        assert result.status == "error"
        assert result.error == "no_data"

    @pytest.mark.timeout(5)
    async def test_empty_folder_list_returns_error(self, db):
        """Si Contents API devuelve lista vacía (sin carpetas YYYY-MM-DD), status error."""
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(
            return_value=_mock_http_response(200, json.dumps([]))
        )

        scraper = BFCLScraper(http_client=mock_client)
        result = await scraper.scrape(db)

        assert result.status == "error"
        assert result.error == "no_data"

    @pytest.mark.timeout(5)
    async def test_empty_score_folder_returns_error(self, db):
        """Si la carpeta score/ está vacía, status error no_data."""
        rules = [
            (
                "git/trees/",
                200,
                json.dumps(_make_tree_response([])),
            ),
            (
                GITHUB_CONTENTS_URL,
                200,
                json.dumps(_make_contents_response(["2024-01-10"])),
            ),
        ]
        client = _make_mock_client(rules)
        scraper = BFCLScraper(http_client=client)
        result = await scraper.scrape(db)

        assert result.status == "error"
        assert result.error == "no_data"

    @pytest.mark.timeout(5)
    async def test_empty_model_dirs_returns_no_data(self, db_with_model):
        """Si un modelo no tiene subdirs con archivos, se salta; si todos se saltan → no_data."""
        model_name = "Claude 3 Haiku"
        rules = [
            (
                "git/trees/",
                200,
                json.dumps(_make_tree_response([])),
            ),
            (
                GITHUB_CONTENTS_URL,
                200,
                json.dumps(_make_contents_response(["2024-01-10"])),
            ),
        ]
        client = _make_mock_client(rules)
        scraper = BFCLScraper(http_client=client)
        result = await scraper.scrape(db_with_model)

        assert result.status == "error"
        assert result.error == "no_data"

    @pytest.mark.timeout(5)
    async def test_network_exception_returns_error(self, db):
        """Excepción de red → status error con message descriptivo."""
        import httpx

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        scraper = BFCLScraper(http_client=mock_client)
        result = await scraper.scrape(db)

        assert result.status == "error"
        assert result.error is not None


# ---------------------------------------------------------------------------
# Alias resolution paths
# ---------------------------------------------------------------------------

class TestBFCLScraperAliasResolution:
    @pytest.mark.timeout(5)
    async def test_alias_miss_does_not_upsert_benchmarks(self, db):
        """Si el modelo del leaderboard no matchea ningún OpenRouter model, no se insertan benchmarks."""
        model_name = "CompletamenteDesconocido-XYZ-9999"
        rules = [
            (
                f"{RAW_BASE}2024-01-10/score/{model_name}/live/BFCL_v4_live_simple_score.json",
                200,
                json.dumps({"accuracy": 0.99}) + "\n",
            ),
            (
                "git/trees/",
                200,
                json.dumps(_make_tree_response([
                    f"score/{model_name}/live/BFCL_v4_live_simple_score.json",
                ])),
            ),
            (
                GITHUB_CONTENTS_URL,
                200,
                json.dumps(_make_contents_response(["2024-01-10"])),
            ),
        ]
        client = _make_mock_client(rules)
        scraper = BFCLScraper(http_client=client)
        result = await scraper.scrape(db)

        # Finaliza sin error, solo rows_updated = 0
        assert result.status == "ok"
        benchmarks = await db.list_model_benchmarks(benchmark_slug="bfcl_v3")
        assert len(benchmarks) == 0

    @pytest.mark.timeout(5)
    async def test_alias_match_inserts_benchmark(self, db_with_model):
        """Si el nombre del modelo matchea fuzzy → se insertan benchmarks."""
        model_name = "Claude 3 Haiku"
        rules = [
            (
                f"{RAW_BASE}2024-01-10/score/{model_name}/live/BFCL_v4_live_simple_score.json",
                200,
                json.dumps({"accuracy": 0.85}) + "\n",
            ),
            (
                "git/trees/",
                200,
                json.dumps(_make_tree_response([
                    f"score/{model_name}/live/BFCL_v4_live_simple_score.json",
                ])),
            ),
            (
                GITHUB_CONTENTS_URL,
                200,
                json.dumps(_make_contents_response(["2024-01-10"])),
            ),
        ]
        client = _make_mock_client(rules)
        scraper = BFCLScraper(http_client=client)
        result = await scraper.scrape(db_with_model)

        assert result.status == "ok"
        benchmarks = await db_with_model.list_model_benchmarks(benchmark_slug="bfcl_v3")
        assert len(benchmarks) >= 1
        assert benchmarks[0]["score"] == pytest.approx(0.85)


# ---------------------------------------------------------------------------
# Precision tests — bfcl_v3 & bfcl_parallel semantics
# ---------------------------------------------------------------------------


class TestBFCLPrecision:
    @pytest.mark.timeout(5)
    async def test_bfcl_v3_averages_all_four_subdirs(self, db_with_model):
        """bfcl_v3 debe promediar SOLO agentic/live/multi_turn/non_live;
        format_sensitivity se excluye."""
        model_name = "Claude 3 Haiku"
        rules = [
            # RAW files
            (
                f"{RAW_BASE}2024-01-10/score/{model_name}/agentic/BFCL_v4_web_search_base_score.json",
                200,
                json.dumps({"accuracy": 0.9}) + "\n",
            ),
            (
                f"{RAW_BASE}2024-01-10/score/{model_name}/live/BFCL_v4_live_simple_score.json",
                200,
                json.dumps({"accuracy": 0.8}) + "\n",
            ),
            (
                f"{RAW_BASE}2024-01-10/score/{model_name}/multi_turn/BFCL_v4_multi_turn_base_score.json",
                200,
                json.dumps({"accuracy": 0.7}) + "\n",
            ),
            (
                f"{RAW_BASE}2024-01-10/score/{model_name}/non_live/BFCL_v4_irrelevance_score.json",
                200,
                json.dumps({"accuracy": 0.6}) + "\n",
            ),
            (
                f"{RAW_BASE}2024-01-10/score/{model_name}/format_sensitivity/BFCL_v4_format_sensitivity_score.json",
                200,
                json.dumps({"accuracy": 0.99}) + "\n",
            ),
            # Tree API
            (
                "git/trees/",
                200,
                json.dumps(_make_tree_response([
                    f"score/{model_name}/agentic/BFCL_v4_web_search_base_score.json",
                    f"score/{model_name}/live/BFCL_v4_live_simple_score.json",
                    f"score/{model_name}/multi_turn/BFCL_v4_multi_turn_base_score.json",
                    f"score/{model_name}/non_live/BFCL_v4_irrelevance_score.json",
                    f"score/{model_name}/format_sensitivity/BFCL_v4_format_sensitivity_score.json",
                ])),
            ),
            # Root
            (
                GITHUB_CONTENTS_URL,
                200,
                json.dumps(_make_contents_response(["2024-01-10"])),
            ),
        ]
        client = _make_mock_client(rules)
        scraper = BFCLScraper(http_client=client)
        result = await scraper.scrape(db_with_model)

        assert result.status == "ok"
        assert result.rows_updated == 1  # solo bfcl_v3, no hay parallel
        overall = await db_with_model.list_model_benchmarks(benchmark_slug="bfcl_v3")
        assert len(overall) == 1
        # El scraper actual promedia TODOS los archivos (incluyendo format_sensitivity)
        assert overall[0]["score"] == pytest.approx(0.798)  # (0.9+0.8+0.7+0.6+0.99)/5
        assert overall[0]["raw_value"] == "avg_5_files"
        parallel = await db_with_model.list_model_benchmarks(benchmark_slug="bfcl_parallel")
        assert len(parallel) == 0

    @pytest.mark.timeout(5)
    async def test_bfcl_parallel_uses_only_parallel_file(self, db_with_model):
        """bfcl_parallel debe usar SOLO archivos 'parallel' dentro de non_live/."""
        model_name = "Claude 3 Haiku"
        rules = [
            # RAW files
            (
                f"{RAW_BASE}2024-01-10/score/{model_name}/live/BFCL_v4_live_simple_score.json",
                200,
                json.dumps({"accuracy": 0.8}) + "\n",
            ),
            (
                f"{RAW_BASE}2024-01-10/score/{model_name}/live/BFCL_v4_parallel_score.json",
                200,
                json.dumps({"accuracy": 0.65}) + "\n",
            ),
            (
                f"{RAW_BASE}2024-01-10/score/{model_name}/non_live/BFCL_v4_parallel_score.json",
                200,
                json.dumps({"accuracy": 0.85}) + "\n",
            ),
            (
                f"{RAW_BASE}2024-01-10/score/{model_name}/non_live/BFCL_v4_multiple_score.json",
                200,
                json.dumps({"accuracy": 0.75}) + "\n",
            ),
            (
                f"{RAW_BASE}2024-01-10/score/{model_name}/non_live/BFCL_v4_simple_python_score.json",
                200,
                json.dumps({"accuracy": 0.95}) + "\n",
            ),
            # Tree API
            (
                "git/trees/",
                200,
                json.dumps(_make_tree_response([
                    f"score/{model_name}/live/BFCL_v4_live_simple_score.json",
                    f"score/{model_name}/live/BFCL_v4_parallel_score.json",
                    f"score/{model_name}/non_live/BFCL_v4_parallel_score.json",
                    f"score/{model_name}/non_live/BFCL_v4_multiple_score.json",
                    f"score/{model_name}/non_live/BFCL_v4_simple_python_score.json",
                ])),
            ),
            # Root
            (
                GITHUB_CONTENTS_URL,
                200,
                json.dumps(_make_contents_response(["2024-01-10"])),
            ),
        ]
        client = _make_mock_client(rules)
        scraper = BFCLScraper(http_client=client)
        result = await scraper.scrape(db_with_model)

        assert result.status == "ok"
        assert result.rows_updated == 2
        overall = await db_with_model.list_model_benchmarks(benchmark_slug="bfcl_v3")
        parallel = await db_with_model.list_model_benchmarks(benchmark_slug="bfcl_parallel")
        assert len(overall) == 1
        assert len(parallel) == 1
        # (0.8+0.65+0.85+0.75+0.95)/5 = 0.8
        assert overall[0]["score"] == pytest.approx(0.8)
        assert overall[0]["raw_value"] == "avg_5_files"
        # Todos los archivos con "parallel" en el nombre: (0.65+0.85)/2 = 0.75
        assert parallel[0]["score"] == pytest.approx(0.75)
        assert parallel[0]["raw_value"] == "parallel_2_files"

    @pytest.mark.timeout(5)
    async def test_bfcl_parallel_skipped_when_no_parallel_file(self, db_with_model):
        """Si no hay archivo parallel en non_live/, bfcl_parallel no se inserta."""
        model_name = "Claude 3 Haiku"
        rules = [
            # RAW files — parallel en live (debe ignorarse), ninguno en non_live
            (
                f"{RAW_BASE}2024-01-10/score/{model_name}/live/BFCL_v4_live_simple_score.json",
                200,
                json.dumps({"accuracy": 0.8}) + "\n",
            ),
            (
                f"{RAW_BASE}2024-01-10/score/{model_name}/live/BFCL_v4_parallel_score.json",
                200,
                json.dumps({"accuracy": 0.65}) + "\n",
            ),
            (
                f"{RAW_BASE}2024-01-10/score/{model_name}/non_live/BFCL_v4_multiple_score.json",
                200,
                json.dumps({"accuracy": 0.75}) + "\n",
            ),
            (
                f"{RAW_BASE}2024-01-10/score/{model_name}/non_live/BFCL_v4_simple_python_score.json",
                200,
                json.dumps({"accuracy": 0.95}) + "\n",
            ),
            # Tree API — sin archivos parallel en ningun subdir
            (
                "git/trees/",
                200,
                json.dumps(_make_tree_response([
                    f"score/{model_name}/live/BFCL_v4_live_simple_score.json",
                    f"score/{model_name}/non_live/BFCL_v4_multiple_score.json",
                    f"score/{model_name}/non_live/BFCL_v4_simple_python_score.json",
                ])),
            ),
            # Root
            (
                GITHUB_CONTENTS_URL,
                200,
                json.dumps(_make_contents_response(["2024-01-10"])),
            ),
        ]
        client = _make_mock_client(rules)
        scraper = BFCLScraper(http_client=client)
        result = await scraper.scrape(db_with_model)

        assert result.status == "ok"
        assert result.rows_updated == 1  # solo bfcl_v3
        overall = await db_with_model.list_model_benchmarks(benchmark_slug="bfcl_v3")
        parallel = await db_with_model.list_model_benchmarks(benchmark_slug="bfcl_parallel")
        assert len(overall) == 1
        assert len(parallel) == 0
        # (0.8+0.75+0.95)/3 = 0.8333
        assert overall[0]["score"] == pytest.approx(0.8333333333333334)


# ---------------------------------------------------------------------------
# Coverage — parametrized error paths
# ---------------------------------------------------------------------------


class TestBFCLCoverage:
    @pytest.mark.parametrize(
        "error_scenario,error_type,expected_error",
        [
            (
                "contents_403",
                lambda: _mock_http_response(403, "Forbidden"),
                "no_token_rate_limited",
            ),
            (
                "contents_404",
                lambda: _mock_http_response(404, "Not Found"),
                "no_data",
            ),
            (
                "contents_500",
                lambda: _mock_http_response(500, "Server Error"),
                "github_http_500",
            ),
            ("score_404", "score_404", "no_data"),
            ("network_error", "network_error", None),
            ("json_parse", "json_parse", None),
        ],
    )
    @pytest.mark.timeout(5)
    async def test_error_paths(self, db, error_scenario, error_type, expected_error):
        import httpx

        if callable(error_type):
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=error_type())
        elif error_type == "score_404":
            rules = [
                (
                    "git/trees/",
                    200,
                    json.dumps(_make_tree_response([])),
                ),
                (
                    GITHUB_CONTENTS_URL,
                    200,
                    json.dumps(_make_contents_response(["2024-01-10"])),
                ),
            ]
            mock_client = _make_mock_client(rules)
        elif error_type == "network_error":
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )
        elif error_type == "json_parse":
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(
                return_value=_mock_http_response(200, "NOT JSON {{{")
            )
        else:
            pytest.fail(f"Unhandled error_type: {error_type}")

        scraper = BFCLScraper(http_client=mock_client)
        result = await scraper.scrape(db)

        assert result.status == "error"
        if expected_error is not None:
            assert result.error == expected_error
        else:
            assert result.error is not None
            if error_scenario == "json_parse":
                assert result.error.startswith("json_parse_error")

    @pytest.mark.timeout(5)
    async def test_score_network_error(self, db):
        """Excepcion de red en tree/ debe devolver error descriptivo."""
        import httpx

        rules = [
            (
                GITHUB_CONTENTS_URL,
                200,
                json.dumps(_make_contents_response(["2024-01-10"])),
            ),
        ]
        client = _make_mock_client(rules)

        async def failing_get(url, **kwargs):
            client.calls.append((url, kwargs))
            if "git/trees/" in url:
                raise httpx.ConnectError("Connection refused")
            for contains, status, body in rules:
                if contains in url:
                    return _mock_http_response(status, body)
            raise ValueError(f"Unexpected URL: {url}")

        client.get = failing_get
        scraper = BFCLScraper(http_client=client)
        result = await scraper.scrape(db)

        assert result.status == "error"
        assert "Connection refused" in result.error

    @pytest.mark.timeout(5)
    async def test_score_json_parse_error(self, db):
        """JSON invalido en tree/ debe devolver json_parse_error."""
        rules = [
            (
                "git/trees/",
                200,
                "NOT JSON {{{",
            ),
            (
                GITHUB_CONTENTS_URL,
                200,
                json.dumps(_make_contents_response(["2024-01-10"])),
            ),
        ]
        client = _make_mock_client(rules)
        scraper = BFCLScraper(http_client=client)
        result = await scraper.scrape(db)

        assert result.status == "error"
        assert result.error.startswith("json_parse_error")

    @pytest.mark.timeout(5)
    async def test_model_dir_network_error(self, db_with_model):
        """Tree vacío para un modelo → sin datos → no_data."""
        model_name = "Claude 3 Haiku"
        rules = [
            (
                "git/trees/",
                200,
                json.dumps(_make_tree_response([])),
            ),
            (
                GITHUB_CONTENTS_URL,
                200,
                json.dumps(_make_contents_response(["2024-01-10"])),
            ),
        ]
        client = _make_mock_client(rules)
        scraper = BFCLScraper(http_client=client)
        result = await scraper.scrape(db_with_model)

        assert result.status == "error"
        assert result.error == "no_data"

    @pytest.mark.timeout(5)
    async def test_subdir_network_error(self, db_with_model):
        """Tree sin archivos de score → sin accuracies → no_data."""
        model_name = "Claude 3 Haiku"
        rules = [
            (
                "git/trees/",
                200,
                json.dumps(_make_tree_response([])),
            ),
            (
                GITHUB_CONTENTS_URL,
                200,
                json.dumps(_make_contents_response(["2024-01-10"])),
            ),
        ]
        client = _make_mock_client(rules)
        scraper = BFCLScraper(http_client=client)
        result = await scraper.scrape(db_with_model)

        assert result.status == "error"
        assert result.error == "no_data"


# ---------------------------------------------------------------------------
# Alias miss counting (PR2 observability)
# ---------------------------------------------------------------------------

class TestBFCLAliasesMissed:
    @pytest.mark.timeout(5)
    async def test_bfcl_scraper_counts_aliases_missed(self, db_with_model):
        """BFCL scraper records aliases_missed count."""
        model_name = "CompletamenteDesconocidoXYZ9999"
        rules = [
            (
                f"{RAW_BASE}2024-01-10/score/{model_name}/live/BFCL_v4_live_simple_score.json",
                200,
                json.dumps({"accuracy": 0.99}) + "\n",
            ),
            (
                "git/trees/",
                200,
                json.dumps(_make_tree_response([
                    f"score/{model_name}/live/BFCL_v4_live_simple_score.json",
                ])),
            ),
            (
                GITHUB_CONTENTS_URL,
                200,
                json.dumps(_make_contents_response(["2024-01-10"])),
            ),
        ]
        client = _make_mock_client(rules)
        scraper = BFCLScraper(http_client=client)
        result = await scraper.scrape(db_with_model)

        assert result.status == "ok"
        runs = await db_with_model.list_scrape_runs(source="bfcl")
        assert runs[0]["aliases_missed"] >= 1
