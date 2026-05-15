"""Tests para ranking.py — funciones puras de normalización y ranking.

TDD: RED primero, luego GREEN implementando ranking.py.
Cubre: normalize_higher_is_better, normalize_lower_is_better,
weighted_score, rank_top_n, compute_ranking_for_phase (con DB mockeado).
"""
from __future__ import annotations

import pytest

# Estas importaciones fallarán hasta que exista ranking.py (RED phase)
from src.bot.plugins.openrouter_prices.ranking import (
    normalize_higher_is_better,
    normalize_lower_is_better,
    weighted_score,
    rank_top_n,
    compute_ranking_for_phase,
)


# ---------------------------------------------------------------------------
# normalize_higher_is_better
# ---------------------------------------------------------------------------

class TestNormalizeHigherIsBetter:
    @pytest.mark.timeout(5)
    def test_basic_min_max(self):
        values = {"a": 10.0, "b": 0.0, "c": 5.0}
        result = normalize_higher_is_better(values)
        assert result["a"] == pytest.approx(1.0)
        assert result["b"] == pytest.approx(0.0)
        assert result["c"] == pytest.approx(0.5)

    @pytest.mark.timeout(5)
    def test_empty_input(self):
        assert normalize_higher_is_better({}) == {}

    @pytest.mark.timeout(5)
    def test_single_value(self):
        # Un solo valor: min == max → resultado es 0.5
        result = normalize_higher_is_better({"a": 42.0})
        assert result["a"] == pytest.approx(0.5)

    @pytest.mark.timeout(5)
    def test_all_equal_returns_half(self):
        values = {"a": 7.0, "b": 7.0, "c": 7.0}
        result = normalize_higher_is_better(values)
        for v in result.values():
            assert v == pytest.approx(0.5)

    @pytest.mark.timeout(5)
    def test_preserves_all_keys(self):
        values = {"x": 1.0, "y": 2.0, "z": 3.0}
        result = normalize_higher_is_better(values)
        assert set(result.keys()) == {"x", "y", "z"}

    @pytest.mark.timeout(5)
    def test_result_bounded_zero_one(self):
        values = {"a": 100.0, "b": 50.0, "c": 0.0}
        result = normalize_higher_is_better(values)
        for v in result.values():
            assert 0.0 <= v <= 1.0


# ---------------------------------------------------------------------------
# normalize_lower_is_better
# ---------------------------------------------------------------------------

class TestNormalizeLowerIsBetter:
    @pytest.mark.timeout(5)
    def test_inverted_min_max(self):
        # lower raw → higher normalized
        values = {"a": 0.0, "b": 10.0, "c": 5.0}
        result = normalize_lower_is_better(values)
        assert result["a"] == pytest.approx(1.0)  # lowest raw → score 1.0
        assert result["b"] == pytest.approx(0.0)  # highest raw → score 0.0
        assert result["c"] == pytest.approx(0.5)

    @pytest.mark.timeout(5)
    def test_empty_input(self):
        assert normalize_lower_is_better({}) == {}

    @pytest.mark.timeout(5)
    def test_single_value_returns_half(self):
        result = normalize_lower_is_better({"only": 99.0})
        assert result["only"] == pytest.approx(0.5)

    @pytest.mark.timeout(5)
    def test_all_equal_returns_half(self):
        values = {"a": 5.0, "b": 5.0}
        result = normalize_lower_is_better(values)
        for v in result.values():
            assert v == pytest.approx(0.5)

    @pytest.mark.timeout(5)
    def test_result_bounded_zero_one(self):
        values = {"a": 1.0, "b": 100.0}
        result = normalize_lower_is_better(values)
        for v in result.values():
            assert 0.0 <= v <= 1.0


# ---------------------------------------------------------------------------
# weighted_score
# ---------------------------------------------------------------------------

