import pytest
from src.bot.plugins.linux_updates.database import LinuxUpdatesDatabase


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
