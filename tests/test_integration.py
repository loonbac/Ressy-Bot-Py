"""Tests de integración — flujos completos del sistema.

Usan TestClient sync para evitar conflictos con event loops.
NO prueban el frontend build (diseño visual lo hace el usuario).
"""

from unittest.mock import MagicMock
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient


class TestAppEdgeCases:
    """Tests para edge cases de la app."""

    def test_api_without_config_manager_returns_500(self):
        """Sin ConfigManager, los endpoints devuelven 500."""
        from src.web.app import create_app

        app = create_app(config_manager=None)

        with TestClient(app) as client:
            response = client.get("/api/config")
            assert response.status_code == 500
            assert "not initialized" in response.json()["detail"]

            response = client.put("/api/config/test", json={"value": "x"})
            assert response.status_code == 500
            assert "not initialized" in response.json()["detail"]

    def test_status_with_mock_bot_shows_online(self):
        """Con un bot mockeado, /api/status refleja sus datos."""
        from src.web.app import create_app
        from src.bot.core.config import ConfigManager

        cm = ConfigManager()
        bot = MagicMock()
        bot.is_ready.return_value = True
        bot.start_time = datetime.now(timezone.utc)
        bot.cogs = {"AboutCog": MagicMock()}
        bot.latency = 0.024

        app = create_app(config_manager=cm, bot=bot)
        client = TestClient(app)

        response = client.get("/api/status")
        data = response.json()
        assert data["online"] is True
        assert data["uptime_seconds"] > 0
        assert "AboutCog" in data["loaded_cogs"]
        assert data["latency_ms"] == 24.0
        assert "memory_mb" in data
        assert isinstance(data["memory_mb"], (int, float))


class TestFullConfigFlow:
    """Flujo completo de configuración."""

    def test_get_empty_then_update_then_verify(self, app: FastAPI):
        """GET config inicial → PUT update → GET verifica cambio."""
        client = TestClient(app)

        # GET initial config
        response = client.get("/api/config")
        assert response.status_code == 200
        configs = response.json()["configs"]
        bot_prefix = next(c for c in configs if c["key"] == "bot_prefix")
        assert bot_prefix["value"] == "/"

        # PUT update
        response = client.put(
            "/api/config/bot_prefix",
            json={"value": "!"},
        )
        assert response.status_code == 200
        assert response.json()["value"] == "!"

        # GET verify change persisted
        response = client.get("/api/config")
        configs = response.json()["configs"]
        bot_prefix = next(c for c in configs if c["key"] == "bot_prefix")
        assert bot_prefix["value"] == "!"

    def test_status_endpoint(self, app: FastAPI):
        """GET /api/status devuelve estructura correcta sin bot."""
        client = TestClient(app)

        response = client.get("/api/status")
        assert response.status_code == 200
        data = response.json()
        assert data["online"] is False
        assert data["uptime_seconds"] == 0.0
        assert data["loaded_cogs"] == []
        assert data["latency_ms"] == 0.0
        assert isinstance(data["connected_ws_clients"], int)
        assert "memory_mb" in data
        assert isinstance(data["memory_mb"], (int, float))

    def test_invalid_key_returns_400(self, app: FastAPI):
        """PUT con key inválida da error."""
        client = TestClient(app)
        response = client.put(
            "/api/config/key_inexistente",
            json={"value": "test"},
        )
        assert response.status_code == 400
        assert "Invalid config key" in response.json()["detail"]

    def test_multiple_config_updates(self, app: FastAPI):
        """Múltiples updates a distintas keys."""
        client = TestClient(app)

        client.put("/api/config/bot_prefix", json={"value": "!"})
        client.put("/api/config/version", json={"value": "2.0.0"})

        response = client.get("/api/config")
        configs = {c["key"]: c["value"] for c in response.json()["configs"]}
        assert configs["bot_prefix"] == "!"
        assert configs["version"] == "2.0.0"


class TestLifespanBroadcast:
    """Verifica que el lifespan registra el observer de WS."""

    def test_lifespan_registers_ws_observer(self, app: FastAPI):
        """Al actualizar config via API, los clientes WS reciben broadcast."""
        with TestClient(app) as client:
            with client.websocket_connect("/ws") as ws:
                response = client.put(
                    "/api/config/bot_prefix",
                    json={"value": "Broadcast test"},
                )
                assert response.status_code == 200

                message = ws.receive_json()
                assert message["event"] == "config:updated"
                assert message["key"] == "bot_prefix"
                assert message["value"] == "Broadcast test"


class TestStatusEdgeCases:
    """Edge cases del endpoint /api/status."""

    def test_status_when_no_is_ready_attribute(self):
        """Si el bot no tiene is_ready, online=False."""
        from src.web.app import create_app
        from src.bot.core.config import ConfigManager

        cm = ConfigManager()

        class FakeBot:
            pass

        app = create_app(config_manager=cm, bot=FakeBot())
        client = TestClient(app)
        response = client.get("/api/status")
        assert response.json()["online"] is False

    def test_status_when_is_ready_raises_exception(self):
        """Si bot.is_ready() lanza excepción, online=False."""
        from src.web.app import create_app
        from src.bot.core.config import ConfigManager

        cm = ConfigManager()
        bot = MagicMock()
        bot.is_ready.side_effect = Exception("Bot error")

        app = create_app(config_manager=cm, bot=bot)
        client = TestClient(app)
        response = client.get("/api/status")
        assert response.json()["online"] is False

    def test_status_when_is_ready_returns_coroutine(self):
        """Si bot.is_ready() es async, se awaitea correctamente."""
        from src.web.app import create_app
        from src.bot.core.config import ConfigManager

        cm = ConfigManager()
        bot = MagicMock()

        async def async_ready():
            return True

        bot.is_ready = async_ready

        app = create_app(config_manager=cm, bot=bot)
        client = TestClient(app)
        response = client.get("/api/status")
        assert response.json()["online"] is True

    def test_status_when_start_time_is_none(self):
        """Si start_time es None, uptime_seconds=0.0."""
        from src.web.app import create_app
        from src.bot.core.config import ConfigManager

        cm = ConfigManager()
        bot = MagicMock()
        bot.is_ready.return_value = True
        bot.start_time = None

        app = create_app(config_manager=cm, bot=bot)
        client = TestClient(app)
        response = client.get("/api/status")
        assert response.json()["uptime_seconds"] == 0.0

    def test_status_when_no_cogs_attribute(self):
        """Si el bot no tiene cogs, loaded_cogs está vacío."""
        from src.web.app import create_app
        from src.bot.core.config import ConfigManager

        cm = ConfigManager()

        class FakeBot:
            def is_ready(self):
                return True

        app = create_app(config_manager=cm, bot=FakeBot())
        client = TestClient(app)
        response = client.get("/api/status")
        assert response.json()["loaded_cogs"] == []
