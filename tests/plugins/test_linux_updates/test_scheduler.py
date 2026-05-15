"""Tests para LinuxUpdatesScheduler.

TDD estricto: test primero (RED), implementacion despues (GREEN).
Mock de tiempo via Counter; cero asyncio.sleep real.
"""
from __future__ import annotations

import asyncio
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.bot.plugins.linux_updates.scheduler import LinuxUpdatesScheduler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class Counter:
    """Proveedor de tiempo determinista para tests."""

    def __init__(self, start: int = 1_000_000) -> None:
        self.value = start

    def advance(self, seconds: int) -> None:
        self.value += seconds

    def __call__(self) -> int:
        return self.value


async def _mark_all_fresh(db, clock):
    """Marca todos los productos como recien revisados."""
    now = clock()
    await db._db.execute(
        "UPDATE products SET last_check_at = ?",
        (now,),
    )
    await db._db.commit()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_client():
    from src.bot.plugins.linux_updates.client import EndOfLifeClient

    client = MagicMock(spec=EndOfLifeClient)
    client.fetch_product = AsyncMock(return_value=[{
        "cycle": "24.04",
        "codename": "Noble Numbat",
        "release_date": "2024-04-25",
        "eol_date": "2029-05-31",
        "latest_version": "24.04.4",
        "lts": True,
        "support_date": "2029-05-31",
        "extended_support_date": None,
        "link": None,
        "release_label": None,
        "raw_json": "{}",
    }])
    client.close = AsyncMock()
    return client


@pytest.fixture
def embed_publisher():
    return AsyncMock(return_value=True)


@pytest.fixture
def scheduler(db, mock_client, embed_publisher):
    clock = Counter()
    sched = LinuxUpdatesScheduler(
        db=db,
        client=mock_client,
        embed_publisher=embed_publisher,
        time_provider=clock,
    )
    return sched, clock


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_stop(scheduler):
    """start crea task, stop la cancela limpiamente."""
    sched, clock = scheduler
    await sched.start()
    assert sched._task is not None
    assert not sched._task.done()

    await sched.stop()
    assert sched._task.done()


@pytest.mark.asyncio
async def test_stop_before_start_noop(scheduler):
    """stop sin start no lanza excepcion."""
    sched, clock = scheduler
    await sched.stop()  # No deberia fallar
    assert sched._task is None


# ---------------------------------------------------------------------------
# Tick — refresco de productos
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tick_refreshes_overdue_product(scheduler, db, mock_client):
    """Producto sin last_check_at -> fetch_product + upsert + status ok."""
    sched, clock = scheduler

    # Marcar los demas productos como frescos para que solo ubuntu se refresque
    await db._db.execute(
        "UPDATE products SET last_check_at = ? WHERE slug != ?",
        (clock(), "ubuntu"),
    )
    await db._db.commit()

    await sched._tick(await db.get_config())

    mock_client.fetch_product.assert_awaited_once_with("ubuntu")
    rows = await db.get_releases("ubuntu")
    assert len(rows) == 1
    assert rows[0]["cycle"] == "24.04"

    # Status actualizado
    product = await db.get_product("ubuntu")
    assert product["last_check_status"] == "ok"
    assert product["last_check_error"] is None
    assert product["last_check_at"] == clock()


@pytest.mark.asyncio
async def test_tick_skips_fresh_product(scheduler, db, mock_client):
    """Producto refrescado hace 1h, intervalo 12h -> skip."""
    sched, clock = scheduler

    # Marcar todos los productos como frescos
    await _mark_all_fresh(db, clock)
    # Simular que ubuntu se reviso hace 1 hora (aun asi dentro del intervalo)
    await db._db.execute(
        "UPDATE products SET last_check_at = ? WHERE slug = ?",
        (clock() - 3600, "ubuntu"),
    )
    await db._db.commit()

    await sched._tick(await db.get_config())

    mock_client.fetch_product.assert_not_awaited()


@pytest.mark.asyncio
async def test_tick_continues_on_error(scheduler, db, mock_client):
    """Un producto falla, el otro se refresca."""
    sched, clock = scheduler

    # ubuntu falla, debian sigue
    async def side_effect(slug):
        if slug == "ubuntu":
            raise RuntimeError("boom")
        return [{
            "cycle": "12",
            "codename": None,
            "release_date": "2023-06-10",
            "eol_date": "2026-06-10",
            "latest_version": "12.9",
            "lts": None,
            "support_date": None,
            "extended_support_date": None,
            "link": None,
            "release_label": None,
            "raw_json": "{}",
        }]

    mock_client.fetch_product = AsyncMock(side_effect=side_effect)

    await sched._tick(await db.get_config())

    # ubuntu quedo en error
    ubuntu = await db.get_product("ubuntu")
    assert ubuntu["last_check_status"] == "error"
    assert "boom" in ubuntu["last_check_error"]

    # debian se refresco
    debian = await db.get_releases("debian")
    assert len(debian) == 1
    debian_product = await db.get_product("debian")
    assert debian_product["last_check_status"] == "ok"


