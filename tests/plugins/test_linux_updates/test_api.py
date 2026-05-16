import time
from datetime import date, timedelta

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.bot.plugins.linux_updates.api import router


@pytest.fixture
async def app(db):
    app = FastAPI()
    app.state.linux_updates_db = db
    app.include_router(router, prefix="/api/plugins/linux-updates")
    return app


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def client_no_db():
    app = FastAPI()
    app.include_router(router, prefix="/api/plugins/linux-updates")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# GET /products
# ---------------------------------------------------------------------------


class TestListProducts:
    async def test_list_products_empty(self, client):
        response = await client.get("/api/plugins/linux-updates/products")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 6
        for p in data:
            assert "slug" in p
            assert "display_name" in p
            assert p["release_count"] == 0
            assert p["active_count"] == 0
            assert p["expiring_soon_count"] == 0
            assert p["last_check_at"] is None
            assert p["last_check_status"] == "ok"
            assert p["stale"] is True
            assert p["updated_at"] == "Nunca"

    async def test_list_products_with_data(self, client, db):
        releases = [
            {
                "cycle": "24.04",
                "codename": "Noble Numbat",
                "release_date": "2024-04-25",
                "eol_date": "2034-04-25",
                "latest_version": "24.04.1",
                "latest_release_date": "2024-08-15",
                "lts": True,
                "support_date": None,
                "extended_support_date": None,
                "release_label": None,
                "link": None,
            }
        ]
        await db.upsert_releases("ubuntu", releases)

        response = await client.get("/api/plugins/linux-updates/products")
        assert response.status_code == 200
        data = response.json()
        ubuntu = next(p for p in data if p["slug"] == "ubuntu")
        assert ubuntu["release_count"] == 1
        assert ubuntu["active_count"] == 1
        assert ubuntu["expiring_soon_count"] == 0


# ---------------------------------------------------------------------------
# GET /products/{slug}
# ---------------------------------------------------------------------------


class TestGetProduct:
    async def test_get_product_found(self, client):
        response = await client.get("/api/plugins/linux-updates/products/ubuntu")
        assert response.status_code == 200
        data = response.json()
        assert data["slug"] == "ubuntu"
        assert data["display_name"] == "Ubuntu"

    async def test_get_product_not_found(self, client):
        response = await client.get("/api/plugins/linux-updates/products/nonexistent")
        assert response.status_code == 404
        assert "no encontrado" in response.json()["detail"].lower()

    async def test_get_product_with_releases(self, client, db):
        releases = [
            {
                "cycle": "22.04",
                "codename": "Jammy Jellyfish",
                "release_date": "2022-04-21",
                "eol_date": (date.today() + timedelta(days=30)).isoformat(),
                "latest_version": "22.04.5",
                "latest_release_date": "2024-08-15",
                "lts": True,
                "support_date": None,
                "extended_support_date": None,
                "release_label": None,
                "link": None,
            },
            {
                "cycle": "20.04",
                "codename": "Focal Fossa",
                "release_date": "2020-04-23",
                "eol_date": (date.today() - timedelta(days=30)).isoformat(),
                "latest_version": "20.04.6",
                "latest_release_date": "2024-04-10",
                "lts": True,
                "support_date": None,
                "extended_support_date": None,
                "release_label": None,
                "link": None,
            },
            {
                "cycle": "rolling",
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
            },
        ]
        await db.upsert_releases("ubuntu", releases)

        response = await client.get("/api/plugins/linux-updates/products/ubuntu")
        assert response.status_code == 200
        data = response.json()
        assert len(data["releases"]) == 3

        r1 = next(r for r in data["releases"] if r["cycle"] == "22.04")
        assert r1["status"] == "active"
        assert r1["days_until_eol"] == 30
        assert r1["lts"] is True

        r2 = next(r for r in data["releases"] if r["cycle"] == "20.04")
        assert r2["status"] == "expired"
        assert r2["days_until_eol"] < 0
        assert r2["lts"] is True

        r3 = next(r for r in data["releases"] if r["cycle"] == "rolling")
        assert r3["status"] == "unknown"
        assert r3["days_until_eol"] is None
        assert r3["lts"] is False


# ---------------------------------------------------------------------------
# GET /summary
# ---------------------------------------------------------------------------


