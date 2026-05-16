"""Tests para LinuxUpdatesDatabase.

TDD estricto: cada test escrito primero (RED), luego implementado (GREEN).
Base de datos en memoria (:memory:) para aislar cada test.
"""
from __future__ import annotations

import pytest

from src.bot.plugins.linux_updates.database import LinuxUpdatesDatabase


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def db():
    database = LinuxUpdatesDatabase(":memory:")
    await database.connect()
    yield database
    await database.close()


def _make_release(cycle: str, **overrides) -> dict:
    base = {
        "cycle": cycle,
        "codename": None,
        "release_date": "2024-01-01",
        "eol_date": None,
        "latest_version": None,
        "latest_release_date": None,
        "lts": None,
        "support_date": None,
        "extended_support_date": None,
        "release_label": None,
        "link": None,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Schema + Seeds
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_connect_creates_tables(db: LinuxUpdatesDatabase):
    """Verifica que las tablas existen tras connect()."""
    assert db._db is not None
    tables = await db._db.execute_fetchall(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    names = {r["name"] for r in tables}
    assert {"config", "products", "releases", "metadata"}.issubset(names)


@pytest.mark.asyncio
async def test_connect_creates_indexes(db: LinuxUpdatesDatabase):
    """Verifica que los indices existen."""
    indexes = await db._db.execute_fetchall(
        "SELECT name FROM sqlite_master WHERE type='index'"
    )
    names = {r["name"] for r in indexes}
    assert "idx_releases_product" in names
    assert "idx_releases_eol" in names


@pytest.mark.asyncio
async def test_connect_seeds_products(db: LinuxUpdatesDatabase):
    """Deben existir los 16 productos semilla (6 originales + 5 EOL + 5 rolling)."""
    products = await db.get_products()
    slugs = {p["slug"] for p in products}
    expected = {
        # Originales
        "ubuntu", "debian", "fedora", "rocky-linux", "linuxmint", "linux",
        # EOL tracked
        "opensuse", "almalinux", "alpine-linux", "pop-os", "rhel",
        # Rolling (seed only, never fetched)
        "arch", "bazzite", "manjaro", "endeavouros", "cachyos",
    }
    assert slugs == expected


@pytest.mark.asyncio
async def test_connect_seeds_config_defaults(db: LinuxUpdatesDatabase):
    """Los defaults deben estar insertados."""
    config = await db.get_config()
    assert config["enabled"] == "true"
    assert config["refresh_interval_hours"] == "12"
    assert config["eol_warning_days"] == "90"
    assert config["discord_channel_id"] == ""


@pytest.mark.asyncio
async def test_connect_idempotent(db: LinuxUpdatesDatabase):
    """Re-conectar no duplica seeds ni productos."""
    await db.connect()
    products = await db.get_products()
    config = await db.get_config()
    assert len(products) == 16
    # Config sigue teniendo solo las 4 claves default (más cualquier custom no existe)
    assert len(config) == 4


# ---------------------------------------------------------------------------
# Product CRUD
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_product_found(db: LinuxUpdatesDatabase):
    p = await db.get_product("ubuntu")
    assert p is not None
    assert p["slug"] == "ubuntu"
    assert p["display_name"] == "Ubuntu"


@pytest.mark.asyncio
async def test_get_product_not_found(db: LinuxUpdatesDatabase):
    p = await db.get_product("no-existe")
    assert p is None


@pytest.mark.asyncio
async def test_get_products_returns_all(db: LinuxUpdatesDatabase):
    products = await db.get_products()
    assert len(products) == 16


@pytest.mark.asyncio
async def test_rolling_products_seeded(db: LinuxUpdatesDatabase):
    """Los productos rolling deben estar en la DB con sus nombres correctos."""
    products = await db.get_products()
    product_map = {p["slug"]: p["display_name"] for p in products}
    rolling_expected = {
        "arch": "Arch Linux",
        "bazzite": "Bazzite",
        "manjaro": "Manjaro",
        "endeavouros": "EndeavourOS",
        "cachyos": "CachyOS",
    }
    for slug, name in rolling_expected.items():
        assert slug in product_map, f"Producto rolling '{slug}' no encontrado"
        assert product_map[slug] == name


@pytest.mark.asyncio
async def test_eol_products_seeded(db: LinuxUpdatesDatabase):
    """Los 5 productos EOL adicionales deben estar en la DB con sus nombres correctos."""
    products = await db.get_products()
    product_map = {p["slug"]: p["display_name"] for p in products}
    eol_expected = {
        "opensuse": "openSUSE",
        "almalinux": "AlmaLinux",
        "alpine-linux": "Alpine Linux",
        "pop-os": "Pop!_OS",
        "rhel": "RHEL",
    }
    for slug, name in eol_expected.items():
        assert slug in product_map, f"Producto EOL '{slug}' no encontrado"
        assert product_map[slug] == name


# ---------------------------------------------------------------------------
# Releases upsert + query
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_upsert_releases_inserts_new(db: LinuxUpdatesDatabase):
    rels = [_make_release("24.04", eol_date="2034-04-01")]
    await db.upsert_releases("ubuntu", rels)
    rows = await db.get_releases("ubuntu")
    assert len(rows) == 1
    assert rows[0]["cycle"] == "24.04"


@pytest.mark.asyncio
async def test_upsert_releases_updates_existing(db: LinuxUpdatesDatabase):
    rels = [_make_release("24.04", eol_date="2034-04-01")]
    await db.upsert_releases("ubuntu", rels)
    # Mismo cycle, distinto eol
    rels2 = [_make_release("24.04", eol_date="2035-05-01")]
    await db.upsert_releases("ubuntu", rels2)
    rows = await db.get_releases("ubuntu")
    assert len(rows) == 1
    assert rows[0]["eol_date"] == "2035-05-01"


@pytest.mark.asyncio
async def test_upsert_replaces_old_cycles(db: LinuxUpdatesDatabase):
    await db.upsert_releases("ubuntu", [
        _make_release("24.04", eol_date="2034-04-01"),
        _make_release("22.04", eol_date="2027-04-01"),
    ])
    # Ahora solo 24.04
    await db.upsert_releases("ubuntu", [_make_release("24.04", eol_date="2034-04-01")])
    rows = await db.get_releases("ubuntu")
    assert len(rows) == 1
    assert rows[0]["cycle"] == "24.04"


@pytest.mark.asyncio
async def test_get_releases_ordered(db: LinuxUpdatesDatabase):
    await db.upsert_releases("ubuntu", [
        _make_release("22.04", release_date="2022-04-21"),
        _make_release("24.04", release_date="2024-04-25"),
        _make_release("20.04", release_date="2020-04-23"),
    ])
    rows = await db.get_releases("ubuntu")
    cycles = [r["cycle"] for r in rows]
    assert cycles == ["24.04", "22.04", "20.04"]


@pytest.mark.asyncio
async def test_get_active_releases_filters_eol(db: LinuxUpdatesDatabase):
    # una activa (eol en el futuro), una expirada, una sin eol
    await db.upsert_releases("ubuntu", [
        _make_release("24.04", eol_date="2099-04-01"),
        _make_release("20.04", eol_date="2020-04-01"),
        _make_release("rolling", eol_date=None),
    ])
    rows = await db.get_active_releases("ubuntu")
    cycles = {r["cycle"] for r in rows}
    assert cycles == {"24.04", "rolling"}


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_summary_counts(db: LinuxUpdatesDatabase):
    await db.upsert_releases("ubuntu", [
        _make_release("24.04", eol_date="2099-04-01"),
        _make_release("20.04", eol_date="2020-04-01"),
    ])
    summary = await db.get_summary()
    assert summary["total_releases"] == 2
    assert summary["active_releases"] == 1


@pytest.mark.asyncio
async def test_get_summary_expiring_soon(db: LinuxUpdatesDatabase):
    # eol dentro de ~30 dias
    from datetime import datetime, timedelta, timezone
    soon = (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%Y-%m-%d")
    await db.upsert_releases("ubuntu", [
        _make_release("24.04", eol_date=soon),
    ])
    summary = await db.get_summary()
    assert len(summary["expiring_soon"]) == 1
    assert summary["expiring_soon"][0]["cycle"] == "24.04"


@pytest.mark.asyncio
async def test_get_summary_no_eol_date(db: LinuxUpdatesDatabase):
    await db.upsert_releases("ubuntu", [
        _make_release("rolling", eol_date=None),
    ])
    summary = await db.get_summary()
    assert len(summary["no_eol_date"]) == 1
    assert summary["no_eol_date"][0]["cycle"] == "rolling"


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_config_validates(db: LinuxUpdatesDatabase):
    with pytest.raises(ValueError):
        await db.update_config({"refresh_interval_hours": "0"})
    with pytest.raises(ValueError):
        await db.update_config({"eol_warning_days": "3"})


@pytest.mark.asyncio
async def test_update_config_success(db: LinuxUpdatesDatabase):
    await db.update_config({"refresh_interval_hours": "6", "eol_warning_days": "30"})
    config = await db.get_config()
    assert config["refresh_interval_hours"] == "6"
    assert config["eol_warning_days"] == "30"


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_metadata_set_and_get(db: LinuxUpdatesDatabase):
    await db.set_metadata("last_run", "12345")
    assert await db.get_metadata_value("last_run") == "12345"
    meta = await db.get_metadata()
    assert meta["last_run"] == "12345"


@pytest.mark.asyncio
async def test_get_metadata_value_missing(db: LinuxUpdatesDatabase):
    assert await db.get_metadata_value("no_existe") is None


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_close_releases_connection():
    database = LinuxUpdatesDatabase(":memory:")
    await database.connect()
    await database.close()
    assert database._db is None