@pytest.mark.asyncio
async def test_tick_disabled_skips_all(scheduler, db, mock_client):
    """enabled=false -> nada se refresca."""
    sched, clock = scheduler
    await db.update_config({"enabled": "false"})

    await sched._tick(await db.get_config())

    mock_client.fetch_product.assert_not_awaited()


@pytest.mark.asyncio
async def test_tick_updates_product_status(scheduler, db):
    """Refresh exitoso -> last_check_status='ok'."""
    sched, clock = scheduler

    await sched._tick(await db.get_config())

    product = await db.get_product("ubuntu")
    assert product["last_check_status"] == "ok"
    assert product["last_check_at"] == clock()


# ---------------------------------------------------------------------------
# EOL Notifications
# ---------------------------------------------------------------------------


@pytest.fixture
def _seed_expiring_soon_release(db):
    """Inserta un release que expira dentro de 30 dias."""
    eol = (date.today() + timedelta(days=30)).isoformat()
    releases = [{
        "cycle": "22.04",
        "codename": "Jammy Jellyfish",
        "release_date": "2022-04-21",
        "eol_date": eol,
        "latest_version": "22.04.5",
        "lts": True,
        "support_date": eol,
        "extended_support_date": None,
        "link": None,
        "release_label": None,
        "raw_json": "{}",
    }]
    return releases


@pytest.mark.asyncio
async def test_eol_notification_sent(
    scheduler, db, mock_client, embed_publisher, _seed_expiring_soon_release
):
    """Release con eol dentro de warning_days -> embed_publisher llamado."""
    sched, clock = scheduler

    # Marcar los demas productos como frescos para que solo ubuntu se refresque
    await db._db.execute(
        "UPDATE products SET last_check_at = ? WHERE slug != ?",
        (clock(), "ubuntu"),
    )
    await db._db.commit()

    # Seed para que haya releases con EOL proximo
    mock_client.fetch_product = AsyncMock(return_value=_seed_expiring_soon_release)
    await db.update_config({"discord_channel_id": "123456789012345678"})

    await sched._tick(await db.get_config())

    embed_publisher.assert_awaited_once()
    args = embed_publisher.await_args
    assert args[0][0] == "123456789012345678"


@pytest.mark.asyncio
async def test_eol_notification_deduplicated(
    scheduler, db, mock_client, embed_publisher, _seed_expiring_soon_release
):
    """Misma release ya notificada -> skip."""
    sched, clock = scheduler

    # Marcar los demas productos como frescos
    await db._db.execute(
        "UPDATE products SET last_check_at = ? WHERE slug != ?",
        (clock(), "ubuntu"),
    )
    await db._db.commit()

    mock_client.fetch_product = AsyncMock(return_value=_seed_expiring_soon_release)
    await db.update_config({"discord_channel_id": "123456789012345678"})

    # Primera vez: notifica
    await sched._tick(await db.get_config())
    assert embed_publisher.await_count == 1

    # Reset mocks para verificar que no se llama de nuevo
    embed_publisher.reset_mock()

    # Avanzar el clock para que el producto este "overdue" de nuevo
    clock.advance(12 * 3600 + 1)
    await db._db.execute(
        "UPDATE products SET last_check_at = ? WHERE slug = ?",
        (clock() - 12 * 3600 - 2, "ubuntu"),
    )
    # Mantener los demas productos frescos para que solo ubuntu se reevalua
    await db._db.execute(
        "UPDATE products SET last_check_at = ? WHERE slug != ?",
        (clock(), "ubuntu"),
    )
    await db._db.commit()

    # Segunda vez: no debe notificar porque ya se envio
    await sched._tick(await db.get_config())
    embed_publisher.assert_not_awaited()


@pytest.mark.asyncio
async def test_eol_notification_no_channel(
    scheduler, db, mock_client, embed_publisher, _seed_expiring_soon_release
):
    """discord_channel_id vacio -> skip."""
    sched, clock = scheduler

    # Marcar los demas productos como frescos
    await db._db.execute(
        "UPDATE products SET last_check_at = ? WHERE slug != ?",
        (clock(), "ubuntu"),
    )
    await db._db.commit()

    mock_client.fetch_product = AsyncMock(return_value=_seed_expiring_soon_release)
    # channel_id ya esta vacio por defecto

    await sched._tick(await db.get_config())

    embed_publisher.assert_not_awaited()


