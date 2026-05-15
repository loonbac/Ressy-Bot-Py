"""Tests para extensiones de OpenRouterDatabase (PR 1 de openrouter-ranking).

TDD: RED primero. Cubre: schema nuevas tablas, seeds idempotentes,
upsert model_benchmark + retrieval, CRUD aliases, scrape_runs.
"""
from __future__ import annotations

import time
import pytest

from src.bot.plugins.openrouter_prices.database import OpenRouterDatabase


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
async def db():
    database = OpenRouterDatabase(":memory:")
    await database.connect()
    yield database
    await database.close()


# ---------------------------------------------------------------------------
# Schema: tablas nuevas
# ---------------------------------------------------------------------------

class TestNewTableSchema:
    @pytest.mark.timeout(5)
    async def test_benchmarks_table_exists(self, db):
        rows = await db._db.execute_fetchall(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='benchmarks'"
        )
        assert rows, "Tabla 'benchmarks' no fue creada"

    @pytest.mark.timeout(5)
    async def test_model_benchmarks_table_exists(self, db):
        rows = await db._db.execute_fetchall(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='model_benchmarks'"
        )
        assert rows, "Tabla 'model_benchmarks' no fue creada"

    @pytest.mark.timeout(5)
    async def test_phase_profiles_table_exists(self, db):
        rows = await db._db.execute_fetchall(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='phase_profiles'"
        )
        assert rows, "Tabla 'phase_profiles' no fue creada"

    @pytest.mark.timeout(5)
    async def test_model_aliases_table_exists(self, db):
        rows = await db._db.execute_fetchall(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='model_aliases'"
        )
        assert rows, "Tabla 'model_aliases' no fue creada"

    @pytest.mark.timeout(5)
    async def test_scrape_runs_table_exists(self, db):
        rows = await db._db.execute_fetchall(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='scrape_runs'"
        )
        assert rows, "Tabla 'scrape_runs' no fue creada"

    @pytest.mark.timeout(5)
    async def test_new_indexes_exist(self, db):
        rows = await db._db.execute_fetchall(
            "SELECT name FROM sqlite_master WHERE type='index'"
        )
        index_names = {r[0] for r in rows}
        assert "idx_model_benchmarks_slug" in index_names


# ---------------------------------------------------------------------------
# Seeds: benchmarks (8 rows)
# ---------------------------------------------------------------------------

class TestBenchmarkSeeds:
    @pytest.mark.timeout(5)
    async def test_nine_benchmarks_seeded(self, db):
        benchmarks = await db.get_benchmarks()
        assert len(benchmarks) == 8

    @pytest.mark.timeout(5)
    async def test_benchmark_slugs_present(self, db):
        benchmarks = await db.get_benchmarks()
        slugs = {b["slug"] for b in benchmarks}
        expected = {
            "ifbench",
            "multichallenge",
            "tau2_telecom",
            "bfcl_v3",
            "bfcl_parallel",
            "aa_intelligence_index",
            "ruler",
            "longbench",
        }
        assert expected == slugs

    @pytest.mark.timeout(5)
    async def test_seed_idempotent(self, db):
        # Llamar _seed_benchmarks dos veces no duplica
        await db._seed_benchmarks()
        await db._seed_benchmarks()
        benchmarks = await db.get_benchmarks()
        assert len(benchmarks) == 9

    @pytest.mark.timeout(5)
    async def test_higher_is_better_set_correctly(self, db):
        benchmarks = await db.get_benchmarks()
        bmap = {b["slug"]: b for b in benchmarks}
        # Todos son higher_is_better en este diseño
        for slug in ("ifbench", "bfcl_v3", "bfcl_parallel"):
            assert bmap[slug]["higher_is_better"] in (True, 1)


# ---------------------------------------------------------------------------
# Seeds: phase_profiles (orchestrator)
# ---------------------------------------------------------------------------

