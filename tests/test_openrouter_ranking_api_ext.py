"""Tests para los 6 nuevos endpoints de api.py (PR3).

TDD: RED primero. Estos tests fallan hasta que se implementen los endpoints.

Cubre:
  GET  /rankings/{phase}
  GET  /benchmarks
  POST /scrape/{source}
  GET  /aliases
  PUT  /aliases/{openrouter_id}
  GET  /scrape-runs
  PUT  /config — validación de las 14 nuevas claves (REQ-EXT-11)
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.web.app import create_app


# ---------------------------------------------------------------------------
# App factory con mocks inyectados
# ---------------------------------------------------------------------------

def _make_app(scheduler=None, ranking_data=None):
    """Crea una app de test con DB y scheduler mockeados."""
    app = create_app()

    # DB mock
    db = AsyncMock()
    db.get_config = AsyncMock(return_value={
        "enabled": "true",
        "ttl_seconds": "3600",
        "max_models_command": "10",
        "discord_channel_id": "",
        "openrouter_refresh_interval_hours": "24",
        "aa_scrape_enabled": "true",
        "aa_scrape_interval_days": "7",
        "bfcl_scrape_enabled": "true",
        "bfcl_scrape_interval_days": "7",
        "weekly_report_enabled": "true",
        "weekly_report_channel_id": "",
        "weekly_report_day": "monday",
        "weekly_report_hour": "9",
        "weekly_report_count": "10",
        "ranking_embed_enabled": "true",
        "ranking_embed_channel_id": "",
        "ranking_embed_cron_days": "14",
        "ranking_phase": "orchestrator",
        "stale_threshold_days": "14",
        "aa_api_key": "",
    })
    db.get_scrape_health = AsyncMock(return_value=[])
    db.update_config = AsyncMock()
    db.get_metadata = AsyncMock(return_value={})
    db.count_models = AsyncMock(return_value=0)
    db.list_models = AsyncMock(return_value=[])
    db.get_model = AsyncMock(return_value=None)
    db.upsert_models = AsyncMock(return_value=0)
    db.set_metadata = AsyncMock()

    # Benchmark rows
    db.get_benchmarks = AsyncMock(return_value=[
        {"id": 1, "slug": "ifbench", "display_name": "IFBench", "source": "ifbench", "higher_is_better": 1, "description": ""},
        {"id": 2, "slug": "bfcl_v3", "display_name": "BFCL v3", "source": "bfcl", "higher_is_better": 1, "description": ""},
    ])

    # Alias rows
    db.list_aliases = AsyncMock(return_value=[
        {"openrouter_id": "m/model-a", "artificial_analysis_name": "Model A", "bfcl_key": "model-a", "match_confidence": 0.9, "updated_at": 1700000000},
    ])
    db.get_alias = AsyncMock(return_value=None)
    db.upsert_alias = AsyncMock()

    # Scrape runs
    db.list_scrape_runs = AsyncMock(return_value=[
        {"id": 1, "source": "bfcl", "started_at": 1700000000, "finished_at": 1700000100, "status": "ok", "error": None, "rows_updated": 5},
    ])

    # Phase profile
    db.get_phase_profile = AsyncMock(return_value=None)  # por defecto sin datos

    # Client mock
    client = AsyncMock()
    client.fetch_models = AsyncMock(return_value=[])

    # Scheduler mock
    if scheduler is None:
        scheduler = MagicMock()
        scheduler.trigger_scrape = AsyncMock(return_value=True)
        scheduler.is_scraping = MagicMock(return_value=False)

    from src.bot.plugins.openrouter_prices import api as _api
    app.include_router(
        _api.router,
        prefix="/api/plugins/openrouter-prices",
        tags=["openrouter-prices"],
    )

    app.state.openrouter_prices_db = db
    app.state.openrouter_prices_client = client
    app.state.openrouter_prices_scheduler = scheduler

    return app


# ---------------------------------------------------------------------------
# GET /rankings/{phase}
# ---------------------------------------------------------------------------

@pytest.mark.timeout(5)
def test_get_ranking_unknown_phase():
    """Fase desconocida (get_phase_profile devuelve None) → 404."""
    app = _make_app()
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/plugins/openrouter-prices/rankings/nonexistent")
    assert response.status_code == 404
    assert "no encontrado" in response.json()["detail"].lower()


@pytest.mark.timeout(5)
def test_get_ranking_known_phase_returns_list():
    """Fase conocida con datos → 200 con lista."""
    app = _make_app()
    # Asegurar que get_phase_profile retorna datos para que el endpoint no devuelva 404
    app.state.openrouter_prices_db.get_phase_profile = AsyncMock(return_value=[
        {"phase": "orchestrator", "benchmark_slug": "ifbench", "weight": 1.0, "is_feature_factor": False},
    ])
    # Parchear compute_ranking_for_phase para devolver datos
    ranking_data = [
        {"rank": 1, "model_id": "m/alpha", "name": "Alpha", "score": 0.9, "breakdown": []},
        {"rank": 2, "model_id": "m/beta", "name": "Beta", "score": 0.8, "breakdown": []},
    ]
    with patch(
        "src.bot.plugins.openrouter_prices.api.compute_ranking_for_phase",
        new=AsyncMock(return_value=ranking_data),
    ):
        with TestClient(app, raise_server_exceptions=False) as tc:
            response = tc.get("/api/plugins/openrouter-prices/rankings/orchestrator")
    assert response.status_code == 200
    data = response.json()
    assert "models" in data
    assert len(data["models"]) == 2


@pytest.mark.timeout(5)
def test_get_ranking_respects_limit():
    """El parámetro limit se respeta."""
    app = _make_app()
    app.state.openrouter_prices_db.get_phase_profile = AsyncMock(return_value=[
        {"phase": "orchestrator", "benchmark_slug": "ifbench", "weight": 1.0, "is_feature_factor": False},
    ])
    ranking_data = [
        {"rank": i + 1, "model_id": f"m/{i}", "name": f"M{i}", "score": 0.9 - i * 0.05, "breakdown": []}
        for i in range(10)
    ]
    with patch(
        "src.bot.plugins.openrouter_prices.api.compute_ranking_for_phase",
        new=AsyncMock(return_value=ranking_data[:5]),
    ):
        with TestClient(app, raise_server_exceptions=False) as tc:
            response = tc.get("/api/plugins/openrouter-prices/rankings/orchestrator?limit=5")
    assert response.status_code == 200
    assert len(response.json()["models"]) == 5


# ---------------------------------------------------------------------------
# GET /benchmarks
# ---------------------------------------------------------------------------

@pytest.mark.timeout(5)
def test_list_benchmarks_returns_200():
    app = _make_app()
    with TestClient(app, raise_server_exceptions=False) as tc:
        response = tc.get("/api/plugins/openrouter-prices/benchmarks")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 2
    assert data[0]["slug"] == "ifbench"


# ---------------------------------------------------------------------------
# POST /scrape/{source}
# ---------------------------------------------------------------------------

@pytest.mark.timeout(5)
def test_trigger_scrape_valid_source():
    """Fuente válida → 200 {started: true, source: ...}"""
    scheduler = MagicMock()
    scheduler.trigger_scrape = AsyncMock(return_value=True)
    scheduler.is_scraping = MagicMock(return_value=False)

    app = _make_app(scheduler=scheduler)
    with TestClient(app, raise_server_exceptions=False) as tc:
        response = tc.post("/api/plugins/openrouter-prices/scrape/bfcl")
    assert response.status_code == 200
    data = response.json()
    assert data["started"] is True
    assert data["source"] == "bfcl"


@pytest.mark.timeout(5)
def test_trigger_scrape_invalid_source():
    """Fuente inválida → 400."""
    app = _make_app()
    with TestClient(app, raise_server_exceptions=False) as tc:
        response = tc.post("/api/plugins/openrouter-prices/scrape/unknown")
    assert response.status_code == 400
    detail = response.json()["detail"].lower()
    assert "invalida" in detail or "inválida" in detail or "permitidos" in detail


@pytest.mark.timeout(5)
def test_trigger_scrape_conflict():
    """Scrape ya en curso → 409."""
    scheduler = MagicMock()
    scheduler.is_scraping = MagicMock(return_value=True)
    scheduler.trigger_scrape = AsyncMock(return_value=False)

    app = _make_app(scheduler=scheduler)
    with TestClient(app, raise_server_exceptions=False) as tc:
        response = tc.post("/api/plugins/openrouter-prices/scrape/bfcl")
    assert response.status_code == 409


@pytest.mark.timeout(5)
def test_trigger_scrape_all_valid_sources():
    """Todas las fuentes válidas retornan 200."""
    for source in ("openrouter", "aa", "bfcl"):
        scheduler = MagicMock()
        scheduler.trigger_scrape = AsyncMock(return_value=True)
        scheduler.is_scraping = MagicMock(return_value=False)
        app = _make_app(scheduler=scheduler)
        with TestClient(app, raise_server_exceptions=False) as tc:
            response = tc.post(f"/api/plugins/openrouter-prices/scrape/{source}")
        assert response.status_code == 200, f"Source '{source}' failed: {response.text}"


# ---------------------------------------------------------------------------
# GET /aliases
# ---------------------------------------------------------------------------

@pytest.mark.timeout(5)
def test_list_aliases_returns_200():
    app = _make_app()
    with TestClient(app, raise_server_exceptions=False) as tc:
        response = tc.get("/api/plugins/openrouter-prices/aliases")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["openrouter_id"] == "m/model-a"


# ---------------------------------------------------------------------------
# PUT /aliases/{openrouter_id}
# ---------------------------------------------------------------------------

@pytest.mark.timeout(5)
def test_update_alias_not_found():
    """Si el alias no existe → 404."""
    app = _make_app()
    with TestClient(app, raise_server_exceptions=False) as tc:
        response = tc.put(
            "/api/plugins/openrouter-prices/aliases/m%2Fnonexistent",
            json={"artificial_analysis_name": "Some Model"},
        )
    assert response.status_code == 404


@pytest.mark.timeout(5)
def test_update_alias_success():
    """Alias existente → 200 con la fila actualizada."""
    existing_alias = {
        "openrouter_id": "m/model-a",
        "artificial_analysis_name": "Model A",
        "bfcl_key": "model-a",
        "match_confidence": 0.9,
        "updated_at": 1700000000,
    }
    app = _make_app()
    app.state.openrouter_prices_db.get_alias = AsyncMock(return_value=existing_alias)

    updated_alias = {**existing_alias, "artificial_analysis_name": "Updated Name"}
    app.state.openrouter_prices_db.upsert_alias = AsyncMock(return_value=updated_alias)

    with TestClient(app, raise_server_exceptions=False) as tc:
        response = tc.put(
            "/api/plugins/openrouter-prices/aliases/m%2Fmodel-a",
            json={"artificial_analysis_name": "Updated Name"},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["openrouter_id"] == "m/model-a"


@pytest.mark.timeout(5)
def test_update_alias_empty_body_is_noop():
    """Body vacío → 200 con la fila actual sin cambios."""
    existing_alias = {
        "openrouter_id": "m/model-a",
        "artificial_analysis_name": "Model A",
        "bfcl_key": "model-a",
        "match_confidence": 0.9,
        "updated_at": 1700000000,
    }
    app = _make_app()
    app.state.openrouter_prices_db.get_alias = AsyncMock(return_value=existing_alias)
    app.state.openrouter_prices_db.upsert_alias = AsyncMock(return_value=existing_alias)

    with TestClient(app, raise_server_exceptions=False) as tc:
        response = tc.put(
            "/api/plugins/openrouter-prices/aliases/m%2Fmodel-a",
            json={},
        )
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# GET /scrape-runs
# ---------------------------------------------------------------------------

@pytest.mark.timeout(5)
def test_list_scrape_runs_returns_200():
    app = _make_app()
    with TestClient(app, raise_server_exceptions=False) as tc:
        response = tc.get("/api/plugins/openrouter-prices/scrape-runs")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert data[0]["source"] == "bfcl"


@pytest.mark.timeout(5)
def test_list_scrape_runs_source_filter():
    """Filtrar por source llama list_scrape_runs con el parámetro correcto."""
    app = _make_app()
    app.state.openrouter_prices_db.list_scrape_runs = AsyncMock(return_value=[])
    with TestClient(app, raise_server_exceptions=False) as tc:
        response = tc.get("/api/plugins/openrouter-prices/scrape-runs?source=aa")
    assert response.status_code == 200
    # Verificar que list_scrape_runs fue llamada con source="aa"
    app.state.openrouter_prices_db.list_scrape_runs.assert_called_once()
    call_kwargs = app.state.openrouter_prices_db.list_scrape_runs.call_args
    # source debería aparecer en los args o kwargs
    args_str = str(call_kwargs)
    assert "aa" in args_str


# ---------------------------------------------------------------------------
# PUT /config — validación de nuevas claves (REQ-EXT-11)
# ---------------------------------------------------------------------------

@pytest.mark.timeout(5)
def test_config_rejects_zero_refresh_interval():
    """openrouter_refresh_interval_hours = "0" → 400."""
    app = _make_app()
    with TestClient(app, raise_server_exceptions=False) as tc:
        response = tc.put(
            "/api/plugins/openrouter-prices/config",
            json={"openrouter_refresh_interval_hours": "0"},
        )
    assert response.status_code == 400
    assert "0" in response.json()["detail"] or "mayor" in response.json()["detail"].lower()


@pytest.mark.timeout(5)
def test_config_rejects_negative_refresh_interval():
    """openrouter_refresh_interval_hours negativo → 400."""
    app = _make_app()
    with TestClient(app, raise_server_exceptions=False) as tc:
        response = tc.put(
            "/api/plugins/openrouter-prices/config",
            json={"openrouter_refresh_interval_hours": "-1"},
        )
    assert response.status_code == 400


@pytest.mark.timeout(5)
def test_config_accepts_valid_refresh_interval():
    """openrouter_refresh_interval_hours = "12" → 200."""
    app = _make_app()
    with TestClient(app, raise_server_exceptions=False) as tc:
        response = tc.put(
            "/api/plugins/openrouter-prices/config",
            json={"openrouter_refresh_interval_hours": "12"},
        )
    assert response.status_code == 200


@pytest.mark.timeout(5)
def test_config_rejects_invalid_boolean_flag():
    """aa_scrape_enabled = "maybe" → 400."""
    app = _make_app()
    with TestClient(app, raise_server_exceptions=False) as tc:
        response = tc.put(
            "/api/plugins/openrouter-prices/config",
            json={"aa_scrape_enabled": "maybe"},
        )
    assert response.status_code == 400
    assert "true" in response.json()["detail"].lower() or "false" in response.json()["detail"].lower()


@pytest.mark.timeout(5)
def test_config_accepts_valid_boolean_flags():
    """Flags booleanos válidos → 200."""
    for key in ("aa_scrape_enabled", "bfcl_scrape_enabled", "weekly_report_enabled", "ranking_embed_enabled"):
        app = _make_app()
        with TestClient(app, raise_server_exceptions=False) as tc:
            response = tc.put(
                "/api/plugins/openrouter-prices/config",
                json={key: "false"},
            )
        assert response.status_code == 200, f"Key '{key}' failed: {response.text}"


@pytest.mark.timeout(5)
def test_config_rejects_zero_scrape_interval_days():
    """aa_scrape_interval_days = "0" → 400."""
    app = _make_app()
    with TestClient(app, raise_server_exceptions=False) as tc:
        response = tc.put(
            "/api/plugins/openrouter-prices/config",
            json={"aa_scrape_interval_days": "0"},
        )
    assert response.status_code == 400


@pytest.mark.timeout(5)
def test_config_rejects_invalid_weekly_report_day():
    """weekly_report_day = "funday" → 400."""
    app = _make_app()
    with TestClient(app, raise_server_exceptions=False) as tc:
        response = tc.put(
            "/api/plugins/openrouter-prices/config",
            json={"weekly_report_day": "funday"},
        )
    assert response.status_code == 400


@pytest.mark.timeout(5)
def test_config_accepts_valid_weekly_report_day():
    """weekly_report_day = "friday" → 200."""
    app = _make_app()
    with TestClient(app, raise_server_exceptions=False) as tc:
        response = tc.put(
            "/api/plugins/openrouter-prices/config",
            json={"weekly_report_day": "friday"},
        )
    assert response.status_code == 200


@pytest.mark.timeout(5)
def test_config_rejects_invalid_weekly_report_hour():
    """weekly_report_hour = "25" → 400."""
    app = _make_app()
    with TestClient(app, raise_server_exceptions=False) as tc:
        response = tc.put(
            "/api/plugins/openrouter-prices/config",
            json={"weekly_report_hour": "25"},
        )
    assert response.status_code == 400


@pytest.mark.timeout(5)
def test_config_accepts_valid_channel_id_for_new_keys():
    """weekly_report_channel_id con snowflake válido → 200."""
    app = _make_app()
    with TestClient(app, raise_server_exceptions=False) as tc:
        response = tc.put(
            "/api/plugins/openrouter-prices/config",
            json={"weekly_report_channel_id": "123456789012345678"},
        )
    assert response.status_code == 200


@pytest.mark.timeout(5)
def test_config_rejects_invalid_channel_id_for_new_keys():
    """weekly_report_channel_id no numérico → 400."""
    app = _make_app()
    with TestClient(app, raise_server_exceptions=False) as tc:
        response = tc.put(
            "/api/plugins/openrouter-prices/config",
            json={"weekly_report_channel_id": "not-a-snowflake"},
        )
    assert response.status_code == 400


@pytest.mark.timeout(5)
def test_config_rejects_invalid_ranking_embed_cron_days():
    """ranking_embed_cron_days = "0" → 400."""
    app = _make_app()
    with TestClient(app, raise_server_exceptions=False) as tc:
        response = tc.put(
            "/api/plugins/openrouter-prices/config",
            json={"ranking_embed_cron_days": "0"},
        )
    assert response.status_code == 400


@pytest.mark.timeout(5)
def test_config_accepts_valid_ranking_phase():
    """ranking_phase = "orchestrator" → 200."""
    app = _make_app()
    with TestClient(app, raise_server_exceptions=False) as tc:
        response = tc.put(
            "/api/plugins/openrouter-prices/config",
            json={"ranking_phase": "orchestrator"},
        )
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# GET /status — scrape_health y warnings (PR2 observability)
# ---------------------------------------------------------------------------

@pytest.mark.timeout(5)
def test_status_reports_scrape_health():
    """GET /status includes scrape_health with per-source info."""
    import time
    now = int(time.time())
    app = _make_app()
    app.state.openrouter_prices_db.get_scrape_health = AsyncMock(side_effect=lambda source=None: [
        {"source": "artificial_analysis", "started_at": now - 3600, "finished_at": now - 3500,
         "status": "ok", "error": None, "rows_updated": 50, "aliases_missed": 3},
    ] if source == "artificial_analysis" else [
        {"source": "bfcl", "started_at": now - 86400 * 15, "finished_at": now - 86400 * 15 + 60,
         "status": "error", "error": "rate_limited", "rows_updated": 0, "aliases_missed": 0},
    ] if source == "bfcl" else [])
    app.state.openrouter_prices_db.get_config = AsyncMock(return_value={
        "stale_threshold_days": "14",
        "aa_api_key": "aa_test",
        "bfcl_scrape_enabled": "true",
        "aa_scrape_enabled": "true",
    })

    with TestClient(app, raise_server_exceptions=False) as tc:
        response = tc.get("/api/plugins/openrouter-prices/status")

    assert response.status_code == 200
    data = response.json()
    assert "scrape_health" in data
    assert "artificial_analysis" in data["scrape_health"]
    assert "bfcl" in data["scrape_health"]

    aa = data["scrape_health"]["artificial_analysis"]
    assert aa["last_status"] == "ok"
    assert aa["stale"] is False
    assert aa["age_seconds"] is not None

    bfcl = data["scrape_health"]["bfcl"]
    assert bfcl["last_status"] == "error"
    assert bfcl["stale"] is True


@pytest.mark.timeout(5)
def test_status_warns_when_aa_key_missing_and_unauthorized():
    """aa_api_key missing + unauthorized error → warning."""
    import time
    now = int(time.time())
    app = _make_app()
    app.state.openrouter_prices_db.get_scrape_health = AsyncMock(side_effect=lambda source=None: [
        {"source": "artificial_analysis", "started_at": now - 3600, "finished_at": now - 3500,
         "status": "error", "error": "unauthorized", "rows_updated": 0, "aliases_missed": 0},
    ] if source == "artificial_analysis" else [])
    app.state.openrouter_prices_db.get_config = AsyncMock(return_value={
        "stale_threshold_days": "14",
        "aa_api_key": "",
        "bfcl_scrape_enabled": "true",
        "aa_scrape_enabled": "true",
    })

    with TestClient(app, raise_server_exceptions=False) as tc:
        response = tc.get("/api/plugins/openrouter-prices/status")

    assert response.status_code == 200
    data = response.json()
    assert "warnings" in data
    assert "aa_api_key_missing" in data["warnings"]


@pytest.mark.timeout(5)
def test_status_warns_when_scrape_stale():
    """last_finished_at > 14 days ago → stale warning."""
    import time
    now = int(time.time())
    app = _make_app()
    app.state.openrouter_prices_db.get_scrape_health = AsyncMock(side_effect=lambda source=None: [
        {"source": "bfcl", "started_at": now - 86400 * 20, "finished_at": now - 86400 * 20 + 60,
         "status": "ok", "error": None, "rows_updated": 10, "aliases_missed": 0},
    ] if source == "bfcl" else [])
    app.state.openrouter_prices_db.get_config = AsyncMock(return_value={
        "stale_threshold_days": "14",
        "aa_api_key": "aa_test",
        "bfcl_scrape_enabled": "true",
        "aa_scrape_enabled": "true",
    })

    with TestClient(app, raise_server_exceptions=False) as tc:
        response = tc.get("/api/plugins/openrouter-prices/status")

    assert response.status_code == 200
    data = response.json()
    assert "warnings" in data
    assert "bfcl_scrape_stale" in data["warnings"]


# ---------------------------------------------------------------------------
# GET /scrape-runs — includes aliases_missed
# ---------------------------------------------------------------------------

    @pytest.mark.timeout(5)
    def test_scrape_runs_endpoint_includes_aliases_missed():
        """GET /scrape-runs response includes aliases_missed field."""
        app = _make_app()
        app.state.openrouter_prices_db.list_scrape_runs = AsyncMock(return_value=[
            {"id": 1, "source": "bfcl", "started_at": 1700000000, "finished_at": 1700000100,
             "status": "ok", "error": None, "rows_updated": 5, "aliases_missed": 2},
        ])
        with TestClient(app, raise_server_exceptions=False) as tc:
            response = tc.get("/api/plugins/openrouter-prices/scrape-runs")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert data[0]["aliases_missed"] == 2


# ---------------------------------------------------------------------------
# PR2: sdd_init phase support + /phases endpoint
# ---------------------------------------------------------------------------

@pytest.mark.timeout(5)
def test_rankings_endpoint_supports_sdd_init():
    """GET /rankings/sdd_init retorna 200 con lista de modelos."""
    app = _make_app()
    app.state.openrouter_prices_db.get_phase_profile = AsyncMock(return_value=[
        {"phase": "sdd_init", "benchmark_slug": "ifbench", "weight": 0.3, "is_feature_factor": False},
    ])
    ranking_data = [
        {"rank": 1, "model_id": "m/alpha", "name": "Alpha", "score": 0.9, "breakdown": []},
    ]
    with patch(
        "src.bot.plugins.openrouter_prices.api.compute_ranking_for_phase",
        new=AsyncMock(return_value=ranking_data),
    ):
        with TestClient(app, raise_server_exceptions=False) as tc:
            response = tc.get("/api/plugins/openrouter-prices/rankings/sdd_init")
    assert response.status_code == 200
    data = response.json()
    assert data["phase"] == "sdd_init"
    assert len(data["models"]) == 1


@pytest.mark.timeout(5)
def test_phases_endpoint_lists_all_seeded():
    """GET /phases retorna todas las fases registradas."""
    app = _make_app()
    app.state.openrouter_prices_db.get_phases = AsyncMock(return_value=[
        {
            "slug": "orchestrator",
            "description": "Orchestrator phase weights for benchmark ranking",
            "weights_count": 11,
            "active_benchmarks_count": 8,
            "reserved_benchmarks_count": 3,
            "feature_factors_count": 3,
            "last_ranking_computed_at": None,
        },
        {
            "slug": "sdd_init",
            "description": "SDD init phase weights for benchmark ranking",
            "weights_count": 11,
            "active_benchmarks_count": 8,
            "reserved_benchmarks_count": 3,
            "feature_factors_count": 3,
            "last_ranking_computed_at": None,
        },
    ])
    with TestClient(app, raise_server_exceptions=False) as tc:
        response = tc.get("/api/plugins/openrouter-prices/phases")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert [item["slug"] for item in data] == ["orchestrator", "sdd_init"]


@pytest.mark.timeout(5)
def test_phases_endpoint_returns_empty_when_no_phases():
    """GET /phases retorna lista vacia si no hay fases."""
    app = _make_app()
    app.state.openrouter_prices_db.get_phases = AsyncMock(return_value=[])
    with TestClient(app, raise_server_exceptions=False) as tc:
        response = tc.get("/api/plugins/openrouter-prices/phases")
    assert response.status_code == 200
    data = response.json()
    assert data == []