class TestWeightedScore:
    @pytest.mark.timeout(5)
    def test_basic_weighted_sum(self):
        # 2 benchmarks, equal weight, model_a perfect on both
        per_benchmark = {
            "bench1": {"model_a": 1.0, "model_b": 0.0},
            "bench2": {"model_a": 1.0, "model_b": 1.0},
        }
        weights = {"bench1": 0.5, "bench2": 0.5}
        result = weighted_score(per_benchmark, weights)
        assert result["model_a"] == pytest.approx(1.0)
        assert result["model_b"] == pytest.approx(0.5)

    @pytest.mark.timeout(5)
    def test_missing_model_data_contributes_zero(self):
        # model_b has no data for bench1
        per_benchmark = {
            "bench1": {"model_a": 1.0},         # model_b missing
            "bench2": {"model_a": 0.5, "model_b": 0.5},
        }
        weights = {"bench1": 0.5, "bench2": 0.5}
        result = weighted_score(per_benchmark, weights)
        # model_b: 0 * 0.5 + 0.5 * 0.5 = 0.25
        assert result["model_b"] == pytest.approx(0.25)

    @pytest.mark.timeout(5)
    def test_zero_weight_benchmark_excluded(self):
        per_benchmark = {
            "active": {"model_a": 0.8, "model_b": 0.4},
            "inactive": {"model_a": 0.0, "model_b": 1.0},  # weight=0, excluded
        }
        weights = {"active": 1.0, "inactive": 0.0}
        result = weighted_score(per_benchmark, weights)
        # Only active benchmark counts, renormalized to 1.0
        assert result["model_a"] == pytest.approx(0.8)
        assert result["model_b"] == pytest.approx(0.4)

    @pytest.mark.timeout(5)
    def test_weights_renormalized(self):
        # Weights don't sum to 1.0 — should be renormalized
        per_benchmark = {
            "b1": {"m": 1.0},
            "b2": {"m": 1.0},
        }
        weights = {"b1": 2.0, "b2": 2.0}  # raw sum = 4.0
        result = weighted_score(per_benchmark, weights)
        assert result["m"] == pytest.approx(1.0)

    @pytest.mark.timeout(5)
    def test_benchmark_with_no_models_excluded_from_renorm(self):
        # bench2 has weight > 0 but no model has data → excluded from renorm
        per_benchmark = {
            "bench1": {"model_a": 0.6},
            "bench2": {},  # no data
        }
        weights = {"bench1": 0.5, "bench2": 0.5}
        result = weighted_score(per_benchmark, weights)
        # bench2 excluded (no data), bench1 renormalized to 1.0
        assert result["model_a"] == pytest.approx(0.6)

    @pytest.mark.timeout(5)
    def test_all_benchmarks_zero_or_no_data(self):
        per_benchmark = {
            "b1": {},
        }
        weights = {"b1": 1.0}
        result = weighted_score(per_benchmark, weights)
        assert result == {}

    @pytest.mark.timeout(5)
    def test_result_bounded_zero_one(self):
        per_benchmark = {
            "b1": {"m": 0.5},
            "b2": {"m": 0.7},
        }
        weights = {"b1": 0.6, "b2": 0.4}
        result = weighted_score(per_benchmark, weights)
        for v in result.values():
            assert 0.0 <= v <= 1.0


# ---------------------------------------------------------------------------
# rank_top_n
# ---------------------------------------------------------------------------

