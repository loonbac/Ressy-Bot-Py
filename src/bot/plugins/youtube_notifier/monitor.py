import asyncio
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

        rows = await self._db.execute_fetchall(
            "SELECT channel_id, channel_name, notifications_enabled FROM youtube_subscriptions WHERE active = 1"
        )

        new_videos: list[YouTubeVideo] = []
        for row in rows:
            channel_id = row[0]
            channel_name = row[1]
            notifications_enabled = bool(row[2])
            try:
                videos = await self.fetch_recent_videos(channel_id)
                # Success: reset failure counter
                self._consecutive_failures[channel_id] = 0
            except httpx.HTTPStatusError as exc:
                self._consecutive_failures[channel_id] = self._consecutive_failures.get(channel_id, 0) + 1
                fails = self._consecutive_failures[channel_id]
                if fails == 1:
                    print(f"[YouTubeMonitor] RSS no disponible para {channel_id} (HTTP {exc.response.status_code})")
                elif fails >= 3:
                    await self._db.execute(
                        "UPDATE youtube_subscriptions SET active = 0 WHERE channel_id = ?",
                        (channel_id,),
                    )
                    await self._db.commit()
                    print(f"[YouTubeMonitor] Canal {channel_id} desactivado tras {fails} fallos consecutivos")
                continue
            except Exception as exc:
                print(f"[YouTubeMonitor] Error inesperado para {channel_id}: {exc}")
                continue

            for video in videos:
                exists = await self._db.execute_fetchall(
                    "SELECT 1 FROM youtube_videos WHERE video_id = ?", (video.video_id,)
                )
                if not exists:
                    await self._store_video(video)
                    new_videos.append(video)
                    if notifications_enabled:
                        await self.notify_new_video(video, channel_name)

            await self._db.execute(
                "UPDATE youtube_subscriptions SET last_checked = ? WHERE channel_id = ?",
                (datetime.now(timezone.utc).isoformat(), channel_id),
            )
            await self._db.commit()

        return new_videos

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
            "order": "date",
            "maxResults": 10,
            "key": api_key,
        }

        try:
            response = await self._http.get(url, params=params, follow_redirects=True)
            if response.status_code == 403:
                print(f"[YouTubeMonitor] API key inválida o cuota excedida para {channel_id}")
                return []
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 404:  # silent on 404 (RSS fallback already failed)
                print(f"[YouTubeMonitor] Error API al obtener videos de {channel_id}: HTTP {exc.response.status_code}")
            return []
        except Exception:
            return []

        videos = []
        for item in data.get("items", []):
            if item["id"]["kind"] != "youtube#video":
                continue  # skip playlists, channels

            video_id = item["id"]["videoId"]
            published_at = item["snippet"]["publishedAt"]

            videos.append(YouTubeVideo(
                video_id=video_id,
                channel_id=channel_id,
                title=item["snippet"]["title"],
                url=f"https://www.youtube.com/watch?v={video_id}",
                published_at=datetime.fromisoformat(published_at.replace("Z", "+00:00")),
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
            title = title_elem.text or ""
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

    async def notify_new_video(self, video: YouTubeVideo, channel_name: str = "") -> None:
        config = await self.get_config()
        channel_id = config.discord_channel_id
        if channel_id is None or self.bot is None:
            return

        # Apply content filters
        if config.filter_shorts and self._is_short(video):
            return
        if config.filter_premieres and self._is_premiere(video):
            return
        # filter_min_duration: RSS doesn't provide duration; skip for now

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

        description = f"Nuevo video de {channel_name}" if channel_name else "Nuevo video"
        embed = discord.Embed(
            title=video.title,
            url=video.url,
            description=description,
            color=discord.Color.red(),
        )
        if channel_name:
            embed.set_author(
                name=channel_name,
                url=f"https://youtube.com/channel/{video.channel_id}",
            )
        embed.set_footer(text="YouTube Notifier")

        try:
            if message and not message.startswith("@everyone"):
                await discord_channel.send(message, embed=embed)
            elif message:
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

        data = {
            "hub.callback": f"{callback_url}/api/plugins/youtube/callback",
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

        data = {
            "hub.callback": f"{callback_url}/api/plugins/youtube/callback",
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

            video = YouTubeVideo(
                video_id=vid,
                channel_id=cid,
                title=title_elem.text if title_elem is not None else "Unknown",
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
            "discord_channel_id": config.discord_channel_id,
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
