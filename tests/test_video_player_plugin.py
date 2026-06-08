"""Tests del plugin de videos (RessyTube).

Replican el comportamiento real del código: serialización de config
(bool/int/list), alta/baja de workers contra un worker-manager fake, y que el
token nunca se devuelva completo (solo preview). Filosofía del proyecto: el
test copia lo que hace el código, no lo idealiza.
"""

import aiosqlite
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.bot.plugins.video_player import DEFAULTS
from src.bot.plugins.video_player.api import router as video_router
from src.bot.plugins.video_player.manager_client import ManagerError
from src.web.routes.activity import ALLOWED_KINDS

USER_A = "1145678901234567890"  # snowflake real (19 dígitos)
TOKEN_A = "MToolongusertokenABCDEF.x1y2z3.qwertyuiopASDF1234"


class FakeManager:
    """Stub del ManagerClient: registra llamadas, devuelve datos plausibles."""

    def __init__(self):
        self.workers: dict[str, dict] = {}
        self.quality: dict | None = None
        self.base_url = "http://fake:8081"
        self.fail_add: ManagerError | None = None

    def update(self, base_url=None, secret=None):
        if base_url is not None:
            self.base_url = base_url

    async def health(self):
        return {"max_workers": 5, "workers": len(self.workers), "idle": len(self.workers), "busy": 0}

    async def list_workers(self):
        return list(self.workers.values())

    async def add_worker(self, token):
        if self.fail_add is not None:
            raise self.fail_add
        info = {
            "user_id": USER_A,
            "username": "ressyworker",
            "tag": "ressyworker#0001",
            "avatar_url": "https://cdn.discordapp.com/avatars/x/y.png",
            "status": "idle",
            "busy": False,
        }
        self.workers[USER_A] = info
        return info

    async def remove_worker(self, worker_id):
        self.workers.pop(worker_id, None)
        return {"removed": worker_id}

    async def stop_worker(self, worker_id):
        return {"ok": True}

    async def set_quality(self, quality):
        self.quality = quality
        return {"quality": quality}

    async def play(self, *, guild_id, channel_id, video, worker_id=None):
        return {"user_id": USER_A, "tag": "ressyworker#0001", "video_id": "abc"}

    async def stop(self, channel_id=None):
        return {"stopped": []}


@pytest.fixture
async def video_client():
    db = await aiosqlite.connect(":memory:")
    await db.execute(
        "CREATE TABLE IF NOT EXISTS video_config (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
    )
    await db.execute(
        """
        CREATE TABLE IF NOT EXISTS video_workers (
            user_id TEXT PRIMARY KEY, token TEXT NOT NULL, username TEXT DEFAULT '',
            tag TEXT DEFAULT '', avatar_url TEXT DEFAULT '', added_at TEXT DEFAULT (datetime('now'))
        )
        """
    )
    for key, value in DEFAULTS.items():
        await db.execute(
            "INSERT OR IGNORE INTO video_config (key, value) VALUES (?, ?)", (key, value)
        )
    await db.commit()

    manager = FakeManager()
    app = FastAPI()
    app.state.video_db = db
    app.state.video_manager = manager
    app.include_router(video_router, prefix="/api/plugins/videos")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        client.fake_manager = manager  # type: ignore[attr-defined]
        yield client

    await db.close()


def test_videos_kind_registered():
    assert "videos" in ALLOWED_KINDS


async def test_config_defaults_types(video_client: AsyncClient):
    body = (await video_client.get("/api/plugins/videos/config")).json()
    assert body["enabled"] is True
    assert isinstance(body["width"], int) and body["width"] == 1280
    assert isinstance(body["enabled_commands"], list)
    assert body["enabled_commands"] == ["ver", "parar", "siguiente"]


async def test_config_update_quality_propagates(video_client: AsyncClient):
    put = await video_client.put(
        "/api/plugins/videos/config", json={"width": 1920, "height": 1080, "fps": 60}
    )
    assert put.status_code == 200
    body = put.json()
    assert body["width"] == 1920 and body["height"] == 1080 and body["fps"] == 60
    # La calidad debe haberse propagado al manager (camelCase bitrateMax).
    assert video_client.fake_manager.quality is not None
    assert video_client.fake_manager.quality["width"] == 1920
    assert "bitrateMax" in video_client.fake_manager.quality


async def test_config_rejects_unknown_commands(video_client: AsyncClient):
    put = await video_client.put(
        "/api/plugins/videos/config", json={"enabled_commands": ["ver", "hackear"]}
    )
    assert put.json()["enabled_commands"] == ["ver"]


async def test_add_worker_stores_and_masks_token(video_client: AsyncClient):
    res = await video_client.post("/api/plugins/videos/workers", json={"token": TOKEN_A})
    assert res.status_code == 200
    body = res.json()
    assert body["user_id"] == USER_A
    # El token NUNCA se devuelve completo, solo preview de los últimos 4.
    assert TOKEN_A not in str(body)
    assert body["token_preview"].endswith(TOKEN_A[-4:])

    # GET /workers fusiona DB + estado en vivo del manager.
    listing = (await video_client.get("/api/plugins/videos/workers")).json()
    assert listing["manager_online"] is True
    assert len(listing["workers"]) == 1
    assert listing["workers"][0]["status"] == "idle"
    assert TOKEN_A not in str(listing)


async def test_add_worker_empty_token_400(video_client: AsyncClient):
    res = await video_client.post("/api/plugins/videos/workers", json={"token": "  "})
    assert res.status_code == 400


async def test_add_worker_invalid_token_propagates_detail(video_client: AsyncClient):
    video_client.fake_manager.fail_add = ManagerError(400, "token inválido")
    res = await video_client.post("/api/plugins/videos/workers", json={"token": "bad"})
    assert res.status_code == 400
    assert res.json()["detail"] == "token inválido"


async def test_delete_worker_removes_from_db(video_client: AsyncClient):
    await video_client.post("/api/plugins/videos/workers", json={"token": TOKEN_A})
    res = await video_client.request("DELETE", f"/api/plugins/videos/workers/{USER_A}")
    assert res.status_code == 200
    listing = (await video_client.get("/api/plugins/videos/workers")).json()
    assert listing["workers"] == []


async def test_status_reports_online(video_client: AsyncClient):
    res = await video_client.get("/api/plugins/videos/status")
    assert res.status_code == 200
    assert res.json()["online"] is True


async def test_status_offline_when_manager_down(video_client: AsyncClient):
    async def boom():
        raise ManagerError(503, "sin conexión")

    video_client.fake_manager.health = boom  # type: ignore[assignment]
    res = await video_client.get("/api/plugins/videos/status")
    assert res.status_code == 200
    assert res.json()["online"] is False