class TestPhaseProfileSeeds:
    @pytest.mark.timeout(5)
    async def test_orchestrator_profile_seeded(self, db):
        entries = await db.get_phase_profile("orchestrator")
        assert len(entries) == 11  # 8 benchmarks + 3 feature factors

    @pytest.mark.timeout(5)
    async def test_orchestrator_profile_idempotent(self, db):
        await db._seed_phase_profile()
        await db._seed_phase_profile()
        entries = await db.get_phase_profile("orchestrator")
        assert len(entries) == 11

    @pytest.mark.timeout(5)
    async def test_feature_factors_present(self, db):
        entries = await db.get_phase_profile("orchestrator")
        feature_slugs = {e["benchmark_slug"] for e in entries if e["is_feature_factor"]}
        expected_features = {
            "input_cache_read_ratio",
            "supports_reasoning_effort",
            "supports_verbosity",
        }
        assert expected_features == feature_slugs

    @pytest.mark.timeout(5)
    async def test_weights_non_negative(self, db):
        entries = await db.get_phase_profile("orchestrator")
        for entry in entries:
            assert entry["weight"] >= 0.0


# ---------------------------------------------------------------------------
# New config defaults (14 keys per REQ-EXT-11)
# ---------------------------------------------------------------------------

class TestNewConfigDefaults:
    @pytest.mark.timeout(5)
    async def test_all_14_new_keys_seeded(self, db):
        config = await db.get_config()
        new_keys = [
            "openrouter_refresh_interval_hours",
            "aa_scrape_enabled",
            "aa_scrape_interval_days",
            "bfcl_scrape_enabled",
            "bfcl_scrape_interval_days",
            "weekly_report_enabled",
            "weekly_report_channel_id",
            "weekly_report_day",
            "weekly_report_hour",
            "weekly_report_count",
            "ranking_embed_enabled",
            "ranking_embed_channel_id",
            "ranking_embed_cron_days",
            "ranking_phase",
        ]
        for key in new_keys:
            assert key in config, f"Clave '{key}' no encontrada en config"

    @pytest.mark.timeout(5)
    async def test_default_values_correct(self, db):
        config = await db.get_config()
        assert config["openrouter_refresh_interval_hours"] == "24"
        assert config["aa_scrape_enabled"] == "true"
        assert config["aa_scrape_interval_days"] == "7"
        assert config["bfcl_scrape_enabled"] == "true"
        assert config["bfcl_scrape_interval_days"] == "7"
        assert config["weekly_report_enabled"] == "true"
        assert config["weekly_report_channel_id"] == ""
        assert config["weekly_report_day"] == "monday"
        assert config["weekly_report_hour"] == "9"
        assert config["weekly_report_count"] == "10"
        assert config["ranking_embed_enabled"] == "true"
        assert config["ranking_embed_channel_id"] == ""
        assert config["ranking_embed_cron_days"] == "14"
        assert config["ranking_phase"] == "orchestrator"

    @pytest.mark.timeout(5)
    async def test_new_defaults_dont_overwrite_custom(self, db):
        await db.update_config({"ranking_phase": "custom_phase"})
        await db._seed_defaults()
        config = await db.get_config()
        assert config["ranking_phase"] == "custom_phase"


# ---------------------------------------------------------------------------
# upsert_model_benchmark + list_model_benchmarks
# ---------------------------------------------------------------------------

class TestModelBenchmarks:
    @pytest.mark.timeout(5)
    async def test_upsert_and_retrieve(self, db):
        ts = int(time.time())
        await db.upsert_model_benchmark(
            model_id="vendor/model-a",
            benchmark_slug="ifbench",
            score=82.5,
            raw_value="82.5",
            fetched_at=ts,
            source="artificial_analysis",
        )
        rows = await db.list_model_benchmarks(benchmark_slug="ifbench")
        assert len(rows) == 1
        assert rows[0]["model_id"] == "vendor/model-a"
        assert rows[0]["score"] == pytest.approx(82.5)

    @pytest.mark.timeout(5)
    async def test_upsert_updates_existing(self, db):
        ts = int(time.time())
        await db.upsert_model_benchmark(
            model_id="vendor/model-a",
            benchmark_slug="ifbench",
            score=80.0,
            raw_value="80.0",
            fetched_at=ts,
            source="artificial_analysis",
        )
        await db.upsert_model_benchmark(
            model_id="vendor/model-a",
            benchmark_slug="ifbench",
            score=85.0,
            raw_value="85.0",
            fetched_at=ts + 100,
            source="artificial_analysis",
        )
        rows = await db.list_model_benchmarks(benchmark_slug="ifbench")
        assert len(rows) == 1
        assert rows[0]["score"] == pytest.approx(85.0)
        assert rows[0]["fetched_at"] == ts + 100

    @pytest.mark.timeout(5)
    async def test_list_all_benchmarks(self, db):
        ts = int(time.time())
        await db.upsert_model_benchmark("vendor/a", "ifbench", 80.0, "80", ts, "test")
        await db.upsert_model_benchmark("vendor/a", "bfcl_v3", 70.0, "70", ts, "test")
        await db.upsert_model_benchmark("vendor/b", "ifbench", 60.0, "60", ts, "test")
        all_rows = await db.list_model_benchmarks()
        assert len(all_rows) == 3

    @pytest.mark.timeout(5)
    async def test_filter_by_slug(self, db):
        ts = int(time.time())
        await db.upsert_model_benchmark("vendor/a", "ifbench", 80.0, "80", ts, "test")
        await db.upsert_model_benchmark("vendor/b", "bfcl_v3", 70.0, "70", ts, "test")
        rows = await db.list_model_benchmarks(benchmark_slug="ifbench")
        assert len(rows) == 1
        assert rows[0]["benchmark_slug"] == "ifbench"


