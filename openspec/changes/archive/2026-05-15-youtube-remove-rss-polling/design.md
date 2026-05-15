# Design: YouTube Remove RSS Polling

## Technical Approach

Replace the RSS polling mechanism entirely with PubSubHubbub push. The `YouTubeMonitor` transforms from a polling-based system to a push-based one: `add_subscription()` auto-subscribes to the hub, a lightweight `_hub_renewal_loop` refreshes leases every 24h, and `process_pubsub_notification` gains an `added_at` cutoff to suppress notifications for pre-subscription videos. The standalone `callback_server.py` receives the same cutoff logic.

## Architecture Decisions

| Decision | Choice | Rejected | Rationale |
|----------|--------|----------|-----------|
| Video discovery | PubSubHubbub push only | Keep RSS as fallback | RSS adds 30-min latency and ~330 LOC with zero benefit over push. Removing it halves monitor complexity. |
| Initial seed | `_seed_via_api` (YouTube Data API) only | RSS feed parse as seed | RSS requires Accept:text/xml headers and XML parsing that shares code with pubsub. API-only seed is cleaner and provides richer metadata. |
| Hub lease renewal | 24h loop, re-subscribe if ≥4 days old | Renew on timer per-channel | PubSubHubbub leases are ~5 days. A single 24h sweep checking `hub_subscribed_at < 4 days` covers all channels with minimal logic. |
| Pending subscriptions | `pending_hub_subscribe` column + resolve on config save | Queue, retry scheduler | A boolean flag + config-time resolution is the simplest correct solution. No background scheduler complexity needed. |
| Old video suppression | `published_at < added_at` → `notified=1` | TTL-based, grace period | Comparing against `added_at` is deterministic and requires no magic numbers. Both callback_server and process_pubsub_notification enforce it. |
| TTL cleanup location | Inside `_hub_renewal_loop` after renewal sweep | Separate scheduled task | Avoids adding another asyncio task. The 24h cadence matches cleanup needs. |
| Default `pending_hub_subscribe` | `DEFAULT 1` for new columns | `DEFAULT 0` | Existing channels migrated via ALTER TABLE get NULL → treated as pending. New channels without callback_url also need pending=1. Default 1 covers both. |

## Data Flow

### Auto-Subscribe on Channel Add

```
POST /subscriptions {channel_id, channel_name, thumbnail_url}
  │
  ├─ add_subscription()
  │   ├─ INSERT INTO youtube_subscriptions (...)
  │   ├─ callback_url configured?
  │   │   ├─ YES → subscribe_to_hub(channel_id, callback_url)
  │   │   │   ├─ SUCCESS (202/204)
  │   │   │   │   ├─ UPDATE hub_subscribed_at = now
  │   │   │   │   └─ google_api_key? → _seed_via_api → INSERT OR IGNORE notified=1
  │   │   │   └─ FAIL → log error (sub exists, hub subscribe pending)
  │   │   └─ NO → pending_hub_subscribe = 1
  │   └─ Return {channel_id, warning?}
  │
  └─ api.py returns response with warning if pending
```

### Hub Renewal Loop (replaces _polling_loop)

```
__init__.py setup()
  └─ monitor.start_hub_renewal_loop()
       └─ asyncio.create_task(_hub_renewal_loop)

_hub_renewal_loop (every 24h):
  │
  ├─ SELECT active subs WHERE hub_subscribed_at IS NULL
  │                       OR < datetime('now', '-4 days')
  ├─ For each: subscribe_to_hub → update hub_subscribed_at on success
  ├─ _ttl_cleanup: DELETE videos > 30 days
  └─ await asyncio.sleep(86400)
```

### PubSub Notification with Cutoff

```
POST /callback (Atom XML body)
  │
  ├─ process_pubsub_notification(body)
  │   ├─ Parse Atom XML → entries
  │   ├─ For each entry:
  │   │   ├─ Skip if video_id already in youtube_videos
  │   │   ├─ Parse published_at
  │   │   ├─ SELECT added_at FROM youtube_subscriptions WHERE channel_id = ?
  │   │   ├─ published_at < added_at?
  │   │   │   ├─ YES → _store_video(video, notified=1)  [silent]
  │   │   │   └─ NO  → _store_video(video, notified=0) + notify_new_video()
  │   │   └─ Continue to next entry
  │   └─ Done
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/bot/plugins/youtube_notifier/monitor.py` | **Modify** | Remove ~330 LOC (polling loop, RSS fetch, diagnostics, failures). Add ~80 LOC: `_hub_renewal_loop`, `_seed_via_api` rename, `_ttl_cleanup` extraction, cutoff logic in `process_pubsub_notification`, auto-subscribe in `add_subscription`, auto-unsubscribe in `remove_subscription`, `subscribe_pending_on_callback_configured`, `start_hub_renewal_loop`. Remove attrs: `_http`, `_poll_interval`, `_last_poll`, `_stop_event`, `_consecutive_failures`. |
| `src/bot/plugins/youtube_notifier/models.py` | **Modify** | Remove `poll_interval_minutes` field from `YouTubePluginConfig`. |
| `src/bot/plugins/youtube_notifier/api.py` | **Modify** | Remove `POST /poll` and `DELETE /subscriptions/failed` endpoints. Add API key guard to `POST /test-notify`. Return `pending_hub_subscribe` + `hub_subscribed_at` in subscription responses. Return `warning` from `POST /subscriptions` when hub subscribe pending. Trigger `subscribe_pending_on_callback_configured` in `PUT /config`. |
| `src/bot/plugins/youtube_notifier/callback_server.py` | **Modify** | Add `added_at` cutoff: read `youtube_subscriptions.added_at`, insert with `notified=1` if `published < added_at`. Ensure `youtube_subscriptions` table is queryable (shared DB file). |
| `src/bot/plugins/youtube_notifier/__init__.py` | **Modify** | Call `monitor.start_hub_renewal_loop()` after init. Update teardown to `stop_hub_renewal_loop()`. |
| `frontend/src/api/youtube.ts` | **Modify** | Remove `PollDiagnostics`, `triggerYouTubePoll`, `removeFailedSubscriptions`. Remove `poll_interval_minutes` from `YouTubeConfig` interface. Add `pending_hub_subscribe`, `hub_subscribed_at` to `YouTubeSubscription`. |
| `frontend/src/components/youtube/ConnectionCard.tsx` | **Modify** | Add prominent visual warning when `callback_url` is empty (required field indicator, info banner). |
| `frontend/src/components/youtube/ChannelsListCard.tsx` | **Modify** | Pass `pending_hub_subscribe` to `AnimatedChannelCard`. |
| `frontend/src/components/youtube/AnimatedChannelCard.tsx` | **Modify** | Show pending hub chip/badge when `pending_hub_subscribe=true`. |