class TestGetSummary:
    async def test_summary_empty(self, client):
        response = await client.get("/api/plugins/linux-updates/summary")
        assert response.status_code == 200
        data = response.json()
        assert data["total_releases"] == 0
        assert data["active_releases"] == 0
        assert data["expiring_soon"] == []
        assert data["expired"] == []
        assert data["no_eol_date"] == []

    async def test_summary_with_data(self, client, db):
        releases = [
            {
                "cycle": "22.04",
                "codename": None,
                "release_date": "2022-04-21",
                "eol_date": (date.today() + timedelta(days=30)).isoformat(),
                "latest_version": None,
                "latest_release_date": None,
                "lts": None,
                "support_date": None,
                "extended_support_date": None,
                "release_label": None,
                "link": None,
            },
            {
                "cycle": "20.04",
                "codename": None,
                "release_date": "2020-04-23",
                "eol_date": (date.today() - timedelta(days=30)).isoformat(),
                "latest_version": None,
                "latest_release_date": None,
                "lts": None,
                "support_date": None,
                "extended_support_date": None,
                "release_label": None,
                "link": None,
            },
            {
                "cycle": "rolling",
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
            },
        ]
        await db.upsert_releases("ubuntu", releases)

        response = await client.get("/api/plugins/linux-updates/summary")
        assert response.status_code == 200
        data = response.json()
        assert data["total_releases"] == 3
        assert data["active_releases"] == 2
        assert len(data["expiring_soon"]) == 1
        assert data["expiring_soon"][0]["cycle"] == "22.04"
        assert len(data["expired"]) == 1
        assert data["expired"][0]["cycle"] == "20.04"
        assert len(data["no_eol_date"]) == 1
        assert data["no_eol_date"][0]["cycle"] == "rolling"


# ---------------------------------------------------------------------------
# GET /config
# ---------------------------------------------------------------------------


class TestGetConfig:
    async def test_get_config_defaults(self, client):
        response = await client.get("/api/plugins/linux-updates/config")
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is True
        assert data["refresh_interval_hours"] == 12
        assert data["eol_warning_days"] == 90
        assert data["discord_channel_id"] == ""


# ---------------------------------------------------------------------------
# PUT /config
# ---------------------------------------------------------------------------


