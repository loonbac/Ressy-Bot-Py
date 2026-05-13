"""Blackboard plugin entry point.

Initializes database, mounts API routes, and starts background polling.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from src.bot.core.bot import Bot
from src.bot.core.config import ConfigManager


async def setup(bot: Bot, config_manager: ConfigManager, app):
    """Inicializa el plugin de Blackboard."""
    db_dir = "data/plugins"
    os.makedirs(db_dir, exist_ok=True)
    db_path = f"{db_dir}/blackboard.db"

    from .database import BlackboardDatabase
    from .api import router as bb_router

    db = BlackboardDatabase(db_path)
    await db.init_db()

    # Montar rutas API
    app.include_router(bb_router, prefix="/api/plugins/blackboard")
    app.state.blackboard_db = db

    # Iniciar tarea de fondo para polling
    stop_event = asyncio.Event()
    app.state.blackboard_stop_event = stop_event

    async def _polling_loop():
        while not stop_event.is_set():
            try:
                raw = await db.get_config()
                enabled = raw.get("enabled", "true").lower() == "true"
                interval = int(raw.get("poll_interval_minutes", "60"))
                if enabled:
                    await _run_scrape_cycle(db, bot)
            except Exception as exc:
                print(f"[BlackboardPlugin] Error en polling: {exc}")

            try:
                await asyncio.wait_for(stop_event.wait(), timeout=interval * 60)
            except asyncio.TimeoutError:
                continue

    task = asyncio.create_task(_polling_loop())
    app.state.blackboard_task = task

    return db


async def _run_scrape_cycle(db: "BlackboardDatabase", bot: Bot) -> None:
    """Run one scrape cycle and send notifications."""
    from .models import BlackboardConfig
    from .scraper import BlackboardScraper
    from .notifier import BlackboardNotifier

    raw = await db.get_config()
    cfg = BlackboardConfig(
        enabled=raw.get("enabled", "true").lower() == "true",
        blackboard_url=raw.get("blackboard_url", "https://senati.blackboard.com"),
        blackboard_user=raw.get("blackboard_user", ""),
        blackboard_pass=raw.get("blackboard_pass", ""),
        discord_channel_id=int(raw.get("discord_channel_id", "") or 0) or None,
        mention_role_id=int(raw.get("mention_role_id", "") or 0) or None,
        poll_interval_minutes=int(raw.get("poll_interval_minutes", "60")),
        weekly_digest_day=int(raw.get("weekly_digest_day", "1")),
        timezone=raw.get("timezone", "America/Lima"),
        headless=raw.get("headless", "true").lower() == "true",
    )

    if not cfg.enabled or not cfg.blackboard_user or not cfg.blackboard_pass:
        return

    scraper = BlackboardScraper(cfg)
    try:
        assignments = await scraper.scrape_assignments()
    except Exception as exc:
        print(f"[BlackboardPlugin] Scrape error: {exc}")
        await scraper.close()
        return
    finally:
        await scraper.close()

    notifier = None
    if cfg.discord_channel_id:
        notifier = BlackboardNotifier(bot)

    new_assignments: list[dict[str, Any]] = []
    for a in assignments:
        is_new, date_changed = await db.upsert_assignment(
            assignment_id=a["assignment_id"],
            title=a["title"],
            course_name=a["course_name"],
            course_id=a.get("course_id", ""),
            due_date=a.get("due_date"),
            status=a.get("status", "Pending"),
            source_url=a.get("source_url", ""),
        )
        if is_new:
            new_assignments.append(a)
            if notifier and not await db.is_new_assignment_notified(a["assignment_id"]):
                await notifier.send_new_assignment_notification(
                    cfg.discord_channel_id, a, cfg.timezone, cfg.mention_role_id
                )
                await db.mark_new_assignment_notified(a["assignment_id"])
        elif date_changed:
            # Could send date-changed notification here
            pass

    # 24h alerts
    alerts = await db.get_assignments_due_within_hours(24)
    for alert in alerts:
        if notifier and not await db.is_24h_alerted(alert["id"]):
            await notifier.send_24h_alert(
                cfg.discord_channel_id, alert, cfg.timezone, cfg.mention_role_id
            )
            await db.mark_24h_alerted(alert["id"])

    # Weekly digest
    today = datetime.now(timezone.utc)
    if today.weekday() == cfg.weekly_digest_day:
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)
        week_key = week_start.strftime("%Y-W%W")
        if not await db.is_week_digest_sent(week_key):
            week_assignments = await db.get_assignments_by_week(
                week_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                week_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            )
            if notifier:
                await notifier.send_weekly_digest(
                    cfg.discord_channel_id, week_assignments, week_key, cfg.timezone, cfg.mention_role_id
                )
            await db.mark_week_digest_sent(week_key)

    if notifier:
        await notifier.close()
