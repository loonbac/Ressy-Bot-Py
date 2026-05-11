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
        value = config_manager.get("welcome_message")
        assert value == SCHEMA["welcome_message"]["default"]

    async def test_get_missing_key_returns_none(self, config_manager):
        value = config_manager.get("nonexistent_key")
        assert value is None

    async def test_get_all_returns_full_config(self, config_manager):
        all_config = config_manager.get_all()
        assert "welcome_message" in all_config
        assert "bot_prefix" in all_config

    async def test_update_existing_key(self, config_manager):
        await config_manager.update("welcome_message", "Hola!")
        assert config_manager.get("welcome_message") == "Hola!"

    async def test_update_persists_value(self, config_manager):
        await config_manager.update("welcome_message", "Persisted")
        all_values = config_manager.get_all()
        assert all_values["welcome_message"] == "Persisted"


class TestPersistence:
    async def test_values_survive_reload(self, tmp_path):
        db_path = str(tmp_path / "config.db")
        ConfigManager.reset_instance()
        cm1 = ConfigManager()
        await cm1.load(db_path)
        await cm1.update("welcome_message", "Reloaded")
        await cm1._db.close()

        ConfigManager.reset_instance()
        cm2 = ConfigManager()
        await cm2.load(db_path)
        assert cm2.get("welcome_message") == "Reloaded"
        await cm2._db.close()
        ConfigManager.reset_instance()


class TestListeners:
    async def test_observer_fires_on_update(self, config_manager):
        events = []

        def listener(key, value):
            events.append((key, value))

        config_manager.on_change(listener)
        await config_manager.update("welcome_message", "Updated")
        assert events == [("welcome_message", "Updated")]

    async def test_async_observer_fires(self, config_manager):
        events = []

        async def listener(key, value):
            events.append((key, value))

        config_manager.on_change(listener)
        await config_manager.update("welcome_message", "Async")
        assert events == [("welcome_message", "Async")]

    async def test_multiple_observers(self, config_manager):
        events1 = []
        events2 = []

        config_manager.on_change(lambda k, v: events1.append(v))
        config_manager.on_change(lambda k, v: events2.append(v))
        await config_manager.update("welcome_message", "Multi")
        assert events1 == ["Multi"]
        assert events2 == ["Multi"]

    async def test_observer_exception_does_not_break(self, config_manager):
        config_manager.on_change(lambda k, v: (_ for _ in ()).throw(RuntimeError("boom")))
        config_manager.on_change(lambda k, v: None)
        await config_manager.update("welcome_message", "Safe")
        assert config_manager.get("welcome_message") == "Safe"


class TestValidation:
    async def test_invalid_key_raises(self, config_manager):
        with pytest.raises(ValueError, match="Invalid config key"):
            await config_manager.update("bad_key", "value")

    async def test_wrong_type_raises(self, config_manager):
        with pytest.raises(ValueError, match="expects type"):
            await config_manager.update("welcome_message", 123)

    async def test_none_allowed_when_default_none(self, config_manager):
        await config_manager.update("mod_role_id", None)
        assert config_manager.get("mod_role_id") is None

    async def test_none_rejected_when_default_not_none(self, config_manager):
        with pytest.raises(ValueError, match="does not accept None"):
            await config_manager.update("welcome_message", None)


class TestAtomicity:
    async def test_concurrent_updates_are_atomic(self, config_manager):
        async def updater(value):
            for _ in range(50):
                await config_manager.update("welcome_message", value)

        await asyncio.gather(updater("A"), updater("B"))
        final = config_manager.get("welcome_message")
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

    async def test_value_none_for_default_none(self, config_manager):
        await config_manager.update("mod_role_id", None)
        assert config_manager.get("mod_role_id") is None

    async def test_empty_schema_cannot_update(self):
        ConfigManager.reset_instance()
        cm = ConfigManager()
        cm._schema = {}
        await cm.load(":memory:")
        with pytest.raises(ValueError, match="Invalid config key"):
            await cm.update("anything", "value")
        await cm._db.close()
        ConfigManager.reset_instance()
