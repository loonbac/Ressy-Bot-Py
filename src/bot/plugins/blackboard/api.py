"""FastAPI router for Blackboard plugin."""

import asyncio
from typing import Any

import discord
from fastapi import APIRouter, HTTPException, Request

from src.bot.plugins.blackboard.models import BlackboardConfig
from src.web.routes.activity import push_event

router = APIRouter()


def _get_db(request: Request):
    db = getattr(request.app.state, "blackboard_db", None)
    if db is None:
        raise HTTPException(status_code=500, detail="Blackboard plugin no inicializado")
    return db


def _parse_id(raw: str) -> int | None:
    try:
        v = int(raw or 0)
        return v or None
    except (TypeError, ValueError):
        return None


def _id_str(value: int | None) -> str | None:
    """Snowflake IDs serialized as strings to preserve 64-bit precision in JSON."""
    return str(value) if value else None


def _config_from_raw(raw: dict[str, str]) -> BlackboardConfig:
    return BlackboardConfig(
        enabled=raw.get("enabled", "true").lower() == "true",
        blackboard_url=raw.get("blackboard_url", "https://senati.blackboard.com"),
        blackboard_user=raw.get("blackboard_user", ""),
        blackboard_pass=raw.get("blackboard_pass", ""),
        discord_channel_id=_parse_id(raw.get("discord_channel_id", "")),
        mention_role_id=_parse_id(raw.get("mention_role_id", "")),
        poll_interval_minutes=int(raw.get("poll_interval_minutes", "60")),
        weekly_digest_day=int(raw.get("weekly_digest_day", "1")),
        timezone=raw.get("timezone", "America/Lima"),
        headless=raw.get("headless", "true").lower() == "true",
    )


def _serialize_config(raw: dict[str, str]) -> dict[str, Any]:
    """Build JSON-safe config response. Discord IDs returned as strings
    to preserve 64-bit precision (JS Number can't hold 19-digit snowflakes).
    """
    return {
        "enabled": raw.get("enabled", "true").lower() == "true",
        "blackboard_url": raw.get("blackboard_url", "https://senati.blackboard.com"),
        "blackboard_user": raw.get("blackboard_user", ""),
        "blackboard_pass": raw.get("blackboard_pass", ""),
        "discord_channel_id": _id_str(_parse_id(raw.get("discord_channel_id", ""))),
        "mention_role_id": _id_str(_parse_id(raw.get("mention_role_id", ""))),
        "poll_interval_minutes": int(raw.get("poll_interval_minutes", "60")),
        "weekly_digest_day": int(raw.get("weekly_digest_day", "1")),
        "timezone": raw.get("timezone", "America/Lima"),
        "headless": raw.get("headless", "true").lower() == "true",
    }


@router.get("/config")
async def get_config(request: Request) -> dict[str, Any]:
    db = _get_db(request)
    raw = await db.get_config()
    return _serialize_config(raw)


@router.put("/config")
async def save_config(request: Request, body: dict[str, Any]) -> dict[str, Any]:
    db = _get_db(request)
    try:
        cfg = BlackboardConfig(**body)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    persisted = {
        "enabled": str(cfg.enabled).lower(),
        "blackboard_url": cfg.blackboard_url,
        "blackboard_user": cfg.blackboard_user,
        "blackboard_pass": cfg.blackboard_pass,
        "discord_channel_id": str(cfg.discord_channel_id or ""),
        "mention_role_id": str(cfg.mention_role_id or ""),
        "poll_interval_minutes": str(cfg.poll_interval_minutes),
        "weekly_digest_day": str(cfg.weekly_digest_day),
        "timezone": cfg.timezone,
        "headless": str(cfg.headless).lower(),
    }
    await db.update_config(persisted)
    return _serialize_config(persisted)


SCRAPE_TIMEOUT_SECONDS = 180


