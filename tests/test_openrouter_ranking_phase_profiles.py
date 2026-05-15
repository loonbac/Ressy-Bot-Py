"""Tests para phase profiles de sdd_init (PR1 de add-sdd-init-phase-profile).

TDD: RED primero. Cubre:
- sdd_init seeded en cold start
- pesos suman 1.0
- ranking con sdd_init favorece IFBench (weight 0.30)
- orchestrator sigue intacto
- loader salta JSON invalido con warning
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import pytest

from src.bot.plugins.openrouter_prices.database import OpenRouterDatabase, SEEDS_DIR
from src.bot.plugins.openrouter_prices.ranking import compute_ranking_for_phase


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def db():
    database = OpenRouterDatabase(":memory:")
    await database.connect()
    yield database
    await database.close()


class MockDB:
    """Mock minimo del DB para tests de compute_ranking_for_phase."""

    def __init__(self, phase_profile=None, model_benchmarks=None, models=None):
        self._phase_profile = phase_profile or []
        self._model_benchmarks = model_benchmarks or []
        self._models = models or []

    async def get_phase_profile(self, phase: str):
        return self._phase_profile

    async def list_model_benchmarks(self, benchmark_slug: str | None = None):
        if benchmark_slug:
            return [m for m in self._model_benchmarks if m["benchmark_slug"] == benchmark_slug]
        return self._model_benchmarks

    async def list_models(self, text_only=False, include_stale=True):
        return self._models


def _make_profile_entry(slug: str, weight: float, is_feature_factor: bool = False):
    return {
        "phase": "sdd_init",
        "benchmark_slug": slug,
        "weight": weight,
        "is_feature_factor": is_feature_factor,
    }


def _make_benchmark_row(model_id: str, slug: str, score: float):
    return {
        "model_id": model_id,
        "benchmark_slug": slug,
        "score": score,
        "raw_value": str(score),
        "fetched_at": 1700000000,
        "source": "test",
    }


def _make_model_row(model_id: str, name: str, prompt: str = "0.0001",
                    input_cache_read: str = "0.00001",
                    supported_parameters: str = "[]"):
    return {
        "id": model_id,
        "name": name,
        "pricing_prompt": prompt,
        "pricing_input_cache_read": input_cache_read,
        "raw_json": f'{{"id":"{model_id}","supported_parameters":{supported_parameters}}}',
        "stale": 0,
    }


# ---------------------------------------------------------------------------
# 1. sdd_init profile seeded on cold start
# ---------------------------------------------------------------------------

class TestSddInitProfileSeeded:
    @pytest.mark.timeout(5)
    async def test_sdd_init_profile_seeded_on_cold_start(self, db):
        entries = await db.get_phase_profile("sdd_init")
        assert len(entries) == 11

    @pytest.mark.timeout(5)
    async def test_sdd_init_profile_idempotent(self, db):
        await db._seed_phase_profile()
        await db._seed_phase_profile()
        entries = await db.get_phase_profile("sdd_init")
        assert len(entries) == 11


# ---------------------------------------------------------------------------
# 2. sdd_init weights sum to 1.0
# ---------------------------------------------------------------------------

def test_sdd_init_weights_sum_to_one():
    seed_path = SEEDS_DIR / "sdd_init_phase_weights.json"
    assert seed_path.exists(), f"Archivo no encontrado: {seed_path}"
    data = json.loads(seed_path.read_text())
    total = sum(w["weight"] for w in data["weights"])
    assert abs(total - 1.0) < 1e-9, f"Weights suman {total}, esperado 1.0"


# ---------------------------------------------------------------------------
# 3. ranking con sdd_init favorece IFBench (weight 0.30)
# ---------------------------------------------------------------------------

class TestSddInitRanking:
    @pytest.mark.timeout(5)
    async def test_sdd_init_ranking_returns_topN(self):
        """Con peso IFBench=0.30, modelo con mejor IFBench debe ganar aunque
        pierda en otros benchmarks con datos. Solo se proveen datos para
        ifbench y tau2_telecom; el resto se excluye por falta de datos."""
        # Cargar pesos reales desde el JSON
        seed_path = SEEDS_DIR / "sdd_init_phase_weights.json"
        data = json.loads(seed_path.read_text())
        profile = [
            {
                "phase": data["phase"],
                "benchmark_slug": w["benchmark_slug"],
                "weight": w["weight"],
                "is_feature_factor": w.get("is_feature_factor", False),
            }
            for w in data["weights"]
        ]
        # model_a: gana en IFBench, pierde en tau2_telecom
        # model_b: pierde en IFBench, gana en tau2_telecom
        # Los demas benchmarks no tienen datos en model_benchmarks → se excluyen
        benchmarks = [
            _make_benchmark_row("vendor/a", "ifbench", 95.0),
            _make_benchmark_row("vendor/a", "tau2_telecom", 50.0),
            _make_benchmark_row("vendor/b", "ifbench", 60.0),
            _make_benchmark_row("vendor/b", "tau2_telecom", 90.0),
        ]
        models = [
            _make_model_row("vendor/a", "Model A"),
            _make_model_row("vendor/b", "Model B"),
        ]
        db = MockDB(profile, benchmarks, models)
        result = await compute_ranking_for_phase(db, "sdd_init", n=2)
        assert len(result) == 2
        # vendor/a debe ganar porque IFBench (0.30) pesa mas que tau2_telecom (0.18)
        assert result[0]["model_id"] == "vendor/a"


# ---------------------------------------------------------------------------
# 4. orchestrator profile still intact
# ---------------------------------------------------------------------------

class TestOrchestratorProfileStillIntact:
    @pytest.mark.timeout(5)
    async def test_orchestrator_profile_still_intact(self, db):
        entries = await db.get_phase_profile("orchestrator")
        assert len(entries) == 11

    @pytest.mark.timeout(5)
    async def test_orchestrator_weights_unchanged(self, db):
        entries = await db.get_phase_profile("orchestrator")
        wmap = {e["benchmark_slug"]: e["weight"] for e in entries}
        assert wmap["ifbench"] == pytest.approx(0.25)


# ---------------------------------------------------------------------------
# 5. seed loader skips invalid weights json
# ---------------------------------------------------------------------------

class TestSeedLoaderSkipsInvalidWeights:
    @pytest.mark.timeout(5)
    async def test_seed_loader_skips_invalid_weights_json(self, tmp_path, caplog):
        """Crear un JSON invalido (sum != 1.0), verificar que _seed_phase_profile
        lo salta y emite warning."""
        # Crear JSON temporal con pesos invalidos
        invalid_json = tmp_path / "invalid_phase_weights.json"
        invalid_json.write_text(json.dumps({
            "phase": "invalid",
            "weights": [
                {"benchmark_slug": "ifbench", "weight": 0.5},
                {"benchmark_slug": "bfcl_v3", "weight": 0.3},  # sum = 0.8
            ]
        }))

        # Monkeypatch SEEDS_DIR temporalmente
        original_seeds_dir = SEEDS_DIR
        try:
            from src.bot.plugins.openrouter_prices import database
            database.SEEDS_DIR = tmp_path

            database_instance = OpenRouterDatabase(":memory:")
            await database_instance.connect()

            with caplog.at_level(logging.WARNING, logger="src.bot.plugins.openrouter_prices.database"):
                await database_instance._seed_phase_profile()

            # No debe haber insertado el perfil invalido
            entries = await database_instance.get_phase_profile("invalid")
            assert len(entries) == 0

            # Debe haber un warning
            assert any("invalid" in rec.message.lower() or "skip" in rec.message.lower()
                       for rec in caplog.records), f"No se encontro warning. Logs: {[r.message for r in caplog.records]}"

            await database_instance.close()
        finally:
            database.SEEDS_DIR = original_seeds_dir


class TestSeedMetadataContract:
    def test_seed_metadata_field_uses_no_underscore_prefix(self):
        for seed_name in (
            "orchestrator_phase_weights.json",
            "sdd_init_phase_weights.json",
            "sdd_explore_phase_weights.json",
            "sdd_propose_phase_weights.json",
            "sdd_spec_phase_weights.json",
            "sdd_design_phase_weights.json",
            "sdd_tasks_phase_weights.json",
            "sdd_apply_phase_weights.json",
            "sdd_verify_phase_weights.json",
            "sdd_archive_phase_weights.json",
        ):
            data = json.loads((SEEDS_DIR / seed_name).read_text())
            assert "metadata" in data
            assert "_metadata" not in data

    def test_seed_metadata_has_required_fields(self):
        for seed_name in (
            "orchestrator_phase_weights.json",
            "sdd_init_phase_weights.json",
            "sdd_explore_phase_weights.json",
            "sdd_propose_phase_weights.json",
            "sdd_spec_phase_weights.json",
            "sdd_design_phase_weights.json",
            "sdd_tasks_phase_weights.json",
            "sdd_apply_phase_weights.json",
            "sdd_verify_phase_weights.json",
            "sdd_archive_phase_weights.json",
        ):
            data = json.loads((SEEDS_DIR / seed_name).read_text())
            metadata = data["metadata"]
            assert isinstance(metadata["description"], str)
            assert isinstance(metadata["rationale"], str)
            assert isinstance(metadata["reserved_zero"], list)
            assert all(isinstance(item, str) for item in metadata["reserved_zero"])

    @pytest.mark.timeout(5)
    async def test_loader_warns_when_metadata_missing(self, tmp_path, caplog):
        seed = tmp_path / "missing_metadata_phase_weights.json"
        seed.write_text(json.dumps({
            "phase": "missing_metadata",
            "weights": [{"benchmark_slug": "ifbench", "weight": 1.0}],
        }))

        original_seeds_dir = SEEDS_DIR
        try:
            from src.bot.plugins.openrouter_prices import database
            database.SEEDS_DIR = tmp_path
            database_instance = OpenRouterDatabase(":memory:")
            await database_instance.connect()

            with caplog.at_level(logging.WARNING, logger="src.bot.plugins.openrouter_prices.database"):
                await database_instance._seed_phase_profile()

            entries = await database_instance.get_phase_profile("missing_metadata")
            assert len(entries) == 1
            assert any("metadata" in rec.message.lower() for rec in caplog.records)
            await database_instance.close()
        finally:
            database.SEEDS_DIR = original_seeds_dir


# ---------------------------------------------------------------------------
# sdd_explore phase profile
# ---------------------------------------------------------------------------

class TestSddExploreProfileSeeded:
    @pytest.mark.timeout(5)
    async def test_sdd_explore_profile_seeded_on_cold_start(self, db):
        entries = await db.get_phase_profile("sdd_explore")
        assert len(entries) == 11

    @pytest.mark.timeout(5)
    async def test_sdd_explore_profile_idempotent(self, db):
        await db._seed_phase_profile()
        await db._seed_phase_profile()
        entries = await db.get_phase_profile("sdd_explore")
        assert len(entries) == 11


def test_sdd_explore_weights_sum_to_one():
    seed_path = SEEDS_DIR / "sdd_explore_phase_weights.json"
    assert seed_path.exists(), f"Archivo no encontrado: {seed_path}"
    data = json.loads(seed_path.read_text())
    total = sum(w["weight"] for w in data["weights"])
    assert abs(total - 1.0) < 1e-9, f"Weights suman {total}, esperado 1.0"


class TestSddExploreRanking:
    @pytest.mark.timeout(5)
    async def test_sdd_explore_ranking_favors_aa_intelligence_index(self):
        """aa_intelligence_index pesa 0.30, ifbench pesa 0.20.
        Modelo con mejor intelligence_index debe ganar aunque pierda en ifbench."""
        seed_path = SEEDS_DIR / "sdd_explore_phase_weights.json"
        data = json.loads(seed_path.read_text())
        profile = [
            {
                "phase": data["phase"],
                "benchmark_slug": w["benchmark_slug"],
                "weight": w["weight"],
                "is_feature_factor": w.get("is_feature_factor", False),
            }
            for w in data["weights"]
        ]
        benchmarks = [
            _make_benchmark_row("vendor/a", "aa_intelligence_index", 95.0),
            _make_benchmark_row("vendor/a", "ifbench", 50.0),
            _make_benchmark_row("vendor/b", "aa_intelligence_index", 60.0),
            _make_benchmark_row("vendor/b", "ifbench", 90.0),
        ]
        models = [
            _make_model_row("vendor/a", "Model A"),
            _make_model_row("vendor/b", "Model B"),
        ]
        mock_db = MockDB(profile, benchmarks, models)
        result = await compute_ranking_for_phase(mock_db, "sdd_explore", n=2)
        assert len(result) == 2
        assert result[0]["model_id"] == "vendor/a"


class TestPhaseLabelsSddExplore:
    def test_sdd_explore_label_present(self):
        from src.bot.plugins.openrouter_prices.api import _PHASE_LABELS, _phase_label
        assert _PHASE_LABELS.get("sdd_explore") == "SDD Explore"
        assert _phase_label("sdd_explore") == "SDD Explore"


# ---------------------------------------------------------------------------
# sdd_propose phase profile
# ---------------------------------------------------------------------------

class TestSddProposeProfileSeeded:
    @pytest.mark.timeout(5)
    async def test_sdd_propose_profile_seeded_on_cold_start(self, db):
        entries = await db.get_phase_profile("sdd_propose")
        assert len(entries) == 11

    @pytest.mark.timeout(5)
    async def test_sdd_propose_profile_idempotent(self, db):
        await db._seed_phase_profile()
        await db._seed_phase_profile()
        entries = await db.get_phase_profile("sdd_propose")
        assert len(entries) == 11


def test_sdd_propose_weights_sum_to_one():
    seed_path = SEEDS_DIR / "sdd_propose_phase_weights.json"
    assert seed_path.exists(), f"Archivo no encontrado: {seed_path}"
    data = json.loads(seed_path.read_text())
    total = sum(w["weight"] for w in data["weights"])
    assert abs(total - 1.0) < 1e-9, f"Weights suman {total}, esperado 1.0"


class TestSddProposeRanking:
    @pytest.mark.timeout(5)
    async def test_sdd_propose_ranking_favors_aa_intelligence_index(self):
        """aa_intelligence_index 0.30 + ifbench 0.25 combinados (0.55) > tau2_telecom 0.10.
        Modelo A lidera AA + ifbench (top dos pesos), B solo lidera tau2."""
        seed_path = SEEDS_DIR / "sdd_propose_phase_weights.json"
        data = json.loads(seed_path.read_text())
        profile = [
            {
                "phase": data["phase"],
                "benchmark_slug": w["benchmark_slug"],
                "weight": w["weight"],
                "is_feature_factor": w.get("is_feature_factor", False),
            }
            for w in data["weights"]
        ]
        benchmarks = [
            _make_benchmark_row("vendor/a", "aa_intelligence_index", 95.0),
            _make_benchmark_row("vendor/a", "ifbench", 95.0),
            _make_benchmark_row("vendor/a", "tau2_telecom", 50.0),
            _make_benchmark_row("vendor/b", "aa_intelligence_index", 60.0),
            _make_benchmark_row("vendor/b", "ifbench", 60.0),
            _make_benchmark_row("vendor/b", "tau2_telecom", 95.0),
        ]
        models = [
            _make_model_row("vendor/a", "Model A"),
            _make_model_row("vendor/b", "Model B"),
        ]
        mock_db = MockDB(profile, benchmarks, models)
        result = await compute_ranking_for_phase(mock_db, "sdd_propose", n=2)
        assert len(result) == 2
        assert result[0]["model_id"] == "vendor/a"


class TestPhaseLabelsSddPropose:
    def test_sdd_propose_label_present(self):
        from src.bot.plugins.openrouter_prices.api import _PHASE_LABELS, _phase_label
        assert _PHASE_LABELS.get("sdd_propose") == "SDD Propose"
        assert _phase_label("sdd_propose") == "SDD Propose"


# ---------------------------------------------------------------------------
# sdd_spec phase profile
# ---------------------------------------------------------------------------

class TestSddSpecProfileSeeded:
    @pytest.mark.timeout(5)
    async def test_sdd_spec_profile_seeded_on_cold_start(self, db):
        entries = await db.get_phase_profile("sdd_spec")
        assert len(entries) == 11

    @pytest.mark.timeout(5)
    async def test_sdd_spec_profile_idempotent(self, db):
        await db._seed_phase_profile()
        await db._seed_phase_profile()
        entries = await db.get_phase_profile("sdd_spec")
        assert len(entries) == 11


def test_sdd_spec_weights_sum_to_one():
    seed_path = SEEDS_DIR / "sdd_spec_phase_weights.json"
    assert seed_path.exists(), f"Archivo no encontrado: {seed_path}"
    data = json.loads(seed_path.read_text())
    total = sum(w["weight"] for w in data["weights"])
    assert abs(total - 1.0) < 1e-9, f"Weights suman {total}, esperado 1.0"


class TestSddSpecRanking:
    @pytest.mark.timeout(5)
    async def test_sdd_spec_ranking_favors_ifbench(self):
        """ifbench pesa 0.35 (top dominante), aa_intelligence_index 0.20, tau2_telecom 0.10.
        Modelo con mejor ifbench gana aunque pierda en otros, porque format adherence domina."""
        seed_path = SEEDS_DIR / "sdd_spec_phase_weights.json"
        data = json.loads(seed_path.read_text())
        profile = [
            {
                "phase": data["phase"],
                "benchmark_slug": w["benchmark_slug"],
                "weight": w["weight"],
                "is_feature_factor": w.get("is_feature_factor", False),
            }
            for w in data["weights"]
        ]
        benchmarks = [
            _make_benchmark_row("vendor/a", "ifbench", 95.0),
            _make_benchmark_row("vendor/a", "aa_intelligence_index", 50.0),
            _make_benchmark_row("vendor/a", "tau2_telecom", 50.0),
            _make_benchmark_row("vendor/b", "ifbench", 60.0),
            _make_benchmark_row("vendor/b", "aa_intelligence_index", 90.0),
            _make_benchmark_row("vendor/b", "tau2_telecom", 90.0),
        ]
        models = [
            _make_model_row("vendor/a", "Model A"),
            _make_model_row("vendor/b", "Model B"),
        ]
        mock_db = MockDB(profile, benchmarks, models)
        result = await compute_ranking_for_phase(mock_db, "sdd_spec", n=2)
        assert len(result) == 2
        assert result[0]["model_id"] == "vendor/a"


class TestPhaseLabelsSddSpec:
    def test_sdd_spec_label_present(self):
        from src.bot.plugins.openrouter_prices.api import _PHASE_LABELS, _phase_label
        assert _PHASE_LABELS.get("sdd_spec") == "SDD Spec"
        assert _phase_label("sdd_spec") == "SDD Spec"


# ---------------------------------------------------------------------------
# sdd_design phase profile
# ---------------------------------------------------------------------------

class TestSddDesignProfileSeeded:
    @pytest.mark.timeout(5)
    async def test_sdd_design_profile_seeded_on_cold_start(self, db):
        entries = await db.get_phase_profile("sdd_design")
        assert len(entries) == 11

    @pytest.mark.timeout(5)
    async def test_sdd_design_profile_idempotent(self, db):
        await db._seed_phase_profile()
        await db._seed_phase_profile()
        entries = await db.get_phase_profile("sdd_design")
        assert len(entries) == 11


def test_sdd_design_weights_sum_to_one():
    seed_path = SEEDS_DIR / "sdd_design_phase_weights.json"
    assert seed_path.exists(), f"Archivo no encontrado: {seed_path}"
    data = json.loads(seed_path.read_text())
    total = sum(w["weight"] for w in data["weights"])
    assert abs(total - 1.0) < 1e-9, f"Weights suman {total}, esperado 1.0"


class TestSddDesignRanking:
    @pytest.mark.timeout(5)
    async def test_sdd_design_ranking_favors_aa_intelligence_index(self):
        """aa_intelligence_index pesa 0.35 (top dominante), ifbench 0.20.
        Modelo con mejor intelligence_index gana porque razonamiento arquitectonico es lo critico."""
        seed_path = SEEDS_DIR / "sdd_design_phase_weights.json"
        data = json.loads(seed_path.read_text())
        profile = [
            {
                "phase": data["phase"],
                "benchmark_slug": w["benchmark_slug"],
                "weight": w["weight"],
                "is_feature_factor": w.get("is_feature_factor", False),
            }
            for w in data["weights"]
        ]
        benchmarks = [
            _make_benchmark_row("vendor/a", "aa_intelligence_index", 95.0),
            _make_benchmark_row("vendor/a", "ifbench", 50.0),
            _make_benchmark_row("vendor/b", "aa_intelligence_index", 60.0),
            _make_benchmark_row("vendor/b", "ifbench", 90.0),
        ]
        models = [
            _make_model_row("vendor/a", "Model A"),
            _make_model_row("vendor/b", "Model B"),
        ]
        mock_db = MockDB(profile, benchmarks, models)
        result = await compute_ranking_for_phase(mock_db, "sdd_design", n=2)
        assert len(result) == 2
        assert result[0]["model_id"] == "vendor/a"


class TestPhaseLabelsSddDesign:
    def test_sdd_design_label_present(self):
        from src.bot.plugins.openrouter_prices.api import _PHASE_LABELS, _phase_label
        assert _PHASE_LABELS.get("sdd_design") == "SDD Design"
        assert _phase_label("sdd_design") == "SDD Design"


# ---------------------------------------------------------------------------
# sdd_tasks phase profile
# ---------------------------------------------------------------------------

class TestSddTasksProfileSeeded:
    @pytest.mark.timeout(5)
    async def test_sdd_tasks_profile_seeded_on_cold_start(self, db):
        entries = await db.get_phase_profile("sdd_tasks")
        assert len(entries) == 11

    @pytest.mark.timeout(5)
    async def test_sdd_tasks_profile_idempotent(self, db):
        await db._seed_phase_profile()
        await db._seed_phase_profile()
        entries = await db.get_phase_profile("sdd_tasks")
        assert len(entries) == 11


def test_sdd_tasks_weights_sum_to_one():
    seed_path = SEEDS_DIR / "sdd_tasks_phase_weights.json"
    assert seed_path.exists(), f"Archivo no encontrado: {seed_path}"
    data = json.loads(seed_path.read_text())
    total = sum(w["weight"] for w in data["weights"])
    assert abs(total - 1.0) < 1e-9, f"Weights suman {total}, esperado 1.0"


class TestSddTasksRanking:
    @pytest.mark.timeout(5)
    async def test_sdd_tasks_ranking_favors_ifbench(self):
        """ifbench 0.30 + aa_intelligence_index 0.20 combinados (0.50) > tau2_telecom 0.15.
        Modelo A lidera ifbench + aa (top dos pesos), B solo lidera tau2."""
        seed_path = SEEDS_DIR / "sdd_tasks_phase_weights.json"
        data = json.loads(seed_path.read_text())
        profile = [
            {
                "phase": data["phase"],
                "benchmark_slug": w["benchmark_slug"],
                "weight": w["weight"],
                "is_feature_factor": w.get("is_feature_factor", False),
            }
            for w in data["weights"]
        ]
        benchmarks = [
            _make_benchmark_row("vendor/a", "ifbench", 95.0),
            _make_benchmark_row("vendor/a", "aa_intelligence_index", 95.0),
            _make_benchmark_row("vendor/a", "tau2_telecom", 50.0),
            _make_benchmark_row("vendor/b", "ifbench", 60.0),
            _make_benchmark_row("vendor/b", "aa_intelligence_index", 60.0),
            _make_benchmark_row("vendor/b", "tau2_telecom", 95.0),
        ]
        models = [
            _make_model_row("vendor/a", "Model A"),
            _make_model_row("vendor/b", "Model B"),
        ]
        mock_db = MockDB(profile, benchmarks, models)
        result = await compute_ranking_for_phase(mock_db, "sdd_tasks", n=2)
        assert len(result) == 2
        assert result[0]["model_id"] == "vendor/a"


class TestPhaseLabelsSddTasks:
    def test_sdd_tasks_label_present(self):
        from src.bot.plugins.openrouter_prices.api import _PHASE_LABELS, _phase_label
        assert _PHASE_LABELS.get("sdd_tasks") == "SDD Tasks"
        assert _phase_label("sdd_tasks") == "SDD Tasks"


# ---------------------------------------------------------------------------
# sdd_apply phase profile
# ---------------------------------------------------------------------------

class TestSddApplyProfileSeeded:
    @pytest.mark.timeout(5)
    async def test_sdd_apply_profile_seeded_on_cold_start(self, db):
        entries = await db.get_phase_profile("sdd_apply")
        assert len(entries) == 11

    @pytest.mark.timeout(5)
    async def test_sdd_apply_profile_idempotent(self, db):
        await db._seed_phase_profile()
        await db._seed_phase_profile()
        entries = await db.get_phase_profile("sdd_apply")
        assert len(entries) == 11


def test_sdd_apply_weights_sum_to_one():
    seed_path = SEEDS_DIR / "sdd_apply_phase_weights.json"
    assert seed_path.exists(), f"Archivo no encontrado: {seed_path}"
    data = json.loads(seed_path.read_text())
    total = sum(w["weight"] for w in data["weights"])
    assert abs(total - 1.0) < 1e-9, f"Weights suman {total}, esperado 1.0"


class TestSddApplyRanking:
    @pytest.mark.timeout(5)
    async def test_sdd_apply_ranking_favors_aa_intelligence_index(self):
        """aa_intelligence_index 0.25 + bfcl_v3 0.20 combinados (0.45) > tau2_telecom 0.15.
        Modelo A lidera aa + bfcl_v3 (top dos pesos), B solo lidera tau2."""
        seed_path = SEEDS_DIR / "sdd_apply_phase_weights.json"
        data = json.loads(seed_path.read_text())
        profile = [
            {
                "phase": data["phase"],
                "benchmark_slug": w["benchmark_slug"],
                "weight": w["weight"],
                "is_feature_factor": w.get("is_feature_factor", False),
            }
            for w in data["weights"]
        ]
        benchmarks = [
            _make_benchmark_row("vendor/a", "aa_intelligence_index", 95.0),
            _make_benchmark_row("vendor/a", "bfcl_v3", 95.0),
            _make_benchmark_row("vendor/a", "tau2_telecom", 50.0),
            _make_benchmark_row("vendor/b", "aa_intelligence_index", 60.0),
            _make_benchmark_row("vendor/b", "bfcl_v3", 60.0),
            _make_benchmark_row("vendor/b", "tau2_telecom", 95.0),
        ]
        models = [
            _make_model_row("vendor/a", "Model A"),
            _make_model_row("vendor/b", "Model B"),
        ]
        mock_db = MockDB(profile, benchmarks, models)
        result = await compute_ranking_for_phase(mock_db, "sdd_apply", n=2)
        assert len(result) == 2
        assert result[0]["model_id"] == "vendor/a"

    @pytest.mark.timeout(5)
    async def test_sdd_apply_ranking_tool_use_combined_beats_pure_quality(self):
        """bfcl_v3 0.20 + bfcl_parallel 0.10 + tau2_telecom 0.15 = 0.45 combinado.
        Esto debe ganar contra modelo con aa_intelligence_index 0.25 dominante si tool use scores
        son MUY altos y aa es promedio. Valida que el peso tool-heavy esta correctamente distribuido."""
        seed_path = SEEDS_DIR / "sdd_apply_phase_weights.json"
        data = json.loads(seed_path.read_text())
        profile = [
            {
                "phase": data["phase"],
                "benchmark_slug": w["benchmark_slug"],
                "weight": w["weight"],
                "is_feature_factor": w.get("is_feature_factor", False),
            }
            for w in data["weights"]
        ]
        benchmarks = [
            # Modelo A: tool use combinado 100%, aa 0%
            _make_benchmark_row("vendor/a", "aa_intelligence_index", 0.0),
            _make_benchmark_row("vendor/a", "bfcl_v3", 100.0),
            _make_benchmark_row("vendor/a", "bfcl_parallel", 100.0),
            _make_benchmark_row("vendor/a", "tau2_telecom", 100.0),
            # Modelo B: aa 100%, tool use 0%
            _make_benchmark_row("vendor/b", "aa_intelligence_index", 100.0),
            _make_benchmark_row("vendor/b", "bfcl_v3", 0.0),
            _make_benchmark_row("vendor/b", "bfcl_parallel", 0.0),
            _make_benchmark_row("vendor/b", "tau2_telecom", 0.0),
        ]
        models = [
            _make_model_row("vendor/a", "Tool Specialist"),
            _make_model_row("vendor/b", "Quality Specialist"),
        ]
        mock_db = MockDB(profile, benchmarks, models)
        result = await compute_ranking_for_phase(mock_db, "sdd_apply", n=2)
        assert len(result) == 2
        # Tool combinado 0.45 > aa solo 0.25, A debe ganar
        assert result[0]["model_id"] == "vendor/a"


class TestPhaseLabelsSddApply:
    def test_sdd_apply_label_present(self):
        from src.bot.plugins.openrouter_prices.api import _PHASE_LABELS, _phase_label
        assert _PHASE_LABELS.get("sdd_apply") == "SDD Apply"
        assert _phase_label("sdd_apply") == "SDD Apply"


# ---------------------------------------------------------------------------
# sdd_verify phase profile
# ---------------------------------------------------------------------------

class TestSddVerifyProfileSeeded:
    @pytest.mark.timeout(5)
    async def test_sdd_verify_profile_seeded_on_cold_start(self, db):
        entries = await db.get_phase_profile("sdd_verify")
        assert len(entries) == 11

    @pytest.mark.timeout(5)
    async def test_sdd_verify_profile_idempotent(self, db):
        await db._seed_phase_profile()
        await db._seed_phase_profile()
        entries = await db.get_phase_profile("sdd_verify")
        assert len(entries) == 11


def test_sdd_verify_weights_sum_to_one():
    seed_path = SEEDS_DIR / "sdd_verify_phase_weights.json"
    assert seed_path.exists(), f"Archivo no encontrado: {seed_path}"
    data = json.loads(seed_path.read_text())
    total = sum(w["weight"] for w in data["weights"])
    assert abs(total - 1.0) < 1e-9, f"Weights suman {total}, esperado 1.0"


class TestSddVerifyRanking:
    @pytest.mark.timeout(5)
    async def test_sdd_verify_ranking_favors_aa_intelligence_index(self):
        """aa_intelligence_index 0.25 + ifbench 0.20 combinados (0.45) > bfcl_v3 0.15.
        Modelo A lidera aa + ifbench (top dos pesos), B solo lidera bfcl_v3."""
        seed_path = SEEDS_DIR / "sdd_verify_phase_weights.json"
        data = json.loads(seed_path.read_text())
        profile = [
            {
                "phase": data["phase"],
                "benchmark_slug": w["benchmark_slug"],
                "weight": w["weight"],
                "is_feature_factor": w.get("is_feature_factor", False),
            }
            for w in data["weights"]
        ]
        benchmarks = [
            _make_benchmark_row("vendor/a", "aa_intelligence_index", 95.0),
            _make_benchmark_row("vendor/a", "ifbench", 95.0),
            _make_benchmark_row("vendor/a", "bfcl_v3", 50.0),
            _make_benchmark_row("vendor/b", "aa_intelligence_index", 60.0),
            _make_benchmark_row("vendor/b", "ifbench", 60.0),
            _make_benchmark_row("vendor/b", "bfcl_v3", 95.0),
        ]
        models = [
            _make_model_row("vendor/a", "Audit Specialist"),
            _make_model_row("vendor/b", "Tool Specialist"),
        ]
        mock_db = MockDB(profile, benchmarks, models)
        result = await compute_ranking_for_phase(mock_db, "sdd_verify", n=2)
        assert len(result) == 2
        assert result[0]["model_id"] == "vendor/a"

    @pytest.mark.timeout(5)
    async def test_sdd_verify_ifbench_higher_than_apply(self):
        """Validacion estructural: verify tiene ifbench 0.20 mientras apply tiene 0.10.
        Diferencia documentada en rationale: severity classification rules + structured report
        + strict verdict no hedging son contractuales en verify, mientras en apply el code es largo."""
        verify_data = json.loads((SEEDS_DIR / "sdd_verify_phase_weights.json").read_text())
        apply_data = json.loads((SEEDS_DIR / "sdd_apply_phase_weights.json").read_text())

        verify_ifbench = next(w["weight"] for w in verify_data["weights"] if w["benchmark_slug"] == "ifbench")
        apply_ifbench = next(w["weight"] for w in apply_data["weights"] if w["benchmark_slug"] == "ifbench")

        assert verify_ifbench > apply_ifbench, (
            f"verify ifbench ({verify_ifbench}) debe ser mayor que apply ifbench ({apply_ifbench})"
        )


class TestPhaseLabelsSddVerify:
    def test_sdd_verify_label_present(self):
        from src.bot.plugins.openrouter_prices.api import _PHASE_LABELS, _phase_label
        assert _PHASE_LABELS.get("sdd_verify") == "SDD Verify"
        assert _phase_label("sdd_verify") == "SDD Verify"


# ---------------------------------------------------------------------------
# sdd_archive phase profile — perfil INVERTIDO: obediencia mecanica > inteligencia
# ---------------------------------------------------------------------------

class TestSddArchiveProfileSeeded:
    @pytest.mark.timeout(5)
    async def test_sdd_archive_profile_seeded_on_cold_start(self, db):
        entries = await db.get_phase_profile("sdd_archive")
        assert len(entries) == 11

    @pytest.mark.timeout(5)
    async def test_sdd_archive_profile_idempotent(self, db):
        await db._seed_phase_profile()
        await db._seed_phase_profile()
        entries = await db.get_phase_profile("sdd_archive")
        assert len(entries) == 11


def test_sdd_archive_weights_sum_to_one():
    seed_path = SEEDS_DIR / "sdd_archive_phase_weights.json"
    assert seed_path.exists(), f"Archivo no encontrado: {seed_path}"
    data = json.loads(seed_path.read_text())
    total = sum(w["weight"] for w in data["weights"])
    assert abs(total - 1.0) < 1e-9, f"Weights suman {total}, esperado 1.0"


class TestSddArchiveRanking:
    @pytest.mark.timeout(5)
    async def test_sdd_archive_ranking_favors_ifbench_dominant(self):
        """ifbench pesa 0.45 (top dominante MAXIMO del pipeline entero).
        Modelo con mejor ifbench gana abrumadoramente porque mechanical adherence + format strict
        + negative instructions COMPLEX dominan en archive (obediencia mecanica)."""
        seed_path = SEEDS_DIR / "sdd_archive_phase_weights.json"
        data = json.loads(seed_path.read_text())
        profile = [
            {
                "phase": data["phase"],
                "benchmark_slug": w["benchmark_slug"],
                "weight": w["weight"],
                "is_feature_factor": w.get("is_feature_factor", False),
            }
            for w in data["weights"]
        ]
        benchmarks = [
            _make_benchmark_row("vendor/a", "ifbench", 95.0),
            _make_benchmark_row("vendor/a", "aa_intelligence_index", 50.0),
            _make_benchmark_row("vendor/a", "bfcl_v3", 50.0),
            _make_benchmark_row("vendor/b", "ifbench", 60.0),
            _make_benchmark_row("vendor/b", "aa_intelligence_index", 95.0),
            _make_benchmark_row("vendor/b", "bfcl_v3", 95.0),
        ]
        models = [
            _make_model_row("vendor/a", "Obedient Mechanical"),
            _make_model_row("vendor/b", "Intelligent Helper"),
        ]
        mock_db = MockDB(profile, benchmarks, models)
        result = await compute_ranking_for_phase(mock_db, "sdd_archive", n=2)
        assert len(result) == 2
        # vendor/a gana porque ifbench 0.45 >> aa 0.05 + bfcl_v3 0.15
        assert result[0]["model_id"] == "vendor/a"

    def test_sdd_archive_inverted_profile_vs_other_phases(self):
        """Validacion estructural: archive tiene el perfil INVERTIDO unico del pipeline.
        ifbench debe ser MAXIMO (>= 0.40), aa_intelligence_index debe ser MINIMO (<= 0.10),
        supports_reasoning_effort debe ser MINIMO (<= 0.05). Si esta validacion falla,
        el perfil perdio su caracteristica distintiva 'obediencia > inteligencia'."""
        data = json.loads((SEEDS_DIR / "sdd_archive_phase_weights.json").read_text())
        weights = {w["benchmark_slug"]: w["weight"] for w in data["weights"]}

        assert weights["ifbench"] >= 0.40, (
            f"archive ifbench debe ser >= 0.40 (perfil obediencia maxima), "
            f"encontrado {weights['ifbench']}"
        )
        assert weights["aa_intelligence_index"] <= 0.10, (
            f"archive aa_intelligence_index debe ser <= 0.10 (alta inteligencia contraproducente), "
            f"encontrado {weights['aa_intelligence_index']}"
        )
        assert weights["supports_reasoning_effort"] <= 0.05, (
            f"archive supports_reasoning_effort debe ser <= 0.05 (reasoning hurts acá), "
            f"encontrado {weights['supports_reasoning_effort']}"
        )

    def test_sdd_archive_ifbench_higher_than_any_other_phase(self):
        """Validacion estructural cross-phase: archive.ifbench debe ser el MAXIMO del pipeline.
        Esto codifica el insight contraintuitivo del analisis: archive necesita obediencia
        mecanica mas pura que cualquier otra fase."""
        archive_ifbench = json.loads(
            (SEEDS_DIR / "sdd_archive_phase_weights.json").read_text()
        )
        archive_w = next(
            w["weight"] for w in archive_ifbench["weights"] if w["benchmark_slug"] == "ifbench"
        )

        for other_seed in (
            "orchestrator_phase_weights.json",
            "sdd_init_phase_weights.json",
            "sdd_explore_phase_weights.json",
            "sdd_propose_phase_weights.json",
            "sdd_spec_phase_weights.json",
            "sdd_design_phase_weights.json",
            "sdd_tasks_phase_weights.json",
            "sdd_apply_phase_weights.json",
            "sdd_verify_phase_weights.json",
        ):
            other_data = json.loads((SEEDS_DIR / other_seed).read_text())
            other_w = next(
                w["weight"] for w in other_data["weights"] if w["benchmark_slug"] == "ifbench"
            )
            assert archive_w > other_w, (
                f"archive.ifbench ({archive_w}) debe ser mayor que {other_seed} ifbench ({other_w})"
            )


class TestPhaseLabelsSddArchive:
    def test_sdd_archive_label_present(self):
        from src.bot.plugins.openrouter_prices.api import _PHASE_LABELS, _phase_label
        assert _PHASE_LABELS.get("sdd_archive") == "SDD Archive"
        assert _phase_label("sdd_archive") == "SDD Archive"
