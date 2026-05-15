"""REST API del plugin openrouter_prices.

Router FastAPI con 11 endpoints:
  GET  /models
  GET  /models/{model_id}
  GET  /config
  PUT  /config
  POST /refresh
  GET  /status
  GET  /rankings/{phase}
  GET  /benchmarks
  POST /scrape/{source}
  GET  /aliases
  PUT  /aliases/{openrouter_id}
  GET  /scrape-runs

La TTL cache check, sort allowlist y lógica de cache_stale están implementadas aquí.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from src.web.routes.activity import push_event
from src.bot.plugins.openrouter_prices.ranking import compute_ranking_for_phase

router = APIRouter()

# Sort allowlist: query param → columna DB
SORT_COLUMNS: dict[str, str] = {
    "prompt": "pricing_prompt",
    "completion": "pricing_completion",
    "context": "context_length",
    "name": "name",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_db(request: Request):
    """Obtiene la instancia de OpenRouterDatabase desde app.state."""
    db = getattr(request.app.state, "openrouter_prices_db", None)
    if db is None:
        raise HTTPException(
            status_code=500,
            detail="Plugin openrouter_prices no inicializado correctamente.",
        )
    return db


def _get_client(request: Request):
    """Obtiene la instancia de OpenRouterClient desde app.state."""
    client = getattr(request.app.state, "openrouter_prices_client", None)
    if client is None:
        raise HTTPException(
            status_code=500,
            detail="Cliente HTTP de OpenRouter no inicializado.",
        )
    return client


def _get_scheduler(request: Request):
    """Obtiene el scheduler desde app.state. Puede ser None si no está configurado."""
    return getattr(request.app.state, "openrouter_prices_scheduler", None)


_VALID_REPORT_DAYS = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}
_VALID_SCRAPE_SOURCES = {"openrouter", "aa", "artificial_analysis", "bfcl"}
_VALID_ALIAS_SOURCES = {"artificial_analysis", "bfcl"}
_CONFIG_KEYS = {
    "enabled",
    "ttl_seconds",
    "max_models_command",
    "discord_channel_id",
    "openrouter_refresh_interval_hours",
    "aa_scrape_enabled",
    "bfcl_scrape_enabled",
    "weekly_report_enabled",
    "ranking_embed_enabled",
    "aa_scrape_interval_days",
    "bfcl_scrape_interval_days",
    "ranking_embed_cron_days",
    "weekly_report_channel_id",
    "ranking_embed_channel_id",
    "weekly_report_day",
    "weekly_report_hour",
    "weekly_report_count",
    "ranking_phase",
    "phases_enabled",
    "ranking_embed_per_phase",
    "aa_api_key",
    "stale_threshold_days",
    "github_token",
    "bfcl_scrape_max_models",
}
_PHASE_LABELS = {
    "orchestrator": "Orquestador",
    "sdd_init": "SDD Init",
    "sdd_explore": "SDD Explore",
    "sdd_propose": "SDD Propose",
    "sdd_spec": "SDD Spec",
    "sdd_design": "SDD Design",
    "sdd_tasks": "SDD Tasks",
    "sdd_apply": "SDD Apply",
    "sdd_verify": "SDD Verify",
    "sdd_archive": "SDD Archive",
}


def _push_activity(kind: str, title: str, detail: str = "", meta: dict | None = None) -> None:
    """Envía un evento de actividad al feed global. No propaga excepciones."""
    try:
        push_event(kind=kind, title=title, detail=detail, meta=meta or {})
    except Exception:
        pass


def _phase_label(slug: str) -> str:
    return _PHASE_LABELS.get(slug, slug.replace("_", " ").title())


def _iso_from_timestamp(value: int | None) -> str | None:
    if value is None:
        return None
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()


def _row_to_model_dict(row: dict[str, Any]) -> dict[str, Any]:
    """Convierte una fila de la tabla models a un dict serializable."""
    import json as _json
    from src.bot.plugins.openrouter_prices.models import to_per_million

    input_mod = row.get("input_modalities", "[]")
    output_mod = row.get("output_modalities", "[]")

    try:
        input_mod = _json.loads(input_mod)
    except Exception:
        input_mod = []

    try:
        output_mod = _json.loads(output_mod)
    except Exception:
        output_mod = []

    pricing_prompt_raw = row.get("pricing_prompt")
    pricing_completion_raw = row.get("pricing_completion")

    return {
        "id": row.get("id", ""),
        "name": row.get("name", ""),
        "description": row.get("description", ""),
        "context_length": row.get("context_length") or 0,
        "input_modalities": input_mod,
        "output_modalities": output_mod,
        "modality": row.get("modality", ""),
        "pricing_prompt_raw": pricing_prompt_raw,
        "pricing_completion_raw": pricing_completion_raw,
        "pricing_image_raw": row.get("pricing_image"),
        "pricing_prompt_per_mtok": to_per_million(pricing_prompt_raw),
        "pricing_completion_per_mtok": to_per_million(pricing_completion_raw),
        "stale": bool(row.get("stale", 0)),
        "fetched_at": row.get("fetched_at", 0),
    }


async def _get_config_dict(db) -> dict[str, Any]:
    """Devuelve la configuración como dict tipado.

    Incluye todas las keys editables vía PUT /config para que el frontend
    pueda renderizar campos persistentes.
    """
    raw = await db.get_config()

    def _as_int(key: str, default: int) -> int:
        try:
            return int(raw.get(key, str(default)))
        except (TypeError, ValueError):
            return default

    def _as_bool(key: str, default: bool) -> bool:
        val = raw.get(key, "true" if default else "false")
        if isinstance(val, bool):
            return val
        return str(val).lower() == "true"

    # phases_enabled persistido como JSON-array string (o CSV legacy)
    phases_raw = raw.get("phases_enabled", '["orchestrator","sdd_init"]')
    phases_enabled: list[str]
    try:
        parsed = json.loads(phases_raw)
        phases_enabled = [str(x) for x in parsed] if isinstance(parsed, list) else []
    except (TypeError, ValueError, json.JSONDecodeError):
        phases_enabled = [p.strip() for p in str(phases_raw).split(",") if p.strip()]

    return {
        "enabled": _as_bool("enabled", True),
        "ttl_seconds": _as_int("ttl_seconds", 3600),
        "max_models_command": _as_int("max_models_command", 10),
        "discord_channel_id": raw.get("discord_channel_id", ""),
        "ranking_phase": raw.get("ranking_phase", "orchestrator"),
        "phases_enabled": phases_enabled,
        "ranking_embed_per_phase": _as_bool("ranking_embed_per_phase", True),
        "aa_api_key": raw.get("aa_api_key", ""),
        "github_token": raw.get("github_token", ""),
        "stale_threshold_days": _as_int("stale_threshold_days", 14),
        "bfcl_scrape_max_models": _as_int("bfcl_scrape_max_models", 200),
    }


async def _check_and_refresh_cache(db, client, config: dict[str, Any]) -> tuple[bool, bool]:
    """Comprueba si el caché es válido; si no, realiza un fetch con fallback.

    Returns:
        (was_cached, cache_stale): was_cached=True si no hubo fetch nuevo.
        cache_stale=True solo si se sirvió caché viejo (>2x TTL) tras un fetch fallido.
    """
    now = int(time.time())
    metadata = await db.get_metadata()
    last_fetched_str = metadata.get("last_fetched_at")
    ttl = config["ttl_seconds"]

    if last_fetched_str is not None:
        last_fetched_at = int(last_fetched_str)
        if (now - last_fetched_at) <= ttl:
            return True, False

        # Caché expirado pero hay datos — intentar refresh, fallback a caché si falla
        try:
            await _do_fetch(db, client)
            return False, False
        except Exception as exc:
            await db.set_metadata("last_fetch_status", "error")
            await db.set_metadata("last_fetch_error", str(exc))
            cache_stale = (now - last_fetched_at) > 2 * ttl
            return True, cache_stale

    # Sin caché previo — fetch obligatorio
    await _do_fetch(db, client)
    return False, False


async def _do_fetch(db, client) -> int:
    """Realiza el fetch HTTP y actualiza DB + metadata. Propaga excepciones."""
    models = await client.fetch_models()
    now = int(time.time())
    count = await db.upsert_models(models, now)
    await db.set_metadata("last_fetched_at", str(now))
    await db.set_metadata("last_fetch_status", "ok")
    await db.set_metadata("last_fetch_error", "")
    return count


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/models")
async def list_models(
    request: Request,
    text_only: bool = Query(default=True),
    sort: str = Query(default="prompt"),
    direction: str = Query(default="asc"),
    limit: int | None = Query(default=None, gt=0),
) -> dict[str, Any]:
    """Lista modelos con filtros opcionales.

    Query params:
        text_only: Solo modelos con 'text' en input_modalities (default True).
        sort: Campo de ordenamiento — prompt | completion | context | name.
        direction: asc | desc.
        limit: Máximo de modelos a devolver.
    """
    db = _get_db(request)
    client = _get_client(request)
    config = await _get_config_dict(db)

    # Validar sort; fallback silencioso si no está en el allowlist
    sort_col_key = sort if sort in SORT_COLUMNS else "prompt"
    dir_normalized = "asc" if direction.lower() != "desc" else "desc"

    was_cached, cache_stale = await _check_and_refresh_cache(db, client, config)

    rows = await db.list_models(
        text_only=text_only,
        sort_by=sort_col_key,
        sort_dir=dir_normalized,
        limit=limit,
    )

    metadata = await db.get_metadata()
    last_fetched_str = metadata.get("last_fetched_at")
    last_fetched_at = int(last_fetched_str) if last_fetched_str else None

    models_out = [_row_to_model_dict(r) for r in rows]

    return {
        "models": models_out,
        "count": len(models_out),
        "cached": was_cached,
        "cache_stale": cache_stale,
        "last_fetched_at": last_fetched_at,
    }


@router.get("/models/{model_id:path}")
async def get_model(request: Request, model_id: str) -> dict[str, Any]:
    """Devuelve un modelo por ID.

    Returns:
        El modelo si existe; 404 si no se encuentra.
    """
    db = _get_db(request)
    row = await db.get_model(model_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Modelo no encontrado.")
    return _row_to_model_dict(row)


@router.get("/config")
async def get_config(request: Request) -> dict[str, Any]:
    """Devuelve la configuración actual del plugin."""
    db = _get_db(request)
    return await _get_config_dict(db)


@router.put("/config")
async def update_config(request: Request) -> dict[str, Any]:
    """Actualiza la configuración del plugin (actualización parcial).

    Campos aceptados: enabled, ttl_seconds, max_models_command, discord_channel_id.
    Devuelve 400 en valores inválidos.
    """
    db = _get_db(request)
    body = await request.json()

    unknown_keys = sorted(set(body) - _CONFIG_KEYS)
    if unknown_keys:
        raise HTTPException(
            status_code=400,
            detail=f"Claves de configuración no soportadas: {', '.join(unknown_keys)}.",
        )

    updates: dict[str, str] = {}
    updated_keys: list[str] = []

    # --- enabled ---
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
        updated_keys.append("enabled")

    # --- ttl_seconds ---
    if "ttl_seconds" in body:
        val = body["ttl_seconds"]
        try:
            ttl = int(val)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=422,
                detail="El valor de ttl_seconds debe ser un número entero.",
            )
        if ttl <= 0:
            raise HTTPException(
                status_code=422,
                detail="El valor de ttl_seconds debe ser mayor a 0.",
            )
        updates["ttl_seconds"] = str(ttl)
        updated_keys.append("ttl_seconds")

    # --- max_models_command ---
    if "max_models_command" in body:
        val = body["max_models_command"]
        try:
            n = int(val)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=422,
                detail="El valor de max_models_command debe ser un número entero.",
            )
        if not (1 <= n <= 25):
            raise HTTPException(
                status_code=422,
                detail="El valor de max_models_command debe estar entre 1 y 25.",
            )
        updates["max_models_command"] = str(n)
        updated_keys.append("max_models_command")

    # --- discord_channel_id ---
    if "discord_channel_id" in body:
        val = body["discord_channel_id"]
        if not isinstance(val, str):
            raise HTTPException(
                status_code=400,
                detail="discord_channel_id debe ser un string (Snowflake).",
            )
        # Vacío = deseleccionar canal (válido)
        if val != "" and (not val.isdigit() or not (17 <= len(val) <= 20)):
            raise HTTPException(
                status_code=400,
                detail=(
                    "discord_channel_id debe ser una cadena numérica de 17 a 20 dígitos "
                    "o una cadena vacía."
                ),
            )
        updates["discord_channel_id"] = val
        updated_keys.append("discord_channel_id")

    # -----------------------------------------------------------------
    # Claves nuevas REQ-EXT-11
    # -----------------------------------------------------------------

    # --- openrouter_refresh_interval_hours ---
    if "openrouter_refresh_interval_hours" in body:
        val = body["openrouter_refresh_interval_hours"]
        try:
            n = int(val)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=400,
                detail="openrouter_refresh_interval_hours debe ser un número entero.",
            )
        if n <= 0:
            raise HTTPException(
                status_code=400,
                detail="openrouter_refresh_interval_hours debe ser mayor a 0.",
            )
        updates["openrouter_refresh_interval_hours"] = str(n)
        updated_keys.append("openrouter_refresh_interval_hours")

    # --- flags booleanos ---
    for bool_key in ("aa_scrape_enabled", "bfcl_scrape_enabled", "weekly_report_enabled", "ranking_embed_enabled"):
        if bool_key in body:
            val = body[bool_key]
            if isinstance(val, bool):
                updates[bool_key] = "true" if val else "false"
            elif isinstance(val, str) and val.lower() in ("true", "false"):
                updates[bool_key] = val.lower()
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"{bool_key} debe ser 'true' o 'false'.",
                )
            updated_keys.append(bool_key)

    # --- intervalos en días ---
    for day_key in ("aa_scrape_interval_days", "bfcl_scrape_interval_days", "ranking_embed_cron_days"):
        if day_key in body:
            val = body[day_key]
            try:
                n = int(val)
            except (TypeError, ValueError):
                raise HTTPException(
                    status_code=400,
                    detail=f"{day_key} debe ser un número entero.",
                )
            if n <= 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"{day_key} debe ser mayor a 0.",
                )
            updates[day_key] = str(n)
            updated_keys.append(day_key)

    # --- channel_ids de los nuevos canales ---
    for ch_key in ("weekly_report_channel_id", "ranking_embed_channel_id"):
        if ch_key in body:
            val = body[ch_key]
            if not isinstance(val, str):
                raise HTTPException(
                    status_code=400,
                    detail=f"{ch_key} debe ser un string (Snowflake).",
                )
            if val != "" and (not val.isdigit() or not (17 <= len(val) <= 20)):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"{ch_key} debe ser una cadena numérica de 17 a 20 dígitos "
                        "o una cadena vacía."
                    ),
                )
            updates[ch_key] = val
            updated_keys.append(ch_key)

    # --- weekly_report_day ---
    if "weekly_report_day" in body:
        val = str(body["weekly_report_day"]).lower()
        if val not in _VALID_REPORT_DAYS:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"weekly_report_day debe ser uno de: {', '.join(sorted(_VALID_REPORT_DAYS))}."
                ),
            )
        updates["weekly_report_day"] = val
        updated_keys.append("weekly_report_day")

    # --- weekly_report_hour ---
    if "weekly_report_hour" in body:
        val = body["weekly_report_hour"]
        try:
            h = int(val)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=400,
                detail="weekly_report_hour debe ser un número entero entre 0 y 23.",
            )
        if not (0 <= h <= 23):
            raise HTTPException(
                status_code=400,
                detail="weekly_report_hour debe estar entre 0 y 23.",
            )
        updates["weekly_report_hour"] = str(h)
        updated_keys.append("weekly_report_hour")

    # --- weekly_report_count ---
    if "weekly_report_count" in body:
        val = body["weekly_report_count"]
        try:
            n = int(val)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=400,
                detail="weekly_report_count debe ser un número entero.",
            )
        if n <= 0:
            raise HTTPException(
                status_code=400,
                detail="weekly_report_count debe ser mayor a 0.",
            )
        updates["weekly_report_count"] = str(n)
        updated_keys.append("weekly_report_count")

    # --- ranking_phase ---
    if "ranking_phase" in body:
        val = str(body["ranking_phase"]).strip()
        if not val:
            raise HTTPException(
                status_code=400,
                detail="ranking_phase no puede estar vacío.",
            )
        updates["ranking_phase"] = val
        updated_keys.append("ranking_phase")

    # --- phases_enabled ---
    if "phases_enabled" in body:
        val = body["phases_enabled"]
        if isinstance(val, str):
            try:
                phases_enabled = json.loads(val)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=422,
                    detail="phases_enabled debe ser una lista de fases en formato JSON.",
                )
        else:
            phases_enabled = val

        if not isinstance(phases_enabled, list):
            raise HTTPException(
                status_code=422,
                detail="phases_enabled debe ser una lista de fases.",
            )
        if not phases_enabled:
            raise HTTPException(
                status_code=422,
                detail="phases_enabled debe contener al menos una fase.",
            )
        if not all(isinstance(item, str) and item.strip() for item in phases_enabled):
            raise HTTPException(
                status_code=422,
                detail="phases_enabled debe ser una lista de fases con strings no vacíos.",
            )

        phases = [item.strip() for item in phases_enabled]
        registered = set(await db.get_registered_phases())
        invalid = [phase for phase in phases if phase not in registered]
        if invalid:
            raise HTTPException(
                status_code=422,
                detail=f"phases_enabled contiene fases no registradas: {', '.join(invalid)}.",
            )

        updates["phases_enabled"] = json.dumps(phases)
        updated_keys.append("phases_enabled")

    # --- ranking_embed_per_phase ---
    if "ranking_embed_per_phase" in body:
        val = body["ranking_embed_per_phase"]
        if isinstance(val, bool):
            updates["ranking_embed_per_phase"] = "true" if val else "false"
        elif isinstance(val, str) and val.lower() in ("true", "false"):
            updates["ranking_embed_per_phase"] = val.lower()
        else:
            raise HTTPException(
                status_code=400,
                detail="ranking_embed_per_phase debe ser 'true' o 'false'.",
            )
        updated_keys.append("ranking_embed_per_phase")

    # --- aa_api_key ---
    if "aa_api_key" in body:
        val = body["aa_api_key"]
        if not isinstance(val, str):
            raise HTTPException(
                status_code=422,
                detail="aa_api_key debe ser un string.",
            )
        updates["aa_api_key"] = val
        updated_keys.append("aa_api_key")

    # --- stale_threshold_days ---
    if "stale_threshold_days" in body:
        val = body["stale_threshold_days"]
        try:
            n = int(val)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=422,
                detail="stale_threshold_days debe ser un número entero.",
            )
        if n <= 0:
            raise HTTPException(
                status_code=422,
                detail="stale_threshold_days debe ser mayor a 0.",
            )
        updates["stale_threshold_days"] = str(n)
        updated_keys.append("stale_threshold_days")

    # --- github_token ---
    if "github_token" in body:
        val = body["github_token"]
        if not isinstance(val, str):
            raise HTTPException(
                status_code=422,
                detail="github_token debe ser un string.",
            )
        updates["github_token"] = val
        updated_keys.append("github_token")

    # --- bfcl_scrape_max_models ---
    if "bfcl_scrape_max_models" in body:
        val = body["bfcl_scrape_max_models"]
        try:
            n = int(val)
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=422,
                detail="bfcl_scrape_max_models debe ser un número entero.",
            )
        if not (1 <= n <= 1000):
            raise HTTPException(
                status_code=422,
                detail="bfcl_scrape_max_models debe estar entre 1 y 1000.",
            )
        updates["bfcl_scrape_max_models"] = str(n)
        updated_keys.append("bfcl_scrape_max_models")

    if updates:
        await db.update_config(updates)

    if updated_keys:
        _push_activity(
            kind="openrouter",
            title="Configuración OpenRouter actualizada",
            detail=f"Claves cambiadas: {', '.join(updated_keys)}",
            meta={"keys": updated_keys},
        )

    return await _get_config_dict(db)


@router.post("/refresh")
async def force_refresh(request: Request) -> dict[str, Any]:
    """Fuerza un re-fetch del catálogo de OpenRouter ignorando el TTL.

    En caso de error HTTP, retorna source='cache_fallback' con los datos
    previos (graceful degradation). Siempre retorna HTTP 200.
    """
    db = _get_db(request)
    client = _get_client(request)

    try:
        count = await _do_fetch(db, client)
        metadata = await db.get_metadata()
        fetched_at = int(metadata.get("last_fetched_at", str(int(time.time()))))

        _push_activity(
            kind="openrouter",
            title="Precios OpenRouter actualizados",
            detail=f"{count} modelos sincronizados",
            meta={"count": count, "source": "openrouter"},
        )

        return {
            "updated": count,
            "source": "openrouter",
            "fetched_at": fetched_at,
        }

    except Exception as exc:
        # Registrar error sin borrar datos previos
        await db.set_metadata("last_fetch_status", "error")
        await db.set_metadata("last_fetch_error", str(exc))

        _push_activity(
            kind="openrouter",
            title="Error al actualizar precios OpenRouter",
            detail=str(exc),
            meta={"error": str(exc)},
        )

        # Retornar datos del caché previo
        metadata = await db.get_metadata()
        prior_fetched_str = metadata.get("last_fetched_at")
        prior_fetched_at = int(prior_fetched_str) if prior_fetched_str else int(time.time())

        return {
            "updated": 0,
            "source": "cache_fallback",
            "fetched_at": prior_fetched_at,
        }


@router.get("/status")
async def get_status(request: Request) -> dict[str, Any]:
    """Devuelve el estado general del plugin."""
    db = _get_db(request)
    raw_config = await db.get_config()
    metadata = await db.get_metadata()

    last_fetched_str = metadata.get("last_fetched_at")
    last_fetched_at = int(last_fetched_str) if last_fetched_str else None

    models_count = await db.count_models(stale=False)
    stale_count = await db.count_models(stale=True)

    # Scrape health
    stale_threshold = int(raw_config.get("stale_threshold_days", "14")) * 86400
    now = int(time.time())

    def compute_health(rows, source_key):
        if not rows:
            return {
                "last_status": "never",
                "stale": True,
                "age_seconds": None,
                "last_started_at": None,
                "last_finished_at": None,
                "last_error": None,
                "aliases_missed": 0,
            }
        row = rows[0]
        age = now - (row.get("finished_at") or row.get("started_at", now))
        is_stale = age > stale_threshold or row.get("status") != "ok"
        return {
            "last_started_at": row.get("started_at"),
            "last_finished_at": row.get("finished_at"),
            "last_status": row.get("status"),
            "last_error": row.get("error"),
            "aliases_missed": row.get("aliases_missed", 0),
            "age_seconds": age,
            "stale": is_stale,
        }

    aa_health = await db.get_scrape_health(source="artificial_analysis")
    bfcl_health = await db.get_scrape_health(source="bfcl")

    scrape_health = {
        "artificial_analysis": compute_health(aa_health, "aa"),
        "bfcl": compute_health(bfcl_health, "bfcl"),
    }

    # Warnings
    warnings = []
    aa_key = raw_config.get("aa_api_key", "")
    if not aa_key:
        aa_last = scrape_health["artificial_analysis"]
        if aa_last.get("last_status") in ("error",) and aa_last.get("last_error") in ("unauthorized", "401", "403"):
            warnings.append("aa_api_key_missing")

    for source_key, health in scrape_health.items():
        if health.get("stale"):
            warnings.append(f"{source_key}_scrape_stale")
        if health.get("last_status") == "error" and health.get("last_error"):
            warnings.append(f"{source_key}_scrape_error")

    return {
        "enabled": raw_config.get("enabled", "true") == "true",
        "models_count": models_count,
        "stale_count": stale_count,
        "last_fetched_at": last_fetched_at,
        "ttl_seconds": int(raw_config.get("ttl_seconds", "3600")),
        "last_fetch_status": metadata.get("last_fetch_status", ""),
        "last_fetch_error": metadata.get("last_fetch_error") or None,
        "scrape_health": scrape_health,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Nuevos endpoints (PR 3 — REQ-EXT-5, REQ-EXT-9, REQ-EXT-10)
# ---------------------------------------------------------------------------


@router.get("/rankings/{phase}")
async def get_ranking(
    request: Request,
    phase: str,
    limit: int = Query(default=10, gt=0, le=50),
) -> dict[str, Any]:
    """Calcula el ranking de modelos para una fase de perfil.

    Args:
        phase: Identificador de la fase (ej. "orchestrator").
        limit: Número máximo de modelos a retornar (1–50).

    Returns:
        {phase, models: [...], generated_at}

    Raises:
        404 si el perfil de fase no existe.
    """
    db = _get_db(request)

    # Verificar que la fase existe
    profile = await db.get_phase_profile(phase)
    if profile is None or len(profile) == 0:
        raise HTTPException(
            status_code=404,
            detail="Perfil de fase no encontrado.",
        )

    try:
        ranked = await compute_ranking_for_phase(db, phase, n=limit)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Error al calcular el ranking: {exc}",
        )

    # Lookup de pricing por model_id para enriquecer cada entry
    all_models = await db.list_models(text_only=False, include_stale=True)
    pricing_by_id: dict[str, dict[str, Any]] = {}
    for m in all_models:
        mid = m.get("id", "")
        if not mid:
            continue
        from .models import to_per_million
        pricing_by_id[mid] = {
            "pricing_prompt_per_mtok": to_per_million(m.get("pricing_prompt")),
            "pricing_completion_per_mtok": to_per_million(m.get("pricing_completion")),
            "context_length": m.get("context_length") or 0,
        }

    entries = []
    for r in ranked:
        mid = r.get("model_id", "")
        price = pricing_by_id.get(mid, {})
        entries.append(
            {
                "rank": r.get("rank"),
                "model_id": mid,
                "model_name": r.get("name") or mid,
                "score": r.get("score", 0.0),
                "breakdown": r.get("breakdown", []),
                "pricing_prompt_per_mtok": price.get("pricing_prompt_per_mtok"),
                "pricing_completion_per_mtok": price.get("pricing_completion_per_mtok"),
                "context_length": price.get("context_length"),
            }
        )

    now_ts = int(time.time())
    return {
        "phase": phase,
        "entries": entries,
        "computed_at": now_ts,
        # Aliases legacy para retro-compat
        "models": ranked,
        "generated_at": now_ts,
    }


@router.get("/benchmarks")
async def list_benchmarks(request: Request) -> list[dict[str, Any]]:
    """Devuelve todos los benchmarks registrados."""
    db = _get_db(request)
    rows = await db.get_benchmarks()
    return [
        {
            "id": r.get("id"),
            "slug": r.get("slug", ""),
            "display_name": r.get("display_name", ""),
            "source": r.get("source", ""),
            "higher_is_better": bool(r.get("higher_is_better", 1)),
            "description": r.get("description", ""),
        }
        for r in rows
    ]


@router.post("/scrape/{source}")
async def trigger_scrape(request: Request, source: str) -> dict[str, Any]:
    """Dispara un scrape manual para la fuente indicada.

    Args:
        source: Fuente a scrapear — openrouter | aa | bfcl.

    Returns:
        {started: true, source: "..."}

    Raises:
        400 si la fuente no es válida.
        409 si ya hay un scrape en curso para esa fuente.
    """
    if source not in _VALID_SCRAPE_SOURCES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Fuente de scrape invalida. "
                f"Valores permitidos: {', '.join(sorted(_VALID_SCRAPE_SOURCES))}."
            ),
        )

    scheduler = _get_scheduler(request)
    if scheduler is None:
        raise HTTPException(
            status_code=503,
            detail="Scheduler no disponible. El plugin puede no haber iniciado correctamente.",
        )

    if scheduler.is_scraping(source):
        raise HTTPException(status_code=409, detail="Scrape ya en curso.")

    started = await scheduler.trigger_scrape(source)
    if not started:
        raise HTTPException(status_code=409, detail="Scrape ya en curso.")

    return {"started": True, "source": source}


@router.get("/aliases")
async def list_aliases(request: Request) -> list[dict[str, Any]]:
    """Devuelve todas las entradas de la tabla model_aliases."""
    db = _get_db(request)
    rows = await db.list_aliases()
    return [
        {
            "openrouter_id": r.get("openrouter_id", ""),
            "artificial_analysis_name": r.get("artificial_analysis_name"),
            "bfcl_key": r.get("bfcl_key"),
            "match_confidence": r.get("match_confidence"),
            "updated_at": r.get("updated_at", 0),
        }
        for r in rows
    ]


@router.put("/aliases/{openrouter_id:path}")
async def update_alias(request: Request, openrouter_id: str) -> dict[str, Any]:
    """Actualiza el mapeo de alias para un modelo de OpenRouter.

    Body (todos opcionales):
        artificial_analysis_name: Nombre en Artificial Analysis.
        bfcl_key: Clave en el leaderboard BFCL.

    Returns:
        La fila actualizada de model_aliases.

    Raises:
        404 si el openrouter_id no existe en model_aliases.
    """
    db = _get_db(request)
    body = await request.json()

    if "source" in body:
        source = body["source"]
        if source not in _VALID_ALIAS_SOURCES:
            raise HTTPException(
                status_code=422,
                detail=f"source debe ser uno de: {', '.join(sorted(_VALID_ALIAS_SOURCES))}.",
            )

    existing = await db.get_alias(openrouter_id)
    if existing is None:
        raise HTTPException(
            status_code=404,
            detail=f"Alias para '{openrouter_id}' no encontrado.",
        )

    # Actualización parcial — solo lo que viene en el body
    new_aa_name = body.get("artificial_analysis_name", existing.get("artificial_analysis_name"))
    new_bfcl_key = body.get("bfcl_key", existing.get("bfcl_key"))
    confidence = existing.get("match_confidence")

    # Si no hay nada que cambiar, retornar el existente directamente
    if not body:
        return {
            "openrouter_id": existing.get("openrouter_id", openrouter_id),
            "artificial_analysis_name": existing.get("artificial_analysis_name"),
            "bfcl_key": existing.get("bfcl_key"),
            "match_confidence": confidence,
            "updated_at": existing.get("updated_at", 0),
        }

    await db.upsert_alias(openrouter_id, new_aa_name, new_bfcl_key, confidence)
    updated = await db.get_alias(openrouter_id)
    if updated is None:
        updated = existing

    return {
        "openrouter_id": updated.get("openrouter_id", openrouter_id),
        "artificial_analysis_name": updated.get("artificial_analysis_name"),
        "bfcl_key": updated.get("bfcl_key"),
        "match_confidence": updated.get("match_confidence"),
        "updated_at": updated.get("updated_at", 0),
    }


@router.get("/phases")
async def list_phases(request: Request) -> list[dict[str, Any]]:
    """Devuelve todas las fases registradas con conteos y metadata."""
    db = _get_db(request)
    phases = await db.get_phases()
    return [
        {
            "slug": phase["slug"],
            "label": _phase_label(phase["slug"]),
            "description": phase["description"],
            "weights_count": phase["weights_count"],
            "active_benchmarks_count": phase["active_benchmarks_count"],
            "reserved_benchmarks_count": phase["reserved_benchmarks_count"],
            "feature_factors_count": phase["feature_factors_count"],
            "last_ranking_computed_at": _iso_from_timestamp(phase["last_ranking_computed_at"]),
        }
        for phase in phases
    ]


@router.post("/embed/ranking/{phase}")
async def trigger_ranking_embed(request: Request, phase: str) -> dict[str, Any]:
    """Envía manualmente el embed de ranking para una fase específica al canal Discord.

    Reset el timestamp `last_ranking_embed_at` para forzar el next tick.
    Si embed_publisher no está configurado, retorna 503.
    """
    scheduler = _get_scheduler(request)
    if scheduler is None:
        raise HTTPException(status_code=503, detail="Scheduler no disponible.")

    db = _get_db(request)
    config = await db.get_config()
    channel_id = (
        config.get("ranking_embed_channel_id", "")
        or config.get("discord_channel_id", "")
    )
    if not channel_id:
        raise HTTPException(
            status_code=400,
            detail="Sin canal Discord configurado (configura discord_channel_id en /config).",
        )

    # Verificar fase existe
    profile = await db.get_phase_profile(phase)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Fase '{phase}' no encontrada.")

    # Ejecutar manualmente: importar lo necesario
    from .ranking import compute_ranking_for_phase
    from .discord_embeds import build_ranking_embed

    publisher = getattr(scheduler, "_embed_publisher", None)
    if publisher is None:
        raise HTTPException(
            status_code=503,
            detail="embed_publisher no inicializado (bot Discord no disponible).",
        )

    try:
        entries = await compute_ranking_for_phase(db, phase, n=10)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Error calculando ranking: {type(exc).__name__}: {exc}",
        )

    if not entries:
        raise HTTPException(
            status_code=400,
            detail="No hay datos suficientes para generar el ranking. Ejecuta los scrapes primero.",
        )

    embed = build_ranking_embed(
        phase=phase,
        ranked=entries,
        previous_top1=None,
        generated_at=int(time.time()),
    )
    try:
        success = await publisher(channel_id, embed)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Error enviando embed: {type(exc).__name__}: {exc}",
        )

    if not success:
        raise HTTPException(
            status_code=502,
            detail=f"embed_publisher rechazó el envío al canal {channel_id}.",
        )

    _push_activity(
        kind="openrouter",
        title=f"Embed ranking enviado · {phase}",
        detail=f"Top {len(entries)} modelos publicado en canal {channel_id}.",
    )

    return {
        "phase": phase,
        "channel_id": channel_id,
        "models_published": len(entries),
    }


@router.get("/phases/{phase}/weights")
async def get_phase_weights(request: Request, phase: str) -> list[dict[str, Any]]:
    """Devuelve los pesos crudos del perfil de fase."""
    db = _get_db(request)
    rows = await db.get_phase_profile(phase)
    if not rows:
        raise HTTPException(
            status_code=404, detail=f"Fase '{phase}' no encontrada."
        )
    return [
        {
            "benchmark_slug": r.get("benchmark_slug", ""),
            "weight": float(r.get("weight", 0) or 0),
            "is_feature_factor": bool(r.get("is_feature_factor", False)),
        }
        for r in rows
    ]


@router.put("/phases/{phase}/weights")
async def update_phase_weights(
    request: Request, phase: str
) -> dict[str, Any]:
    """Reemplaza los pesos de un perfil de fase.

    Body: {weights: [{benchmark_slug, weight, is_feature_factor}, ...]}
    Valida que la suma de weights sea aproximadamente 1.0.

    Raises:
        400 si la fase no existe o la suma de pesos no es 1.0.
        422 si el body tiene shape inválida.
    """
    db = _get_db(request)
    body = await request.json()

    weights = body.get("weights")
    if not isinstance(weights, list):
        raise HTTPException(
            status_code=422, detail="weights debe ser una lista de objetos."
        )

    cleaned: list[dict[str, Any]] = []
    total = 0.0
    for item in weights:
        if not isinstance(item, dict):
            continue
        slug = item.get("benchmark_slug")
        if not isinstance(slug, str) or not slug:
            continue
        try:
            w = float(item.get("weight", 0))
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=422,
                detail=f"weight de '{slug}' debe ser numérico.",
            )
        if w < 0 or w > 1:
            raise HTTPException(
                status_code=422,
                detail=f"weight de '{slug}' debe estar entre 0 y 1.",
            )
        is_ff = bool(item.get("is_feature_factor", False))
        cleaned.append(
            {"benchmark_slug": slug, "weight": w, "is_feature_factor": is_ff}
        )
        total += w

    if abs(total - 1.0) > 1e-6:
        raise HTTPException(
            status_code=400,
            detail=f"La suma de pesos debe ser 1.0 (actual: {total:.4f}).",
        )

    # Verificar que la fase existe
    existing = await db.get_phase_profile(phase)
    if not existing:
        raise HTTPException(
            status_code=404,
            detail=f"Fase '{phase}' no encontrada en phase_profiles.",
        )

    inserted = await db.replace_phase_profile(phase, cleaned)

    _push_activity(
        kind="openrouter",
        title=f"Pesos actualizados · {phase}",
        detail=f"{inserted} benchmarks rebalanceados.",
    )

    return {
        "phase": phase,
        "weights_count": inserted,
        "sum": total,
    }


@router.get("/scrape-state")
async def get_scrape_state(request: Request) -> dict[str, Any]:
    """Devuelve estado actual de scrapes activos.

    Útil para diagnóstico cuando 409 'scrape ya en curso' persiste.
    """
    scheduler = _get_scheduler(request)
    if scheduler is None:
        return {"active": {}, "scheduler_available": False}

    active_raw = getattr(scheduler, "_active_scrapes", {}) or {}
    now = int(time.time())
    return {
        "scheduler_available": True,
        "active": {
            source: {
                "started_at": ts,
                "age_seconds": now - (ts if isinstance(ts, int) else 0),
            }
            for source, ts in (active_raw.items() if isinstance(active_raw, dict) else {})
        },
    }


@router.post("/scrape-state/reset")
async def reset_scrape_state(request: Request) -> dict[str, Any]:
    """Limpia el estado de scrapes activos (admin/diagnostico).

    Útil cuando un scrape quedó stuck y bloquea nuevos triggers con 409.
    """
    scheduler = _get_scheduler(request)
    if scheduler is None:
        raise HTTPException(status_code=503, detail="Scheduler no disponible.")

    active = getattr(scheduler, "_active_scrapes", None)
    if active is None:
        return {"cleared": 0}

    count = len(active)
    if isinstance(active, dict):
        active.clear()
    elif isinstance(active, set):
        active.clear()
    return {"cleared": count}


@router.get("/discord-channels")
async def list_discord_channels(request: Request) -> dict[str, Any]:
    """Lista canales de texto del Discord del bot.

    Filtra por guild_id si está configurado en ConfigManager global.
    Devuelve {"channels": [{id, name, guild_name}]}.
    """
    bot = getattr(request.app.state, "bot", None)
    if bot is None:
        return {"channels": []}

    cm = getattr(request.app.state, "config_manager", None)
    guild_id_str = cm.get("guild_id") if cm else None
    try:
        guild_id = int(guild_id_str) if guild_id_str else None
    except (TypeError, ValueError):
        guild_id = None

    channels: list[dict[str, str]] = []
    for guild in getattr(bot, "guilds", []) or []:
        if guild_id is not None and guild.id != guild_id:
            continue
        for channel in getattr(guild, "text_channels", []) or []:
            channels.append(
                {
                    "id": str(channel.id),
                    "name": f"#{channel.name}",
                    "guild_name": guild.name,
                }
            )
    return {"channels": channels}


@router.get("/scrape-runs")
async def list_scrape_runs(
    request: Request,
    source: str | None = Query(default=None),
    limit: int = Query(default=10, gt=0, le=100),
) -> list[dict[str, Any]]:
    """Lista el historial de ejecuciones de scrapers.

    Query params:
        source: Filtrar por fuente (openrouter | aa | bfcl). Opcional.
        limit: Número máximo de resultados (1–100).
    """
    db = _get_db(request)
    rows = await db.list_scrape_runs(source=source, limit=limit)
    return [
        {
            "id": r.get("id"),
            "source": r.get("source", ""),
            "started_at": r.get("started_at"),
            "finished_at": r.get("finished_at"),
            "status": r.get("status", ""),
            "error": r.get("error"),
            "rows_updated": r.get("rows_updated", 0),
            "aliases_missed": r.get("aliases_missed", 0),
        }
        for r in rows
    ]
