import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.bot.plugins.welcome.cog import WelcomeCog


@pytest.fixture
async def welcome_db():
    import aiosqlite
    db = await aiosqlite.connect(":memory:")
    await db.execute("CREATE TABLE IF NOT EXISTS welcome_config (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    defaults = {
        "enabled": "true",
        "welcome_channel_id": "",
        "welcome_message": "¡Bienvenido {{user}} al servidor!",
    }
    for key, value in defaults.items():
        await db.execute("INSERT OR IGNORE INTO welcome_config (key, value) VALUES (?, ?)", (key, value))
    await db.commit()
    yield db
    await db.close()


@pytest.fixture
async def welcome_client(welcome_db):
    from src.bot.plugins.welcome.api import router as welcome_router

    app = FastAPI()
    app.state.welcome_db = welcome_db
    app.include_router(welcome_router, prefix="/api/plugins/welcome")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


class TestConfigDatabase:
    async def test_default_config(self, welcome_db):
        rows = await welcome_db.execute_fetchall("SELECT key, value FROM welcome_config")
        cfg = {r[0]: r[1] for r in rows}
        assert cfg["enabled"] == "true"
        assert cfg["welcome_channel_id"] == ""
        assert cfg["welcome_message"] == "¡Bienvenido {{user}} al servidor!"

    async def test_update_config(self, welcome_db):
        await welcome_db.execute(
            "INSERT OR REPLACE INTO welcome_config (key, value) VALUES (?, ?)",
            ("enabled", "false"),
        )
        await welcome_db.commit()

        rows = await welcome_db.execute_fetchall("SELECT value FROM welcome_config WHERE key = 'enabled'")
        assert rows[0][0] == "false"

    async def test_update_channel_id(self, welcome_db):
        await welcome_db.execute(
            "INSERT OR REPLACE INTO welcome_config (key, value) VALUES (?, ?)",
            ("welcome_channel_id", "123456789"),
        )
        await welcome_db.commit()

        rows = await welcome_db.execute_fetchall("SELECT value FROM welcome_config WHERE key = 'welcome_channel_id'")
        assert rows[0][0] == "123456789"


