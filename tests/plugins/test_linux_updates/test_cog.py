"""Tests para LinuxCog.

TDD estricto: test primero (RED), implementacion despues (GREEN).
Mockea interaction y db para evitar dependencias de Discord en vivo.
"""
from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest
from discord import app_commands


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_release(cycle: str, **overrides) -> dict:
    base = {
        "cycle": cycle,
        "codename": None,
        "release_date": "2024-01-01",
        "eol_date": None,
        "latest_version": None,
        "latest_release_date": None,
        "lts": None,
        "support_date": None,
        "extended_support_date": None,
        "release_label": None,
        "link": None,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def interaction():
    i = AsyncMock(spec=discord.Interaction)
    i.response.defer = AsyncMock()
    i.followup.send = AsyncMock()
    return i


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.get_products.return_value = []
    db.get_releases.return_value = []
    db.get_active_releases.return_value = []
    db.get_product.return_value = None
    return db


@pytest.fixture
def cog(mock_db):
    from src.bot.plugins.linux_updates.cog import LinuxCog
    bot = MagicMock()
    return LinuxCog(bot=bot, db=mock_db)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestStatusCommand:
    @pytest.mark.asyncio
    async def test_status_command_empty(self, cog, mock_db, interaction):
        """Sin releases -> embed con 'Sin datos'."""
        mock_db.get_products.return_value = [
            {"slug": "ubuntu", "display_name": "Ubuntu"}
        ]
        mock_db.get_releases.return_value = []
        mock_db.get_active_releases.return_value = []

        await cog.linux_status.callback(cog, interaction)

        interaction.response.defer.assert_awaited_once()
        interaction.followup.send.assert_awaited_once()
        call_args = interaction.followup.send.call_args
        embed = call_args[1].get("embed")
        assert embed is not None
        assert isinstance(embed, discord.Embed)
        assert "Sin datos" in embed.description or "No hay datos" in embed.description

    @pytest.mark.asyncio
    async def test_status_command_with_data(self, cog, mock_db, interaction):
        """Con releases -> embed tiene titulo correcto."""
        mock_db.get_products.return_value = [
            {"slug": "ubuntu", "display_name": "Ubuntu"}
        ]
        mock_db.get_releases.return_value = [
            _make_release("24.04", eol_date=(date.today() + timedelta(days=365)).isoformat(), lts=True),
        ]
        mock_db.get_active_releases.return_value = [
            _make_release("24.04", eol_date=(date.today() + timedelta(days=365)).isoformat(), lts=True),
        ]

        await cog.linux_status.callback(cog, interaction)

        interaction.followup.send.assert_awaited_once()
        embed = interaction.followup.send.call_args[1].get("embed")
        assert embed.title == "Estado de Distribuciones Linux"


class TestCheckCommand:
    @pytest.mark.asyncio
    async def test_check_command_found(self, cog, mock_db, interaction):
        """Producto existe -> embed detallado."""
        mock_db.get_product.return_value = {"slug": "ubuntu", "display_name": "Ubuntu"}
        mock_db.get_releases.return_value = [
            _make_release("24.04", eol_date=(date.today() + timedelta(days=365)).isoformat()),
        ]

        await cog.linux_check.callback(cog, interaction, producto="ubuntu")

        interaction.response.defer.assert_awaited_once()
        interaction.followup.send.assert_awaited_once()
        embed = interaction.followup.send.call_args[1].get("embed")
        assert embed is not None
        assert "Versiones" in embed.title

    @pytest.mark.asyncio
    async def test_check_command_not_found(self, cog, mock_db, interaction):
        """Producto no existe -> ephemeral message."""
        mock_db.get_product.return_value = None

        await cog.linux_check.callback(cog, interaction, producto="nonexistent")

        interaction.followup.send.assert_awaited_once()
        call_args = interaction.followup.send.call_args
        assert call_args[1].get("ephemeral") is True
        assert "no encontrado" in call_args[0][0].lower()

    @pytest.mark.asyncio
    async def test_check_displays_days_until_eol(self, cog, mock_db, interaction):
        """Release con eol -> muestra dias."""
        mock_db.get_product.return_value = {"slug": "ubuntu", "display_name": "Ubuntu"}
        eol = (date.today() + timedelta(days=30)).isoformat()
        mock_db.get_releases.return_value = [
            _make_release("22.04", eol_date=eol),
        ]

        await cog.linux_check.callback(cog, interaction, producto="ubuntu")

        embed = interaction.followup.send.call_args[1].get("embed")
        assert embed is not None
        # Verificar que el embed tiene al menos un campo o descripcion que mencione dias
        field_text = ""
        if embed.fields:
            field_text = " ".join(f.value for f in embed.fields)
        assert "dias" in field_text or "Sin datos" in embed.description


class TestAutocomplete:
    @pytest.mark.asyncio
    async def test_autocomplete_returns_matches(self):
        """'ub' -> ['ubuntu']."""
        from src.bot.plugins.linux_updates.cog import _autocomplete_product

        interaction = AsyncMock()
        result = await _autocomplete_product(interaction, "ub")
        values = [c.value for c in result]
        assert "ubuntu" in values

    @pytest.mark.asyncio
    async def test_autocomplete_empty_current(self):
        """'' -> todos los slugs."""
        from src.bot.plugins.linux_updates.cog import _autocomplete_product, _PRODUCT_SLUGS

        interaction = AsyncMock()
        result = await _autocomplete_product(interaction, "")
        values = [c.value for c in result]
        for slug in _PRODUCT_SLUGS:
            assert slug in values


class TestCogMeta:
    def test_cog_name(self, cog):
        """cog.name == 'Linux'."""
        assert cog.name == "Linux"
