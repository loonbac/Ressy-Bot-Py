import asyncio
import html
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any

import aiosqlite
import discord
import httpx

from src.bot.plugins.youtube_notifier.models import YouTubePluginConfig, YouTubeVideo


class YouTubeMonitor:
    def __init__(self, db_path: str, config_manager: Any, bot: Any):
        self.db_path = db_path
        self.config_manager = config_manager
        self.bot = bot
        self._db: aiosqlite.Connection | None = None
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task | None = None
        self._poll_interval = 10
        self._last_poll: datetime | None = None
        self._http = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                "Accept": "text/xml, application/xml, */*",
            },
            follow_redirects=True,
        )
        self._consecutive_failures: dict[str, int] = {}

    async def init_db(self) -> None:
        self._db = await aiosqlite.connect(self.db_path)
        await self._db.execute("PRAGMA journal_mode=WAL")

        await self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS youtube_subscriptions (
                channel_id TEXT PRIMARY KEY,
                channel_name TEXT DEFAULT '',
                thumbnail_url TEXT DEFAULT '',
                added_at TEXT NOT NULL,
                last_checked TEXT,
                active INTEGER DEFAULT 1,
                notifications_enabled INTEGER DEFAULT 1
            )
            """
        )
        # Migrate existing tables that don't have notifications_enabled
        try:
            await self._db.execute(
                "ALTER TABLE youtube_subscriptions ADD COLUMN notifications_enabled INTEGER DEFAULT 1"
            )
            await self._db.commit()
        except Exception:
            pass  # column already exists

        # Migrate existing tables that don't have thumbnail_url
        try:
            await self._db.execute(
                "ALTER TABLE youtube_subscriptions ADD COLUMN thumbnail_url TEXT DEFAULT ''"
            )
            await self._db.commit()
        except Exception:
            pass  # column already exists

        await self._db.execute(
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
        await self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS youtube_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        await self._db.commit()

        # Seed default config
        defaults = {
            "enabled": "true",
            "poll_interval_minutes": "30",
            "discord_channel_id": "",
            "callback_url": "",
            "google_api_key": "",
            "announcement_message": "@everyone ¡Hay un nuevo video en {canal}!",
            "filter_shorts": "false",
            "filter_premieres": "false",
            "filter_min_duration": "0",
        }
        for key, value in defaults.items():
            await self._db.execute(
                "INSERT OR IGNORE INTO youtube_config (key, value) VALUES (?, ?)",
                (key, value),
            )
        await self._db.commit()

    async def close_db(self) -> None:
        if self._db is not None:
            await self._db.close()
            self._db = None
        await self._http.aclose()

    async def start(self) -> None:
        self._stop_event.clear()
        self._task = asyncio.create_task(self._polling_loop())

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _polling_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                config = await self.get_config()
                if config.enabled:
                    self._poll_interval = config.poll_interval_minutes
                    await self.poll_channels()
                    self._last_poll = datetime.now(timezone.utc)
            except Exception as exc:
                print(f"[YouTubeMonitor] Error en polling: {exc}")

            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self._poll_interval * 60,
                )
            except asyncio.TimeoutError:
                continue

    async def poll_channels(self) -> list[YouTubeVideo]:
        if self._db is None:
            raise RuntimeError("DB no inicializada")

        result = await self.poll_channels_with_diagnostics()
        return result["videos"]

    async def poll_channels_with_diagnostics(self) -> dict[str, Any]:
        """Poll channels and return detailed diagnostics per channel."""
        if self._db is None:
            raise RuntimeError("DB no inicializada")

        rows = await self._db.execute_fetchall(
            "SELECT channel_id, channel_name, thumbnail_url, notifications_enabled FROM youtube_subscriptions WHERE active = 1"
        )

        new_videos: list[YouTubeVideo] = []
        diagnostics: list[dict[str, Any]] = []

        for row in rows:
            channel_id = row[0]
            channel_name = row[1]
            channel_thumbnail = row[2] or ""
            notifications_enabled = bool(row[3])

            diag: dict[str, Any] = {
                "channel_id": channel_id,
                "channel_name": channel_name,
                "status": "ok",
                "videos_found": 0,
                "new_videos": 0,
            }

            try:
                videos = await self.fetch_recent_videos(channel_id)
                # Success: reset failure counter
                self._consecutive_failures[channel_id] = 0
            except httpx.HTTPStatusError as exc:
                self._consecutive_failures[channel_id] = self._consecutive_failures.get(channel_id, 0) + 1
                fails = self._consecutive_failures[channel_id]
                diag["status"] = "error"
                diag["error"] = f"HTTP {exc.response.status_code}"
                try:
                    diag["error_detail"] = exc.response.text[:500]
                except Exception:
                    diag["error_detail"] = "No detail available"

                if fails == 1:
                    print(f"[YouTubeMonitor] RSS no disponible para {channel_id} (HTTP {exc.response.status_code})")
                elif fails >= 3:
                    await self._db.execute(
                        "UPDATE youtube_subscriptions SET active = 0 WHERE channel_id = ?",
                        (channel_id,),
                    )
                    await self._db.commit()
                    print(f"[YouTubeMonitor] Canal {channel_id} desactivado tras {fails} fallos consecutivos")
                diagnostics.append(diag)
                continue
            except Exception as exc:
                diag["status"] = "error"
                diag["error"] = str(exc)
                diagnostics.append(diag)
                print(f"[YouTubeMonitor] Error inesperado para {channel_id}: {exc}")
                continue

            diag["videos_found"] = len(videos)

            for video in videos:
                exists = await self._db.execute_fetchall(
                    "SELECT 1 FROM youtube_videos WHERE video_id = ?", (video.video_id,)
                )
                if not exists:
                    await self._store_video(video)
                    new_videos.append(video)
                    diag["new_videos"] += 1
                    if notifications_enabled:
                        await self.notify_new_video(video, channel_name, channel_thumbnail)

            await self._db.execute(
                "UPDATE youtube_subscriptions SET last_checked = ? WHERE channel_id = ?",
                (datetime.now(timezone.utc).isoformat(), channel_id),
            )
            await self._db.commit()
            diagnostics.append(diag)

        return {
            "videos": new_videos,
            "diagnostics": diagnostics,
            "channels_checked": len(rows),
        }

    async def fetch_recent_videos(self, channel_id: str) -> list[YouTubeVideo]:
        """Fetch recent videos using YouTube Data API v3 (preferred) or RSS fallback."""
        config = await self.get_config()

        if config.google_api_key:
            return await self._fetch_via_api(channel_id, config.google_api_key)
        else:
            return await self._fetch_via_rss(channel_id)

    async def _fetch_via_api(self, channel_id: str, api_key: str) -> list[YouTubeVideo]:
        """Fetch videos using YouTube Data API v3."""
        url = "https://www.googleapis.com/youtube/v3/search"
        params = {
            "part": "snippet",
            "channelId": channel_id,
            "type": "video",
            "order": "date",
            "maxResults": 10,
            "key": api_key,
        }

        # Use a fresh client with default headers instead of the RSS-optimised
        # client that sends Accept: text/xml. This matches what search_channels
        # does in api.py and avoids any header-related surprises.
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params)

        if response.status_code == 403:
            try:
                error_data = response.json()
                error_msg = error_data.get("error", {}).get("message", "Unknown 403")
            except Exception:
                error_msg = response.text[:500] or "Unknown 403"
            print(f"[YouTubeMonitor] API 403 for {channel_id}: {error_msg}")
            return []

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            try:
                error_body = exc.response.text[:500]
            except Exception:
                error_body = "Unable to read response body"
            print(f"[YouTubeMonitor] API HTTP {exc.response.status_code} for {channel_id}: {error_body}")
            raise

        try:
            data = response.json()
        except Exception as exc:
            print(f"[YouTubeMonitor] API JSON decode error for {channel_id}: {exc}")
            raise

        videos = []
        for item in data.get("items", []):
            item_id = item.get("id", {})
            if item_id.get("kind") != "youtube#video":
                continue

            video_id = item_id.get("videoId")
            if not video_id:
                continue

            snippet = item.get("snippet", {})
            published_at = snippet.get("publishedAt")
            if not published_at:
                continue

            try:
                published_dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
            except ValueError:
                continue

            videos.append(YouTubeVideo(
                video_id=video_id,
                channel_id=channel_id,
                title=snippet.get("title", "Unknown"),
                url=f"https://www.youtube.com/watch?v={video_id}",
                published_at=published_dt,
            ))

        return videos

    async def _fetch_via_rss(self, channel_id: str) -> list[YouTubeVideo]:
        url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        response = await self._http.get(url, follow_redirects=True)
        response.raise_for_status()
        text = response.text

        root = ET.fromstring(text)

        # NS map for Atom + yt
        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "yt": "http://www.youtube.com/xml/schemas/2015",
        }

        videos: list[YouTubeVideo] = []
        for entry in root.findall("atom:entry", ns):
            video_id_elem = entry.find("yt:videoId", ns)
            title_elem = entry.find("atom:title", ns)
            link_elem = entry.find("atom:link[@rel='alternate']", ns)
            published_elem = entry.find("atom:published", ns)

            if video_id_elem is None or title_elem is None:
                continue

            video_id = video_id_elem.text or ""
            title = html.unescape(title_elem.text or "")
            video_url = (
                link_elem.get("href")
                if link_elem is not None
                else f"https://www.youtube.com/watch?v={video_id}"
            )
            published_at = datetime.now(timezone.utc)
            if published_elem is not None and published_elem.text:
                try:
                    published_at = datetime.fromisoformat(
                        published_elem.text.replace("Z", "+00:00")
                    )
                except ValueError:
                    pass

            videos.append(
                YouTubeVideo(
                    video_id=video_id,
                    channel_id=channel_id,
                    title=title,
                    url=video_url,
                    published_at=published_at,
                    notified=False,
                )
            )

        return videos

    async def check_rss(self, channel_id: str) -> bool:
        """Check if a channel's RSS feed is accessible."""
        url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        try:
            response = await self._http.get(url, follow_redirects=True, timeout=10.0)
            return response.status_code == 200
        except Exception:
            return False

    async def notify_new_video(
        self,
        video: YouTubeVideo,
        channel_name: str = "",
        channel_thumbnail: str = "",
        skip_filters: bool = False,
    ) -> None:
        config = await self.get_config()
        channel_id = config.discord_channel_id
        if channel_id is None or self.bot is None:
            return

        if not skip_filters:
            if config.filter_shorts and self._is_short(video):
                return
            if config.filter_premieres and self._is_premiere(video):
                return
            # filter_min_duration: RSS doesn't provide duration; skip for now

        # Backfill channel info from DB if caller didn't pass it.
        if (not channel_name or not channel_thumbnail) and self._db is not None:
            sub_rows = await self._db.execute_fetchall(
                "SELECT channel_name, thumbnail_url FROM youtube_subscriptions WHERE channel_id = ?",
                (video.channel_id,),
            )
            if sub_rows:
                if not channel_name:
                    channel_name = sub_rows[0][0] or ""
                if not channel_thumbnail:
                    channel_thumbnail = sub_rows[0][1] or ""

        try:
            discord_channel = self.bot.get_channel(channel_id)
            if discord_channel is None:
                discord_channel = await self.bot.fetch_channel(channel_id)
        except Exception as exc:
            print(f"[YouTubeMonitor] No se pudo obtener canal Discord {channel_id}: {exc}")
            return

        if not isinstance(discord_channel, discord.TextChannel):
            return

        message = config.announcement_message
        if "{canal}" in message:
            message = message.replace("{canal}", channel_name or "YouTube")

        embed = discord.Embed(
            title=video.title,
            url=video.url,
            description="Nuevo video publicado en YouTube",
            color=discord.Color.red(),
            timestamp=video.published_at,
        )
        if channel_name:
            embed.set_author(
                name=channel_name,
                url=f"https://youtube.com/channel/{video.channel_id}",
                icon_url=channel_thumbnail or None,
            )
        embed.set_image(url=f"https://i.ytimg.com/vi/{video.video_id}/hqdefault.jpg")
        embed.set_footer(text="YouTube")

        try:
            if message:
                await discord_channel.send(message, embed=embed)
            else:
                await discord_channel.send(embed=embed)
        except Exception as exc:
            print(f"[YouTubeMonitor] Error al enviar notificación: {exc}")
            return

        if self._db is not None:
            await self._db.execute(
                "UPDATE youtube_videos SET notified = 1, notified_at = ? WHERE video_id = ?",
                (datetime.now(timezone.utc).isoformat(), video.video_id),
            )
            await self._db.commit()

    async def test_notify_latest(self, count: int) -> dict[str, Any]:
        """Send notifications for the N latest videos of each active subscription.

        Bypasses content filters so the user can preview the embed regardless
        of shorts/premiere settings. Does NOT dedupe — re-sends even if the
        video was already notified.
        """
        if self._db is None:
            raise RuntimeError("DB no inicializada")
        if count < 1:
            count = 1
        if count > 10:
            count = 10

        config = await self.get_config()
        rows = await self._db.execute_fetchall(
            "SELECT channel_id, channel_name, thumbnail_url FROM youtube_subscriptions WHERE active = 1"
        )

        diagnostics: list[dict[str, Any]] = []
        total_sent = 0

        for row in rows:
            channel_id = row[0]
            channel_name = row[1]
            channel_thumbnail = row[2] or ""

            diag: dict[str, Any] = {
                "channel_id": channel_id,
                "channel_name": channel_name,
                "status": "ok",
                "videos_sent": 0,
            }

            try:
                videos = await self.fetch_recent_videos(channel_id)
            except httpx.HTTPStatusError as exc:
                diag["status"] = "error"
                diag["error"] = f"HTTP {exc.response.status_code}"
                try:
                    diag["error_detail"] = exc.response.text[:500]
                except Exception:
                    diag["error_detail"] = "No detail available"
                diagnostics.append(diag)
                continue
            except Exception as exc:
                diag["status"] = "error"
                diag["error"] = str(exc)
                diagnostics.append(diag)
                continue

            for video in videos[:count]:
                try:
                    await self.notify_new_video(
                        video, channel_name, channel_thumbnail, skip_filters=True
                    )
                    diag["videos_sent"] += 1
                    total_sent += 1
                except Exception as exc:
                    diag["status"] = "error"
                    diag["error"] = str(exc)

            diagnostics.append(diag)

        return {
            "total_sent": total_sent,
            "has_api_key": bool(config.google_api_key),
            "channels_checked": len(rows),
            "diagnostics": diagnostics,
        }

    def _is_short(self, video: YouTubeVideo) -> bool:
        title = video.title.lower()
        return "#shorts" in title or "#short" in title

    def _is_premiere(self, video: YouTubeVideo) -> bool:
        title = video.title.lower()
        return "premiere" in title or "premier" in title or "estreno" in title

    async def _store_video(self, video: YouTubeVideo) -> None:
        if self._db is None:
            raise RuntimeError("DB no inicializada")
        await self._db.execute(
            """INSERT OR IGNORE INTO youtube_videos
               (video_id, channel_id, title, url, published_at, notified)
               VALUES (?, ?, ?, ?, ?, 0)""",
            (video.video_id, video.channel_id, video.title, video.url, video.published_at.isoformat()),
        )
        await self._db.commit()

    async def subscribe_to_hub(self, channel_id: str, callback_url: str) -> bool:
        """Subscribe to a YouTube channel via PubSubHubbub."""
        if not callback_url:
            return False
        topic_url = f"https://www.youtube.com/xml/feeds/videos.xml?channel_id={channel_id}"
        hub_url = "https://pubsubhubbub.appspot.com/subscribe"
        base = callback_url.rstrip("/")

        data = {
            "hub.callback": f"{base}/api/plugins/youtube/callback",
            "hub.topic": topic_url,
            "hub.mode": "subscribe",
            "hub.verify": "async",
        }

        try:
            resp = await self._http.post(hub_url, data=data, timeout=30)
            return resp.status_code in (202, 204)
        except Exception as exc:
            print(f"PubSubHubbub subscribe failed for {channel_id}: {exc}")
            return False

    async def unsubscribe_from_hub(self, channel_id: str, callback_url: str) -> bool:
        """Unsubscribe from a YouTube channel."""
        if not callback_url:
            return False
        topic_url = f"https://www.youtube.com/xml/feeds/videos.xml?channel_id={channel_id}"
        hub_url = "https://pubsubhubbub.appspot.com/subscribe"
        base = callback_url.rstrip("/")

        data = {
            "hub.callback": f"{base}/api/plugins/youtube/callback",
            "hub.topic": topic_url,
            "hub.mode": "unsubscribe",
            "hub.verify": "async",
        }

        try:
            resp = await self._http.post(hub_url, data=data, timeout=30)
            return resp.status_code in (202, 204)
        except Exception as exc:
            print(f"PubSubHubbub unsubscribe failed for {channel_id}: {exc}")
            return False

    async def process_pubsub_notification(self, body: bytes) -> None:
        """Process a PubSubHubbub notification (Atom XML)."""
        root = ET.fromstring(body)
        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "yt": "http://www.youtube.com/xml/schemas/2015",
        }

        for entry in root.findall("atom:entry", ns):
            video_id_elem = entry.find("yt:videoId", ns)
            channel_id_elem = entry.find("yt:channelId", ns)
            title_elem = entry.find("atom:title", ns)
            published_elem = entry.find("atom:published", ns)

            if video_id_elem is None or channel_id_elem is None:
                continue

            vid = video_id_elem.text
            cid = channel_id_elem.text
            if vid is None or cid is None:
                continue

            # Check if already known
            if self._db is not None:
                existing = await self._db.execute_fetchall(
                    "SELECT 1 FROM youtube_videos WHERE video_id = ?", (vid,)
                )
                if existing:
                    continue  # already processed

            # Parse published date
            published_at = datetime.now(timezone.utc)
            if published_elem is not None and published_elem.text:
                try:
                    published_at = datetime.fromisoformat(
                        published_elem.text.replace("Z", "+00:00")
                    )
                except ValueError:
                    pass

            raw_title = title_elem.text if title_elem is not None else "Unknown"
            video = YouTubeVideo(
                video_id=vid,
                channel_id=cid,
                title=html.unescape(raw_title or "Unknown"),
                url=f"https://www.youtube.com/watch?v={vid}",
                published_at=published_at,
            )

            await self._store_video(video)
            await self.notify_new_video(video)

    # --- DB helpers ---

    async def add_subscription(self, channel_id: str, channel_name: str = "", thumbnail_url: str = "") -> bool:
        if self._db is None:
            raise RuntimeError("DB no inicializada")
        try:
            await self._db.execute(
                """
                INSERT INTO youtube_subscriptions (channel_id, channel_name, thumbnail_url, added_at, active, notifications_enabled)
                VALUES (?, ?, ?, ?, 1, 1)
                ON CONFLICT(channel_id) DO UPDATE SET active = 1, channel_name = excluded.channel_name, thumbnail_url = excluded.thumbnail_url
                """,
                (channel_id, channel_name, thumbnail_url, datetime.now(timezone.utc).isoformat()),
            )
            await self._db.commit()
            return True
        except Exception as exc:
            print(f"[YouTubeMonitor] Error al agregar suscripción: {exc}")
            return False

    async def update_subscription_notifications(self, channel_id: str, enabled: bool) -> None:
        if self._db is None:
            raise RuntimeError("DB no inicializada")
        await self._db.execute(
            "UPDATE youtube_subscriptions SET notifications_enabled = ? WHERE channel_id = ?",
            (1 if enabled else 0, channel_id),
        )
        await self._db.commit()

    async def remove_subscription(self, channel_id: str) -> bool:
        if self._db is None:
            raise RuntimeError("DB no inicializada")
        await self._db.execute(
            "UPDATE youtube_subscriptions SET active = 0 WHERE channel_id = ?",
            (channel_id,),
        )
        await self._db.commit()
        return True

    async def list_subscriptions(self) -> list[dict[str, Any]]:
        if self._db is None:
            raise RuntimeError("DB no inicializada")
        rows = await self._db.execute_fetchall(
            "SELECT channel_id, channel_name, thumbnail_url, added_at, last_checked, active, notifications_enabled FROM youtube_subscriptions WHERE active = 1"
        )
        return [
            {
                "channel_id": r[0],
                "channel_name": r[1],
                "thumbnail_url": r[2],
                "added_at": r[3],
                "last_checked": r[4],
                "active": bool(r[5]),
                "notifications_enabled": bool(r[6]),
            }
            for r in rows
        ]

    async def get_subscription(self, channel_id: str) -> dict[str, Any] | None:
        if self._db is None:
            raise RuntimeError("DB no inicializada")
        row = await self._db.execute_fetchall(
            "SELECT channel_id, channel_name, thumbnail_url, added_at, last_checked, active, notifications_enabled FROM youtube_subscriptions WHERE channel_id = ?",
            (channel_id,),
        )
        if not row:
            return None
        r = row[0]
        return {
            "channel_id": r[0],
            "channel_name": r[1],
            "thumbnail_url": r[2],
            "added_at": r[3],
            "last_checked": r[4],
            "active": bool(r[5]),
            "notifications_enabled": bool(r[6]),
        }

    async def get_videos(
        self, channel_id: str | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        if self._db is None:
            raise RuntimeError("DB no inicializada")
        if channel_id:
            rows = await self._db.execute_fetchall(
                "SELECT video_id, channel_id, title, url, published_at, notified FROM youtube_videos WHERE channel_id = ? ORDER BY published_at DESC LIMIT ?",
                (channel_id, limit),
            )
        else:
            rows = await self._db.execute_fetchall(
                "SELECT video_id, channel_id, title, url, published_at, notified FROM youtube_videos ORDER BY published_at DESC LIMIT ?",
                (limit,),
            )
        return [
            {
                "video_id": r[0],
                "channel_id": r[1],
                "title": r[2],
                "url": r[3],
                "published_at": r[4],
                "notified": bool(r[5]),
            }
            for r in rows
        ]

    async def get_config(self) -> YouTubePluginConfig:
        if self._db is None:
            raise RuntimeError("DB no inicializada")
        rows = await self._db.execute_fetchall("SELECT key, value FROM youtube_config")
        cfg: dict[str, Any] = {r[0]: r[1] for r in rows}
        return YouTubePluginConfig(
            enabled=cfg.get("enabled", "true").lower() == "true",
            poll_interval_minutes=int(cfg.get("poll_interval_minutes", "30")),
            discord_channel_id=int(cfg["discord_channel_id"])
            if cfg.get("discord_channel_id", "")
            else None,
            callback_url=cfg.get("callback_url", ""),
            google_api_key=cfg.get("google_api_key", ""),
            announcement_message=cfg.get("announcement_message", "@everyone ¡Hay un nuevo video en {canal}!"),
            filter_shorts=cfg.get("filter_shorts", "false").lower() == "true",
            filter_premieres=cfg.get("filter_premieres", "false").lower() == "true",
            filter_min_duration=int(cfg.get("filter_min_duration", "0")),
        )

    async def update_config(self, config: YouTubePluginConfig) -> None:
        if self._db is None:
            raise RuntimeError("DB no inicializada")
        await self._db.execute(
            "INSERT OR REPLACE INTO youtube_config (key, value) VALUES (?, ?)",
            ("enabled", str(config.enabled).lower()),
        )
        await self._db.execute(
            "INSERT OR REPLACE INTO youtube_config (key, value) VALUES (?, ?)",
            ("poll_interval_minutes", str(config.poll_interval_minutes)),
        )
        await self._db.execute(
            "INSERT OR REPLACE INTO youtube_config (key, value) VALUES (?, ?)",
            (
                "discord_channel_id",
                str(config.discord_channel_id) if config.discord_channel_id is not None else "",
            ),
        )
        await self._db.execute(
            "INSERT OR REPLACE INTO youtube_config (key, value) VALUES (?, ?)",
            ("callback_url", config.callback_url),
        )
        await self._db.execute(
            "INSERT OR REPLACE INTO youtube_config (key, value) VALUES (?, ?)",
            ("google_api_key", config.google_api_key),
        )
        await self._db.execute(
            "INSERT OR REPLACE INTO youtube_config (key, value) VALUES (?, ?)",
            ("announcement_message", config.announcement_message),
        )
        await self._db.execute(
            "INSERT OR REPLACE INTO youtube_config (key, value) VALUES (?, ?)",
            ("filter_shorts", str(config.filter_shorts).lower()),
        )
        await self._db.execute(
            "INSERT OR REPLACE INTO youtube_config (key, value) VALUES (?, ?)",
            ("filter_premieres", str(config.filter_premieres).lower()),
        )
        await self._db.execute(
            "INSERT OR REPLACE INTO youtube_config (key, value) VALUES (?, ?)",
            ("filter_min_duration", str(config.filter_min_duration)),
        )
        await self._db.commit()

    async def get_status(self) -> dict[str, Any]:
        if self._db is None:
            raise RuntimeError("DB no inicializada")
        sub_count = await self._db.execute_fetchall(
            "SELECT COUNT(*) FROM youtube_subscriptions WHERE active = 1"
        )
        video_count = await self._db.execute_fetchall(
            "SELECT COUNT(*) FROM youtube_videos"
        )
        config = await self.get_config()
        return {
            "enabled": config.enabled,
            "poll_interval_minutes": config.poll_interval_minutes,
            "discord_channel_id": str(config.discord_channel_id) if config.discord_channel_id is not None else None,
            "callback_url": config.callback_url,
            "google_api_key": config.google_api_key,
            "announcement_message": config.announcement_message,
            "filter_shorts": config.filter_shorts,
            "filter_premieres": config.filter_premieres,
            "filter_min_duration": config.filter_min_duration,
            "channels_count": sub_count[0][0] if sub_count else 0,
            "videos_count": video_count[0][0] if video_count else 0,
            "last_poll": self._last_poll.isoformat() if self._last_poll else None,
        }

    async def get_latest_videos_per_channel(self) -> list[dict[str, Any]]:
        if self._db is None:
            raise RuntimeError("DB no inicializada")
        rows = await self._db.execute_fetchall(
            """
            SELECT v.video_id, v.channel_id, v.title, v.url, v.published_at, s.channel_name
            FROM youtube_videos v
            JOIN youtube_subscriptions s ON v.channel_id = s.channel_id
            WHERE v.published_at = (
                SELECT MAX(published_at) FROM youtube_videos WHERE channel_id = v.channel_id
            )
            ORDER BY v.published_at DESC
            """
        )
        return [
            {
                "video_id": r[0],
                "channel_id": r[1],
                "title": r[2],
                "url": r[3],
                "published_at": r[4],
                "channel_name": r[5],
            }
            for r in rows
        ]