class TestConfigAPI:
    async def test_get_config_returns_defaults(self, welcome_client: AsyncClient):
        response = await welcome_client.get("/api/plugins/welcome/config")
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] == True
        assert data["welcome_channel_id"] == ""
        assert data["welcome_message"] == "¡Bienvenido {{user}} al servidor!"

    async def test_put_config_updates_values(self, welcome_client: AsyncClient):
        response = await welcome_client.put(
            "/api/plugins/welcome/config",
            json={
                "enabled": "false",
                "welcome_channel_id": "987654321",
                "welcome_message": "Hola {{user}}!",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] == False
        assert data["welcome_channel_id"] == "987654321"
        assert data["welcome_message"] == "Hola {{user}}!"

    async def test_put_config_ignores_unknown_keys(self, welcome_client: AsyncClient):
        response = await welcome_client.put(
            "/api/plugins/welcome/config",
            json={"unknown_key": "should_be_ignored"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "unknown_key" not in data

    async def test_get_config_after_update(self, welcome_client: AsyncClient):
        await welcome_client.put(
            "/api/plugins/welcome/config",
            json={"welcome_message": "Updated message"},
        )

        response = await welcome_client.get("/api/plugins/welcome/config")
        assert response.status_code == 200
        data = response.json()
        assert data["welcome_message"] == "Updated message"


class TestWelcomeCog:
    async def test_on_member_join_disabled(self, welcome_db):
        mock_bot = MagicMock()
        cog = WelcomeCog(welcome_db, mock_bot)

        # Disable welcome
        await welcome_db.execute(
            "INSERT OR REPLACE INTO welcome_config (key, value) VALUES (?, ?)",
            ("enabled", "false"),
        )
        await welcome_db.commit()

        mock_member = MagicMock()
        mock_member.mention = "<@123>"
        mock_member.guild.members = [mock_member]
        mock_member.display_avatar.url = "https://example.com/avatar.png"

        await cog.on_member_join(mock_member)

        # Bot should not try to get channel when disabled
        mock_bot.get_channel.assert_not_called()

    async def test_on_member_join_no_channel(self, welcome_db):
        mock_bot = MagicMock()
        cog = WelcomeCog(welcome_db, mock_bot)

        mock_member = MagicMock()
        mock_member.mention = "<@123>"
        mock_member.guild.members = [mock_member]
        mock_member.display_avatar.url = "https://example.com/avatar.png"

        await cog.on_member_join(mock_member)

        # Bot should try to get channel but channel_id is empty
        mock_bot.get_channel.assert_not_called()

    async def test_on_member_join_sends_embed(self, welcome_db):
        mock_bot = MagicMock()
        mock_channel = AsyncMock()
        mock_bot.get_channel.return_value = mock_channel

        cog = WelcomeCog(welcome_db, mock_bot)

        # Set channel
        await welcome_db.execute(
            "INSERT OR REPLACE INTO welcome_config (key, value) VALUES (?, ?)",
            ("welcome_channel_id", "123456789"),
        )
        await welcome_db.commit()

        mock_member = MagicMock()
        mock_member.bot = False
        mock_member.joined_at = datetime.datetime.now(datetime.timezone.utc)
        mock_member.display_name = "TestUser"
        mock_member.mention = "<@123>"
        mock_member.guild.name = "TestGuild"
        mock_member.guild.members = [mock_member]
        mock_member.display_avatar.url = "https://example.com/avatar.png"

        await cog.on_member_join(mock_member)

        mock_bot.get_channel.assert_called_once_with(123456789)
        mock_channel.send.assert_awaited_once()

        # Check embed was sent
        call_args = mock_channel.send.await_args
        assert "embed" in call_args.kwargs
        embed = call_args.kwargs["embed"]
        assert embed.title == "Bienvenid@ TestUser"
        assert "<@123>" in embed.description

    async def test_on_member_join_channel_not_found(self, welcome_db):
        mock_bot = MagicMock()
        mock_bot.get_channel.return_value = None

        cog = WelcomeCog(welcome_db, mock_bot)

        # Set channel
        await welcome_db.execute(
            "INSERT OR REPLACE INTO welcome_config (key, value) VALUES (?, ?)",
            ("welcome_channel_id", "123456789"),
        )
        await welcome_db.commit()

        mock_member = MagicMock()
        mock_member.bot = False
        mock_member.joined_at = datetime.datetime.now(datetime.timezone.utc)
        mock_member.display_name = "TestUser"
        mock_member.mention = "<@123>"
        mock_member.guild.name = "TestGuild"
        mock_member.guild.members = [mock_member]
        mock_member.display_avatar.url = "https://example.com/avatar.png"

        await cog.on_member_join(mock_member)

        mock_bot.get_channel.assert_called_once_with(123456789)


class TestWelcomePluginIntegration:
    """Test que los endpoints del plugin responden (sin bot)."""

    @pytest.fixture
    async def app_with_plugin(self):
        """Crea app y carga el plugin IGUAL que en produccion, pero sin bot."""
        from src.web.app import create_app
        from src.bot.core.config import ConfigManager

        ConfigManager.reset_instance()
        cm = ConfigManager()
        await cm.load(":memory:")

        mock_bot = MagicMock()
        mock_bot.add_cog = AsyncMock()

        app = create_app(config_manager=cm, bot=mock_bot)

        from src.bot.plugins.welcome import setup as setup_welcome
        await setup_welcome(mock_bot, cm, app)
        return app

    async def test_config_returns_200(self, app_with_plugin):
        transport = ASGITransport(app=app_with_plugin)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/plugins/welcome/config")
            assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    async def test_put_config_returns_200(self, app_with_plugin):
        transport = ASGITransport(app=app_with_plugin)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.put(
                "/api/plugins/welcome/config",
                json={"enabled": "false", "welcome_message": "Hola!"},
            )
            assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
            data = resp.json()
            assert data["enabled"] == False
            assert data["welcome_message"] == "Hola!"


class TestWelcomeModels:
    async def test_welcome_config_defaults(self):
        from src.bot.plugins.welcome.models import WelcomeConfig

        cfg = WelcomeConfig()
        assert cfg.enabled is True
        assert cfg.welcome_channel_id is None
        assert cfg.welcome_message == ""

    async def test_welcome_config_custom(self):
        from src.bot.plugins.welcome.models import WelcomeConfig

        cfg = WelcomeConfig(
            enabled=False,
            welcome_channel_id="123456",
            welcome_message="Hello {{user}}!",
        )
        assert cfg.enabled is False
        assert cfg.welcome_channel_id == "123456"
        assert cfg.welcome_message == "Hello {{user}}!"
