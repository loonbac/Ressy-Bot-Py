"""Standalone callback server for YouTube PubSubHubbub.

Runs on a separate port (8001) behind ngrok.
Only handles YouTube callbacks — NO dashboard, NO auth needed.
"""

import html
import os
import xml.etree.ElementTree as ET
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import aiosqlite
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse

DB_PATH = os.environ.get("YOUTUBE_DB_PATH", "data/plugins/youtube.db")


async def _init_db():
    """Ensure the videos table exists so the callback server can write
    independently even if the main bot hasn't started yet."""
    db = await aiosqlite.connect(DB_PATH)
    try:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS youtube_videos (
                video_id TEXT PRIMARY KEY,
                channel_id TEXT NOT NULL,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                published_at TEXT NOT NULL,
                notified INTEGER DEFAULT 0,
                notified_at TEXT
            )
            """
        )
        await db.commit()
    finally:
        await db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _init_db()
    yield


app = FastAPI(title="YouTube Callback", lifespan=lifespan)


async def _get_db():
    db = await aiosqlite.connect(DB_PATH)
    await db.execute("PRAGMA journal_mode=WAL")
    db.row_factory = aiosqlite.Row
    return db


@app.get("/api/plugins/youtube/callback")
async def handle_verification(request: Request):
    """Handle PubSubHubbub subscription verification."""
    challenge = request.query_params.get("hub.challenge")
    if challenge:
        return PlainTextResponse(challenge)
    return PlainTextResponse("OK")


@app.post("/api/plugins/youtube/callback")
async def handle_notification(request: Request):
    """Handle PubSubHubbub notification (Atom XML)."""
    body = await request.body()
    if not body:
        return {"status": "ok"}

    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return {"status": "error", "detail": "Invalid XML"}

    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "yt": "http://www.youtube.com/xml/schemas/2015",
    }

    db = await _get_db()
    try:
        for entry in root.findall("atom:entry", ns):
            video_id_elem = entry.find("yt:videoId", ns)
            channel_id_elem = entry.find("yt:channelId", ns)

            if video_id_elem is None or channel_id_elem is None:
                continue

            video_id = video_id_elem.text
            channel_id = channel_id_elem.text
            title_elem = entry.find("atom:title", ns)
            published_elem = entry.find("atom:published", ns)

            title = html.unescape(title_elem.text) if title_elem is not None and title_elem.text else "Unknown"
            published = published_elem.text if published_elem is not None else datetime.now(timezone.utc).isoformat()

            await db.execute(
                """INSERT OR IGNORE INTO youtube_videos
                   (video_id, channel_id, title, url, published_at, notified)
                   VALUES (?, ?, ?, ?, ?, 0)""",
                (
                    video_id,
                    channel_id,
                    title,
                    f"https://www.youtube.com/watch?v={video_id}",
                    published,
                ),
            )
            await db.commit()
    finally:
        await db.close()

    return {"status": "ok"}


@app.get("/health")
async def health():
    return {"status": "ok"}


def main():
    port = int(os.environ.get("CALLBACK_PORT", "8001"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    main()
