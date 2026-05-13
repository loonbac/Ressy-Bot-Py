"""Discord bot notifier for Blackboard assignments."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import discord


DIGEST_COLOR: int = 3447003  # Blue
ALERT_COLOR: int = 16711680  # Red
NEW_ASSIGNMENT_COLOR: int = 8388736  # Purple
PENDING_COLOR: int = 16753920  # Orange


def _role_content(mention_role_id: int | None) -> str | None:
    """Return a content string with the role mention if provided."""
    if mention_role_id:
        return f"<@&{mention_role_id}>"
    return None


def _allowed_mentions(mention_role_id: int | None) -> discord.AllowedMentions:
    """Allow only the configured role to actually ping users."""
    if mention_role_id:
        return discord.AllowedMentions(
            everyone=False,
            users=False,
            roles=[discord.Object(id=mention_role_id)],
        )
    return discord.AllowedMentions.none()


class BlackboardNotifier:
    """Sends Discord notifications for Blackboard assignments via bot channel."""

    def __init__(self, bot) -> None:
        self._bot = bot

    async def close(self) -> None:
        pass

    async def send_new_assignment_notification(
        self,
        channel_id: int,
        assignment: dict[str, Any],
        tz_name: str = "America/Lima",
        mention_role_id: int | None = None,
    ) -> bool:
        channel = self._bot.get_channel(channel_id)
        if channel is None:
            return False

        checked_at = datetime.now(timezone.utc).isoformat()
        due_display = _format_due_date_display(assignment.get("due_date", ""), tz_name)
        title = assignment.get("title", "Unknown")
        course = assignment.get("course_name", "")
        source_url = assignment.get("source_url", "")

        embed = discord.Embed(
            title="🆕 ¡Nueva Tarea Publicada!",
            url=source_url or None,
            description="Se ha agregado una nueva tarea a tus cursos.",
            color=discord.Color(value=NEW_ASSIGNMENT_COLOR),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="Tarea", value=title, inline=True)
        embed.add_field(name="Fecha de entrega", value=due_display, inline=True)
        embed.add_field(name="Curso", value=course if course else "—", inline=True)
        embed.set_footer(text=f"Bot Blackboard | Checked at {checked_at}")

        await channel.send(
            content=_role_content(mention_role_id),
            embed=embed,
            allowed_mentions=_allowed_mentions(mention_role_id),
        )
        return True

    async def send_weekly_digest(
        self,
        channel_id: int,
        assignments: list[dict[str, Any]],
        week_key: str,
        tz_name: str = "America/Lima",
        mention_role_id: int | None = None,
    ) -> bool:
        channel = self._bot.get_channel(channel_id)
        if channel is None:
            return False

        checked_at = datetime.now(timezone.utc).isoformat()
        week_parts = week_key.split("-")
        week_num = week_parts[1] if len(week_parts) == 2 else week_parts[-1]

        embed = discord.Embed(
            title=f"📋 Tareas de la Semana — Semana {week_num}",
            color=discord.Color(value=DIGEST_COLOR),
            timestamp=discord.utils.utcnow(),
        )

        if assignments:
            embed.description = "Tus tareas que vencen esta semana:\n\n"
            for a in assignments:
                due_date_str = a.get("due_date", "")
                hours = _hours_until(due_date_str)
                emoji = _urgency_emoji(hours)
                due_display = _format_due_date_display(due_date_str, tz_name)
                remaining = _format_remaining(hours)
                a_title = a.get("title", "Unknown")
                course = a.get("course_name", "")

                field_name = f"{emoji} {a_title}"
                if course:
                    field_name += f" — {course}"
                embed.add_field(
                    name=field_name,
                    value=f"Vence: {due_display} | {remaining}",
                    inline=False,
                )
        else:
            embed.description = "✅ Todo al día. No hay tareas pendientes esta semana."

        embed.set_footer(text=f"Bot Blackboard | Checked at {checked_at}")

        await channel.send(
            content=_role_content(mention_role_id),
            embed=embed,
            allowed_mentions=_allowed_mentions(mention_role_id),
        )
        return True

    async def send_24h_alert(
        self,
        channel_id: int,
        assignment: dict[str, Any],
        tz_name: str = "America/Lima",
        mention_role_id: int | None = None,
    ) -> bool:
        channel = self._bot.get_channel(channel_id)
        if channel is None:
            return False

        checked_at = datetime.now(timezone.utc).isoformat()
        due_date_str = assignment.get("due_date", "")
        hours = _hours_until(due_date_str)
        due_display = _format_due_date_display(due_date_str, tz_name)
        remaining = _format_remaining(hours)
        title = assignment.get("title", "Unknown")
        course = assignment.get("course_name", "")
        source_url = assignment.get("source_url", "")

        embed = discord.Embed(
            title="⏰ ¡Tarea por Vencer!",
            url=source_url or None,
            description="Esta tarea vence en menos de 24 horas.",
            color=discord.Color(value=ALERT_COLOR),
            timestamp=discord.utils.utcnow(),
        )
        embed.add_field(name="Tarea", value=title, inline=True)
        embed.add_field(name="Fecha de entrega", value=due_display, inline=True)
        embed.add_field(name="Tiempo restante", value=remaining, inline=True)
        embed.add_field(name="Curso", value=course if course else "—", inline=True)
        embed.set_footer(text=f"Bot Blackboard | Checked at {checked_at}")

        await channel.send(
            content=_role_content(mention_role_id),
            embed=embed,
            allowed_mentions=_allowed_mentions(mention_role_id),
        )
        return True

    async def send_pending_digest(
        self,
        channel_id: int,
        assignments: list[dict[str, Any]],
        tz_name: str = "America/Lima",
        mention_role_id: int | None = None,
    ) -> bool:
        """Send a manual digest with all pending assignments (regardless of week)."""
        channel = self._bot.get_channel(channel_id)
        if channel is None:
            return False

        checked_at = datetime.now(timezone.utc).isoformat()
        embed = discord.Embed(
            title="📌 Tareas Pendientes",
            color=discord.Color(value=PENDING_COLOR),
            timestamp=discord.utils.utcnow(),
        )

        if not assignments:
            embed.description = "✅ No hay tareas pendientes ahora mismo."
        else:
            lines = [
                f"Tienes **{len(assignments)}** tarea(s) pendiente(s)."
            ]
            embed.description = "\n".join(lines)
            for a in assignments[:24]:  # Discord allows max 25 fields
                due_date_str = a.get("due_date", "")
                hours = _hours_until(due_date_str)
                emoji = _urgency_emoji(hours)
                due_display = _format_due_date_display(due_date_str, tz_name)
                remaining = _format_remaining(hours)
                a_title = a.get("title", "Unknown")
                course = a.get("course_name", "")
                field_name = f"{emoji} {a_title}"
                if course:
                    field_name += f" — {course}"
                embed.add_field(
                    name=field_name[:256],
                    value=f"Vence: {due_display} · {remaining}"[:1024],
                    inline=False,
                )
            if len(assignments) > 24:
                embed.add_field(
                    name="…",
                    value=f"+{len(assignments) - 24} más",
                    inline=False,
                )

        embed.set_footer(text=f"Bot Blackboard | Checked at {checked_at}")

        await channel.send(
            content=_role_content(mention_role_id),
            embed=embed,
            allowed_mentions=_allowed_mentions(mention_role_id),
        )
        return True


def _hours_until(due_date_str: str) -> float:
    if not due_date_str:
        return 0.0
    try:
        from dateutil import parser as dateutil_parser

        due = dateutil_parser.isoparse(due_date_str)
        if due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        return (due - now).total_seconds() / 3600.0
    except Exception:
        return 0.0


def _format_due_date_display(due_date_str: str, tz_name: str) -> str:
    if not due_date_str:
        return "—"
    try:
        from dateutil import parser as dateutil_parser
        from zoneinfo import ZoneInfo

        due = dateutil_parser.isoparse(due_date_str)
        if due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)
        try:
            tz = ZoneInfo(tz_name)
            due_local = due.astimezone(tz)
        except Exception:
            due_local = due
        return due_local.strftime("%d %b %Y %H:%M")
    except Exception:
        return due_date_str


def _format_remaining(hours: float) -> str:
    if hours <= 0:
        return "vencida!"
    elif hours < 1:
        return f"~{int(hours * 60)} minutos"
    elif hours < 24:
        return f"~{int(hours)} horas"
    else:
        days = int(hours // 24)
        rem = int(hours % 24)
        if rem > 0:
            return f"{days} días, {rem}h"
        return f"{days} días"


def _urgency_emoji(hours: float) -> str:
    if hours < 24:
        return "🔴"
    elif hours < 72:
        return "🟡"
    return "🟢"