# ---------------------------------------------------------------------------
# Aliases CRUD
# ---------------------------------------------------------------------------

class TestAliasesCRUD:
    @pytest.mark.timeout(5)
    async def test_upsert_and_get(self, db):
        await db.upsert_alias(
            openrouter_id="anthropic/claude-3-haiku",
            artificial_analysis_name="Claude 3 Haiku",
            bfcl_key=None,
            match_confidence=0.9,
        )
        row = await db.get_alias("anthropic/claude-3-haiku")
        assert row is not None
        assert row["openrouter_id"] == "anthropic/claude-3-haiku"
        assert row["artificial_analysis_name"] == "Claude 3 Haiku"
        assert row["bfcl_key"] is None
        assert row["match_confidence"] == pytest.approx(0.9)

    @pytest.mark.timeout(5)
    async def test_upsert_updates_existing(self, db):
        await db.upsert_alias("vendor/m", "Old Name", None, 0.7)
        await db.upsert_alias("vendor/m", "New Name", "new-key", 0.95)
        row = await db.get_alias("vendor/m")
        assert row["artificial_analysis_name"] == "New Name"
        assert row["bfcl_key"] == "new-key"

    @pytest.mark.timeout(5)
    async def test_get_nonexistent_returns_none(self, db):
        row = await db.get_alias("does/not-exist")
        assert row is None

    @pytest.mark.timeout(5)
    async def test_list_aliases_multiple(self, db):
        await db.upsert_alias("vendor/a", "Model A", None, 0.9)
        await db.upsert_alias("vendor/b", None, "b-key", 0.85)
        rows = await db.list_aliases()
        assert len(rows) == 2


# ---------------------------------------------------------------------------
# scrape_runs CRUD
# ---------------------------------------------------------------------------

class TestScrapeRuns:
    @pytest.mark.timeout(5)
    async def test_record_and_list_scrape_runs(self, db):
        ts = int(time.time())
        await db.record_scrape_run(
            source="bfcl_github",
            started_at=ts,
            finished_at=ts + 30,
            status="ok",
            error=None,
            rows_updated=15,
        )
        rows = await db.list_scrape_runs()
        assert len(rows) == 1
        assert rows[0]["source"] == "bfcl_github"
        assert rows[0]["status"] == "ok"
        assert rows[0]["rows_updated"] == 15

    @pytest.mark.timeout(5)
    async def test_list_scrape_runs_filter_by_source(self, db):
        ts = int(time.time())
        await db.record_scrape_run("aa", ts, ts + 20, "ok", None, 5)
        await db.record_scrape_run("bfcl_github", ts + 100, ts + 130, "error", "timeout", 0)
        rows = await db.list_scrape_runs(source="aa")
        assert len(rows) == 1
        assert rows[0]["source"] == "aa"

    @pytest.mark.timeout(5)
    async def test_list_scrape_runs_limit(self, db):
        ts = int(time.time())
        for i in range(5):
            await db.record_scrape_run("aa", ts + i, ts + i + 10, "ok", None, i)
        rows = await db.list_scrape_runs(limit=3)
        assert len(rows) == 3