class TestRankTopN:
    @pytest.mark.timeout(5)
    def test_basic_ranking(self):
        scores = {"a": 0.9, "b": 0.5, "c": 0.7}
        result = rank_top_n(scores, n=3)
        assert result[0] == ("a", pytest.approx(0.9))
        assert result[1][0] == "c"
        assert result[2][0] == "b"

    @pytest.mark.timeout(5)
    def test_n_limits_results(self):
        scores = {"a": 0.9, "b": 0.8, "c": 0.7, "d": 0.6}
        result = rank_top_n(scores, n=2)
        assert len(result) == 2
        assert result[0][0] == "a"
        assert result[1][0] == "b"

    @pytest.mark.timeout(5)
    def test_n_larger_than_keys_returns_all(self):
        scores = {"a": 0.5, "b": 0.3}
        result = rank_top_n(scores, n=10)
        assert len(result) == 2

    @pytest.mark.timeout(5)
    def test_ties_broken_alphabetically(self):
        scores = {"z_model": 0.5, "a_model": 0.5, "m_model": 0.5}
        result = rank_top_n(scores, n=3)
        names = [r[0] for r in result]
        assert names == ["a_model", "m_model", "z_model"]

    @pytest.mark.timeout(5)
    def test_empty_scores(self):
        result = rank_top_n({}, n=10)
        assert result == []

    @pytest.mark.timeout(5)
    def test_single_model(self):
        result = rank_top_n({"only": 0.42}, n=5)
        assert len(result) == 1
        assert result[0] == ("only", pytest.approx(0.42))


# ---------------------------------------------------------------------------
# compute_ranking_for_phase — DB mockeado
# ---------------------------------------------------------------------------

class MockDB:
    """Mock mínimo del DB para tests de compute_ranking_for_phase."""

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
        "phase": "orchestrator",
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


