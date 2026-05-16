"""Scheduler del plugin openrouter_prices.

Implementa un loop asyncio con tick cada 60 segundos. Cada tick evalúa
si algún job está vencido (comparando last_run con el intervalo configurado)
y lo despacha en caso afirmativo. Los jobs están aislados en try/except;
un job que falla no detiene el loop ni afecta a otros jobs.

Jobs:
  - openrouter_refresh : cada openrouter_refresh_interval_hours horas
  - bfcl_scrape        : cada bfcl_scrape_interval_days días (si bfcl_scrape_enabled)
  - aa_scrape          : cada aa_scrape_interval_days días (si aa_scrape_enabled)
  - weekly_price_report: el día/hora configurado (si weekly_report_enabled) — PR3
  - ranking_embed      : cada ranking_embed_cron_days días (if ranking_embed_enabled) — PR3

Notas PR2:
  - embed_publisher acepta None → los jobs de embed se omiten sin error.
  - Los jobs de embed (weekly_report, ranking_embed) están reservados para PR3;
    en PR2 solo se evalúa si el publisher está disponible y se llama si es el caso.
  - openrouter_refresh llama client.fetch_models() + db.upsert_models().
"""
from __future__ import annotations

import asyncio
import inspect
import json
import logging
import time as _time
from typing import Any, Callable

from . import ranking

logger = logging.getLogger(__name__)

# Segundos entre ticks del loop principal
_TICK_INTERVAL = 60
# Si un scrape lleva más de este tiempo en _active_scrapes, lo consideramos
# stuck y permitimos un nuevo trigger (auto-cleanup ante crashes/hangs).
_STALE_SCRAPE_SECONDS = 360  # 6 minutos (timeout job 300s + buffer 60s)

# Clave de metadata para cada job (almacena último timestamp de ejecución)
_META_KEYS = {
    "openrouter_refresh": "last_openrouter_refresh_at",
    "bfcl_scrape": "last_bfcl_scrape_at",
    "aa_scrape": "last_aa_scrape_at",
    "weekly_report": "last_weekly_report_at",
    "ranking_embed": "last_ranking_embed_at",
}