# ---------------------------------------------------------------------------
# list_all_model_slugs
# ---------------------------------------------------------------------------

class TestListAllModelSlugs:
    @pytest.mark.timeout(5)
    async def test_returns_all_model_ids(self, db):
        ts = int(time.time())
        models = [
            {
                "id": f"vendor/model-{i}",
                "name": f"Model {i}",
                "description": "",
                "created": ts,
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
            for i in range(3)
        ]
        await db.upsert_models(models, fetched_at=ts)
        slugs = await db.list_all_model_slugs()
        for i in range(3):
            assert f"vendor/model-{i}" in slugs


# ---------------------------------------------------------------------------
# Orchestrator phase weights JSON validation
# ---------------------------------------------------------------------------

def test_orchestrator_weights_metadata_documents_reserved():
    """Verify metadata field documents reserved-zero benchmarks."""
    import json
    from pathlib import Path
    seed_path = Path("src/bot/plugins/openrouter_prices/seeds/orchestrator_phase_weights.json")
    data = json.loads(seed_path.read_text())
    assert "metadata" in data
    assert "_metadata" not in data
    meta = data["metadata"]
    assert meta["description"] == "Orchestrator phase weights for benchmark ranking"
    assert isinstance(meta["rationale"], str)
    assert meta["reserved_zero"] == ["multichallenge", "ruler", "longbench"]


def test_orchestrator_weights_sum_to_one():
    """Verify phase profile weights sum to exactly 1.0."""
    import json
    from pathlib import Path
    seed_path = Path("src/bot/plugins/openrouter_prices/seeds/orchestrator_phase_weights.json")
    data = json.loads(seed_path.read_text())
    total = sum(w["weight"] for w in data["weights"])
    assert abs(total - 1.0) < 1e-9, f"Weights sum to {total}, expected 1.0"


# ---------------------------------------------------------------------------
# scrape_runs: aliases_missed column (PR2 observability)
# ---------------------------------------------------------------------------

class TestScrapeRunsAliasesMissed:
    @pytest.mark.timeout(5)
    async def test_record_scrape_run_persists_aliases_missed(self, db):
        """record_scrape_run stores aliases_missed correctly."""
        await db.record_scrape_run(
            source="bfcl",
            started_at=100,
            finished_at=200,
            status="ok",
            error=None,
            rows_updated=10,
            aliases_missed=5,
        )
        runs = await db.list_scrape_runs(source="bfcl")
        assert runs[0]["aliases_missed"] == 5

    @pytest.mark.timeout(5)
    async def test_migration_adds_aliases_missed_column(self, db):
        """_run_migrations adds aliases_missed column with default 0."""
        cursor = await db._db.execute("PRAGMA table_info(scrape_runs)")
        columns = {row[1] for row in await cursor.fetchall()}
        assert "aliases_missed" in columns


# ---------------------------------------------------------------------------
# get_scrape_health (PR2 observability)
# ---------------------------------------------------------------------------

class TestGetScrapeHealth:
    @pytest.mark.timeout(5)
    async def test_get_scrape_health_returns_latest_per_source(self, db):
        """get_scrape_health returns the latest run per source."""
        ts = int(time.time())
        await db.record_scrape_run("aa", ts - 200, ts - 150, "ok", None, 5, aliases_missed=1)
        await db.record_scrape_run("aa", ts - 100, ts - 50, "ok", None, 8, aliases_missed=2)
        await db.record_scrape_run("bfcl", ts - 300, ts - 250, "error", "timeout", 0, aliases_missed=0)

        health = await db.get_scrape_health()
        assert len(health) == 2
        sources = {h["source"] for h in health}
        assert sources == {"aa", "bfcl"}

    @pytest.mark.timeout(5)
    async def test_get_scrape_health_filter_by_source(self, db):
        """get_scrape_health(source='aa') returns only aa rows."""
        ts = int(time.time())
        await db.record_scrape_run("aa", ts - 100, ts - 50, "ok", None, 5, aliases_missed=1)
        await db.record_scrape_run("bfcl", ts - 300, ts - 250, "error", "timeout", 0, aliases_missed=0)

        health = await db.get_scrape_health(source="aa")
        assert len(health) == 1
        assert health[0]["source"] == "aa"
