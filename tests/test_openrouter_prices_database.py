"""Tests para OpenRouterDatabase.

Usa base de datos en memoria (':memory:') para aislar cada test.
Cubre: schema creation, config seeding (idempotente), upsert + stale-marking,
list_models con filtros, get_model, metadata CRUD, count_models.
"""
from __future__ import annotations

import json
import time
import pytest

from src.bot.plugins.openrouter_prices.database import OpenRouterDatabase


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def db() -> OpenRouterDatabase:
    database = OpenRouterDatabase(":memory:")
    await database.connect()
    yield database
    await database.close()


def _make_model(model_id: str, modality: str = "text->text", prompt: str = "0.000001",
                completion: str = "0.000002") -> dict:
    """Helper que construye un dict con la forma que devuelve la API de OpenRouter."""
    return {
        "id": model_id,
        "name": f"Model {model_id}",
        "description": "Test model",
        "created": 1_700_000_000,
        "context_length": 4096,
        "architecture": {
            "input_modalities": ["text"],
            "output_modalities": ["text"],
            "modality": modality,
        },
        "pricing": {
            "prompt": prompt,
            "completion": completion,
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


def _make_image_model(model_id: str) -> dict:
    """Modelo con modality image (sin texto en input_modalities)."""
    m = _make_model(model_id, modality="image->text")
    m["architecture"]["input_modalities"] = ["image"]
    return m


# ---------------------------------------------------------------------------
# Schema creation
# ---------------------------------------------------------------------------

class TestSchemaCreation:
    async def test_config_table_exists(self, db: OpenRouterDatabase):
        rows = await db._db.execute_fetchall(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='config'"
        )
        assert rows, "La tabla 'config' no fue creada"

    async def test_models_table_exists(self, db: OpenRouterDatabase):
        rows = await db._db.execute_fetchall(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='models'"
        )
        assert rows, "La tabla 'models' no fue creada"

    async def test_metadata_table_exists(self, db: OpenRouterDatabase):
        rows = await db._db.execute_fetchall(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='metadata'"
        )
        assert rows, "La tabla 'metadata' no fue creada"

    async def test_indexes_exist(self, db: OpenRouterDatabase):
        rows = await db._db.execute_fetchall(
            "SELECT name FROM sqlite_master WHERE type='index'"
        )
        index_names = {r[0] for r in rows}
        assert "idx_models_stale" in index_names
        assert "idx_models_pricing_prompt" in index_names


# ---------------------------------------------------------------------------
# Config seeding (idempotency)
# ---------------------------------------------------------------------------

class TestConfigSeeding:
    async def test_defaults_seeded(self, db: OpenRouterDatabase):
        config = await db.get_config()
        assert config["enabled"] == "true"
        assert config["ttl_seconds"] == "3600"
        assert config["max_models_command"] == "10"
        assert "discord_channel_id" in config

    async def test_seed_is_idempotent(self, db: OpenRouterDatabase):
        # Llamar _seed_defaults dos veces no sobreescribe
        await db._seed_defaults()
        await db._seed_defaults()
        config = await db.get_config()
        # El valor por defecto sigue siendo el original, no se duplicó
        assert config["ttl_seconds"] == "3600"

    async def test_seed_does_not_overwrite_custom_value(self, db: OpenRouterDatabase):
        await db.update_config({"ttl_seconds": "7200"})
        await db._seed_defaults()
        config = await db.get_config()
        assert config["ttl_seconds"] == "7200"


# ---------------------------------------------------------------------------
# update_config
# ---------------------------------------------------------------------------

class TestUpdateConfig:
    async def test_update_single_key(self, db: OpenRouterDatabase):
        await db.update_config({"ttl_seconds": "900"})
        config = await db.get_config()
        assert config["ttl_seconds"] == "900"

    async def test_update_does_not_touch_other_keys(self, db: OpenRouterDatabase):
        await db.update_config({"enabled": "false"})
        config = await db.get_config()
        assert config["ttl_seconds"] == "3600"  # sin cambios
        assert config["enabled"] == "false"


# ---------------------------------------------------------------------------
# upsert_models + stale marking
# ---------------------------------------------------------------------------

class TestUpsertModels:
    async def test_insert_new_models(self, db: OpenRouterDatabase):
        models = [_make_model("a/1"), _make_model("a/2"), _make_model("a/3")]
        count = await db.upsert_models(models, fetched_at=int(time.time()))
        assert count == 3

    async def test_upsert_updates_existing(self, db: OpenRouterDatabase):
        ts = int(time.time())
        await db.upsert_models([_make_model("a/1", prompt="0.000001")], fetched_at=ts)
        # Actualizar precio
        updated = _make_model("a/1", prompt="0.000005")
        count = await db.upsert_models([updated], fetched_at=ts + 1)
        assert count == 1
        row = await db.get_model("a/1")
        assert row is not None
        assert row["pricing_prompt"] == "0.000005"

    async def test_stale_marking_after_partial_upsert(self, db: OpenRouterDatabase):
        ts = int(time.time())
        # Insertar 3 modelos
        initial = [_make_model("a/1"), _make_model("a/2"), _make_model("a/3")]
        await db.upsert_models(initial, fetched_at=ts)

        # Refrescar con solo 2 modelos distintos — "a/3" debe quedar stale
        refresh = [_make_model("a/1"), _make_model("a/2")]
        await db.upsert_models(refresh, fetched_at=ts + 10)

        stale_count = await db.count_models(stale=True)
        assert stale_count == 1

        row = await db.get_model("a/3")
        assert row is not None
        assert row["stale"] == 1

    async def test_non_stale_models_after_upsert(self, db: OpenRouterDatabase):
        ts = int(time.time())
        await db.upsert_models([_make_model("a/1"), _make_model("a/2")], fetched_at=ts)
        await db.upsert_models([_make_model("a/1")], fetched_at=ts + 1)

        row_1 = await db.get_model("a/1")
        assert row_1["stale"] == 0

    async def test_stale_not_marked_on_empty_list(self, db: OpenRouterDatabase):
        """Upsert con lista vacía no debería marcar nada como stale (edge case)."""
        ts = int(time.time())
        await db.upsert_models([_make_model("a/1")], fetched_at=ts)
        # Lista vacía — no marcar stale (la semántica es "no se recibió nada")
        count = await db.upsert_models([], fetched_at=ts + 1)
        assert count == 0
        row = await db.get_model("a/1")
        # Con lista vacía el modelo existente no debería marcarse stale
        assert row["stale"] == 0


# ---------------------------------------------------------------------------
# list_models
# ---------------------------------------------------------------------------

class TestListModels:
    async def test_returns_all_by_default(self, db: OpenRouterDatabase):
        ts = int(time.time())
        await db.upsert_models([_make_model("a/1"), _make_model("a/2")], fetched_at=ts)
        rows = await db.list_models()
        assert len(rows) == 2

    async def test_text_only_excludes_image_models(self, db: OpenRouterDatabase):
        ts = int(time.time())
        models = [
            _make_model("a/text1"),
            _make_model("a/text2"),
            _make_image_model("a/img1"),
        ]
        await db.upsert_models(models, fetched_at=ts)

        rows = await db.list_models(text_only=True)
        ids = [r["id"] for r in rows]
        assert "a/text1" in ids
        assert "a/text2" in ids
        assert "a/img1" not in ids

    async def test_text_only_false_includes_image_models(self, db: OpenRouterDatabase):
        ts = int(time.time())
        models = [_make_model("a/text1"), _make_image_model("a/img1")]
        await db.upsert_models(models, fetched_at=ts)

        rows = await db.list_models(text_only=False)
        ids = [r["id"] for r in rows]
        assert "a/img1" in ids

    async def test_sort_by_prompt_ascending(self, db: OpenRouterDatabase):
        ts = int(time.time())
        models = [
            _make_model("a/cheap", prompt="0.000001"),
            _make_model("a/mid", prompt="0.000005"),
            _make_model("a/exp", prompt="0.00001"),
        ]
        await db.upsert_models(models, fetched_at=ts)

        rows = await db.list_models(sort_by="prompt", sort_dir="asc")
        prices = [r["pricing_prompt"] for r in rows]
        assert prices == sorted(prices)

    async def test_sort_by_name(self, db: OpenRouterDatabase):
        ts = int(time.time())
        await db.upsert_models([
            _make_model("a/z"),
            _make_model("a/a"),
        ], fetched_at=ts)
        rows = await db.list_models(sort_by="name", sort_dir="asc")
        names = [r["name"] for r in rows]
        assert names == sorted(names)

    async def test_limit(self, db: OpenRouterDatabase):
        ts = int(time.time())
        await db.upsert_models([_make_model(f"a/{i}") for i in range(10)], fetched_at=ts)
        rows = await db.list_models(limit=3)
        assert len(rows) == 3

    async def test_excludes_stale_by_default(self, db: OpenRouterDatabase):
        ts = int(time.time())
        await db.upsert_models([_make_model("a/1"), _make_model("a/2")], fetched_at=ts)
        # Re-upsert only "a/1" → "a/2" becomes stale
        await db.upsert_models([_make_model("a/1")], fetched_at=ts + 1)

        rows = await db.list_models(include_stale=False)
        ids = [r["id"] for r in rows]
        assert "a/2" not in ids

    async def test_includes_stale_when_requested(self, db: OpenRouterDatabase):
        ts = int(time.time())
        await db.upsert_models([_make_model("a/1"), _make_model("a/2")], fetched_at=ts)
        await db.upsert_models([_make_model("a/1")], fetched_at=ts + 1)

        rows = await db.list_models(include_stale=True)
        ids = [r["id"] for r in rows]
        assert "a/2" in ids


# ---------------------------------------------------------------------------
# get_model
# ---------------------------------------------------------------------------

class TestGetModel:
    async def test_returns_model_when_exists(self, db: OpenRouterDatabase):
        ts = int(time.time())
        await db.upsert_models([_make_model("vendor/model-1")], fetched_at=ts)
        row = await db.get_model("vendor/model-1")
        assert row is not None
        assert row["id"] == "vendor/model-1"

    async def test_returns_none_when_missing(self, db: OpenRouterDatabase):
        row = await db.get_model("does/not-exist")
        assert row is None


# ---------------------------------------------------------------------------
# Metadata CRUD
# ---------------------------------------------------------------------------

class TestMetadata:
    async def test_set_and_get_round_trip(self, db: OpenRouterDatabase):
        await db.set_metadata("last_fetched_at", "1700000000")
        meta = await db.get_metadata()
        assert meta["last_fetched_at"] == "1700000000"

    async def test_overwrite_metadata(self, db: OpenRouterDatabase):
        await db.set_metadata("last_fetched_at", "100")
        await db.set_metadata("last_fetched_at", "200")
        meta = await db.get_metadata()
        assert meta["last_fetched_at"] == "200"

    async def test_get_metadata_empty(self, db: OpenRouterDatabase):
        meta = await db.get_metadata()
        assert isinstance(meta, dict)


# ---------------------------------------------------------------------------
# count_models
# ---------------------------------------------------------------------------

class TestCountModels:
    async def test_count_zero_initially(self, db: OpenRouterDatabase):
        assert await db.count_models() == 0

    async def test_count_after_insert(self, db: OpenRouterDatabase):
        ts = int(time.time())
        await db.upsert_models([_make_model("a/1"), _make_model("a/2")], fetched_at=ts)
        assert await db.count_models() == 2

    async def test_count_stale(self, db: OpenRouterDatabase):
        ts = int(time.time())
        await db.upsert_models([_make_model("a/1"), _make_model("a/2")], fetched_at=ts)
        await db.upsert_models([_make_model("a/1")], fetched_at=ts + 1)
        assert await db.count_models(stale=True) == 1

    async def test_count_non_stale(self, db: OpenRouterDatabase):
        ts = int(time.time())
        await db.upsert_models([_make_model("a/1"), _make_model("a/2")], fetched_at=ts)
        await db.upsert_models([_make_model("a/1")], fetched_at=ts + 1)
        # count_models() sin stale=True cuenta todos (activos + stale)
        total = await db.count_models()
        assert total == 2