## Interfaces / Contracts

### New columns in `youtube_subscriptions`

```sql
ALTER TABLE youtube_subscriptions ADD COLUMN pending_hub_subscribe INTEGER DEFAULT 1;
ALTER TABLE youtube_subscriptions ADD COLUMN hub_subscribed_at TEXT;
```

### `add_subscription` return type change

```python
async def add_subscription(self, channel_id: str, channel_name: str = "",
                           thumbnail_url: str = "") -> dict[str, Any]:
    """Returns {"success": bool, "warning": str | None}"""
```

### `POST /subscriptions` response change

```json
{
  "channel_id": "UC_xxx",
  "channel_name": "Channel",
  "warning": "callback_url no configurado — suscripción pendiente al hub"
}
```

### `GET /subscriptions` response extension

```json
{
  "subscriptions": [{
    "channel_id": "UC_xxx",
    "pending_hub_subscribe": true,
    "hub_subscribed_at": null,
    ...
  }]
}
```

### `POST /test-notify` error without API key

```json
{"detail": "Google API Key no configurada. Configúrala en Conexión para usar notificaciones de prueba."}
```

### `YouTubePluginConfig` model (models.py)

```python
class YouTubePluginConfig(BaseModel):
    enabled: bool = True
    # poll_interval_minutes removed
    discord_channel_id: int | None = None
    callback_url: str = ""
    google_api_key: str = ""
    announcement_message: str = "@everyone ¡Hay un nuevo video en {canal}!"
    filter_shorts: bool = False
    filter_premieres: bool = False
    filter_min_duration: int = 0
```

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | `_hub_renewal_loop` selects expired subs and re-subscribes | Mock `subscribe_to_hub`, assert SQL WHERE clause and update calls |
| Unit | `add_subscription` auto-subscribes / marks pending | Mock hub + DB, test both callback_url paths |
| Unit | `process_pubsub_notification` cutoff by `added_at` | Insert subscription with known `added_at`, send video before/after |
| Unit | `remove_subscription` calls `unsubscribe_from_hub` | Verify hub POST before `active=0` |
| Unit | `_ttl_cleanup` deletes videos >30 days | Insert old + recent videos, assert only old deleted |
| Unit | `_seed_via_api` inserts with `notified=1` | Mock API response, verify no `notify_new_video` call |
| Unit | `subscribe_pending_on_callback_configured` resolves pending | Insert pending subs, call method, verify flag cleared |
| Integration | API endpoints removed return 404/405 | Test client against router for `/poll` and `/subscriptions/failed` |
| Integration | `PUT /config` with callback_url triggers pending resolution | Full flow with in-memory DB |
| Integration | `POST /test-notify` returns 400 without API key | Test client with empty `google_api_key` |
| Unit | `callback_server.py` cutoff by `added_at` | Mock DB with known `added_at`, parse Atom XML, verify `notified` column |

## Migration / Rollout

Two idempotent `ALTER TABLE` migrations in `init_db()`:

```python
# Migration 1: pending_hub_subscribe
try:
    await self._db.execute(
        "ALTER TABLE youtube_subscriptions ADD COLUMN pending_hub_subscribe INTEGER DEFAULT 1"
    )
    await self._db.commit()
except Exception:
    pass  # column already exists

# Migration 2: hub_subscribed_at
try:
    await self._db.execute(
        "ALTER TABLE youtube_subscriptions ADD COLUMN hub_subscribed_at TEXT"
    )
    await self._db.commit()
except Exception:
    pass  # column already exists
```

Existing active subscriptions get `pending_hub_subscribe=1` (via DEFAULT). When `callback_url` is configured via PUT `/config`, `subscribe_pending_on_callback_configured` resolves them. No data loss, no destructive migration. The `poll_interval_minutes` key remains in `youtube_config` but is ignored — safe to leave.

**Rollback**: Revert the commit. Old code ignores the new columns. No data corruption.

## Open Questions

- [ ] Should `_hub_renewal_loop` also handle `pending_hub_subscribe=1` channels, or only rely on the config-time resolution? (Current design: config-time only, renewal loop handles `hub_subscribed_at` refresh.)
