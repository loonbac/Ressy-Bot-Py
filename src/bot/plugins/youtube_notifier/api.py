import hashlib
import hmac
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse, Response

from src.bot.plugins.youtube_notifier.models import YouTubePluginConfig

router = APIRouter()


def _get_monitor(request: Request):
    monitor = getattr(request.app.state, "youtube_monitor", None)
    if monitor is None:
        raise HTTPException(status_code=500, detail="YouTube plugin no inicializado")
    return monitor


@router.get("/subscriptions")
async def list_subscriptions(request: Request) -> dict[str, Any]:
    monitor = _get_monitor(request)
    subs = await monitor.list_subscriptions()
    for sub in subs:
        videos = await monitor.get_videos(channel_id=sub["channel_id"], limit=1)
        sub["last_video_title"] = videos[0]["title"] if videos else None
        sub["last_video_url"] = videos[0]["url"] if videos else None
        sub["video_count"] = len(await monitor.get_videos(channel_id=sub["channel_id"], limit=9999))
    return {"subscriptions": subs}


@router.post("/subscriptions")
async def add_subscription(request: Request, body: dict[str, Any]) -> dict[str, Any]:
    monitor = _get_monitor(request)
    channel_id = body.get("channel_id")
    channel_name = body.get("channel_name", "")
    thumbnail_url = body.get("thumbnail_url", "")
    if not channel_id:
        raise HTTPException(status_code=400, detail="channel_id es requerido")
    result = await monitor.add_subscription(channel_id, channel_name, thumbnail_url)
    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@router.delete("/subscriptions/{channel_id}")
async def remove_subscription(channel_id: str, request: Request) -> dict[str, str]:
    monitor = _get_monitor(request)
    await monitor.remove_subscription(channel_id)
    return {"detail": f"Canal {channel_id} eliminado"}


@router.get("/videos")
async def list_videos(request: Request, limit: int = 50) -> dict[str, Any]:
    monitor = _get_monitor(request)
    videos = await monitor.get_videos(limit=limit)
    return {"videos": videos}


@router.get("/videos/{channel_id}")
async def list_channel_videos(channel_id: str, request: Request) -> dict[str, Any]:
    monitor = _get_monitor(request)
    videos = await monitor.get_videos(channel_id=channel_id, limit=9999)
    return {"videos": videos}


@router.get("/status")
async def get_status(request: Request) -> dict[str, Any]:
    monitor = _get_monitor(request)
    return await monitor.get_status()


@router.get("/config")
async def get_config(request: Request) -> dict[str, Any]:
    monitor = _get_monitor(request)
    cfg = await monitor.get_config()
    return cfg.model_dump()


@router.put("/config")
async def update_config(request: Request, body: dict[str, Any]) -> dict[str, Any]:
    monitor = _get_monitor(request)
    try:
        cfg = YouTubePluginConfig(**body)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await monitor.update_config(cfg)
    return cfg.model_dump()


@router.put("/subscriptions/{channel_id}/notifications")
async def toggle_notifications(channel_id: str, request: Request, body: dict[str, Any]) -> dict[str, Any]:
    monitor = _get_monitor(request)
    enabled = body.get("enabled", True)
    await monitor.update_subscription_notifications(channel_id, enabled)
    return {"channel_id": channel_id, "notifications_enabled": enabled}


@router.get("/discord-channels")
async def list_discord_channels(request: Request) -> dict[str, Any]:
    bot = getattr(request.app.state, "bot", None)
    if bot is None:
        return {"channels": []}

    cm = getattr(request.app.state, "config_manager", None)
    guild_id_str = cm.get("guild_id") if cm else None
    guild_id = int(guild_id_str) if guild_id_str else None

    channels = []
    for guild in bot.guilds:
        if guild_id is not None and guild.id != guild_id:
            continue
        for channel in guild.text_channels:
            # Snowflake IDs are 64-bit; serialize as string to avoid JS
            # Number.MAX_SAFE_INTEGER precision loss.
            channels.append({
                "id": str(channel.id),
                "name": f"#{channel.name}",
                "guild_name": guild.name,
            })
    return {"channels": channels}


