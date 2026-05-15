"""Pruebas para el cog Discord del plugin openrouter_prices.

Enfocadas en la función pura _build_prices_embed() y el comportamiento
de la instancia del cog (plugin habilitado/deshabilitado).
No requiere un contexto Discord en vivo — todo está mockeado.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import discord
import pytest


# ---------------------------------------------------------------------------
# Fixtures helpers
# ---------------------------------------------------------------------------

def _make_model(
    id: str = "openai/gpt-4o",
    name: str = "GPT-4o",
    prompt_mtok: float | None = 5.0,
    completion_mtok: float | None = 15.0,
    context: int = 128000,
    input_modalities: list[str] | None = None,
) -> dict:
    return {
        "id": id,
        "name": name,
        "pricing_prompt_per_mtok": prompt_mtok,
        "pricing_completion_per_mtok": completion_mtok,
        "context_length": context,
        "input_modalities": input_modalities or ["text"],
    }


def _make_config(
    enabled: bool = True,
    max_models_command: int = 10,
    ttl_seconds: int = 3600,
    discord_channel_id: str = "",
) -> dict:
    return {
        "enabled": enabled,
        "max_models_command": max_models_command,
        "ttl_seconds": ttl_seconds,
        "discord_channel_id": discord_channel_id,
    }


# ---------------------------------------------------------------------------
# Tests for _build_prices_embed (pure function)
# ---------------------------------------------------------------------------


class TestBuildPricesEmbed:
    def _call(self, models, last_fetched_at=None, max_count=10):
        from src.bot.plugins.openrouter_prices.cog import _build_prices_embed
        return _build_prices_embed(models, last_fetched_at=last_fetched_at, max_count=max_count)

    def test_returns_discord_embed(self):
        """La función devuelve una instancia de discord.Embed."""
        embed = self._call([], last_fetched_at=None)
        assert isinstance(embed, discord.Embed)

    def test_embed_has_title(self):
        """El embed tiene el título 'Precios OpenRouter'."""
        embed = self._call([])
        assert embed.title == "Precios OpenRouter"

    def test_embed_has_description_with_model_count(self):
        """El embed tiene descripción con el conteo de modelos."""
        models = [_make_model(id=f"m/{i}", name=f"Model {i}") for i in range(5)]
        embed = self._call(models, max_count=5)
        assert embed.description is not None
        assert "5" in embed.description

    def test_embed_fields_per_model(self):
        """Cada modelo genera un campo en el embed."""
        models = [_make_model(id=f"m/{i}", name=f"Model {i}") for i in range(3)]
        embed = self._call(models)
        assert len(embed.fields) == 3

    def test_embed_respects_max_25_discord_limit(self):
        """El embed no supera 25 campos (límite de Discord)."""
        models = [_make_model(id=f"m/{i}", name=f"Model {i}") for i in range(30)]
        embed = self._call(models, max_count=30)
        assert len(embed.fields) <= 25

    def test_embed_respects_max_count_parameter(self):
        """El embed respeta el parámetro max_count."""
        models = [_make_model(id=f"m/{i}", name=f"Model {i}") for i in range(10)]
        embed = self._call(models, max_count=3)
        assert len(embed.fields) == 3

    def test_field_value_contains_pricing(self):
        """El valor de cada campo contiene el precio de prompt y completion."""
        model = _make_model(prompt_mtok=5.0, completion_mtok=15.0, name="Test Model")
        embed = self._call([model])
        assert len(embed.fields) == 1
        field_value = embed.fields[0].value
        # Debe contener alguna referencia a los precios formateados
        assert "Prompt" in field_value or "prompt" in field_value.lower()

    def test_field_value_contains_context_length(self):
        """El valor del campo contiene el context length."""
        model = _make_model(context=128000, name="Test Model")
        embed = self._call([model])
        field_value = embed.fields[0].value
        # El contexto debe estar en algún formato
        assert "128" in field_value or "128,000" in field_value or "128000" in field_value

    def test_footer_with_last_fetched_at(self):
        """El footer muestra 'Actualizado:' cuando hay timestamp."""
        embed = self._call([_make_model()], last_fetched_at=1715000000)
        assert embed.footer is not None
        assert embed.footer.text is not None
        assert "Actualizado" in embed.footer.text

    def test_footer_without_last_fetched_at_shows_no_data(self):
        """Sin timestamp, el footer indica que no hay datos cacheados."""
        embed = self._call([_make_model()], last_fetched_at=None)
        assert embed.footer is not None
        assert "Sin datos" in embed.footer.text or "sin datos" in embed.footer.text.lower()

    def test_empty_models_list_still_returns_embed(self):
        """Lista vacía → embed válido (sin campos de modelos)."""
        embed = self._call([], last_fetched_at=None)
        assert isinstance(embed, discord.Embed)
        # No hay campos de modelos — puede tener 0 campos o un campo de "sin resultados"
        # Lo que importa es que no lanze excepción

    def test_none_pricing_values_do_not_crash(self):
        """Valores de pricing None → no causan crash; se muestran como 'N/A' o similar."""
        model = _make_model(prompt_mtok=None, completion_mtok=None)
        embed = self._call([model])
        assert isinstance(embed, discord.Embed)
        assert len(embed.fields) == 1


# ---------------------------------------------------------------------------
# Tests for OpenRouterPricesCog
# ---------------------------------------------------------------------------


class TestOpenRouterPricesCog:
    def _make_cog(self, db=None, client=None):
        from src.bot.plugins.openrouter_prices.cog import OpenRouterPricesCog

        mock_bot = MagicMock()
        mock_db = db or AsyncMock()
        mock_client = client or AsyncMock()
        return OpenRouterPricesCog(bot=mock_bot, db=mock_db, client=mock_client)

    def test_cog_instantiation(self):
        """El cog se puede instanciar sin errores."""
        cog = self._make_cog()
        assert cog is not None

    def test_cog_has_bot_attribute(self):
        """El cog expone el atributo bot."""
        mock_bot = MagicMock()
        from src.bot.plugins.openrouter_prices.cog import OpenRouterPricesCog
        cog = OpenRouterPricesCog(bot=mock_bot, db=AsyncMock(), client=AsyncMock())
        assert cog.bot is mock_bot

    @pytest.mark.asyncio
    async def test_command_disabled_sends_ephemeral_message(self):
        """Plugin deshabilitado → mensaje efímero 'Este plugin está desactivado.'"""
        from src.bot.plugins.openrouter_prices.cog import OpenRouterPricesCog

        mock_db = AsyncMock()
        mock_db.get_config.return_value = {
            "enabled": "false",
            "ttl_seconds": "3600",
            "max_models_command": "10",
            "discord_channel_id": "",
        }

        mock_bot = MagicMock()
        mock_client = AsyncMock()
        cog = OpenRouterPricesCog(bot=mock_bot, db=mock_db, client=mock_client)

        interaction = AsyncMock()
        interaction.response.send_message = AsyncMock()

        await cog.precios_openrouter.callback(cog, interaction, público=False)

        interaction.response.send_message.assert_awaited_once()
        call_kwargs = interaction.response.send_message.call_args
        # El mensaje debe ser efímero
        assert call_kwargs[1].get("ephemeral") is True or (
            len(call_kwargs[0]) > 0 and "desactivado" in call_kwargs[0][0].lower()
        )

    @pytest.mark.asyncio
    async def test_command_enabled_sends_embed(self):
        """Plugin habilitado → respuesta con embed."""
        from src.bot.plugins.openrouter_prices.cog import OpenRouterPricesCog

        mock_db = AsyncMock()
        mock_db.get_config.return_value = {
            "enabled": "true",
            "ttl_seconds": "3600",
            "max_models_command": "10",
            "discord_channel_id": "",
        }
        mock_db.get_metadata.return_value = {
            "last_fetched_at": "1715000000",
            "last_fetch_status": "ok",
        }
        mock_db.list_models.return_value = [
            {
                "id": "openai/gpt-4o",
                "name": "GPT-4o",
                "description": "",
                "context_length": 128000,
                "input_modalities": '["text"]',
                "output_modalities": '["text"]',
                "modality": "text",
                "pricing_prompt": "0.000005",
                "pricing_completion": "0.000015",
                "pricing_image": None,
                "stale": 0,
                "fetched_at": 1715000000,
            }
        ]

        mock_bot = MagicMock()
        mock_client = AsyncMock()
        cog = OpenRouterPricesCog(bot=mock_bot, db=mock_db, client=mock_client)

        interaction = AsyncMock()
        interaction.response.send_message = AsyncMock()

        await cog.precios_openrouter.callback(cog, interaction, público=False)

        interaction.response.send_message.assert_awaited_once()
        call_kwargs = interaction.response.send_message.call_args
        # Debe haber un embed en los kwargs
        assert "embed" in call_kwargs[1]
        embed = call_kwargs[1]["embed"]
        assert isinstance(embed, discord.Embed)

    @pytest.mark.asyncio
    async def test_command_public_flag_not_ephemeral(self):
        """público=True → mensaje NO efímero."""
        from src.bot.plugins.openrouter_prices.cog import OpenRouterPricesCog

        mock_db = AsyncMock()
        mock_db.get_config.return_value = {
            "enabled": "true",
            "ttl_seconds": "3600",
            "max_models_command": "10",
            "discord_channel_id": "",
        }
        mock_db.get_metadata.return_value = {"last_fetched_at": "1715000000"}
        mock_db.list_models.return_value = []

        mock_bot = MagicMock()
        mock_client = AsyncMock()
        cog = OpenRouterPricesCog(bot=mock_bot, db=mock_db, client=mock_client)

        interaction = AsyncMock()
        interaction.response.send_message = AsyncMock()

        await cog.precios_openrouter.callback(cog, interaction, público=True)

        interaction.response.send_message.assert_awaited_once()
        call_kwargs = interaction.response.send_message.call_args
        assert call_kwargs[1].get("ephemeral") is False
