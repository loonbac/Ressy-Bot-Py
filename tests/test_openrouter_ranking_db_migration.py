"""Tests para migraciones idempotentes de OpenRouterDatabase.

TDD: RED primero. Cubre: renombrado de benchmark_slug legacy,
idempotencia de re-ejecucion.
"""
from __future__ import annotations

import json

import pytest

from src.bot.plugins.openrouter_prices.database import OpenRouterDatabase


@pytest.fixture
async def db_with_legacy_slug():
    database = OpenRouterDatabase(":memory:")
    await database.connect()
    # Forzar estado legacy: eliminar cualquier fila nueva y dejar solo la vieja
    await database._db.execute("DELETE FROM benchmarks WHERE slug = 'aa_intelligence_index'")
    await database._db.execute("DELETE FROM benchmarks WHERE slug = 'aa_omniscience_nh'")
    await database._db.execute(
        "INSERT INTO benchmarks (slug, display_name, source, higher_is_better) VALUES (?, ?, ?, ?)",
        ("aa_omniscience_nh", "AA Omniscience (NH)", "old", 1),
    )
    await database._db.execute(
        "INSERT INTO model_benchmarks (model_id, benchmark_slug, score, raw_value, fetched_at, source) VALUES (?, ?, ?, ?, ?, ?)",
        ("test/model", "aa_omniscience_nh", 0.5, "0.5", 1_000_000, "test"),
    )
    await database._db.execute(
        "INSERT INTO phase_profiles (phase, benchmark_slug, weight, is_feature_factor) VALUES (?, ?, ?, ?)",
        ("orchestrator", "aa_omniscience_nh", 0.1, 0),
    )
    await database._db.commit()
    # Ejecutar migracion sobre el estado legacy
    await database._run_migrations()
    yield database
    await database.close()


class TestMigrationRenameAaOmniscienceNh:
    @pytest.mark.timeout(5)
    async def test_migration_renames_model_benchmarks(self, db_with_legacy_slug):
        rows = await db_with_legacy_slug.list_model_benchmarks(
            benchmark_slug="aa_intelligence_index"
        )
        assert len(rows) == 1
        assert rows[0]["model_id"] == "test/model"
        assert rows[0]["score"] == pytest.approx(0.5)

    @pytest.mark.timeout(5)
    async def test_migration_renames_phase_profiles(self, db_with_legacy_slug):
        profile = await db_with_legacy_slug.get_phase_profile("orchestrator")
        slugs = {e["benchmark_slug"] for e in profile}
        assert "aa_intelligence_index" in slugs
        assert "aa_omniscience_nh" not in slugs

    @pytest.mark.timeout(5)
    async def test_migration_removes_old_benchmark_row(self, db_with_legacy_slug):
        benchmarks = await db_with_legacy_slug.get_benchmarks()
        slugs = {b["slug"] for b in benchmarks}
        assert "aa_omniscience_nh" not in slugs

    @pytest.mark.timeout(5)
    async def test_migration_inserts_new_benchmark_row(self, db_with_legacy_slug):
        benchmarks = await db_with_legacy_slug.get_benchmarks()
        slugs = {b["slug"] for b in benchmarks}
        assert "aa_intelligence_index" in slugs

    @pytest.mark.timeout(5)
    async def test_migration_is_idempotent(self, db_with_legacy_slug):
        # Segunda ejecucion no debe fallar ni duplicar
        await db_with_legacy_slug._run_migrations()
        rows = await db_with_legacy_slug.list_model_benchmarks(
            benchmark_slug="aa_intelligence_index"
        )
        assert len(rows) == 1
        assert rows[0]["score"] == pytest.approx(0.5)


class TestMigrationPurgeOrphanAaOmniscience:
    @pytest.fixture
    async def db(self):
        database = OpenRouterDatabase(":memory:")
        await database.connect()
        yield database
        await database.close()

    @pytest.mark.timeout(5)
    async def test_orphan_aa_omniscience_purged_on_migration(self, db):
        """Orphan aa_omniscience slug is deleted from all 3 tables."""
        # Ensure legacy orphan rows exist in all 3 tables
        await db._db.execute(
            "INSERT OR IGNORE INTO benchmarks (slug, display_name, source, higher_is_better) VALUES (?, ?, ?, ?)",
            ("aa_omniscience", "AA Omniscience", "old", 1)
        )
        await db._db.execute(
            "INSERT OR REPLACE INTO model_benchmarks (model_id, benchmark_slug, score, raw_value, fetched_at, source) VALUES (?, ?, ?, ?, ?, ?)",
            ("test/model", "aa_omniscience", 0.5, "0.5", 1000000, "test")
        )
        await db._db.execute(
            "INSERT OR REPLACE INTO phase_profiles (phase, benchmark_slug, weight, is_feature_factor) VALUES (?, ?, ?, ?)",
            ("orchestrator", "aa_omniscience", 0.1, 0)
        )
        await db._db.commit()

        # Run migration
        await db._run_migrations()

        # Assert all purged
        rows_bm = await db._db.execute_fetchall("SELECT * FROM benchmarks WHERE slug = 'aa_omniscience'")
        assert len(rows_bm) == 0, "benchmarks row should be deleted"

        rows_mb = await db._db.execute_fetchall("SELECT * FROM model_benchmarks WHERE benchmark_slug = 'aa_omniscience'")
        assert len(rows_mb) == 0, "model_benchmarks rows should be deleted"

        rows_pp = await db._db.execute_fetchall("SELECT * FROM phase_profiles WHERE benchmark_slug = 'aa_omniscience'")
        assert len(rows_pp) == 0, "phase_profiles rows should be deleted"

        # Re-run is safe
        await db._run_migrations()

    @pytest.mark.timeout(5)
    async def test_orphan_purge_idempotent(self, db):
        """Running migration twice without legacy rows does not error."""
        await db._run_migrations()
        await db._run_migrations()
        rows = await db._db.execute_fetchall("SELECT * FROM benchmarks WHERE slug = 'aa_omniscience'")
        assert len(rows) == 0


class TestPhasesEnabledMigration:
    @pytest.fixture
    async def db(self):
        database = OpenRouterDatabase(":memory:")
        await database.connect()
        yield database
        await database.close()

    @pytest.mark.timeout(5)
    async def test_phases_enabled_migration_csv_to_json(self, db):
        await db.update_config({"phases_enabled": "orchestrator,sdd_init"})

        await db._run_migrations()

        config = await db.get_config()
        assert json.loads(config["phases_enabled"]) == ["orchestrator", "sdd_init"]

    @pytest.mark.timeout(5)
    async def test_phases_enabled_migration_idempotent(self, db):
        expected = '["sdd_init"]'
        await db.update_config({"phases_enabled": expected})

        await db._run_migrations()
        await db._run_migrations()

        config = await db.get_config()
        assert config["phases_enabled"] == expected

    @pytest.mark.timeout(5)
    async def test_phases_enabled_migration_inserts_missing_default(self, db):
        await db._db.execute("DELETE FROM config WHERE key = 'phases_enabled'")
        await db._db.commit()

        await db._run_migrations()

        config = await db.get_config()
        assert json.loads(config["phases_enabled"]) == ["orchestrator", "sdd_init"]
