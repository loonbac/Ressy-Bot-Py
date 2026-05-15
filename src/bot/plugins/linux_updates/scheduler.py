"""Scheduler del plugin linux_updates.

Implementa un loop asyncio con tick cada 60 segundos. Cada tick evalua
si algun producto esta vencido (comparando last_check_at con el intervalo
configurado) y lo refresca desde la API endoflife.date. Post-refresh,
chequea notificaciones EOL con deduplicacion via metadata.

El scheduler es la UNICA fuente de refresco; no hay comandos manuales.
"""
from __future__ import annotations

import asyncio
import logging
import time as _time
from datetime import date
from typing import Any, Callable

from .client import EndOfLifeClient
from .database import LinuxUpdatesDatabase
from .embeds import build_eol_notification_embed

logger = logging.getLogger(__name__)

_TICK_INTERVAL = 60  # segundos

# Claves de metadata para notificaciones EOL
_META_EOL_PREFIX = "notified_eol_"


class LinuxUpdatesScheduler:
    """Scheduler de refresco y notificaciones EOL para distribuciones Linux.

    Todos los parametros son inyectados para facilitar testing.

    Args:
        db: Instancia de LinuxUpdatesDatabase.
        client: Instancia de EndOfLifeClient.
        embed_publisher: Callable async (channel_id, embed) -> bool.
            Si None, las notificaciones EOL se omiten sin error.
        time_provider: Callable () -> int que retorna el timestamp actual.
            Por defecto time.time.
    """

    def __init__(
        self,
        *,
        db: LinuxUpdatesDatabase,
        client: EndOfLifeClient,
        embed_publisher: Callable | None = None,
        time_provider: Callable[[], int] | None = None,
    ) -> None:
        self._db = db
        self._client = client
        self._embed_publisher = embed_publisher
        self._now: Callable[[], int] = time_provider or (lambda: int(_time.time()))
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

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

    # ------------------------------------------------------------------
    # Loop
    # ------------------------------------------------------------------

    async def _tick_loop(self) -> None:
        """Loop principal: ejecuta _tick() cada _TICK_INTERVAL segundos."""
        while not self._stop_event.is_set():
            try:
                config = await self._db.get_config()
                if config.get("enabled", "true").lower() == "true":
                    await self._tick(config)
            except Exception as exc:
                logger.error("Error en tick del scheduler: %s", exc, exc_info=True)
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=_TICK_INTERVAL,
                )
                break  # stop_event fue seteado
            except asyncio.TimeoutError:
                pass  # Timeout normal -> siguiente tick

    # ------------------------------------------------------------------
    # Tick
    # ------------------------------------------------------------------

    async def _tick(self, config: dict[str, str]) -> None:
        """Evalua productos vencidos y los refresca."""
        if config.get("enabled", "true").lower() != "true":
            return

        products = await self._db.get_products()
        interval_hours = int(config.get("refresh_interval_hours", "12"))
        interval_seconds = interval_hours * 3600
        now = self._now()

        for product in products:
            slug = product["slug"]
            last_check = product.get("last_check_at")

            # Si no tiene last_check_at o paso el intervalo, refrescar
            if last_check is None or (now - last_check) >= interval_seconds:
                try:
                    releases = await self._client.fetch_product(slug)
                    await self._db.upsert_releases(slug, releases)
                    # Actualizar last_check_at y status en tabla products
                    await self._db._execute(
                        "UPDATE products SET last_check_at=?, last_check_status='ok', last_check_error=NULL WHERE slug=?",
                        (now, slug),
                    )
                    logger.info("Refrescado %s: %d releases", slug, len(releases))

                    # Notificaciones EOL post-refresh
                    if self._embed_publisher is not None:
                        await self._check_eol_notifications(slug, config)

                except Exception as exc:
                    logger.error("Error refrescando %s: %s", slug, exc)
                    await self._db._execute(
                        "UPDATE products SET last_check_status='error', last_check_error=? WHERE slug=?",
                        (str(exc)[:500], slug),
                    )

    # ------------------------------------------------------------------
    # EOL Notifications
    # ------------------------------------------------------------------

    async def _check_eol_notifications(
        self, slug: str, config: dict[str, str]
    ) -> None:
        """Publica notificaciones para releases proximas a EOL."""
        config_warning_days = int(config.get("eol_warning_days", "90"))
        channel_id = config.get("discord_channel_id", "")
        if not channel_id:
            return

        display_name = {
            "ubuntu": "Ubuntu",
            "debian": "Debian",
            "fedora": "Fedora",
            "rocky-linux": "Rocky Linux",
            "linuxmint": "Linux Mint",
            "linux": "Linux Kernel",
        }.get(slug, slug)

        releases = await self._db.get_active_releases(slug)
        metadata = await self._db.get_metadata()

        for release in releases:
            eol_str = release.get("eol_date")
            if not eol_str:
                continue

            try:
                eol_date = date.fromisoformat(eol_str)
                days_left = (eol_date - date.today()).days
            except (ValueError, TypeError):
                continue

            if days_left < 0 or days_left > config_warning_days:
                continue

            cycle = release.get("cycle", "?")
            meta_key = f"{_META_EOL_PREFIX}{slug}_{cycle}"

            if metadata.get(meta_key):
                continue  # ya notificado

            embed = build_eol_notification_embed(
                product_slug=slug,
                display_name=display_name,
                cycle=cycle,
                codename=release.get("codename"),
                eol_date=eol_str,
                days_left=days_left,
            )
            try:
                success = await self._embed_publisher(channel_id, embed)
                if success:
                    await self._db.set_metadata(meta_key, str(self._now()))
                    logger.info(
                        "Notificacion EOL enviada: %s %s (%d dias)",
                        slug, cycle, days_left,
                    )
            except Exception as exc:
                logger.error(
                    "Error enviando notificacion EOL %s %s: %s",
                    slug, cycle, exc,
                )
