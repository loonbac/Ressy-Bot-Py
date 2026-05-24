import asyncio
import os
import tempfile
from typing import Optional

import discord
import yt_dlp
from discord.ext import commands

from src.bot.plugins.music_player.models import TrackInfo
from src.bot.plugins.music_player.queue_manager import Track, TrackQueue


YTDL_OPTIONS = {
    "format": "bestaudio/best",
    "quiet": True,
    "no_warnings": True,
    "extract_flat": False,
    # A watch URL can carry a playlist param (e.g. ?list=RD… radio mixes).
    # Without this, yt-dlp resolves the ENTIRE playlist — radio lists are
    # effectively endless, so extraction hangs forever and /play never
    # answers. noplaylist forces resolving just the single video.
    "noplaylist": True,
    # Fail fast instead of hanging if YouTube stalls the connection.
    "socket_timeout": 20,
}

# Cache of the resolved cookies file path. Written once from the env secret
# and reused for the lifetime of the process. Never logged or exposed via API.
_COOKIE_FILE_CACHE: Optional[str] = None


def _default_cookie_paths() -> list[str]:
    """Conventional on-disk locations for a cookies file, in priority order.

    The data directory (derived from ``DATABASE_PATH``, default ``data/``) is a
    persistent volume in production, so dropping ``yt_cookies.txt`` there keeps
    the cookies across deploys without passing them as an environment variable.
    """
    data_dir = os.path.dirname(os.getenv("DATABASE_PATH", "data/bot.db")) or "."
    return [
        os.path.join(data_dir, "yt_cookies.txt"),
        os.path.join(data_dir, "plugins", "yt_cookies.txt"),
    ]


def _resolve_cookiefile() -> Optional[str]:
    """Return a Netscape cookies.txt path for yt-dlp, or None if unconfigured.

    Resolution order:
    1. ``YTDLP_COOKIES_FILE`` — path to an existing cookies file on disk.
    2. A ``yt_cookies.txt`` in the persistent data volume (see
       :func:`_default_cookie_paths`). Preferred in production: large cookie
       files cannot be passed as an env var (the value blows past ``ARG_MAX``).
    3. ``YTDLP_COOKIES`` — raw cookies.txt content, for tiny cookie sets only.
       Written once to a private temp file (mode 0600) and cached. Single-line
       secrets with literal ``\n`` sequences are normalized to real newlines.

    Cookies bypass YouTube's "Sign in to confirm you're not a bot" gate. The
    secret stays server-side; it is never returned by any API route.
    """
    global _COOKIE_FILE_CACHE

    path = os.getenv("YTDLP_COOKIES_FILE", "").strip()
    if path and os.path.isfile(path):
        return path

    for candidate in _default_cookie_paths():
        if os.path.isfile(candidate):
            return candidate

    raw = os.getenv("YTDLP_COOKIES", "")
    if not raw.strip():
        return None

    if _COOKIE_FILE_CACHE and os.path.isfile(_COOKIE_FILE_CACHE):
        return _COOKIE_FILE_CACHE

    content = raw.replace("\\n", "\n")
    if not content.endswith("\n"):
        content += "\n"
    if not content.lstrip().startswith("# Netscape"):
        content = "# Netscape HTTP Cookie File\n" + content

    fd, tmp_path = tempfile.mkstemp(prefix="ytdlp_cookies_", suffix=".txt")
    try:
        os.write(fd, content.encode("utf-8"))
    finally:
        os.close(fd)
    os.chmod(tmp_path, 0o600)
    _COOKIE_FILE_CACHE = tmp_path
    return tmp_path


def _build_ytdl_options() -> dict:
    """Build yt-dlp options, attaching the cookies file when configured.

    Resolved per call so the bot picks up a cookies secret without a restart
    once the env var is present.
    """
    opts = dict(YTDL_OPTIONS)
    cookiefile = _resolve_cookiefile()
    if cookiefile:
        opts["cookiefile"] = cookiefile
    return opts

FFMPEG_BEFORE_OPTIONS = (
    "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
)