@router.get("/thumbnail")
async def proxy_thumbnail(url: str = "", request: Request = None):
    """Proxy YouTube thumbnails to avoid CORS and rate limiting."""
    if not url:
        raise HTTPException(status_code=400, detail="url parameter required")

    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})

    content_type = resp.headers.get("content-type", "image/jpeg")
    return Response(content=resp.content, media_type=content_type, headers={
        "Cache-Control": "public, max-age=86400",
    })


@router.get("/search")
async def search_channels(request: Request, q: str = ""):
    """Search YouTube channels using the stored Google API key."""
    if not q.strip():
        return {"results": []}

    monitor = _get_monitor(request)
    cfg = await monitor.get_config()

    if not cfg.google_api_key:
        raise HTTPException(status_code=400, detail="Google API Key no configurada. Configúrala en Conexión.")

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={
                "part": "snippet",
                "type": "channel",
                "q": q,
                "key": cfg.google_api_key,
                "maxResults": 5,
            },
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"YouTube API error: {resp.status_code}")

    data = resp.json()
    results = []
    for item in data.get("items", []):
        results.append({
            "channel_id": item["id"]["channelId"],
            "channel_name": item["snippet"]["title"],
            "description": item["snippet"]["description"][:100],
            "thumbnail": item["snippet"]["thumbnails"]["default"]["url"],
        })

    return {"results": results}


@router.get("/callback")
async def handle_verification(request: Request):
    """Handle PubSubHubbub subscription verification (GET with hub.challenge)."""
    challenge = request.query_params.get("hub.challenge")

    if challenge:
        return PlainTextResponse(challenge)

    return PlainTextResponse("OK")


@router.post("/test-notify")
async def test_notify(request: Request, body: dict[str, Any]) -> dict[str, Any]:
    """Send a test notification for the N most recent videos of each subscribed channel.

    Bypasses content filters so the embed can be previewed in Discord
    regardless of shorts/premiere settings. Requires a Google API key.
    """
    monitor = _get_monitor(request)
    cfg = await monitor.get_config()
    if not cfg.google_api_key:
        raise HTTPException(status_code=400, detail="Google API Key no configurada")
    raw_count = body.get("count", 1)
    try:
        count = int(raw_count)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="count debe ser un entero")
    if count < 1 or count > 10:
        raise HTTPException(status_code=400, detail="count debe estar entre 1 y 10")
    return await monitor.test_notify_latest(count)


@router.post("/callback")
async def handle_notification(request: Request):
    """Handle PubSubHubbub notification (POST with Atom XML).

    The callback path is the only endpoint exposed to the public internet.
    Every notification MUST carry a valid X-Hub-Signature (HMAC-SHA1 of the
    raw body, keyed by the per-install hub secret). Per WebSub 11.2 a failed
    verification still returns 2xx but the payload is dropped, so a forged
    POST can never reach process_pubsub_notification (which fans out to
    Discord with @everyone).
    """
    body = await request.body()
    monitor = getattr(request.app.state, "youtube_monitor", None)
    if monitor is None or not body:
        return {"status": "ok"}

    secret = (await monitor.get_config()).callback_secret
    header = request.headers.get("X-Hub-Signature", "")
    expected = "sha1=" + hmac.new(secret.encode(), body, hashlib.sha1).hexdigest()

    if not hmac.compare_digest(expected, header):
        try:
            from src.web.routes.activity import push_event

            push_event(
                kind="youtube",
                title="Notificación de YouTube rechazada",
                detail="Firma X-Hub-Signature inválida o ausente. POST descartado.",
            )
        except Exception:
            pass
        return {"status": "ok"}

    await monitor.process_pubsub_notification(body)
    return {"status": "ok"}
