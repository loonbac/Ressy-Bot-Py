"""REST API del plugin linux_updates.

Router FastAPI con 5 endpoints:
  GET  /products
  GET  /products/{slug}
  GET  /summary
  GET  /config
  PUT  /config
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from .cog import _ROLLING_SLUGS

router = APIRouter(tags=["linux-updates"])

_CONFIG_KEYS = {
    "enabled",
    "refresh_interval_hours",
    "eol_warning_days",
    "discord_channel_id",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_db(request: Request):
    """Obtiene la instancia de LinuxUpdatesDatabase desde app.state."""
    db = getattr(request.app.state, "linux_updates_db", None)
    if db is None:
        raise HTTPException(
            status_code=500,
            detail="Plugin linux_updates no inicializado correctamente.",
        )
    return db


def _days_until(date_str: str | None) -> int | None:
    if date_str is None:
        return None
    try:
        eol = date.fromisoformat(date_str)
        delta = (eol - date.today()).days
        return delta
    except (ValueError, TypeError):
        return None


def _status_from_days(days: int | None) -> str:
    if days is None:
        return "unknown"
    return "active" if days >= 0 else "expired"


def _is_stale(last_check_at: int | None, config: dict[str, str]) -> bool:
    if last_check_at is None:
        return True
    interval_hours = int(config.get("refresh_interval_hours", "12"))
    max_stale = interval_hours * 2 * 3600
    return (datetime.now(timezone.utc).timestamp() - last_check_at) > max_stale


def _humanize_time(timestamp: int | None) -> str:
    if timestamp is None:
        return "Nunca"
    now = datetime.now(timezone.utc).timestamp()
    diff = now - timestamp
    if diff < 60:
        return "hace unos segundos"
    if diff < 3600:
        return f"hace {int(diff // 60)} minuto(s)"
    if diff < 86400:
        return f"hace {int(diff // 3600)} hora(s)"
    return f"hace {int(diff // 86400)} dia(s)"


async def _get_config_dict(db) -> dict[str, Any]:
    raw = await db.get_config()

    def _as_bool(key: str, default: bool) -> bool:
        val = raw.get(key, "true" if default else "false")
        if isinstance(val, bool):
            return val
        return str(val).lower() == "true"

    def _as_int(key: str, default: int) -> int:
        try:
            return int(raw.get(key, str(default)))
        except (TypeError, ValueError):
            return default

    return {
        "enabled": _as_bool("enabled", True),
        "refresh_interval_hours": _as_int("refresh_interval_hours", 12),
        "eol_warning_days": _as_int("eol_warning_days", 90),
        "discord_channel_id": raw.get("discord_channel_id", ""),
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/products")
async def list_products(request: Request) -> list[dict[str, Any]]:
    """Lista productos con campos computados."""
    db = _get_db(request)
    products = await db.get_products()
    config = await _get_config_dict(db)
    warning_days = config["eol_warning_days"]

    result = []
    for p in products:
        releases = await db.get_releases(p["slug"])
        active = await db.get_active_releases(p["slug"])
        expiring = [
            r
            for r in active
            if (days := _days_until(r.get("eol_date"))) is not None
            and days <= warning_days
        ]
        slug = p["slug"]
        # Los productos rolling nunca se fetchean, por lo que last_check_at=None
        # es su estado normal — no deben reportarse como stale.
        is_rolling = slug in _ROLLING_SLUGS
        result.append({
            "slug": slug,
            "display_name": p["display_name"],
            "release_count": len(releases),
            "active_count": len(active),
            "expiring_soon_count": len(expiring),
            "last_check_at": p.get("last_check_at"),
            "last_check_status": p.get("last_check_status", "ok"),
            "stale": False if is_rolling else _is_stale(p.get("last_check_at"), config),
            "updated_at": _humanize_time(p.get("last_check_at")),
        })
    return result


@router.get("/products/{slug}")
async def get_product(request: Request, slug: str) -> dict[str, Any]:
    """Devuelve un producto con sus releases."""
    db = _get_db(request)
    product = await db.get_product(slug)
    if product is None:
        raise HTTPException(status_code=404, detail=f"Producto '{slug}' no encontrado.")

    releases = await db.get_releases(slug)
    releases_out = []
    for r in releases:
        days = _days_until(r.get("eol_date"))
        releases_out.append({
            "cycle": r["cycle"],
            "codename": r.get("codename"),
            "release_date": r.get("release_date"),
            "eol_date": r.get("eol_date"),
            "latest_version": r.get("latest_version"),
            "lts": bool(r.get("lts")) if r.get("lts") is not None else False,
            "days_until_eol": days,
            "status": _status_from_days(days),
        })

    return {
        "slug": product["slug"],
        "display_name": product["display_name"],
        "last_check_at": product.get("last_check_at"),
        "last_check_status": product.get("last_check_status", "ok"),
        "releases": releases_out,
    }


@router.get("/summary")
async def get_summary(request: Request) -> dict[str, Any]:
    """Devuelve agregados de EOL."""
    db = _get_db(request)
    return await db.get_summary()


@router.get("/config")
async def get_config(request: Request) -> dict[str, Any]:
    """Devuelve la configuracion actual del plugin."""
    db = _get_db(request)
    return await _get_config_dict(db)


@router.put("/config")
async def update_config(request: Request) -> dict[str, Any]:
    """Actualiza la configuracion del plugin (actualizacion parcial)."""
    db = _get_db(request)
    body = await request.json()

    unknown_keys = sorted(set(body) - _CONFIG_KEYS)
    if unknown_keys:
        raise HTTPException(
            status_code=400,
            detail=f"Claves de configuracion no soportadas: {', '.join(unknown_keys)}.",
        )

    updates: dict[str, str] = {}

    if "enabled" in body:
        val = body["enabled"]
        if isinstance(val, bool):
            updates["enabled"] = "true" if val else "false"
        elif isinstance(val, str) and val.lower() in ("true", "false"):
            updates["enabled"] = val.lower()
        else:
            raise HTTPException(
                status_code=400,
                detail="El campo 'enabled' debe ser un valor booleano (true o false).",
            )

    if "refresh_interval_hours" in body:
        val = body["refresh_interval_hours"]
        try:
            n = int(val)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=400,
                detail="refresh_interval_hours debe ser un numero entero.",
            )
        if n < 1:
            raise HTTPException(
                status_code=400,
                detail="refresh_interval_hours debe ser mayor o igual a 1.",
            )
        updates["refresh_interval_hours"] = str(n)

    if "eol_warning_days" in body:
        val = body["eol_warning_days"]
        try:
            n = int(val)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=400,
                detail="eol_warning_days debe ser un numero entero.",
            )
        if n < 7:
            raise HTTPException(
                status_code=400,
                detail="eol_warning_days debe ser mayor o igual a 7.",
            )
        updates["eol_warning_days"] = str(n)

    if "discord_channel_id" in body:
        val = body["discord_channel_id"]
        if not isinstance(val, str):
            raise HTTPException(
                status_code=400,
                detail="discord_channel_id debe ser un string (Snowflake).",
            )
        if val != "" and (not val.isdigit() or not (17 <= len(val) <= 20)):
            raise HTTPException(
                status_code=400,
                detail=(
                    "discord_channel_id debe ser una cadena numerica de 17 a 20 digitos "
                    "o una cadena vacia."
                ),
            )
        updates["discord_channel_id"] = val

    if updates:
        await db.update_config(updates)

    return await _get_config_dict(db)
