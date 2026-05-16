"""Base de datos SQLite para el plugin linux_updates.

Maneja el schema, configuracion, productos, releases y metadata.
Sigue el patron async de aiosqlite usado en el resto del proyecto.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any

import aiosqlite

logger = logging.getLogger(__name__)

_PRODUCTS = [
    # Distribuciones originales (trackean EOL)
    ("ubuntu", "Ubuntu"),
    ("debian", "Debian"),
    ("fedora", "Fedora"),
    ("rocky-linux", "Rocky Linux"),
    ("linuxmint", "Linux Mint"),
    ("linux", "Linux Kernel"),
    # Distribuciones EOL adicionales (trackean EOL via endoflife.date)
    ("opensuse", "openSUSE"),
    ("almalinux", "AlmaLinux"),
    ("alpine-linux", "Alpine Linux"),
    ("pop-os", "Pop!_OS"),
    ("rhel", "RHEL"),
    # Distribuciones rolling release (solo seed, NUNCA fetchear de endoflife.date)
    ("arch", "Arch Linux"),
    ("bazzite", "Bazzite"),
    ("manjaro", "Manjaro"),
    ("endeavouros", "EndeavourOS"),
    ("cachyos", "CachyOS"),
]

_DEFAULTS: dict[str, str] = {
    "enabled": "true",
    "refresh_interval_hours": "12",
    "eol_warning_days": "90",
    "discord_channel_id": "",
}


class LinuxUpdatesDatabase:
    """Persistencia SQLite para monitoreo de EOL de distribuciones Linux."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._db: aiosqlite.Connection | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Abre la conexion y crea el schema."""
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._create_schema()
        await self._seed_defaults()

    async def close(self) -> None:
        """Cierra la conexion de forma ordenada."""
        if self._db is not None:
            await self._db.close()
            self._db = None

    async def _execute(self, sql: str, parameters=()) -> None:
        """Ejecuta una sentencia SQL directamente (uso interno)."""
        assert self._db is not None
        await self._db.execute(sql, parameters)
        await self._db.commit()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    async def _create_schema(self) -> None:
        assert self._db is not None

        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS products (
                slug TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                last_check_at INTEGER,
                last_check_status TEXT NOT NULL DEFAULT 'ok',
                last_check_error TEXT
            )
        """)

        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS releases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_slug TEXT NOT NULL REFERENCES products(slug),
                cycle TEXT NOT NULL,
                codename TEXT,
                release_date TEXT,
                eol_date TEXT,
                latest_version TEXT,
                latest_release_date TEXT,
                lts INTEGER,
                support_date TEXT,
                extended_support_date TEXT,
                release_label TEXT,
                link TEXT,
                raw_json TEXT NOT NULL,
                fetched_at INTEGER NOT NULL
            )
        """)

        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_releases_product ON releases(product_slug)
        """)
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_releases_eol ON releases(eol_date)
        """)

        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)

        await self._db.commit()

    async def _seed_defaults(self) -> None:
        assert self._db is not None
        for slug, display_name in _PRODUCTS:
            await self._db.execute(
                "INSERT OR IGNORE INTO products (slug, display_name) VALUES (?, ?)",
                (slug, display_name),
            )
        for key, value in _DEFAULTS.items():
            await self._db.execute(
                "INSERT OR IGNORE INTO config (key, value) VALUES (?, ?)",
                (key, value),
            )
        await self._db.commit()

    # ------------------------------------------------------------------
    # Products
    # ------------------------------------------------------------------

    async def get_product(self, slug: str) -> dict[str, Any] | None:
        assert self._db is not None
        rows = await self._db.execute_fetchall(
            "SELECT * FROM products WHERE slug = ?", (slug,)
        )
        return dict(rows[0]) if rows else None

    async def get_products(self) -> list[dict[str, Any]]:
        assert self._db is not None
        rows = await self._db.execute_fetchall("SELECT * FROM products ORDER BY slug")
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Releases
    # ------------------------------------------------------------------

    async def get_releases(self, slug: str) -> list[dict[str, Any]]:
        assert self._db is not None
        rows = await self._db.execute_fetchall(
            """
            SELECT * FROM releases
            WHERE product_slug = ?
            ORDER BY release_date DESC
            """,
            (slug,),
        )
        return [dict(r) for r in rows]

    async def get_active_releases(self, slug: str) -> list[dict[str, Any]]:
        assert self._db is not None
        rows = await self._db.execute_fetchall(
            """
            SELECT * FROM releases
            WHERE product_slug = ?
              AND (eol_date >= date('now') OR eol_date IS NULL)
            ORDER BY release_date DESC
            """,
            (slug,),
        )
        return [dict(r) for r in rows]

    async def upsert_releases(self, slug: str, releases: list[dict[str, Any]]) -> None:
        assert self._db is not None
        fetched_at = int(__import__("time").time())
        await self._db.execute("BEGIN")
        try:
            await self._db.execute(
                "DELETE FROM releases WHERE product_slug = ?", (slug,)
            )
            for rel in releases:
                await self._db.execute(
                    """
                    INSERT INTO releases (
                        product_slug, cycle, codename, release_date, eol_date,
                        latest_version, latest_release_date, lts, support_date,
                        extended_support_date, release_label, link, raw_json, fetched_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        slug,
                        rel.get("cycle", ""),
                        rel.get("codename"),
                        rel.get("release_date"),
                        rel.get("eol_date"),
                        rel.get("latest_version"),
                        rel.get("latest_release_date"),
                        1 if rel.get("lts") else 0 if rel.get("lts") is not None else None,
                        rel.get("support_date"),
                        rel.get("extended_support_date"),
                        rel.get("release_label"),
                        rel.get("link"),
                        json.dumps(rel),
                        fetched_at,
                    ),
                )
            await self._db.commit()
        except Exception:
            await self._db.rollback()
            raise

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    async def get_summary(self) -> dict[str, Any]:
        assert self._db is not None
        total_rows = await self._db.execute_fetchall(
            "SELECT COUNT(*) as n FROM releases"
        )
        total_releases = total_rows[0]["n"] if total_rows else 0

        active_rows = await self._db.execute_fetchall(
            "SELECT COUNT(*) as n FROM releases WHERE eol_date >= date('now') OR eol_date IS NULL"
        )
        active_releases = active_rows[0]["n"] if active_rows else 0

        soon_rows = await self._db.execute_fetchall(
            """
            SELECT product_slug, cycle, eol_date,
                   julianday(eol_date) - julianday('now') as days_left
            FROM releases
            WHERE eol_date BETWEEN date('now') AND date('now', '+90 days')
            ORDER BY eol_date
            """
        )
        expiring_soon = []
        for r in soon_rows:
            expiring_soon.append({
                "slug": r["product_slug"],
                "cycle": r["cycle"],
                "eol_date": r["eol_date"],
                "days_left": int(r["days_left"]),
            })

        expired_rows = await self._db.execute_fetchall(
            """
            SELECT product_slug, cycle, eol_date
            FROM releases
            WHERE eol_date < date('now')
            ORDER BY eol_date DESC
            """
        )
        expired = []
        for r in expired_rows:
            expired.append({
                "slug": r["product_slug"],
                "cycle": r["cycle"],
                "eol_date": r["eol_date"],
            })

        no_eol_rows = await self._db.execute_fetchall(
            """
            SELECT product_slug, cycle
            FROM releases
            WHERE eol_date IS NULL
            ORDER BY product_slug, cycle
            """
        )
        no_eol_date = []
        for r in no_eol_rows:
            no_eol_date.append({
                "slug": r["product_slug"],
                "cycle": r["cycle"],
                "note": "Sin fecha EOL",
            })

        return {
            "total_releases": total_releases,
            "active_releases": active_releases,
            "expiring_soon": expiring_soon,
            "expired": expired,
            "no_eol_date": no_eol_date,
        }

    # ------------------------------------------------------------------
    # Config
    # ------------------------------------------------------------------

    async def get_config(self) -> dict[str, str]:
        assert self._db is not None
        rows = await self._db.execute_fetchall("SELECT key, value FROM config")
        return {row["key"]: row["value"] for row in rows}

    async def update_config(self, updates: dict[str, str]) -> None:
        assert self._db is not None
        for key, value in updates.items():
            if key == "refresh_interval_hours":
                if int(value) < 1:
                    raise ValueError("refresh_interval_hours debe ser >= 1")
            if key == "eol_warning_days":
                if int(value) < 7:
                    raise ValueError("eol_warning_days debe ser >= 7")
            await self._db.execute(
                "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)",
                (key, value),
            )
        await self._db.commit()

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    async def get_metadata(self) -> dict[str, str]:
        assert self._db is not None
        rows = await self._db.execute_fetchall("SELECT key, value FROM metadata")
        return {row["key"]: row["value"] for row in rows}

    async def set_metadata(self, key: str, value: str) -> None:
        assert self._db is not None
        await self._db.execute(
            "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
            (key, value),
        )
        await self._db.commit()

    async def get_metadata_value(self, key: str) -> str | None:
        assert self._db is not None
        rows = await self._db.execute_fetchall(
            "SELECT value FROM metadata WHERE key = ?", (key,)
        )
        return rows[0]["value"] if rows else None