@router.post("/scrape")
async def trigger_scrape(request: Request) -> dict[str, Any]:
    db = _get_db(request)
    raw = await db.get_config()
    cfg = _config_from_raw(raw)

    if not cfg.enabled:
        raise HTTPException(status_code=400, detail="Plugin deshabilitado")
    if not cfg.blackboard_user or not cfg.blackboard_pass:
        raise HTTPException(status_code=400, detail="Credenciales de Blackboard no configuradas")

    from src.bot.plugins.blackboard.scraper import BlackboardScraper

    scraper = BlackboardScraper(cfg)
    request.app.state.blackboard_last_steps = scraper.steps

    try:
        try:
            assignments = await asyncio.wait_for(
                scraper.scrape_assignments(),
                timeout=SCRAPE_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            scraper._log("ERROR", f"Timeout after {SCRAPE_TIMEOUT_SECONDS}s — abortando")
            raise HTTPException(
                status_code=504,
                detail=f"Scrape excedió {SCRAPE_TIMEOUT_SECONDS}s. Mira los logs del bot o /api/plugins/blackboard/scrape-status.",
            )

        new_count = 0
        for a in assignments:
            is_new, _ = await db.upsert_assignment(
                assignment_id=a["assignment_id"],
                title=a["title"],
                course_name=a["course_name"],
                course_id=a.get("course_id", ""),
                due_date=a.get("due_date"),
                status=a.get("status", "Pending"),
                source_url=a.get("source_url", ""),
            )
            if is_new:
                new_count += 1
        push_event(
            kind="scrape",
            title=f"Scrape Blackboard: {len(assignments)} tareas ({new_count} nuevas)",
            detail=f"Tomó {scraper.steps[-1]['elapsed_s'] if scraper.steps else 0}s" if scraper.steps else "",
        )
        return {
            "assignments_found": len(assignments),
            "new_assignments": new_count,
            "steps": scraper.steps,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Scrape failed: {type(exc).__name__}: {exc}",
        )
    finally:
        await scraper.close()


@router.get("/scrape-status")
async def scrape_status(request: Request) -> dict[str, Any]:
    """Return step-by-step log of the last scrape run (in-memory)."""
    steps = getattr(request.app.state, "blackboard_last_steps", None) or []
    return {"steps": steps, "count": len(steps)}


@router.get("/assignments")
async def list_assignments(request: Request) -> dict[str, Any]:
    db = _get_db(request)
    assignments = await db.get_all_assignments()
    return {"assignments": assignments}


@router.get("/discord-channels")
async def list_discord_channels(request: Request) -> dict[str, Any]:
    bot = getattr(request.app.state, "bot", None)
    if bot is None:
        return {"channels": []}

    cm = getattr(request.app.state, "config_manager", None)
    guild_id_str = cm.get("guild_id") if cm else None
    try:
        guild_id = int(guild_id_str) if guild_id_str else None
    except ValueError:
        guild_id = None

    channels: list[dict[str, str]] = []
    for guild in bot.guilds:
        if guild_id is not None and guild.id != guild_id:
            continue
        for channel in guild.text_channels:
            channels.append({
                "id": str(channel.id),
                "name": f"#{channel.name}",
                "guild_name": guild.name,
            })
    return {"channels": channels}


@router.get("/discord-roles")
async def list_discord_roles(request: Request) -> dict[str, Any]:
    """List mentionable roles in the configured guild."""
    bot = getattr(request.app.state, "bot", None)
    if bot is None:
        return {"roles": []}

    cm = getattr(request.app.state, "config_manager", None)
    guild_id_str = cm.get("guild_id") if cm else None
    try:
        guild_id = int(guild_id_str) if guild_id_str else None
    except ValueError:
        guild_id = None

    roles: list[dict[str, Any]] = []
    for guild in bot.guilds:
        if guild_id is not None and guild.id != guild_id:
            continue
        for role in guild.roles:
            if role.name == "@everyone":
                continue
            roles.append({
                "id": str(role.id),
                "name": role.name,
                "color": role.color.value,
                "guild_name": guild.name,
            })
    return {"roles": roles}


@router.post("/send-pending")
async def send_pending_digest(request: Request) -> dict[str, Any]:
    """Send an immediate digest with all currently pending (future-due) assignments."""
    db = _get_db(request)
    bot = getattr(request.app.state, "bot", None)
    if bot is None:
        raise HTTPException(status_code=503, detail="Bot no disponible")

    raw = await db.get_config()
    cfg = _config_from_raw(raw)

    if cfg.discord_channel_id is None:
        raise HTTPException(status_code=400, detail="No hay canal de Discord configurado")

    channel = bot.get_channel(cfg.discord_channel_id)
    if channel is None:
        raise HTTPException(status_code=400, detail="Canal no encontrado")

    all_assignments = await db.get_all_assignments()
    # Filter to pending (not done) + has due_date in future
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    pending: list[dict[str, Any]] = []
    for a in all_assignments:
        status = (a.get("status") or "").lower()
        if "entreg" in status or "done" in status or "completed" in status:
            continue
        due = a.get("due_date") or ""
        if due:
            try:
                d = datetime.fromisoformat(due.replace("Z", "+00:00"))
                if d <= now:
                    continue
            except ValueError:
                pass
        pending.append(a)
    # Sort by due_date asc, nulls last
    pending.sort(key=lambda a: a.get("due_date") or "9999-12-31")

    from src.bot.plugins.blackboard.notifier import BlackboardNotifier
    notifier = BlackboardNotifier(bot)
    try:
        ok = await notifier.send_pending_digest(
            cfg.discord_channel_id, pending, cfg.timezone, cfg.mention_role_id
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error al enviar digest: {exc}")
    finally:
        await notifier.close()

    if not ok:
        raise HTTPException(status_code=400, detail="Canal no resoluble en el bot")

    push_event(
        kind="blackboard",
        title=f"Digest enviado a #{getattr(channel, 'name', '?')}",
        detail=f"{len(pending)} pendiente(s)",
    )

    return {
        "sent": True,
        "channel_id": str(cfg.discord_channel_id),
        "channel_name": getattr(channel, "name", ""),
        "pending_count": len(pending),
        "mention_role_id": str(cfg.mention_role_id) if cfg.mention_role_id else None,
    }
