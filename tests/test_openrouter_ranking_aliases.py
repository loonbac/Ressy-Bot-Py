"""Tests para aliases.py — fuzzy_match y resolve_alias.

TDD: RED primero, luego GREEN implementando aliases.py.
Cubre: fuzzy_match (exact, close, far, empty), resolve_alias DB roundtrip.
"""
from __future__ import annotations

import time
import pytest

# Importaciones fallarán hasta que exista aliases.py (RED phase)
from src.bot.plugins.openrouter_prices.aliases import fuzzy_match, resolve_alias
from src.bot.plugins.openrouter_prices.database import OpenRouterDatabase


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def db():
    database = OpenRouterDatabase(":memory:")
    await database.connect()
    yield database
    await database.close()


def _make_model(model_id: str, name: str, modality: str = "text->text"):
    return {
        "id": model_id,
        "name": name,
        "description": "",
        "created": 1_700_000_000,
        "context_length": 4096,
        "architecture": {
            "input_modalities": ["text"],
            "output_modalities": ["text"],
            "modality": modality,
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


# ---------------------------------------------------------------------------
# fuzzy_match
# ---------------------------------------------------------------------------

class TestFuzzyMatch:
    @pytest.mark.timeout(5)
    def test_exact_match_returns_one(self):
        target = "Claude 3 Haiku"
        candidates = ["Claude 3 Haiku", "GPT-4o", "Gemini Pro"]
        match, ratio = fuzzy_match(target, candidates)
        assert match == "Claude 3 Haiku"
        assert ratio >= 0.99

    @pytest.mark.timeout(5)
    def test_close_match_above_threshold(self):
        target = "Claude 3 Haiku"
        candidates = ["Claude 3 Hiku", "GPT-4o"]  # typo but close
        match, ratio = fuzzy_match(target, candidates, threshold=0.75)
        assert match is not None
        assert ratio >= 0.75

    @pytest.mark.timeout(5)
    def test_far_match_returns_none(self):
        target = "Claude 3 Haiku"
        candidates = ["GPT-4o", "Llama 2 70B"]
        match, ratio = fuzzy_match(target, candidates, threshold=0.75)
        assert match is None
        assert ratio < 0.75

    @pytest.mark.timeout(5)
    def test_empty_candidates_returns_none(self):
        match, ratio = fuzzy_match("Claude 3 Haiku", [], threshold=0.75)
        assert match is None
        assert ratio == 0.0

    @pytest.mark.timeout(5)
    def test_case_insensitive_comparison(self):
        target = "claude 3 haiku"
        candidates = ["Claude 3 Haiku", "GPT-4o"]
        match, ratio = fuzzy_match(target, candidates, threshold=0.9)
        assert match == "Claude 3 Haiku"

    @pytest.mark.timeout(5)
    def test_returns_best_match_when_multiple_close(self):
        target = "GPT-4o mini"
        candidates = ["GPT-4o mini", "GPT-4o", "GPT-4 turbo"]
        match, ratio = fuzzy_match(target, candidates, threshold=0.75)
        assert match == "GPT-4o mini"
        assert ratio == pytest.approx(1.0, abs=0.01)

    @pytest.mark.timeout(5)
    def test_below_threshold_returns_best_ratio(self):
        """Cuando no hay match, devuelve (None, best_ratio_below_threshold)."""
        target = "Completely Different Name"
        candidates = ["GPT-4o", "Llama 2"]
        match, ratio = fuzzy_match(target, candidates, threshold=0.75)
        assert match is None
        # El ratio devuelto es el mejor encontrado aunque esté bajo el threshold
        assert isinstance(ratio, float)
        assert 0.0 <= ratio < 0.75


# ---------------------------------------------------------------------------
# resolve_alias — DB roundtrip
# ---------------------------------------------------------------------------

class TestResolveAlias:
    @pytest.mark.timeout(5)
    async def test_returns_mapped_id_when_explicit_aa_alias(self, db):
        """Si existe alias explicit para artificial_analysis → retorna openrouter_id."""
        # Primero insertamos un alias manual
        await db.upsert_alias(
            openrouter_id="anthropic/claude-3-haiku",
            artificial_analysis_name="Claude 3 Haiku",
            bfcl_key=None,
            match_confidence=1.0,
        )
        result = await resolve_alias(
            db,
            openrouter_id="anthropic/claude-3-haiku",
            source="artificial_analysis",
            external_name="Claude 3 Haiku",
        )
        assert result == "anthropic/claude-3-haiku"

    @pytest.mark.timeout(5)
    async def test_fuzzy_match_creates_alias_entry(self, db):
        """Si no hay alias pero hay fuzzy match → crea entrada y devuelve matched id."""
        ts = int(time.time())
        await db.upsert_models(
            [_make_model("anthropic/claude-3-haiku", "Claude 3 Haiku")],
            fetched_at=ts,
        )
        result = await resolve_alias(
            db,
            openrouter_id="anthropic/claude-3-haiku",
            source="artificial_analysis",
            external_name="Claude 3 Haiku",
        )
        # Debería retornar el id matcheado
        assert result == "anthropic/claude-3-haiku"
        # Y persistir en model_aliases
        alias_row = await db.get_alias("anthropic/claude-3-haiku")
        assert alias_row is not None
        assert alias_row["match_confidence"] is not None

    @pytest.mark.timeout(5)
    async def test_no_match_returns_none_and_upserts_row(self, db):
        """Sin match → devuelve None y crea fila con confidence baja."""
        ts = int(time.time())
        await db.upsert_models(
            [_make_model("anthropic/claude-3-haiku", "Claude 3 Haiku")],
            fetched_at=ts,
        )
        result = await resolve_alias(
            db,
            openrouter_id="anthropic/claude-3-haiku",
            source="artificial_analysis",
            external_name="Completely Unrelated Name XYZ",
        )
        assert result is None
        # Debe haberse creado una fila con NULL match
        alias_row = await db.get_alias("anthropic/claude-3-haiku")
        assert alias_row is not None

    @pytest.mark.timeout(5)
    async def test_upsert_updates_existing_alias(self, db):
        """Llamar upsert_alias dos veces actualiza sin duplicar."""
        await db.upsert_alias(
            openrouter_id="vendor/model",
            artificial_analysis_name="Model Name",
            bfcl_key=None,
            match_confidence=0.8,
        )
        await db.upsert_alias(
            openrouter_id="vendor/model",
            artificial_analysis_name="Model Name Updated",
            bfcl_key="model-key",
            match_confidence=0.95,
        )
        alias_row = await db.get_alias("vendor/model")
        assert alias_row["artificial_analysis_name"] == "Model Name Updated"
        assert alias_row["bfcl_key"] == "model-key"
        assert alias_row["match_confidence"] == pytest.approx(0.95)

    @pytest.mark.timeout(5)
    async def test_list_aliases_returns_all(self, db):
        """list_aliases devuelve todas las filas de model_aliases."""
        await db.upsert_alias("vendor/a", "Model A", None, 0.9)
        await db.upsert_alias("vendor/b", "Model B", "b-key", 0.85)
        rows = await db.list_aliases()
        assert len(rows) == 2
        ids = {r["openrouter_id"] for r in rows}
        assert "vendor/a" in ids
        assert "vendor/b" in ids

    @pytest.mark.timeout(5)
    async def test_list_all_model_slugs(self, db):
        """list_all_model_slugs devuelve todos los IDs de la tabla models."""
        ts = int(time.time())
        await db.upsert_models(
            [
                _make_model("vendor/model-1", "Model 1"),
                _make_model("vendor/model-2", "Model 2"),
            ],
            fetched_at=ts,
        )
        slugs = await db.list_all_model_slugs()
        assert "vendor/model-1" in slugs
        assert "vendor/model-2" in slugs