class GuildPlayer:
    """Manages voice connection and playback for a single guild."""

    def __init__(self, guild_id: int, bot: commands.Bot, volume: int = 50):
        self.guild_id = guild_id
        self.bot = bot
        self.queue = TrackQueue()
        self.voice_client: Optional[discord.VoiceClient] = None
        self._current_track: Optional[TrackInfo] = None
        self._is_playing = False
        self._is_paused = False
        self.volume = max(1, min(200, volume))

    @property
    def is_playing(self) -> bool:
        return self._is_playing

    @is_playing.setter
    def is_playing(self, value: bool) -> None:
        self._is_playing = value

    @property
    def is_paused(self) -> bool:
        return self._is_paused

    @is_paused.setter
    def is_paused(self, value: bool) -> None:
        self._is_paused = value

    @property
    def current_track(self) -> Optional[TrackInfo]:
        return self._current_track

    async def connect(self, channel: discord.VoiceChannel) -> bool:
        """Join a voice channel. Returns True on success."""
        try:
            self.voice_client = await channel.connect()
            return True
        except Exception as exc:
            print(f"Error conectando al canal de voz: {exc}")
            return False

    async def disconnect(self) -> None:
        """Leave the voice channel and cleanup."""
        if self.voice_client is not None:
            try:
                await self.voice_client.disconnect()
            except Exception:
                pass
            try:
                self.voice_client.cleanup()
            except Exception:
                pass
            self.voice_client = None
        self._is_playing = False
        self._is_paused = False

    def _extract_info_sync(self, url: str) -> dict:
        with yt_dlp.YoutubeDL(_build_ytdl_options()) as ydl:
            return ydl.extract_info(url, download=False)

    async def extract(self, url: str) -> tuple[TrackInfo, str]:
        """Resolve track metadata and a playable stream URL.

        Does NOT touch the voice client or start playback. The caller
        decides whether to enqueue the track or stream it immediately.
        """
        info = await asyncio.to_thread(self._extract_info_sync, url)

        # A search query (ytsearch1:...) or a playlist resolves to a wrapper
        # whose real video lives in entries[]. Unwrap to the first entry so
        # title/url/duration come from the actual track, not the search term.
        entries = info.get("entries")
        if entries:
            info = entries[0]

        track = TrackInfo(
            title=info.get("title", "Unknown"),
            url=info.get("webpage_url") or info.get("original_url") or url,
            requester_id="",
            requester_name="",
            duration_seconds=info.get("duration") or 0,
            thumbnail_url=info.get("thumbnail", ""),
        )

        stream_url = info.get("url") or ""
        if not stream_url and "formats" in info:
            for fmt in info["formats"]:
                if fmt.get("url"):
                    stream_url = fmt["url"]
                    break

        return track, stream_url

    def start_stream(self, stream_url: str, track: TrackInfo) -> None:
        """Start FFmpeg playback for an already-resolved track.

        Assumes nothing is currently playing on the voice client.
        """
        if self.voice_client is None:
            return

        volume_af = f"volume={self.volume / 100:.2f}"
        options = f"-vn -af {volume_af}"

        def after(error):
            coro = self.after_callback(error)
            self.bot.loop.create_task(coro)

        self._current_track = track
        self._is_playing = True
        self._is_paused = False
        self.queue.set_current(Track(
            url=track.url,
            title=track.title,
            requester_id=track.requester_id,
            requester_name=track.requester_name,
            duration_seconds=track.duration_seconds,
            thumbnail_url=track.thumbnail_url,
        ))
        self.voice_client.play(
            discord.FFmpegPCMAudio(
                stream_url,
                before_options=FFMPEG_BEFORE_OPTIONS,
                options=options,
            ),
            after=after,
        )

    async def play_from_queue(self) -> None:
        """Play the next track in the queue."""
        next_track = self.queue.pop()
        if next_track is None:
            self._is_playing = False
            self._current_track = None
            self.queue.set_current(None)
            if self.voice_client is not None:
                await self.disconnect()
            return

        track_info, stream_url = await self.extract(next_track.url)
        # Preserve requester info from queue track
        track_info.requester_id = next_track.requester_id
        track_info.requester_name = next_track.requester_name
        if self.voice_client is not None and stream_url:
            self.start_stream(stream_url, track_info)
        self._current_track = track_info

    async def stop(self) -> None:
        """Stop playback, clear queue, and disconnect."""
        self.queue.clear()
        self.queue.set_current(None)
        if self.voice_client is not None:
            self.voice_client.stop()
        self._is_playing = False
        self._is_paused = False
        self._current_track = None
        await self.disconnect()

    async def after_callback(self, error: Optional[Exception]) -> None:
        """Called when a track finishes. Auto-play next."""
        if error:
            print(f"Error en reproducción: {error}")
        self._is_playing = False
        await self.play_from_queue()


class GuildPlayerManager:
    """Holds one GuildPlayer per guild."""

    def __init__(self):
        self._players: dict[int, GuildPlayer] = {}

    def get(self, guild_id: int) -> Optional[GuildPlayer]:
        return self._players.get(guild_id)

    def get_or_create(self, guild_id: int, bot: commands.Bot) -> GuildPlayer:
        if guild_id not in self._players:
            self._players[guild_id] = GuildPlayer(guild_id, bot)
        return self._players[guild_id]

    def cleanup(self, guild_id: int) -> None:
        player = self._players.pop(guild_id, None)
        if player is not None:
            try:
                import asyncio
                asyncio.create_task(player.stop())
            except RuntimeError:
                pass

    def cleanup_all(self) -> None:
        for player in list(self._players.values()):
            try:
                import asyncio
                asyncio.get_event_loop().create_task(player.stop())
            except RuntimeError:
                pass
        self._players.clear()

    def active_players(self) -> list[tuple[int, GuildPlayer]]:
        return list(self._players.items())
