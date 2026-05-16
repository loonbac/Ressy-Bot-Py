"""Round-trip de /api/plugins/music/config.

Replica el flujo real del dashboard: el usuario selecciona canales de voz
permitidos en la card "Canales permitidos", guarda (PUT) y recarga (GET).
El bug reportado: tras guardar, el canal ya no aparece seleccionado porque
el backend descartaba silenciosamente claves no escalares.
"""

import aiosqlite
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.bot.plugins.music_player import DEFAULTS
from src.bot.plugins.music_player.api import router as music_router


@pytest.fixture
async def music_client():
    """App mínima que replica el setup real del plugin de música."""
    db = await aiosqlite.connect(":memory:")
    await db.execute(
        "CREATE TABLE IF NOT EXISTS music_config (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
    )
    for key, value in DEFAULTS.items():
        await db.execute(
            "INSERT OR IGNORE INTO music_config (key, value) VALUES (?, ?)", (key, value)
        )
    await db.commit()

    app = FastAPI()
    app.state.music_db = db
    app.include_router(music_router, prefix="/api/plugins/music")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    await db.close()


# Snowflakes Discord reales (19 dígitos, > 2^53): la precisión debe sobrevivir.
CH_A = "1145678901234567890"
CH_B = "1098765432109876543"


async def test_allowed_channels_roundtrip(music_client: AsyncClient):
    """Seleccionar canales, guardar y recargar debe conservarlos."""
    put = await music_client.put(
        "/api/plugins/music/config",
        json={"allowed_channel_ids": [CH_A, CH_B]},
    )
    assert put.status_code == 200
    assert put.json()["allowed_channel_ids"] == [CH_A, CH_B]

    get = await music_client.get("/api/plugins/music/config")
    assert get.status_code == 200
    assert get.json()["allowed_channel_ids"] == [CH_A, CH_B]


async def test_snowflake_precision_preserved(music_client: AsyncClient):
    """Los IDs deben volver como string idéntico, sin pérdida de precisión."""
    await music_client.put(
        "/api/plugins/music/config", json={"allowed_channel_ids": [CH_A]}
    )
    body = (await music_client.get("/api/plugins/music/config")).json()
    assert body["allowed_channel_ids"] == [CH_A]
    assert isinstance(body["allowed_channel_ids"][0], str)


async def test_enabled_commands_roundtrip(music_client: AsyncClient):
    """enabled_commands (lista) también debe persistir."""
    cmds = ["play", "skip", "queue"]
    await music_client.put(
        "/api/plugins/music/config", json={"enabled_commands": cmds}
    )
    body = (await music_client.get("/api/plugins/music/config")).json()
    assert body["enabled_commands"] == cmds


async def test_audio_quality_roundtrip(music_client: AsyncClient):
    """audio_quality (string no escalar enum) debe persistir."""
    await music_client.put(
        "/api/plugins/music/config", json={"audio_quality": "medium"}
    )
    body = (await music_client.get("/api/plugins/music/config")).json()
    assert body["audio_quality"] == "medium"