@pytest.mark.asyncio
async def test_eol_notification_outside_window(
    scheduler, db, mock_client, embed_publisher
):
    """Release con eol > warning_days -> skip."""
    sched, clock = scheduler

    # Marcar los demas productos como frescos
    await db._db.execute(
        "UPDATE products SET last_check_at = ? WHERE slug != ?",
        (clock(), "ubuntu"),
    )
    await db._db.commit()

    # EOL dentro de 120 dias, pero warning_days es 90
    eol = (date.today() + timedelta(days=120)).isoformat()
    mock_client.fetch_product = AsyncMock(return_value=[{
        "cycle": "24.04",
        "codename": "Noble Numbat",
        "release_date": "2024-04-25",
        "eol_date": eol,
        "latest_version": "24.04.4",
        "lts": True,
        "support_date": eol,
        "extended_support_date": None,
        "link": None,
        "release_label": None,
        "raw_json": "{}",
    }])
    await db.update_config({"discord_channel_id": "123456789012345678"})

    await sched._tick(await db.get_config())

    embed_publisher.assert_not_awaited()


# ---------------------------------------------------------------------------
# _check_eol_notifications (directo)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_eol_expired_not_notified(
    scheduler, db, mock_client, embed_publisher
):
    """Release ya expirada (days_left < 0) -> no notifica."""
    sched, clock = scheduler

    eol = (date.today() - timedelta(days=5)).isoformat()
    await db.upsert_releases("ubuntu", [{
        "cycle": "20.04",
        "codename": "Focal Fossa",
        "release_date": "2020-04-23",
        "eol_date": eol,
        "latest_version": "20.04.6",
        "lts": True,
        "support_date": eol,
        "extended_support_date": None,
        "link": None,
        "release_label": None,
        "raw_json": "{}",
    }])
    await db.update_config({"discord_channel_id": "123456789012345678"})

    await sched._check_eol_notifications("ubuntu", await db.get_config())

    embed_publisher.assert_not_awaited()


@pytest.mark.asyncio
async def test_check_eol_publisher_failure_not_saved(
    scheduler, db, mock_client, embed_publisher
):
    """Si embed_publisher devuelve False, no guarda metadata."""
    sched, clock = scheduler

    embed_publisher.return_value = False

    eol = (date.today() + timedelta(days=30)).isoformat()
    await db.upsert_releases("ubuntu", [{
        "cycle": "22.04",
        "codename": "Jammy Jellyfish",
        "release_date": "2022-04-21",
        "eol_date": eol,
        "latest_version": "22.04.5",
        "lts": True,
        "support_date": eol,
        "extended_support_date": None,
        "link": None,
        "release_label": None,
        "raw_json": "{}",
    }])
    await db.update_config({"discord_channel_id": "123456789012345678"})

    await sched._check_eol_notifications("ubuntu", await db.get_config())

    # publisher fue llamado pero metadata no se guardo
    embed_publisher.assert_awaited_once()
    meta = await db.get_metadata()
    assert "notified_eol_ubuntu_22.04" not in meta


@pytest.mark.asyncio
async def test_check_eol_publisher_raises_exception(
    scheduler, db, embed_publisher
):
    """Si embed_publisher lanza excepcion, se captura y no se guarda metadata."""
    sched, clock = scheduler

    embed_publisher.side_effect = RuntimeError("discord broken")

    eol = (date.today() + timedelta(days=30)).isoformat()
    await db.upsert_releases("ubuntu", [{
        "cycle": "22.04",
        "codename": "Jammy Jellyfish",
        "release_date": "2022-04-21",
        "eol_date": eol,
        "latest_version": "22.04.5",
        "lts": True,
        "support_date": eol,
        "extended_support_date": None,
        "link": None,
        "release_label": None,
        "raw_json": "{}",
    }])
    await db.update_config({"discord_channel_id": "123456789012345678"})

    # No debe lanzar excepcion
    await sched._check_eol_notifications("ubuntu", await db.get_config())

    embed_publisher.assert_awaited_once()
    meta = await db.get_metadata()
    assert "notified_eol_ubuntu_22.04" not in meta


@pytest.mark.asyncio
async def test_tick_loop_executes_tick(scheduler, db, mock_client):
    """El loop de ticks realmente ejecuta _tick() antes de detenerse."""
    sched, clock = scheduler

    # Marcar todos como frescos para que _tick no haga nada (evitar side effects)
    await _mark_all_fresh(db, clock)

    # Espiamos _tick para verificar que el loop lo llama
    original_tick = sched._tick
    tick_calls = []

    async def spy_tick(config):
        tick_calls.append(config)
        await original_tick(config)
        # Detener inmediatamente tras el primer tick
        sched._stop_event.set()

    sched._tick = spy_tick

    await sched.start()
    # Esperar a que el loop termine (stop_event se setea en spy_tick)
    if sched._task is not None:
        try:
            await asyncio.wait_for(sched._task, timeout=2)
        except asyncio.TimeoutError:
            await sched.stop()

    assert len(tick_calls) >= 1
    assert tick_calls[0].get("enabled") == "true"
