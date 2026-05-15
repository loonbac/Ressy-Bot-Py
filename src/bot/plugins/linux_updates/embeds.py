from __future__ import annotations

import datetime
from typing import Any

import discord

from .models import ProductInfo, ReleaseInfo


COLOR_GREEN = 0x57F287
COLOR_YELLOW = 0xFEE75C
COLOR_RED = 0xED4245
COLOR_BLUE = 0x5865F2


def _days_until(date_str: str | None) -> int | None:
    if date_str is None:
        return None
    try:
        eol = datetime.date.fromisoformat(date_str)
        delta = (eol - datetime.date.today()).days
        return delta
    except (ValueError, TypeError):
        return None


def build_status_embed(
    products: list[dict[str, Any]],
) -> discord.Embed:
    """Embed resumen con semaforo de colores."""
    has_expired = False
    has_warning = False
    total_active = 0

    lines = []
    for p in products:
        slug = p["slug"]
        display = p.get("display_name", slug)
        active = p.get("active_count", 0)
        total_active += active
        eol_soon = p.get("expiring_soon_count", 0)

        if eol_soon > 0:
            has_warning = True
        # Chequear si hay expirados
        releases = p.get("releases", [])
        for r in releases:
            days = _days_until(r.get("eol_date"))
            if days is not None and days < 0:
                has_expired = True
                break

        status_parts = []
        if active > 0:
            status_parts.append(f"{active} activa(s)")
        if eol_soon > 0:
            status_parts.append(f"**{eol_soon} proxima(s) a EOL**")

        status_str = ", ".join(status_parts) if status_parts else "Sin datos"
        lines.append(f"**{display}** — {status_str}")

    if has_expired:
        color = COLOR_RED
    elif has_warning:
        color = COLOR_YELLOW
    else:
        color = COLOR_GREEN

    embed = discord.Embed(
        title="Estado de Distribuciones Linux",
        description="\n".join(lines) if lines else "No hay datos disponibles.",
        color=color,
    )
    embed.set_footer(text="Los datos se descargan automaticamente cada 12 horas")
    return embed


def build_check_embed(
    product_name: str,
    releases: list[dict[str, Any]],
) -> discord.Embed:
    """Embed detallado para un producto."""
    embed = discord.Embed(
        title=f"{product_name} — Versiones",
        color=COLOR_BLUE,
    )

    if not releases:
        embed.description = "Sin datos. Los datos se descargan automaticamente cada 12 horas."
        return embed

    active = []
    historical = []
    for r in releases:
        days = _days_until(r.get("eol_date"))
        if days is None or days >= 0:
            active.append((r, days))
        else:
            historical.append((r, days))

    if active:
        lines = []
        for r, days in active[:10]:
            cycle = r.get("cycle", "?")
            codename = r.get("codename") or ""
            eol_str = r.get("eol_date") or "Sin fecha"
            days_str = f"{days} dias" if days is not None else "Desconocido"
            lts_str = " 🟢 LTS" if r.get("lts") else ""
            lines.append(
                f"**{cycle}** {codename}{lts_str}\n"
                f"  EOL: {eol_str} ({days_str})"
            )
        embed.add_field(
            name="Versiones activas",
            value="\n".join(lines),
            inline=False,
        )

    if historical:
        h_lines = []
        for r, days in historical[:5]:
            cycle = r.get("cycle", "?")
            eol_str = r.get("eol_date") or "?"
            h_lines.append(f"**{cycle}** — EOL: {eol_str}")
        embed.add_field(
            name="Versiones expiradas (ultimas 5)",
            value="\n".join(h_lines),
            inline=False,
        )

    embed.set_footer(text="Los datos se descargan automaticamente cada 12 horas")
    return embed


def build_eol_notification_embed(
    product_slug: str,
    display_name: str,
    cycle: str,
    codename: str | None,
    eol_date: str,
    days_left: int,
) -> discord.Embed:
    """Embed de notificacion automatica EOL."""
    codename_str = f" ({codename})" if codename else ""
    embed = discord.Embed(
        title=f"⚠️ {display_name} {cycle}{codename_str} — Proximo a EOL",
        description=(
            f"**{display_name} {cycle}** alcanzara su fin de vida util "
            f"en **{days_left} dias** ({eol_date}).\n\n"
            "Planifica una actualizacion a una version mas reciente."
        ),
        color=COLOR_YELLOW,
    )
    embed.set_footer(text="Notificacion automatica de fin de vida util")
    return embed
