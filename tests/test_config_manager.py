import asyncio

import pytest

from src.bot.core.config import ConfigManager, SCHEMA


class TestSingleton:
    async def test_same_instance(self):
        ConfigManager.reset_instance()
        cm1 = ConfigManager()
        cm2 = ConfigManager()
        assert cm1 is cm2

    async def test_reset_creates_new(self):
        ConfigManager.reset_instance()
        cm1 = ConfigManager()
        ConfigManager.reset_instance()
        cm2 = ConfigManager()
        assert cm1 is not cm2


class TestCRUD:
    async def test_get_existing_key(self, config_manager):
        value = config_manager.get("bot_prefix")
        assert value == SCHEMA["bot_prefix"]["default"]

    async def test_get_missing_key_returns_none(self, config_manager):
        value = config_manager.get("nonexistent_key")
        assert value is None

    async def test_get_all_returns_full_config(self, config_manager):
        all_config = config_manager.get_all()
        assert "bot_prefix" in all_config
        assert "version" in all_config

    async def test_update_existing_key(self, config_manager):
        await config_manager.update("bot_prefix", "!")
        assert config_manager.get("bot_prefix") == "!"

    async def test_update_persists_value(self, config_manager):
        await config_manager.update("bot_prefix", "Persisted")
        all_values = config_manager.get_all()
        assert all_values["bot_prefix"] == "Persisted"


class TestPersistence:
    async def test_values_survive_reload(self, tmp_path):
        db_path = str(tmp_path / "config.db")
        ConfigManager.reset_instance()
        cm1 = ConfigManager()
        await cm1.load(db_path)
        await cm1.update("bot_prefix", "Reloaded")
        await cm1._db.close()

        ConfigManager.reset_instance()
        cm2 = ConfigManager()
        await cm2.load(db_path)
        assert cm2.get("bot_prefix") == "Reloaded"
        await cm2._db.close()
        ConfigManager.reset_instance()


class TestListeners:
    async def test_observer_fires_on_update(self, config_manager):
        events = []

        def listener(key, value):
            events.append((key, value))

        config_manager.on_change(listener)
        await config_manager.update("bot_prefix", "Updated")
        assert events == [("bot_prefix", "Updated")]

    async def test_async_observer_fires(self, config_manager):
        events = []

        async def listener(key, value):
            events.append((key, value))

        config_manager.on_change(listener)
        await config_manager.update("bot_prefix", "Async")
        assert events == [("bot_prefix", "Async")]

    async def test_multiple_observers(self, config_manager):
        events1 = []
        events2 = []

        config_manager.on_change(lambda k, v: events1.append(v))
        config_manager.on_change(lambda k, v: events2.append(v))
        await config_manager.update("bot_prefix", "Multi")
        assert events1 == ["Multi"]
        assert events2 == ["Multi"]

    async def test_observer_exception_does_not_break(self, config_manager):
        config_manager.on_change(lambda k, v: (_ for _ in ()).throw(RuntimeError("boom")))
        config_manager.on_change(lambda k, v: None)
        await config_manager.update("bot_prefix", "Safe")
        assert config_manager.get("bot_prefix") == "Safe"


class TestValidation:
    async def test_invalid_key_raises(self, config_manager):
        with pytest.raises(ValueError, match="Invalid config key"):
            await config_manager.update("bad_key", "value")

    async def test_wrong_type_raises(self, config_manager):
        with pytest.raises(ValueError, match="expects type"):
            await config_manager.update("bot_prefix", 123)

    async def test_none_rejected_when_default_not_none(self, config_manager):
        with pytest.raises(ValueError, match="does not accept None"):
            await config_manager.update("bot_prefix", None)


class TestAtomicity:
    async def test_concurrent_updates_are_atomic(self, config_manager):
        async def updater(value):
            for _ in range(50):
                await config_manager.update("bot_prefix", value)

        await asyncio.gather(updater("A"), updater("B"))
        final = config_manager.get("bot_prefix")
        assert final in ("A", "B")


