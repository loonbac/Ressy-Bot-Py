"""Constructores de embeds Discord para el plugin openrouter_prices.

Funciones puras de construcción de embeds + helper async de publicación.
No importan nada de .database directamente — reciben datos ya cargados.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import discord


# Límite total de caracteres de un embed Discord
_EMBED_MAX_CHARS = 6000
# Límite de campos por embed
_EMBED_MAX_FIELDS = 25


def _count_embed_chars(embed: discord.Embed) -> int:
    """Cuenta el total de caracteres usados por el embed."""
    total = 0
    if embed.title:
        total += len(embed.title)
    if embed.description:
        total += len(embed.description)
    if embed.footer and embed.footer.text:
        total += len(embed.footer.text)
    for field in embed.fields:
        total += len(field.name) + len(field.value)
    return total


def _format_ts(generated_at: int) -> str:
    """Formatea un timestamp Unix como ISO 8601 UTC."""
    dt = datetime.fromtimestamp(generated_at, tz=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M UTC")


def build_weekly_price_embed(models: list[dict], generated_at: int) -> discord.Embed:
    """Construye un embed con los modelos de texto más económicos de OpenRouter.

    Args:
        models: Lista de dicts con keys: id, name, pricing_prompt_per_mtok,
                pricing_completion_per_mtok, context_length.
        generated_at: Timestamp Unix de generación.

    Returns:
        discord.Embed listo para enviar. Truncado a 6000 chars si es necesario.
        Footer incluye 'Lista recortada' cuando se recortan modelos.
    """
    embed = discord.Embed(
        title="Reporte semanal de precios OpenRouter",
        color=discord.Color.blue(),
    )

    ts_str = _format_ts(generated_at)
    base_footer = f"Generado el {ts_str}"

    if not models:
        embed.set_footer(text=base_footer)
        return embed

    # Limitar a 25 campos máximo
    capped = models[:_EMBED_MAX_FIELDS]
    truncated = len(models) > _EMBED_MAX_FIELDS

    # Construir campos temporales para medir chars
    fields_to_add: list[tuple[str, str]] = []
    for m in capped:
        name = m.get("name") or m.get("id", "Desconocido")
        prompt = m.get("pricing_prompt_per_mtok")
        completion = m.get("pricing_completion_per_mtok")
        ctx = m.get("context_length") or 0

        # Formatear precios
        prompt_str = f"{prompt:.4f}" if prompt is not None else "N/D"
        completion_str = f"{completion:.4f}" if completion is not None else "N/D"

        # Contexto legible
        if ctx >= 1000:
            ctx_str = f"{ctx // 1000}k"
        else:
            ctx_str = str(ctx)

        field_value = (
            f"Prompt: **${prompt_str}**/Mtok\n"
            f"Completado: **${completion_str}**/Mtok\n"
            f"Contexto: {ctx_str} tokens"
        )
        fields_to_add.append((name, field_value))

    # Añadir campos respetando el límite de chars
    footer_text = base_footer
    added = 0
    for fname, fvalue in fields_to_add:
        # Calcular si cabe el nuevo campo + footer
        prospective_chars = _count_embed_chars(embed) + len(fname) + len(fvalue) + len(footer_text)
        if prospective_chars > _EMBED_MAX_CHARS:
            truncated = True
            break
        embed.add_field(name=fname, value=fvalue, inline=False)
        added += 1

    if truncated or added < len(fields_to_add):
        footer_text = f"Lista recortada — mostrando {added} de {len(models)} modelos. {base_footer}"

    embed.set_footer(text=footer_text)
    return embed


def _build_footer(generated_at: int, scrape_ts: int | None = None) -> str:
    """Construye el texto del footer para embeds de ranking."""
    parts = [f"Generado el {_format_ts(generated_at)}"]
    if scrape_ts is not None:
        parts.append(f"Scrape: {_format_ts(scrape_ts)}")
    return " | ".join(parts)


def build_ranking_embed(
    phase: str,
    ranked: list[dict],
    previous_top1: str | None,
    generated_at: int,
    scrape_ts: int | None = None,
) -> discord.Embed:
    """Construye un embed con el ranking de los mejores modelos para una fase SDD.

    Args:
        phase: Nombre de la fase (ej. "orchestrator").
        ranked: Lista de dicts [{rank, model_id, name, score, breakdown: [...]}].
        previous_top1: model_id del anterior #1 (para mostrar marcador de cambio).
        generated_at: Timestamp Unix de generación.
        scrape_ts: Timestamp Unix del scrape mas reciente (opcional, para el footer).

    Returns:
        discord.Embed listo para enviar.
    """
    count = len(ranked)
    embed = discord.Embed(
        title=f"Top {count} modelos — fase {phase}",
        description=f"Ranking de modelos para la fase **{phase}**, basado en benchmarks ponderados.",
        color=discord.Color.green(),
    )

    if not ranked:
        embed.set_footer(text=_build_footer(generated_at, scrape_ts))
        return embed

    # Detectar cambio de top-1
    new_top1 = ranked[0].get("model_id") if ranked else None
    top1_changed = (
        previous_top1 is not None
        and new_top1 is not None
        and new_top1 != previous_top1
    )

    # Agregar campo de cambio al #1 si aplica
    if top1_changed and ranked:
        top1_name = ranked[0].get("name", new_top1)
        embed.add_field(
            name=f"Subio al #1: {top1_name}",
            value=f"Desplazó a `{previous_top1}` en el primer lugar.",
            inline=False,
        )

    for entry in ranked:
        rank = entry.get("rank", "?")
        name = entry.get("name") or entry.get("model_id", "Desconocido")
        score = entry.get("score", 0.0)
        breakdown: list[dict] = entry.get("breakdown", [])

        # Top-3 benchmarks por contribución
        top_benchmarks = sorted(
            breakdown,
            key=lambda b: b.get("weighted_contribution", 0.0),
            reverse=True,
        )[:3]

        bench_lines = []
        for b in top_benchmarks:
            slug = b.get("benchmark_slug", "")
            contrib = b.get("weighted_contribution", 0.0)
            if contrib > 0:
                bench_lines.append(f"  • {slug}: {contrib:.3f}")

        bench_text = "\n".join(bench_lines) if bench_lines else "  Sin datos de benchmarks"
        field_value = f"Score: **{score:.3f}**\nTop benchmarks:\n{bench_text}"

        embed.add_field(
            name=f"#{rank} {name}",
            value=field_value,
            inline=False,
        )

    embed.set_footer(text=_build_footer(generated_at, scrape_ts))
    return embed


async def publish_embed_to_channel(
    bot,
    channel_id: str,
    embed: discord.Embed,
) -> bool:
    """Publica un embed en un canal Discord.

    Args:
        bot: Instancia de discord.Client.
        channel_id: Snowflake del canal como string. Cadena vacía → False.
        embed: Embed a publicar.

    Returns:
        True si se publicó correctamente, False en cualquier falla.
    """
    from src.web.routes.activity import push_event

    if not channel_id or not channel_id.strip():
        return False

    try:
        channel_int = int(channel_id)
    except (ValueError, TypeError):
        return False

    try:
        channel = bot.get_channel(channel_int)
        if channel is None:
            push_event(
                kind="openrouter",
                title="Error al publicar embed",
                detail=f"Canal {channel_id} no encontrado.",
            )
            return False

        await channel.send(embed=embed)
        return True

    except discord.Forbidden as exc:
        push_event(
            kind="openrouter",
            title="Error al publicar embed",
            detail=f"Sin permisos en canal {channel_id}: {exc}",
        )
        return False
    except discord.HTTPException as exc:
        push_event(
            kind="openrouter",
            title="Error al publicar embed",
            detail=f"Error Discord en canal {channel_id}: {exc}",
        )
        return False
    except Exception as exc:
        push_event(
            kind="openrouter",
            title="Error al publicar embed",
            detail=str(exc),
        )
        return False
