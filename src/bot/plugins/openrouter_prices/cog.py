"""Cog Discord para el plugin openrouter_prices.

Registra el slash command /precios-openrouter y expone la función pura
_build_prices_embed() para testabilidad sin contexto Discord en vivo.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands

from src.bot.plugins.openrouter_prices.models import to_per_million


def _build_prices_embed(
    models: list[dict[str, Any]],
    *,
    last_fetched_at: int | None,
    max_count: int = 10,
) -> discord.Embed:
    """Construye un discord.Embed con los precios de los modelos OpenRouter.

    Función pura — no accede a estado externo, testeable sin bot en vivo.

    Args:
        models: Lista de dicts con datos de modelos (de DB o API serializada).
        last_fetched_at: Timestamp Unix del último fetch exitoso; None si no hay.
        max_count: Número máximo de modelos a mostrar (cap en 25 por límite Discord).

    Returns:
        discord.Embed listo para enviar.
    """
    effective_count = min(max_count, 25)
    models_slice = models[:effective_count]

    embed = discord.Embed(
        title="Precios OpenRouter",
        description=f"Top {effective_count} modelos de texto más baratos por prompt token",
        color=discord.Color.blurple(),
    )

    for model in models_slice:
        name = model.get("name") or model.get("id", "Desconocido")
        context = model.get("context_length") or 0

        # Precios — pueden venir ya computados (from api layer) o como raw strings (from db row)
        prompt_mtok = model.get("pricing_prompt_per_mtok")
        completion_mtok = model.get("pricing_completion_per_mtok")

        # Si no vienen ya calculados, intentar calcularlos desde raw
        if prompt_mtok is None:
            prompt_mtok = to_per_million(model.get("pricing_prompt"))
        if completion_mtok is None:
            completion_mtok = to_per_million(model.get("pricing_completion"))

        prompt_str = f"${prompt_mtok:.4f}/Mtok" if prompt_mtok is not None else "N/A"
        completion_str = f"${completion_mtok:.4f}/Mtok" if completion_mtok is not None else "N/A"
        context_str = f"{context:,} tok" if context else "N/A"

        field_value = (
            f"Prompt: {prompt_str} · "
            f"Completion: {completion_str} · "
            f"Context: {context_str}"
        )

        embed.add_field(name=name, value=field_value, inline=False)

    # Footer con timestamp de actualización
    if last_fetched_at is not None:
        ts = datetime.fromtimestamp(last_fetched_at, tz=timezone.utc).isoformat(
            timespec="seconds"
        )
        embed.set_footer(text=f"Actualizado: {ts}")
    else:
        embed.set_footer(text="Sin datos cacheados")

    return embed


class OpenRouterPricesCog(commands.Cog):
    """Cog que expone el slash command /precios-openrouter."""

    def __init__(self, bot: commands.Bot, db, client) -> None:
        self.bot = bot
        self._db = db
        self._client = client

    # ------------------------------------------------------------------
    # Slash command
    # ------------------------------------------------------------------

    @app_commands.command(
        name="precios-openrouter",
        description="Muestra los modelos de IA más baratos de OpenRouter.",
    )
    @app_commands.describe(público="Mostrar el resultado en el canal (visible para todos)")
    async def precios_openrouter(
        self,
        interaction: discord.Interaction,
        público: bool = False,
    ) -> None:
        """Slash command /precios-openrouter.

        Muestra el top N de modelos de texto más económicos por prompt token.
        Por defecto el resultado es efímero (solo visible para quien invoca).
        Con público=True el embed es visible en el canal.
        """
        ephemeral = not público

        raw_config = await self._db.get_config()
        enabled = raw_config.get("enabled", "true") == "true"
        max_count = int(raw_config.get("max_models_command", "10"))
        ttl_seconds = int(raw_config.get("ttl_seconds", "3600"))

        if not enabled:
            await interaction.response.send_message(
                "Este plugin está desactivado.",
                ephemeral=True,
            )
            return

        # Verificar TTL cache
        metadata = await self._db.get_metadata()
        last_fetched_str = metadata.get("last_fetched_at")
        now = int(time.time())

        if last_fetched_str is None or (now - int(last_fetched_str)) > ttl_seconds:
            # Cache expirado → re-fetch
            try:
                models_raw = await self._client.fetch_models()
                count = await self._db.upsert_models(models_raw, now)
                await self._db.set_metadata("last_fetched_at", str(now))
                await self._db.set_metadata("last_fetch_status", "ok")
                last_fetched_at = now
            except Exception:
                # En caso de error usamos lo que haya en caché
                last_fetched_at = int(last_fetched_str) if last_fetched_str else None
        else:
            last_fetched_at = int(last_fetched_str)

        # Obtener todos los modelos de texto y reordenar por (prompt + completion)
        # Spec REQ-5: top N más baratos por costo total ida y vuelta
        rows = await self._db.list_models(
            text_only=True,
            sort_by="prompt",
            sort_dir="asc",
            limit=None,
        )

        def _total_cost(row) -> float:
            try:
                prompt = float(row.get("pricing_prompt") or "0")
                completion = float(row.get("pricing_completion") or "0")
            except (TypeError, ValueError):
                return float("inf")
            return prompt + completion

        rows = sorted(rows, key=_total_cost)[:max_count]

        # Construir embed
        embed = _build_prices_embed(rows, last_fetched_at=last_fetched_at, max_count=max_count)

        await interaction.response.send_message(embed=embed, ephemeral=ephemeral)