class TestWALMode:
    async def test_wal_mode_enabled(self, tmp_path):
        db_path = str(tmp_path / "wal.db")
        ConfigManager.reset_instance()
        cm = ConfigManager()
        await cm.load(db_path)
        async with cm._db.execute("PRAGMA journal_mode") as cursor:
            row = await cursor.fetchone()
        assert row[0].lower() == "wal"
        await cm._db.close()
        ConfigManager.reset_instance()


class TestEdgeCases:
    async def test_empty_key_raises(self, config_manager):
        with pytest.raises(ValueError, match="Invalid config key"):
            await config_manager.update("", "value")

    async def test_empty_schema_cannot_update(self):
        ConfigManager.reset_instance()
        cm = ConfigManager()
        cm._schema = {}
        await cm.load(":memory:")
        with pytest.raises(ValueError, match="Invalid config key"):
            await cm.update("anything", "value")
        await cm._db.close()
        ConfigManager.reset_instance()

    async def test_load_skips_keys_not_in_schema(self, tmp_path):
        import aiosqlite

        db_path = str(tmp_path / "skip.db")

        db = await aiosqlite.connect(db_path)
        await db.execute(
            "CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT)"
        )
        await db.execute(
            "INSERT INTO config (key, value) VALUES (?, ?)",
            ("ghost_key", '"ghost_value"'),
        )
        await db.commit()
        await db.close()

        ConfigManager.reset_instance()
        cm = ConfigManager()
        await cm.load(db_path)
        assert "ghost_key" not in cm.get_all()
        await cm._db.close()
        ConfigManager.reset_instance()

    async def test_unknown_type_raises(self):
        ConfigManager.reset_instance()
        cm = ConfigManager()
        await cm.load(":memory:")
        cm._schema["bad_key"] = {"type": "weird_type", "default": None}
        with pytest.raises(ValueError, match="Unknown type"):
            cm._validate_type("bad_key", "whatever")
        await cm._db.close()
        ConfigManager.reset_instance()

    async def test_persist_before_load_raises(self):
        ConfigManager.reset_instance()
        cm = ConfigManager()
        with pytest.raises(RuntimeError, match="Call load\\(\\) first"):
            await cm._persist("bot_prefix", "test")
        ConfigManager.reset_instance()
        cm = ConfigManager()
        cm._schema = {}
        await cm.load(":memory:")
        with pytest.raises(ValueError, match="Invalid config key"):
            await cm.update("anything", "value")
        await cm._db.close()
        ConfigManager.reset_instance()

    async def test_load_skips_keys_not_in_schema(self, tmp_path):
        import aiosqlite

        db_path = str(tmp_path / "skip.db")

        db = await aiosqlite.connect(db_path)
        await db.execute(
            "CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT)"
        )
        await db.execute(
            "INSERT INTO config (key, value) VALUES (?, ?)",
            ("ghost_key", '"ghost_value"'),
        )
        await db.commit()
        await db.close()

        ConfigManager.reset_instance()
        cm = ConfigManager()
        await cm.load(db_path)
        assert "ghost_key" not in cm.get_all()
        await cm._db.close()
        ConfigManager.reset_instance()

    async def test_unknown_type_raises(self):
        ConfigManager.reset_instance()
        cm = ConfigManager()
        await cm.load(":memory:")
        cm._schema["bad_key"] = {"type": "weird_type", "default": None}
        with pytest.raises(ValueError, match="Unknown type"):
            cm._validate_type("bad_key", "whatever")
        await cm._db.close()
        ConfigManager.reset_instance()

    async def test_persist_before_load_raises(self):
        ConfigManager.reset_instance()
        cm = ConfigManager()
        with pytest.raises(RuntimeError, match="Call load\\(\\) first"):
            await cm._persist("bot_prefix", "test")
        ConfigManager.reset_instance()
