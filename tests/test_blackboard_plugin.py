from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.bot.plugins.blackboard.database import BlackboardDatabase
from src.bot.plugins.blackboard.models import BlackboardConfig


@pytest.fixture
async def bb_db():
    db = BlackboardDatabase(":memory:")
    await db.init_db()
    yield db
    await db.close()


@pytest.fixture
async def bb_client(bb_db: BlackboardDatabase):
    from src.bot.plugins.blackboard.api import router as bb_router

    app = FastAPI()
    app.state.blackboard_db = bb_db
    app.include_router(bb_router, prefix="/api/plugins/blackboard")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


class TestDatabaseOperations:
    async def test_upsert_new_assignment(self, bb_db: BlackboardDatabase):
        is_new, date_changed = await bb_db.upsert_assignment(
            assignment_id="abc123",
            title="Tarea 1",
            course_name="Matemáticas",
            due_date="2025-06-01T23:59:00+00:00",
            status="Pending",
            source_url="https://example.com/tarea1",
        )
        assert is_new is True
        assert date_changed is False

    async def test_upsert_existing_assignment(self, bb_db: BlackboardDatabase):
        await bb_db.upsert_assignment(
            assignment_id="abc123",
            title="Tarea 1",
            course_name="Matemáticas",
            due_date="2025-06-01T23:59:00+00:00",
        )
        is_new, date_changed = await bb_db.upsert_assignment(
            assignment_id="abc123",
            title="Tarea 1 Updated",
            course_name="Matemáticas",
            due_date="2025-06-02T23:59:00+00:00",
        )
        assert is_new is False
        assert date_changed is True

    async def test_get_all_assignments(self, bb_db: BlackboardDatabase):
        await bb_db.upsert_assignment("a1", "Tarea A", "Curso A", due_date="2025-06-01T23:59:00+00:00")
        await bb_db.upsert_assignment("a2", "Tarea B", "Curso B", due_date="2025-06-02T23:59:00+00:00")

        assignments = await bb_db.get_all_assignments()
        assert len(assignments) == 2
        ids = {a["id"] for a in assignments}
        assert ids == {"a1", "a2"}

    async def test_assignment_exists(self, bb_db: BlackboardDatabase):
        await bb_db.upsert_assignment("a1", "Tarea A", "Curso A")
        assert await bb_db.assignment_exists("a1") is True
        assert await bb_db.assignment_exists("missing") is False

    async def test_get_assignment(self, bb_db: BlackboardDatabase):
        await bb_db.upsert_assignment("a1", "Tarea A", "Curso A", due_date="2025-06-01T23:59:00+00:00")
        row = await bb_db.get_assignment("a1")
        assert row is not None
        assert row["title"] == "Tarea A"
        assert row["course_name"] == "Curso A"

    async def test_get_assignment_missing(self, bb_db: BlackboardDatabase):
        row = await bb_db.get_assignment("missing")
        assert row is None

    async def test_notification_tracking(self, bb_db: BlackboardDatabase):
        await bb_db.upsert_assignment("a1", "Tarea A", "Curso A")
        assert await bb_db.is_24h_alerted("a1") is False
        await bb_db.mark_24h_alerted("a1")
        assert await bb_db.is_24h_alerted("a1") is True

        assert await bb_db.is_new_assignment_notified("a1") is False
        await bb_db.mark_new_assignment_notified("a1")
        assert await bb_db.is_new_assignment_notified("a1") is True

        assert await bb_db.is_week_digest_sent("2025-W20") is False
        await bb_db.mark_week_digest_sent("2025-W20")
        assert await bb_db.is_week_digest_sent("2025-W20") is True

    async def test_get_assignments_due_within_hours(self, bb_db: BlackboardDatabase):
        now = datetime.now(timezone.utc)
        soon = (now + timedelta(hours=12)).isoformat()
        later = (now + timedelta(hours=48)).isoformat()

        await bb_db.upsert_assignment("a1", "Soon", "Curso", due_date=soon)
        await bb_db.upsert_assignment("a2", "Later", "Curso", due_date=later)

        result = await bb_db.get_assignments_due_within_hours(24)
        ids = {r["id"] for r in result}
        assert "a1" in ids
        assert "a2" not in ids

    async def test_get_assignments_by_week(self, bb_db: BlackboardDatabase):
        await bb_db.upsert_assignment("a1", "Tarea", "Curso", due_date="2025-06-02T12:00:00+00:00")
        result = await bb_db.get_assignments_by_week(
            "2025-06-01T00:00:00+00:00",
            "2025-06-07T23:59:59+00:00",
        )
        assert len(result) == 1
        assert result[0]["id"] == "a1"


