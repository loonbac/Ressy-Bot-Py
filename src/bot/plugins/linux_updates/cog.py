from __future__ import annotations

import logging
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

from .embeds import _days_until, build_check_embed, build_status_embed

logger = logging.getLogger(__name__)

# Slugs rolling release — se seedean en DB pero NUNCA se fetchean de endoflife.date
_ROLLING_SLUGS = {"arch", "bazzite", "manjaro", "endeavouros", "cachyos"}

# Slugs fetcheables de endoflife.date (excluye rolling)
_PRODUCT_SLUGS = [
    "ubuntu", "debian", "fedora", "rocky-linux", "linuxmint", "linux",
    "opensuse", "almalinux", "alpine-linux", "pop-os", "rhel",
]

# Todos los slugs del catalogo (fetcheables + rolling) — para autocomplete
_ALL_SLUGS = _PRODUCT_SLUGS + sorted(_ROLLING_SLUGS)

_PRODUCT_DISPLAY = {
    "ubuntu": "Ubuntu",
    "debian": "Debian",
    "fedora": "Fedora",
    "rocky-linux": "Rocky Linux",
    "linuxmint": "Linux Mint",
    "linux": "Linux Kernel",
    "opensuse": "openSUSE",
    "almalinux": "AlmaLinux",
    "alpine-linux": "Alpine Linux",
    "pop-os": "Pop!_OS",
    "rhel": "RHEL",
    "arch": "Arch Linux",
    "bazzite": "Bazzite",
    "manjaro": "Manjaro",
    "endeavouros": "EndeavourOS",
    "cachyos": "CachyOS",
}


async def _autocomplete_product(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    matches = [
        app_commands.Choice(name=_PRODUCT_DISPLAY.get(s, s), value=s)
        for s in _ALL_SLUGS
        if current.lower() in s.lower()
    ]
    if not current:
        return matches
    return matches[:25]


class LinuxCog(commands.Cog, name="Linux"):
    """Comandos de monitoreo de versiones Linux."""

    def __init__(self, bot: commands.Bot, db) -> None:
        self.bot = bot
        self.db = db
        self.name = "Linux"

    @app_commands.command(
        name="linux-status",
        description="Muestra resumen del estado de distribuciones Linux",
    )
    async def linux_status(self, interaction: discord.Interaction) -> None:
        """Embed resumen con semaforo de colores."""
        await interaction.response.defer()

        products = await self.db.get_products()
        enriched = []
        for p in products:
            releases = await self.db.get_releases(p["slug"])
            active = await self.db.get_active_releases(p["slug"])
            expiring_soon = 0
            for r in active:
                eol = r.get("eol_date")
                if eol:
                    days = _days_until(eol)
                    if days is not None and days <= 90:
                        expiring_soon += 1
            enriched.append({
                **p,
                "releases": releases,
                "active_count": len(active),
                "expiring_soon_count": expiring_soon,
            })

        embed = build_status_embed(enriched)
        await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="linux-check",
        description="Muestra versiones detalladas de una distribucion",
    )
    @app_commands.describe(producto="Distribucion a consultar")
    @app_commands.autocomplete(producto=_autocomplete_product)
    async def linux_check(
        self, interaction: discord.Interaction, producto: str
    ) -> None:
        """Embed detallado para un producto."""
        await interaction.response.defer()

        product = await self.db.get_product(producto)
        if product is None:
            await interaction.followup.send(
                f"Producto '{producto}' no encontrado. Opciones: {', '.join(_ALL_SLUGS)}",
                ephemeral=True,
            )
            return

        releases = await self.db.get_releases(producto)
        display = _PRODUCT_DISPLAY.get(producto, producto)
        embed = build_check_embed(display, releases)
        await interaction.followup.send(embed=embed)