class TestComputeRankingForPhase:
    @pytest.mark.timeout(5)
    async def test_returns_correct_shape(self):
        profile = [
            _make_profile_entry("ifbench", 0.5),
            _make_profile_entry("tau2_telecom", 0.5),
        ]
        benchmarks = [
            _make_benchmark_row("vendor/a", "ifbench", 80.0),
            _make_benchmark_row("vendor/a", "tau2_telecom", 70.0),
            _make_benchmark_row("vendor/b", "ifbench", 60.0),
            _make_benchmark_row("vendor/b", "tau2_telecom", 90.0),
        ]
        models = [
            _make_model_row("vendor/a", "Model A"),
            _make_model_row("vendor/b", "Model B"),
        ]
        db = MockDB(profile, benchmarks, models)
        result = await compute_ranking_for_phase(db, "orchestrator", n=2)
        assert len(result) == 2
        for entry in result:
            assert "rank" in entry
            assert "model_id" in entry
            assert "name" in entry
            assert "score" in entry
            assert "breakdown" in entry
            assert 0.0 <= entry["score"] <= 1.0

    @pytest.mark.timeout(5)
    async def test_sorted_descending(self):
        profile = [_make_profile_entry("ifbench", 1.0)]
        benchmarks = [
            _make_benchmark_row("vendor/low", "ifbench", 10.0),
            _make_benchmark_row("vendor/high", "ifbench", 90.0),
            _make_benchmark_row("vendor/mid", "ifbench", 50.0),
        ]
        models = [
            _make_model_row("vendor/low", "Low Model"),
            _make_model_row("vendor/high", "High Model"),
            _make_model_row("vendor/mid", "Mid Model"),
        ]
        db = MockDB(profile, benchmarks, models)
        result = await compute_ranking_for_phase(db, "orchestrator", n=3)
        assert result[0]["model_id"] == "vendor/high"
        assert result[0]["rank"] == 1
        assert result[-1]["model_id"] == "vendor/low"

    @pytest.mark.timeout(5)
    async def test_missing_benchmark_score_contributes_zero(self):
        profile = [
            _make_profile_entry("ifbench", 0.5),
            _make_profile_entry("tau2_telecom", 0.5),
        ]
        # vendor/b has no ifbench score
        benchmarks = [
            _make_benchmark_row("vendor/a", "ifbench", 80.0),
            _make_benchmark_row("vendor/a", "tau2_telecom", 70.0),
            _make_benchmark_row("vendor/b", "tau2_telecom", 70.0),
        ]
        models = [
            _make_model_row("vendor/a", "Model A"),
            _make_model_row("vendor/b", "Model B"),
        ]
        db = MockDB(profile, benchmarks, models)
        result = await compute_ranking_for_phase(db, "orchestrator", n=2)
        b_entry = next(e for e in result if e["model_id"] == "vendor/b")
        # Score must be valid float (not NaN), vendor/b gets 0 for ifbench
        assert isinstance(b_entry["score"], float)
        assert b_entry["score"] == b_entry["score"]  # NaN check

    @pytest.mark.timeout(5)
    async def test_n_limits_output(self):
        profile = [_make_profile_entry("ifbench", 1.0)]
        benchmarks = [
            _make_benchmark_row(f"vendor/m{i}", "ifbench", float(i * 10))
            for i in range(1, 11)
        ]
        models = [
            _make_model_row(f"vendor/m{i}", f"Model {i}")
            for i in range(1, 11)
        ]
        db = MockDB(profile, benchmarks, models)
        result = await compute_ranking_for_phase(db, "orchestrator", n=5)
        assert len(result) == 5

    @pytest.mark.timeout(5)
    async def test_breakdown_contains_contributing_benchmarks(self):
        profile = [
            _make_profile_entry("ifbench", 0.6),
            _make_profile_entry("bfcl_v3", 0.4),
        ]
        benchmarks = [
            _make_benchmark_row("vendor/a", "ifbench", 80.0),
            _make_benchmark_row("vendor/a", "bfcl_v3", 60.0),
        ]
        models = [_make_model_row("vendor/a", "Model A")]
        db = MockDB(profile, benchmarks, models)
        result = await compute_ranking_for_phase(db, "orchestrator", n=1)
        breakdown = result[0]["breakdown"]
        slugs = {b["benchmark_slug"] for b in breakdown}
        assert "ifbench" in slugs or "bfcl_v3" in slugs

    @pytest.mark.timeout(5)
    async def test_cache_ratio_feature_factor(self):
        """input_cache_read_ratio: lower ratio → higher score (lower_is_better)."""
        profile = [
            _make_profile_entry("input_cache_read_ratio", 1.0, is_feature_factor=True),
        ]
        # model_a: ratio 0.1 (good), model_b: ratio 0.9 (bad)
        models = [
            _make_model_row("vendor/a", "Model A", prompt="0.01", input_cache_read="0.001"),
            _make_model_row("vendor/b", "Model B", prompt="0.01", input_cache_read="0.009"),
        ]
        db = MockDB(profile, [], models)
        result = await compute_ranking_for_phase(db, "orchestrator", n=2)
        # vendor/a should rank higher (lower cache ratio = better)
        assert result[0]["model_id"] == "vendor/a"

    @pytest.mark.timeout(5)
    async def test_supports_reasoning_effort_feature_factor(self):
        """supports_reasoning_effort: 1.0 if in supported_parameters else 0.0."""
        profile = [
            _make_profile_entry("supports_reasoning_effort", 1.0, is_feature_factor=True),
        ]
        models = [
            _make_model_row("vendor/a", "Model A", supported_parameters='["reasoning_effort"]'),
            _make_model_row("vendor/b", "Model B", supported_parameters='[]'),
        ]
        db = MockDB(profile, [], models)
        result = await compute_ranking_for_phase(db, "orchestrator", n=2)
        assert result[0]["model_id"] == "vendor/a"

    @pytest.mark.timeout(5)
    async def test_supports_verbosity_feature_factor(self):
        """supports_verbosity: 1.0 if in supported_parameters else 0.0."""
        profile = [
            _make_profile_entry("supports_verbosity", 1.0, is_feature_factor=True),
        ]
        models = [
            _make_model_row("vendor/a", "Model A", supported_parameters='["verbosity"]'),
            _make_model_row("vendor/b", "Model B", supported_parameters='[]'),
        ]
        db = MockDB(profile, [], models)
        result = await compute_ranking_for_phase(db, "orchestrator", n=2)
        assert result[0]["model_id"] == "vendor/a"