class TestConfigOperations:
    async def test_config_defaults(self, bb_db: BlackboardDatabase):
        raw = await bb_db.get_config()
        assert raw["enabled"] == "true"
        assert raw["blackboard_url"] == "https://senati.blackboard.com"
        assert raw["poll_interval_minutes"] == "60"
        assert raw["weekly_digest_day"] == "1"
        assert raw["timezone"] == "America/Lima"
        assert raw["headless"] == "true"

    async def test_update_config(self, bb_db: BlackboardDatabase):
        await bb_db.update_config({
            "enabled": "false",
            "blackboard_url": "https://test.com",
            "blackboard_user": "user",
            "blackboard_pass": "pass",
            "discord_channel_id": "123456789",
            "poll_interval_minutes": "30",
            "weekly_digest_day": "2",
            "timezone": "UTC",
            "headless": "false",
        })
        raw = await bb_db.get_config()
        assert raw["enabled"] == "false"
        assert raw["blackboard_url"] == "https://test.com"
        assert raw["blackboard_user"] == "user"
        assert raw["blackboard_pass"] == "pass"
        assert raw["discord_channel_id"] == "123456789"
        assert raw["poll_interval_minutes"] == "30"
        assert raw["weekly_digest_day"] == "2"
        assert raw["timezone"] == "UTC"
        assert raw["headless"] == "false"