class TestPutConfig:
    async def test_put_config_valid(self, client):
        response = await client.put(
            "/api/plugins/linux-updates/config",
            json={"refresh_interval_hours": 6, "eol_warning_days": 30},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["refresh_interval_hours"] == 6
        assert data["eol_warning_days"] == 30

    async def test_put_config_invalid_interval(self, client):
        response = await client.put(
            "/api/plugins/linux-updates/config",
            json={"refresh_interval_hours": 0},
        )
        assert response.status_code == 400
        assert "refresh_interval_hours" in response.json()["detail"].lower()

    async def test_put_config_invalid_warning_days(self, client):
        response = await client.put(
            "/api/plugins/linux-updates/config",
            json={"eol_warning_days": 3},
        )
        assert response.status_code == 400
        assert "eol_warning_days" in response.json()["detail"].lower()

    async def test_put_config_unknown_key(self, client):
        response = await client.put(
            "/api/plugins/linux-updates/config",
            json={"unknown_key": 42},
        )
        assert response.status_code == 400
        assert "unknown_key" in response.json()["detail"]

    async def test_put_config_invalid_enabled(self, client):
        response = await client.put(
            "/api/plugins/linux-updates/config",
            json={"enabled": "maybe"},
        )
        assert response.status_code == 400
        assert "enabled" in response.json()["detail"].lower()

    async def test_put_config_invalid_interval_type(self, client):
        response = await client.put(
            "/api/plugins/linux-updates/config",
            json={"refresh_interval_hours": "abc"},
        )
        assert response.status_code == 400
        assert "refresh_interval_hours" in response.json()["detail"].lower()

    async def test_put_config_invalid_warning_days_type(self, client):
        response = await client.put(
            "/api/plugins/linux-updates/config",
            json={"eol_warning_days": "abc"},
        )
        assert response.status_code == 400
        assert "eol_warning_days" in response.json()["detail"].lower()

    async def test_put_config_invalid_discord_channel_id(self, client):
        response = await client.put(
            "/api/plugins/linux-updates/config",
            json={"discord_channel_id": "not-a-number"},
        )
        assert response.status_code == 400
        assert "discord_channel_id" in response.json()["detail"].lower()

    async def test_put_config_empty_discord_channel_id(self, client):
        response = await client.put(
            "/api/plugins/linux-updates/config",
            json={"discord_channel_id": ""},
        )
        assert response.status_code == 200
        assert response.json()["discord_channel_id"] == ""

    async def test_put_config_enabled_string(self, client):
        response = await client.put(
            "/api/plugins/linux-updates/config",
            json={"enabled": "false"},
        )
        assert response.status_code == 200
        assert response.json()["enabled"] is False


# ---------------------------------------------------------------------------
# Helpers / edge cases
# ---------------------------------------------------------------------------


class TestHelpers:
    async def test_get_db_missing_returns_500(self, client_no_db):
        response = await client_no_db.get("/api/plugins/linux-updates/products")
        assert response.status_code == 500
        assert "no inicializado" in response.json()["detail"].lower()

    async def test_list_products_not_stale(self, client, db):
        now = int(time.time())
        await db.set_metadata("last_check_at_ubuntu", str(now))
        # We can't easily update products.last_check_at via public API,
        # so we test _is_stale via releases insertion which sets fetched_at
        # but not last_check_at. Instead we rely on the empty test for stale=True.
        # Here we just verify the endpoint returns 200 with correct structure.
        response = await client.get("/api/plugins/linux-updates/products")
        assert response.status_code == 200
        data = response.json()
        ubuntu = next(p for p in data if p["slug"] == "ubuntu")
        assert ubuntu["stale"] is True  # because last_check_at is still None

    async def test_list_products_expiring_soon(self, client, db):
        releases = [
            {
                "cycle": "22.04",
                "codename": None,
                "release_date": "2022-04-21",
                "eol_date": (date.today() + timedelta(days=30)).isoformat(),
                "latest_version": None,
                "latest_release_date": None,
                "lts": None,
                "support_date": None,
                "extended_support_date": None,
                "release_label": None,
                "link": None,
            }
        ]
        await db.upsert_releases("ubuntu", releases)

        response = await client.get("/api/plugins/linux-updates/products")
        assert response.status_code == 200
        data = response.json()
        ubuntu = next(p for p in data if p["slug"] == "ubuntu")
        assert ubuntu["expiring_soon_count"] == 1

    async def test_get_product_invalid_eol_date(self, client, db):
        releases = [
            {
                "cycle": "bad",
                "codename": None,
                "release_date": "2024-01-01",
                "eol_date": "not-a-date",
                "latest_version": None,
                "latest_release_date": None,
                "lts": None,
                "support_date": None,
                "extended_support_date": None,
                "release_label": None,
                "link": None,
            }
        ]
        await db.upsert_releases("ubuntu", releases)

        response = await client.get("/api/plugins/linux-updates/products/ubuntu")
        assert response.status_code == 200
        data = response.json()
        bad = next(r for r in data["releases"] if r["cycle"] == "bad")
        assert bad["days_until_eol"] is None
        assert bad["status"] == "unknown"

    async def test_humanize_time_branches(self, client, db):
        now = int(time.time())
        # We can't directly call _humanize_time from the test easily,
        # but we can trigger it via list_products by updating last_check_at.
        # Update the product's last_check_at via direct DB access.
        await db._db.execute(
            "UPDATE products SET last_check_at = ? WHERE slug = ?",
            (now, "ubuntu"),
        )
        await db._db.commit()

        response = await client.get("/api/plugins/linux-updates/products")
        assert response.status_code == 200
        data = response.json()
        ubuntu = next(p for p in data if p["slug"] == "ubuntu")
        assert "segundos" in ubuntu["updated_at"] or "minuto" in ubuntu["updated_at"]

    async def test_is_stale_not_stale(self, client, db):
        now = int(time.time())
        await db._db.execute(
            "UPDATE products SET last_check_at = ? WHERE slug = ?",
            (now, "ubuntu"),
        )
        await db._db.commit()

        response = await client.get("/api/plugins/linux-updates/products")
        assert response.status_code == 200
        data = response.json()
        ubuntu = next(p for p in data if p["slug"] == "ubuntu")
        assert ubuntu["stale"] is False

    async def test_put_config_enabled_bool(self, client):
        response = await client.put(
            "/api/plugins/linux-updates/config",
            json={"enabled": False},
        )
        assert response.status_code == 200
        assert response.json()["enabled"] is False

    async def test_put_config_empty_body(self, client):
        response = await client.put(
            "/api/plugins/linux-updates/config",
            json={},
        )
        assert response.status_code == 200
        assert "enabled" in response.json()

    async def test_put_config_invalid_discord_type(self, client):
        response = await client.put(
            "/api/plugins/linux-updates/config",
            json={"discord_channel_id": 12345},
        )
        assert response.status_code == 400
        assert "discord_channel_id" in response.json()["detail"].lower()

    async def test_get_config_corrupted_int(self, client, db):
        # Bypass DB validation to insert a corrupted value directly
        await db._db.execute(
            "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)",
            ("refresh_interval_hours", "not-a-number"),
        )
        await db._db.commit()
        response = await client.get("/api/plugins/linux-updates/config")
        assert response.status_code == 200
        data = response.json()
        assert data["refresh_interval_hours"] == 12  # falls back to default
