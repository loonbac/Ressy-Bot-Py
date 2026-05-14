import pytest
import aiosqlite


@pytest.mark.anyio
async def test_real_db_has_api_key():
    """Test the user's actual database file."""
    db_path = "data/plugins/youtube.db"
    db = await aiosqlite.connect(db_path)
    rows = await db.execute_fetchall(
        "SELECT value FROM youtube_config WHERE key = 'google_api_key'"
    )
    await db.close()
    # If this fails, the key truly isn't in the DB
    assert len(rows) > 0, "google_api_key not found in DB!"
    assert len(rows[0]) > 0, "google_api_key value is empty!"
    print(f"API key in DB: '{rows[0][0]}'")