class TestAPIEndpoints:
    async def test_get_config(self, bb_client: AsyncClient):
        resp = await bb_client.get("/api/plugins/blackboard/config")
        assert resp.status_code == 200
        data = resp.json()
        assert data["enabled"] is True
        assert data["blackboard_url"] == "https://senati.blackboard.com"
        assert data["poll_interval_minutes"] == 60

    async def test_put_config(self, bb_client: AsyncClient):
        resp = await bb_client.put("/api/plugins/blackboard/config", json={
            "enabled": False,
            "blackboard_url": "https://custom.bb.com",
            "blackboard_user": "student",
            "blackboard_pass": "secret",
            "discord_channel_id": None,
            "poll_interval_minutes": 45,
            "weekly_digest_day": 3,
            "timezone": "America/Lima",
            "headless": True,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["enabled"] is False
        assert data["blackboard_url"] == "https://custom.bb.com"
        assert data["blackboard_user"] == "student"

    async def test_list_assignments_empty(self, bb_client: AsyncClient):
        resp = await bb_client.get("/api/plugins/blackboard/assignments")
        assert resp.status_code == 200
        data = resp.json()
        assert data["assignments"] == []

    async def test_scrape_disabled(self, bb_client: AsyncClient):
        # First disable plugin
        await bb_client.put("/api/plugins/blackboard/config", json={
            "enabled": False,
            "blackboard_url": "https://senati.blackboard.com",
            "blackboard_user": "user",
            "blackboard_pass": "pass",
            "discord_channel_id": None,
            "poll_interval_minutes": 60,
            "weekly_digest_day": 1,
            "timezone": "America/Lima",
            "headless": True,
        })
        resp = await bb_client.post("/api/plugins/blackboard/scrape")
        assert resp.status_code == 400
        assert "deshabilitado" in resp.json()["detail"]

    async def test_scrape_no_credentials(self, bb_client: AsyncClient):
        resp = await bb_client.post("/api/plugins/blackboard/scrape")
        assert resp.status_code == 400
        assert "Credenciales" in resp.json()["detail"]


class TestBlackboardConfigModel:
    def test_defaults(self):
        cfg = BlackboardConfig()
        assert cfg.enabled is True
        assert cfg.blackboard_url == "https://senati.blackboard.com"
        assert cfg.poll_interval_minutes == 60
        assert cfg.weekly_digest_day == 1
        assert cfg.timezone == "America/Lima"
        assert cfg.headless is True

    def test_custom_values(self):
        cfg = BlackboardConfig(
            enabled=False,
            blackboard_url="https://test.com",
            blackboard_user="user",
            blackboard_pass="pass",
            discord_channel_id=123456789,
            poll_interval_minutes=30,
            weekly_digest_day=0,
            timezone="UTC",
            headless=False,
        )
        assert cfg.enabled is False
        assert cfg.blackboard_url == "https://test.com"
        assert cfg.blackboard_user == "user"
        assert cfg.discord_channel_id == 123456789
        assert cfg.weekly_digest_day == 0
        assert cfg.headless is False


class TestNotifierHelpers:
    def test_hours_until(self):
        from src.bot.plugins.blackboard.notifier import _hours_until
        future = (datetime.now(timezone.utc) + timedelta(hours=5)).isoformat()
        hours = _hours_until(future)
        assert 4 <= hours <= 6

    def test_hours_until_past(self):
        from src.bot.plugins.blackboard.notifier import _hours_until
        past = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
        hours = _hours_until(past)
        assert hours <= 0

    def test_format_remaining(self):
        from src.bot.plugins.blackboard.notifier import _format_remaining
        assert _format_remaining(-1) == "vencida!"
        assert _format_remaining(0.5) == "~30 minutos"
        assert _format_remaining(5) == "~5 horas"
        assert _format_remaining(48) == "2 días"
        assert _format_remaining(50) == "2 días, 2h"

    def test_urgency_emoji(self):
        from src.bot.plugins.blackboard.notifier import _urgency_emoji
        assert _urgency_emoji(5) == "🔴"
        assert _urgency_emoji(30) == "🟡"
        assert _urgency_emoji(100) == "🟢"


class TestScraperNormalization:
    def test_normalize_assignment(self):
        from src.bot.plugins.blackboard.scraper import BlackboardScraper
        from src.bot.plugins.blackboard.models import BlackboardConfig

        scraper = BlackboardScraper(BlackboardConfig())
        raw = {
            "title": "Tarea de prueba",
            "course_name": "Matemáticas",
            "course_id": "MAT101",
            "due_date": "15/06/25 23:59",
            "status": "Pending",
            "source_url": "/webapps/assignment",
        }
        norm = scraper._normalize_assignment(raw)
        assert norm["title"] == "Tarea de prueba"
        assert norm["course_name"] == "Matemáticas"
        assert norm["course_id"] == "MAT101"
        assert norm["due_date"] is not None
        assert norm["assignment_id"] is not None
        assert norm["source_url"].startswith("https://")

    def test_normalize_assignment_iso_date(self):
        from src.bot.plugins.blackboard.scraper import BlackboardScraper
        from src.bot.plugins.blackboard.models import BlackboardConfig

        scraper = BlackboardScraper(BlackboardConfig())
        raw = {
            "title": "Tarea",
            "course_name": "Curso",
            "due_date": "2025-06-15T23:59:00+00:00",
        }
        norm = scraper._normalize_assignment(raw)
        assert norm["due_date"] == "2025-06-15T23:59:00+00:00"

    def test_normalize_assignment_no_due_date(self):
        from src.bot.plugins.blackboard.scraper import BlackboardScraper
        from src.bot.plugins.blackboard.models import BlackboardConfig

        scraper = BlackboardScraper(BlackboardConfig())
        raw = {"title": "Sin fecha", "course_name": "Curso"}
        norm = scraper._normalize_assignment(raw)
        assert norm["due_date"] is None


@pytest.mark.live
class TestPluginIntegration:
    """Test que los endpoints del plugin responden (sin scraping real)."""

    @pytest.fixture
    async def app_with_plugin(self):
        from src.web.app import create_app
        from src.bot.core.config import ConfigManager

        ConfigManager.reset_instance()
        cm = ConfigManager()
        await cm.load(":memory:")

        app = create_app(config_manager=cm, bot=MagicMock())

        from src.bot.plugins.blackboard import setup as setup_blackboard
        await setup_blackboard(MagicMock(), cm, app)
        return app

    async def test_config_endpoint_returns_200(self, app_with_plugin):
        from httpx import ASGITransport, AsyncClient
        transport = ASGITransport(app=app_with_plugin)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/plugins/blackboard/config")
            assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    async def test_assignments_endpoint_returns_200(self, app_with_plugin):
        from httpx import ASGITransport, AsyncClient
        transport = ASGITransport(app=app_with_plugin)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/plugins/blackboard/assignments")
            assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

    async def test_scrape_endpoint_no_credentials(self, app_with_plugin):
        from httpx import ASGITransport, AsyncClient
        transport = ASGITransport(app=app_with_plugin)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/plugins/blackboard/scrape")
            assert resp.status_code == 400
