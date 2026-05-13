import asyncio
import inspect
import json
from typing import Any, Callable

import aiosqlite


SCHEMA = {
    "bot_prefix": {"type": "string", "default": "/"},
    "version": {"type": "string", "default": "1.0.0"},
    "guild_id": {"type": "string", "default": ""},
}


class ConfigManager:
    _instance: "ConfigManager | None" = None

    def __new__(cls, *args: Any, **kwargs: Any) -> "ConfigManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._db_path: str | None = None
        self._db: aiosqlite.Connection | None = None
        self._config: dict[str, Any] = {}
        self._listeners: list[Callable[[str, Any], Any]] = []
        self._schema: dict[str, dict[str, Any]] = SCHEMA
        self._write_lock = asyncio.Lock()

    async def load(self, db_path: str) -> None:
        self._db_path = db_path
        self._db = await aiosqlite.connect(db_path)
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute(
            "CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT)"
        )
        await self._db.commit()

        async with self._db.execute("SELECT key, value FROM config") as cursor:
            rows = await cursor.fetchall()
            for key, raw in rows:
                if key in self._schema:
                    self._config[key] = self._deserialize(key, raw)

        for key, meta in self._schema.items():
            if key not in self._config:
                default = meta["default"]
                self._config[key] = default
                await self._persist(key, default)

    def _serialize(self, value: Any) -> str:
        return json.dumps(value)

    def _deserialize(self, key: str, raw: str) -> Any:
        value = json.loads(raw)
        self._validate_type(key, value)
        return value

    def _validate_type(self, key: str, value: Any) -> None:
        meta = self._schema[key]
        expected = meta["type"]
        if value is None:
            if meta["default"] is not None:
                raise ValueError(f"Key '{key}' does not accept None")
            return
        type_map = {
            "string": str,
            "int": int,
            "float": float,
            "bool": bool,
            "list": list,
            "dict": dict,
        }
        if expected not in type_map:
            raise ValueError(f"Unknown type '{expected}' in schema for key '{key}'")
        if not isinstance(value, type_map[expected]):
            raise ValueError(
                f"Key '{key}' expects type '{expected}', got {type(value).__name__}"
            )

    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)

    def get_all(self) -> dict[str, Any]:
        return dict(self._config)

    async def update(self, key: str, value: Any) -> None:
        if key not in self._schema:
            raise ValueError(f"Invalid config key: {key}")
        self._validate_type(key, value)
        async with self._write_lock:
            self._config[key] = value
            await self._persist(key, value)
        await self._notify(key, value)

    def on_change(self, callback: Callable[[str, Any], Any]) -> None:
        self._listeners.append(callback)

    async def _persist(self, key: str, value: Any) -> None:
        if self._db is None:
            raise RuntimeError("ConfigManager has not been loaded. Call load() first.")
        await self._db.execute(
            "INSERT INTO config (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, self._serialize(value)),
        )
        await self._db.commit()

    async def _notify(self, key: str, value: Any) -> None:
        for listener in list(self._listeners):
            try:
                if inspect.iscoroutinefunction(listener):
                    await listener(key, value)
                else:
                    listener(key, value)
            except Exception:
                continue

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None