class PluginScheduler:
    """Scheduler de jobs para el plugin openrouter_prices.

    Todos los parámetros son inyectados para facilitar testing.

    Args:
        bot: Instancia de discord.Client (usado para publicar embeds).
        db: Instancia de OpenRouterDatabase.
        openrouter_client: Instancia de OpenRouterClient.
        aa_scraper_factory: Callable de cero argumentos que retorna un ArtificialAnalysisScraper.
        bfcl_scraper: Instancia singleton de BFCLScraper.
        embed_publisher: Callable async (channel_id, embed) -> bool. Si None, jobs de embed se omiten.
        time_provider: Callable () -> int que retorna el timestamp actual. Por defecto time.time.
    """

    def __init__(
        self,
        *,
        bot,
        db,
        openrouter_client,
        aa_scraper_factory: Callable,
        bfcl_scraper,
        embed_publisher: Callable | None = None,
        time_provider: Callable[[], int] | None = None,
    ) -> None:
        self._bot = bot
        self._db = db
        self._client = openrouter_client
        self._aa_factory = aa_scraper_factory
        self._bfcl = bfcl_scraper
        self._embed_publisher = embed_publisher
        self._now: Callable[[], int] = time_provider or (lambda: int(_time.time()))
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
        # Conjunto de fuentes con scrape activo (para 409 conflict)
        # dict source → timestamp inicio; entradas con age > _STALE_SCRAPE_SECONDS
        # se consideran stuck y se ignoran (próximo trigger las reemplaza).
        self._active_scrapes: dict[str, int] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Inicia el loop de ticks como asyncio background task."""
        self._stop_event.clear()
        self._task = asyncio.create_task(self._tick_loop())

    async def stop(self) -> None:
        """Cancela el loop de forma limpia. Seguro de llamar antes de start()."""
        self._stop_event.set()
        if self._task is not None and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass

    def is_scraping(self, source: str) -> bool:
        """Retorna True si hay un scrape activo para la fuente dada (no stale)."""
        ts = self._active_scrapes.get(source)
        if ts is None:
            return False
        if self._now() - ts > _STALE_SCRAPE_SECONDS:
            # Entrada stuck — limpiar y considerar libre
            self._active_scrapes.pop(source, None)
            return False
        return True

    async def trigger_scrape(self, source: str) -> bool:
        """Dispara un scrape manual para la fuente dada.

        Returns:
            True si el scrape fue iniciado, False si ya estaba en curso (409).
        """
        from src.web.routes.activity import push_event

        if self.is_scraping(source):
            return False

        async def _run():
            self._active_scrapes[source] = self._now()
            try:
                # Cap duro de 300s para que un scrape colgado no quede activo forever
                if source in ("bfcl", "bfcl_github"):
                    await asyncio.wait_for(self._job_bfcl_scrape(), timeout=300)
                elif source in ("aa", "artificial_analysis"):
                    await asyncio.wait_for(self._job_aa_scrape(), timeout=180)
                elif source == "openrouter":
                    await asyncio.wait_for(self._job_openrouter_refresh(), timeout=60)
                else:
                    logger.warning("trigger_scrape: source '%s' no reconocido", source)
            except asyncio.TimeoutError:
                logger.error("trigger_scrape '%s' excedió timeout, abortando", source)
                try:
                    push_event(
                        kind="openrouter",
                        title=f"Scrape manual {source} timeout",
                        detail="Excedió el límite de tiempo y fue abortado.",
                    )
                except Exception:
                    pass
            except Exception as exc:
                logger.error("trigger_scrape '%s' falló: %s", source, exc, exc_info=True)
                try:
                    push_event(
                        kind="openrouter",
                        title=f"Scrape manual {source} falló",
                        detail=str(exc),
                    )
                except Exception:
                    pass
            finally:
                self._active_scrapes.pop(source, None)

        asyncio.create_task(_run())
        return True

    # ------------------------------------------------------------------
    # Loop
    # ------------------------------------------------------------------

    async def _tick_loop(self) -> None:
        """Loop principal: ejecuta _tick() cada _TICK_INTERVAL segundos."""
        while not self._stop_event.is_set():
            try:
                await self._tick()
            except Exception as exc:
                logger.error("Error inesperado en tick del scheduler: %s", exc, exc_info=True)
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=_TICK_INTERVAL,
                )
                break  # stop_event fue seteado
            except asyncio.TimeoutError:
                pass  # Timeout normal → siguiente tick

    # ------------------------------------------------------------------
    # Tick
    # ------------------------------------------------------------------

    async def _tick(self) -> None:
        """Evalúa y despacha jobs vencidos."""
        config = await self._db.get_config()
        metadata = await self._db.get_metadata()
        now = self._now()

        # --- openrouter_refresh ---
        await self._run_job_if_due(
            job_key="openrouter_refresh",
            interval_seconds=int(config.get("openrouter_refresh_interval_hours", "24")) * 3600,
            metadata=metadata,
            now=now,
            job_fn=self._job_openrouter_refresh,
            enabled=True,
        )

        # --- bfcl_scrape ---
        bfcl_enabled = config.get("bfcl_scrape_enabled", "true").lower() == "true"
        await self._run_job_if_due(
            job_key="bfcl_scrape",
            interval_seconds=int(config.get("bfcl_scrape_interval_days", "7")) * 86_400,
            metadata=metadata,
            now=now,
            job_fn=self._job_bfcl_scrape,
            enabled=bfcl_enabled,
        )

        # --- aa_scrape ---
        aa_enabled = config.get("aa_scrape_enabled", "true").lower() == "true"
        await self._run_job_if_due(
            job_key="aa_scrape",
            interval_seconds=int(config.get("aa_scrape_interval_days", "7")) * 86_400,
            metadata=metadata,
            now=now,
            job_fn=self._job_aa_scrape,
            enabled=aa_enabled,
        )

        # --- weekly_report (PR3: embed publisher requerido) ---
        if self._embed_publisher is not None:
            weekly_enabled = config.get("weekly_report_enabled", "true").lower() == "true"
            if weekly_enabled:
                await self._run_job_if_due(
                    job_key="weekly_report",
                    interval_seconds=7 * 86_400,
                    metadata=metadata,
                    now=now,
                    job_fn=self._job_weekly_report,
                    enabled=True,
                )

        # --- ranking_embed (PR3: embed publisher requerido) ---
        if self._embed_publisher is not None:
            embed_enabled = config.get("ranking_embed_enabled", "true").lower() == "true"
            if embed_enabled:
                interval_days = int(config.get("ranking_embed_cron_days", "14"))
                await self._run_job_if_due(
                    job_key="ranking_embed",
                    interval_seconds=interval_days * 86_400,
                    metadata=metadata,
                    now=now,
                    job_fn=self._job_ranking_embed,
                    enabled=True,
                )

    async def _run_job_if_due(
        self,
        *,
        job_key: str,
        interval_seconds: int,
        metadata: dict[str, str],
        now: int,
        job_fn,
        enabled: bool,
    ) -> None:
        """Ejecuta job_fn si enabled y el intervalo ha expirado."""
        if not enabled:
            return

        meta_key = _META_KEYS[job_key]
        last_run = int(metadata.get(meta_key, "0") or "0")

        if now - last_run < interval_seconds:
            return

        try:
            await job_fn()
        except Exception as exc:
            logger.error("Job '%s' falló: %s", job_key, exc, exc_info=True)
            return

        await self._db.set_metadata(meta_key, str(now))

    # ------------------------------------------------------------------
    # Jobs
    # ------------------------------------------------------------------

    async def _job_openrouter_refresh(self) -> None:
        """Actualiza el catálogo de modelos desde la API de OpenRouter."""
        fetched_at = self._now()
        models = await self._client.fetch_models()
        await self._db.upsert_models(models, fetched_at)

    async def _job_bfcl_scrape(self) -> None:
        """Ejecuta el scraper BFCL."""
        await self._bfcl.scrape(self._db)

    async def _job_aa_scrape(self) -> None:
        """Ejecuta el scraper de Artificial Analysis.

        El factory puede ser sincrono (tests) o una corutina (produccion:
        relee aa_api_key de la DB en cada scrape). Se await-ea si es awaitable
        para que la key configurada tras el arranque llegue al scraper sin
        reiniciar el bot.
        """
        aa_scraper = self._aa_factory()
        if inspect.isawaitable(aa_scraper):
            aa_scraper = await aa_scraper
        await aa_scraper.scrape(self._db)

    async def _job_weekly_report(self) -> None:
        """Publica el reporte semanal de precios en Discord."""
        from .discord_embeds import build_weekly_price_embed
        from src.web.routes.activity import push_event

        config = await self._db.get_config()
        channel_id = (
            config.get("weekly_report_channel_id", "")
            or config.get("discord_channel_id", "")
        )
        if not channel_id:
            push_event(
                kind="openrouter",
                title="Reporte semanal de precios fallo",
                detail="Sin canal configurado",
            )
            return

        enabled = config.get("weekly_report_enabled", "true").lower() == "true"
        if not enabled:
            return

        try:
            count = int(config.get("weekly_report_count", "10"))
        except (ValueError, TypeError):
            count = 10

        # Obtener modelos de texto más baratos por prompt
        rows = await self._db.list_models(
            text_only=True,
            sort_by="prompt",
            sort_dir="asc",
            limit=count,
        )

        from src.bot.plugins.openrouter_prices.models import to_per_million
        models = [
            {
                "id": r.get("id", ""),
                "name": r.get("name", r.get("id", "")),
                "pricing_prompt_per_mtok": to_per_million(r.get("pricing_prompt")),
                "pricing_completion_per_mtok": to_per_million(r.get("pricing_completion")),
                "context_length": r.get("context_length") or 0,
            }
            for r in rows
        ]

        embed = build_weekly_price_embed(models, generated_at=self._now())
        success = await self._embed_publisher(channel_id, embed)  # type: ignore[misc]

        if success:
            push_event(
                kind="openrouter",
                title="Reporte semanal de precios enviado",
                detail=f"{len(models)} modelos incluidos",
                meta={"channel_id": channel_id},
            )
        else:
            push_event(
                kind="openrouter",
                title="Reporte semanal de precios fallo",
                detail=f"No se pudo enviar al canal {channel_id}",
            )

    async def _job_ranking_embed(self) -> None:
        """Publica el embed bi-semanal de ranking en Discord."""
        from .discord_embeds import build_ranking_embed
        from src.web.routes.activity import push_event

        config = await self._db.get_config()
        # Fallback: si ranking_embed_channel_id vacío usar discord_channel_id general
        channel_id = (
            config.get("ranking_embed_channel_id", "")
            or config.get("discord_channel_id", "")
        )
        enabled = config.get("ranking_embed_enabled", "true").lower() == "true"

        if not enabled:
            return

        if not channel_id:
            push_event(
                kind="openrouter",
                title="Embed bi-semanal de ranking fallo",
                detail="Sin canal configurado (ni ranking_embed_channel_id ni discord_channel_id)",
            )
            return

        phases_raw = config.get("phases_enabled", "").strip()
        try:
            phases_loaded = json.loads(phases_raw) if phases_raw else []
        except json.JSONDecodeError:
            phases_loaded = []
        phases = [p for p in phases_loaded if isinstance(p, str) and p.strip()]

        if not phases:
            phases = [config.get("ranking_phase", "orchestrator")]

        per_phase = config.get("ranking_embed_per_phase", "true").lower() == "true"
        if not per_phase:
            # Modo backward-compatible: solo la primera fase
            phases = phases[:1]

        metadata = await self._db.get_metadata()

        for phase in phases:
            previous_top1 = (
                metadata.get(f"last_ranking_top1_{phase}")
                or metadata.get("last_ranking_top1")
                or None
            )

            ranked = await ranking.compute_ranking_for_phase(self._db, phase, n=10)

            if len(ranked) < 5:
                logger.warning(
                    "Fase '%s' tiene %d modelos rankeables (<5); se omite el embed.",
                    phase,
                    len(ranked),
                )
                continue

            embed = build_ranking_embed(
                phase=phase,
                ranked=ranked,
                previous_top1=previous_top1,
                generated_at=self._now(),
            )
            success = await self._embed_publisher(channel_id, embed)  # type: ignore[misc]

            if success:
                new_top1 = ranked[0]["model_id"] if ranked else ""
                await self._db.set_metadata(f"last_ranking_top1_{phase}", new_top1)
                push_event(
                    kind="openrouter",
                    title="Embed bi-semanal de ranking enviado",
                    detail=f"Fase: {phase}, top-1: {ranked[0].get('name', new_top1)}",
                    meta={"channel_id": channel_id, "phase": phase},
                )
            else:
                push_event(
                    kind="openrouter",
                    title="Embed bi-semanal de ranking fallo",
                    detail=f"No se pudo enviar al canal {channel_id}",
                )
