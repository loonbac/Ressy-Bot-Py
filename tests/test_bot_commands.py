from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.bot.cogs.about import AboutCog


class MockInteraction:
    def __init__(self, guild=None):
        self.guild = guild
        self.response = AsyncMock()


@pytest.fixture
def mock_config():
    cm = MagicMock()
    cm.get = MagicMock(return_value="1.0.0-test")
    return cm


class TestAboutCommand:
    async def test_about_responds_with_embed(self, mock_config):
        bot = MagicMock()
        cog = AboutCog(bot, mock_config)
        interaction = MockInteraction(guild=MagicMock())

        await cog.about.callback(cog, interaction)

        interaction.response.send_message.assert_awaited_once()
        call_args = interaction.response.send_message.call_args
        embed = call_args.kwargs.get("embed")
        assert embed is not None
        assert embed.title == "Ressy Korosoft Bot"
        field_names = [f.name for f in embed.fields]
        assert "Versión" in field_names
        assert "Comunidad" in field_names
        assert "Uptime" in field_names

    async def test_about_rejects_dm(self, mock_config):
        bot = MagicMock()
        cog = AboutCog(bot, mock_config)
        interaction = MockInteraction(guild=None)

        await cog.about.callback(cog, interaction)

        interaction.response.send_message.assert_awaited_once()
        call_args = interaction.response.send_message.call_args
        content = call_args.args[0] if call_args.args else call_args.kwargs.get("content", "")
        assert "servidor" in content
        assert call_args.kwargs.get("ephemeral") is True

    async def test_about_version_from_config(self, mock_config):
        bot = MagicMock()
        cog = AboutCog(bot, mock_config)
        interaction = MockInteraction(guild=MagicMock())

        await cog.about.callback(cog, interaction)

        embed = interaction.response.send_message.call_args.kwargs["embed"]
        version_field = next(f for f in embed.fields if f.name == "Versión")
        assert version_field.value == "1.0.0-test"

    async def test_setup_adds_cog(self, mock_config):
        bot = MagicMock()
        bot.add_cog = AsyncMock()

        from src.bot.cogs.about import setup

        await setup(bot, mock_config)
        bot.add_cog.assert_awaited_once()
        cog = bot.add_cog.call_args[0][0]
        assert isinstance(cog, AboutCog)
