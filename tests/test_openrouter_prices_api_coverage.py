"""Dedicated API coverage tests for openrouter_prices.api.

Strict TDD PR2 matrix. The fixture mirrors obs #895:
- isolated cwd via monkeypatch.chdir(tmp_path)
- patch API boundaries, not HTTP internals
- explicit teardown closes DB and client resources
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

FIXTURE_MODELS = [
    {
        "id": "anthropic/claude-3-haiku",
        "name": "Claude 3 Haiku",
        "description": "Modelo rapido de Anthropic.",
        "created": 1710000000,
        "context_length": 200000,
        "architecture": {
            "modality": "text->text",
            "input_modalities": ["text"],
            "output_modalities": ["text"],
        },
        "pricing": {"prompt": "0.00000025", "completion": "0.00000125"},
        "top_provider": {"context_length": 200000, "max_completion_tokens": 4096, "is_moderated": False},
    },
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
        "pricing": {"prompt": "0.000005", "completion": "0.000015", "image": "0.001"},
        "top_provider": {"context_length": 128000, "max_completion_tokens": 4096, "is_moderated": True},
    },
    {
        "id": "vendor/image-only",
        "name": "Image Only",
        "description": "No acepta texto.",
        "created": 1700000000,
        "context_length": 4096,
        "architecture": {
            "modality": "image->image",
            "input_modalities": ["image"],
            "output_modalities": ["image"],
        },
        "pricing": {"prompt": "0.00001", "completion": "0.00002", "image": "0.04"},
        "top_provider": {"context_length": 4096, "max_completion_tokens": 0, "is_moderated": False},
    },
]


@dataclass
class ApiHarness:
    app: FastAPI
    db: object
    client: AsyncClient
    openrouter_client: AsyncMock
    scheduler: MagicMock


@pytest.fixture
async def api_harness(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    from src.bot.plugins.openrouter_prices.api import router
    from src.bot.plugins.openrouter_prices.client import OpenRouterClient
    from src.bot.plugins.openrouter_prices.database import OpenRouterDatabase

    db = OpenRouterDatabase(str(tmp_path / "openrouter_prices.db"))
    await db.connect()

    openrouter_client = AsyncMock(spec=OpenRouterClient)
    openrouter_client.fetch_models = AsyncMock(return_value=FIXTURE_MODELS)
    openrouter_client.close = AsyncMock()

    scheduler = MagicMock()
    scheduler.is_scraping = MagicMock(return_value=False)
    scheduler.trigger_scrape = AsyncMock(return_value=True)

    app = FastAPI()
    app.state.openrouter_prices_db = db
    app.state.openrouter_prices_client = openrouter_client
    app.state.openrouter_prices_scheduler = scheduler
    app.include_router(router, prefix="/api/plugins/openrouter-prices")

    transport = ASGITransport(app=app)
    client = AsyncClient(transport=transport, base_url="http://test")

    try:
        yield ApiHarness(app, db, client, openrouter_client, scheduler)
    finally:
        await client.aclose()
        await db.close()
        if hasattr(openrouter_client, "close"):
            await openrouter_client.close()


def _model(model_id: str, name: str) -> dict:
    return {
        "id": model_id,
        "name": name,
        "description": "",
        "created": 1_700_000_000,
        "context_length": 4096,
        "architecture": {"input_modalities": ["text"], "output_modalities": ["text"], "modality": "text->text"},
        "pricing": {"prompt": "0.000001", "completion": "0.000002"},
        "top_provider": {"context_length": 4096, "max_completion_tokens": 2048, "is_moderated": False},
    }


async def _seed_aliases_and_runs(db) -> None:
    now = int(time.time())
    await db.upsert_models([_model("vendor/model-a", "Model A"), _model("vendor/model-b", "Model B")], now)
    await db.upsert_alias("vendor/model-a", "Model A", "model-a", 0.9)
    await db.upsert_alias("vendor/model-b", "Model B", "model-b", 0.8)
    await db.record_scrape_run("bfcl", now - 300, now - 250, "ok", None, 4, aliases_missed=1)
    await db.record_scrape_run("artificial_analysis", now - 200, now - 150, "error", "unauthorized", 0, aliases_missed=2)


async def test_get_status_full_shape(api_harness: ApiHarness):
    await _seed_aliases_and_runs(api_harness.db)

    response = await api_harness.client.get("/api/plugins/openrouter-prices/status")

    assert response.status_code == 200
    data = response.json()
    assert set(data) == {
        "enabled", "models_count", "stale_count", "last_fetched_at", "ttl_seconds",
        "last_fetch_status", "last_fetch_error", "scrape_health", "warnings",
    }
    assert data["models_count"] == 2
    assert set(data["scrape_health"]) == {"artificial_analysis", "bfcl"}
    assert data["scrape_health"]["bfcl"]["last_status"] == "ok"
    assert "aa_api_key_missing" in data["warnings"]


async def test_get_config_returns_all_keys(api_harness: ApiHarness):
    response = await api_harness.client.get("/api/plugins/openrouter-prices/config")

    assert response.status_code == 200
    data = response.json()
    assert data == {
        "enabled": True,
        "ttl_seconds": 3600,
        "max_models_command": 10,
        "discord_channel_id": "",
        "ranking_phase": "orchestrator",
        "phases_enabled": ["orchestrator", "sdd_init"],
        "ranking_embed_per_phase": True,
        "aa_api_key": "",
        "github_token": "",
        "stale_threshold_days": 14,
        "bfcl_scrape_max_models": 200,
    }


@pytest.mark.parametrize(
    ("key", "value", "expected_status"),
    [
        ("enabled", "true", 200),
        ("ttl_seconds", "7200", 200),
        ("ttl_seconds", "-1", 422),
        ("max_models_command", "abc", 422),
        ("unknown_key", "x", 400),
        ("aa_api_key", "sk-xxx", 200),
        ("stale_threshold_days", "30", 200),
        ("stale_threshold_days", "0", 422),
        ("phases_enabled", '["orchestrator"]', 200),
        ("phases_enabled", "csv,fake", 422),
    ],
)
async def test_put_config_validates_keys(api_harness: ApiHarness, key: str, value: str, expected_status: int):
    response = await api_harness.client.put("/api/plugins/openrouter-prices/config", json={key: value})

    assert response.status_code == expected_status
    if expected_status == 200:
        stored = await api_harness.db.get_config()
        assert key == "enabled" or stored[key]
    else:
        assert "detail" in response.json()


async def test_get_models_fetches_when_cache_expired_and_falls_back_when_stale(api_harness: ApiHarness):
    await api_harness.client.post("/api/plugins/openrouter-prices/refresh")
    stale_ts = int(time.time()) - 8_000
    await api_harness.db.update_config({"ttl_seconds": "3600"})
    await api_harness.db.set_metadata("last_fetched_at", str(stale_ts))
    api_harness.openrouter_client.fetch_models.side_effect = RuntimeError("refresh failed")

    response = await api_harness.client.get("/api/plugins/openrouter-prices/models?text_only=false&limit=1")

    assert response.status_code == 200
    data = response.json()
    assert data["cached"] is True
    assert data["cache_stale"] is True
    assert data["count"] == 1


async def test_get_models_filters_and_paginates(api_harness: ApiHarness):
    await api_harness.client.post("/api/plugins/openrouter-prices/refresh")

    response = await api_harness.client.get(
        "/api/plugins/openrouter-prices/models?text_only=true&sort=context&direction=desc&limit=2"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["cached"] is True
    assert data["count"] == 2
    assert [m["id"] for m in data["models"]] == ["anthropic/claude-3-haiku", "openai/gpt-4o"]
    assert all("text" in m["input_modalities"] for m in data["models"])


async def test_get_model_found_and_not_found(api_harness: ApiHarness):
    await api_harness.client.post("/api/plugins/openrouter-prices/refresh")

    found = await api_harness.client.get("/api/plugins/openrouter-prices/models/openai%2Fgpt-4o")
    missing = await api_harness.client.get("/api/plugins/openrouter-prices/models/missing")

    assert found.status_code == 200
    assert found.json()["id"] == "openai/gpt-4o"
    assert missing.status_code == 404
    assert "no encontrado" in missing.json()["detail"].lower()


async def test_post_refresh_triggers_fetch(api_harness: ApiHarness):
    response = await api_harness.client.post("/api/plugins/openrouter-prices/refresh")

    assert response.status_code == 200
    assert response.json()["updated"] == len(FIXTURE_MODELS)
    assert response.json()["source"] == "openrouter"
    api_harness.openrouter_client.fetch_models.assert_awaited_once()


async def test_post_refresh_handles_upstream_error(api_harness: ApiHarness):
    await api_harness.db.set_metadata("last_fetched_at", "1700000000")
    api_harness.openrouter_client.fetch_models.side_effect = RuntimeError("upstream down")

    response = await api_harness.client.post("/api/plugins/openrouter-prices/refresh")

    assert response.status_code == 200
    assert response.json()["source"] == "cache_fallback"
    assert response.json()["updated"] == 0
    metadata = await api_harness.db.get_metadata()
    assert metadata["last_fetch_status"] == "error"
    assert metadata["last_fetch_error"] == "upstream down"


@pytest.mark.parametrize(("phase", "expected_status"), [("orchestrator", 200), ("sdd_init", 200), ("explore", 404)])
async def test_get_rankings_phase_valid_and_invalid(api_harness: ApiHarness, phase: str, expected_status: int):
    ranking_data = [{"rank": 1, "model_id": "vendor/model-a", "name": "Model A", "score": 0.95, "breakdown": []}]
    with patch("src.bot.plugins.openrouter_prices.api.compute_ranking_for_phase", new=AsyncMock(return_value=ranking_data)):
        response = await api_harness.client.get(f"/api/plugins/openrouter-prices/rankings/{phase}")

    assert response.status_code == expected_status
    if expected_status == 200:
        assert response.json()["phase"] == phase
        assert response.json()["models"] == ranking_data
    else:
        assert "no encontrado" in response.json()["detail"].lower()


async def test_get_rankings_empty_when_no_data(api_harness: ApiHarness):
    with patch("src.bot.plugins.openrouter_prices.api.compute_ranking_for_phase", new=AsyncMock(return_value=[])):
        response = await api_harness.client.get("/api/plugins/openrouter-prices/rankings/orchestrator")

    assert response.status_code == 200
    assert response.json()["models"] == []


async def test_get_benchmarks_returns_seeded_list(api_harness: ApiHarness):
    response = await api_harness.client.get("/api/plugins/openrouter-prices/benchmarks")

    assert response.status_code == 200
    data = response.json()
    slugs = {item["slug"] for item in data}
    assert {"ifbench", "bfcl_v3", "aa_intelligence_index"}.issubset(slugs)
    assert all(set(item) == {"id", "slug", "display_name", "source", "higher_is_better", "description"} for item in data)


async def test_post_scrape_rejects_missing_scheduler(api_harness: ApiHarness):
    api_harness.app.state.openrouter_prices_scheduler = None

    response = await api_harness.client.post("/api/plugins/openrouter-prices/scrape/bfcl")

    assert response.status_code == 503
    assert "scheduler" in response.json()["detail"].lower()


@pytest.mark.parametrize(("source", "expected_status"), [("artificial_analysis", 200), ("bfcl", 200), ("unknown", 400)])
async def test_post_scrape_source(api_harness: ApiHarness, source: str, expected_status: int):
    response = await api_harness.client.post(f"/api/plugins/openrouter-prices/scrape/{source}")

    assert response.status_code == expected_status
    if expected_status == 200:
        assert response.json() == {"started": True, "source": source}
        api_harness.scheduler.trigger_scrape.assert_awaited_with(source)
    else:
        assert "permitidos" in response.json()["detail"].lower()


async def test_post_scrape_handles_scraper_error(api_harness: ApiHarness):
    api_harness.scheduler.trigger_scrape = AsyncMock(return_value=False)

    response = await api_harness.client.post("/api/plugins/openrouter-prices/scrape/bfcl")

    assert response.status_code == 409
    assert "curso" in response.json()["detail"].lower()


async def test_put_alias_empty_body_returns_existing(api_harness: ApiHarness):
    await api_harness.db.upsert_models([_model("vendor/model-a", "Model A")], int(time.time()))
    await api_harness.db.upsert_alias("vendor/model-a", "Model A", "model-a", 0.9)

    response = await api_harness.client.put("/api/plugins/openrouter-prices/aliases/vendor%2Fmodel-a", json={})

    assert response.status_code == 200
    assert response.json()["artificial_analysis_name"] == "Model A"
    assert response.json()["bfcl_key"] == "model-a"


async def test_get_aliases_pagination(api_harness: ApiHarness):
    await _seed_aliases_and_runs(api_harness.db)

    response = await api_harness.client.get("/api/plugins/openrouter-prices/aliases?limit=1&offset=0")

    assert response.status_code == 200
    data = response.json()
    assert [row["openrouter_id"] for row in data] == ["vendor/model-a", "vendor/model-b"]
    assert all(set(row) == {"openrouter_id", "artificial_analysis_name", "bfcl_key", "match_confidence", "updated_at"} for row in data)


async def test_put_alias_creates_and_overrides(api_harness: ApiHarness):
    now = int(time.time())
    await api_harness.db.upsert_models([_model("vendor/model-a", "Model A")], now)
    await api_harness.db.upsert_alias("vendor/model-a", "Old A", "old-a", 0.2)

    response = await api_harness.client.put(
        "/api/plugins/openrouter-prices/aliases/vendor%2Fmodel-a",
        json={"artificial_analysis_name": "New A", "bfcl_key": "new-a"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["openrouter_id"] == "vendor/model-a"
    assert data["artificial_analysis_name"] == "New A"
    assert data["bfcl_key"] == "new-a"


async def test_put_alias_rejects_unknown_or_id(api_harness: ApiHarness):
    response = await api_harness.client.put(
        "/api/plugins/openrouter-prices/aliases/vendor%2Fmissing",
        json={"artificial_analysis_name": "Missing"},
    )

    assert response.status_code == 404
    assert "no encontrado" in response.json()["detail"].lower()


async def test_put_alias_validates_source(api_harness: ApiHarness):
    await api_harness.db.upsert_models([_model("vendor/model-a", "Model A")], int(time.time()))
    await api_harness.db.upsert_alias("vendor/model-a", "Model A", "model-a", 0.9)

    response = await api_harness.client.put(
        "/api/plugins/openrouter-prices/aliases/vendor%2Fmodel-a",
        json={"source": "unknown", "external_name": "X"},
    )

    assert response.status_code == 422
    assert "source" in response.json()["detail"].lower()


async def test_get_scrape_runs_returns_recent(api_harness: ApiHarness):
    await _seed_aliases_and_runs(api_harness.db)

    response = await api_harness.client.get("/api/plugins/openrouter-prices/scrape-runs?limit=1")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["source"] == "artificial_analysis"
    assert data[0]["aliases_missed"] == 2


async def test_get_scrape_runs_filters_by_source(api_harness: ApiHarness):
    await _seed_aliases_and_runs(api_harness.db)

    response = await api_harness.client.get("/api/plugins/openrouter-prices/scrape-runs?source=bfcl")

    assert response.status_code == 200
    data = response.json()
    assert [row["source"] for row in data] == ["bfcl"]
    assert data[0]["rows_updated"] == 4
