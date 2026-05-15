# Tasks: YouTube Remove RSS Polling

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~750 (addition + deletion) |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1: Backend (~480) → PR 2: Frontend + Tests (~270) |
| Delivery strategy | ask-on-risk |
| Chain strategy | pending |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: pending
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Notes |
|------|------|-----------|-------|
| 1 | Backend: models + monitor + API + callback + init | PR 1 | ~480 changes, all Python in one plugin dir |
| 2 | Frontend + Tests | PR 2 | ~270 changes, depends on PR 1 API contracts |

## Phase 1: Foundation — DB Migrations + Model Cleanup

- [x] T1: Remove `poll_interval_minutes` from `YouTubePluginConfig` in models.py; remove from `get_config`, `update_config`, `get_status` and defaults dict in monitor.py
- [x] T2: Add idempotent migrations in monitor.py `init_db()` for `pending_hub_subscribe INTEGER DEFAULT 1` and `hub_subscribed_at TEXT`; update `list_subscriptions`/`get_subscription` to include new columns

## Phase 2: Core — Monitor Refactor

- [x] T3: Delete `_polling_loop`, `poll_channels(_with_diagnostics)`, `_fetch_via_rss`, `check_rss`, `fetch_recent_videos`; remove attrs `_http`, `_stop_event`, `_task`, `_poll_interval`, `_last_poll`, `_consecutive_failures`; drop `start()`, simplify `stop()`
- [x] T4: Add `start/stop_hub_renewal_loop()` → `_hub_renewal_loop` (24h sleep, re-subscribe subs with hub_subscribed_at≥4d); extract `_ttl_cleanup()` (DELETE videos >30d)
- [x] T5: Auto-subscribe to hub in `add_subscription()` if callback_url set, else pending=1; auto-unsubscribe in `remove_subscription()`; rename `_fetch_via_api` → `_seed_via_api` (fresh httpx, no Accept:text/xml)
- [x] T6: Cutoff in `process_pubsub_notification` — notified=1 if published_at < added_at; guard `test_notify_latest` with 400 if no google_api_key
- [x] T7: Add `subscribe_pending_on_callback_configured()`; drop poll_interval/last_poll from `get_status`; skip poll_interval in `update_config`

## Phase 3: Integration — API + Callback + Init

- [x] T8: Remove `POST /poll` and `DELETE /subscriptions/failed` from api.py; 400 guard on test-notify without api_key; return hub+warning fields; trigger pending resolution on PUT /config
- [x] T9: Add added_at cutoff to callback_server.py — read `added_at` per channel_id, notified=1 if published < added_at
- [x] T10: Call `start_hub_renewal_loop()` after init in __init__.py; `stop_hub_renewal_loop()` on teardown

## Phase 4: Frontend — Remove Polling UI + Hub Fields

- [x] T11: Remove `PollDiagnostics`, `triggerYouTubePoll`, `removeFailedSubscriptions` from youtube.ts; remove `poll_interval_minutes` from `YouTubeConfig`; add `pending_hub_subscribe`, `hub_subscribed_at` to `YouTubeSubscription`
- [x] T12: Add prominent callback_url warning banner in ConnectionCard.tsx (required indicator, info text when empty)
- [x] T13: Pass `pending_hub_subscribe` via ChannelsListCard.tsx → AnimatedChannelCard.tsx; add yellow warning chip "Sin callback"
- [x] T14: Clean up poll_interval_minutes references from YouTubeConfig.tsx (state type, PUT body, config update)

## Phase 5: Tests

- [x] T15: Remove `TestRSSParsing`, `test_consecutive_failures_sweep`, poll-based `test_new_video_detected`/`test_videos_ttl`; drop poll_interval from config/status tests
- [x] T16: Add tests: hub renewal (expired/fresh/error), auto-subscribe (with/without callback), added_at cutoff (before/after), `_seed_via_api`, pending resolution, removed endpoints 404, test-notify 400, callback_server cutoff
- [x] T17 (PR2): Add API-level tests for pending_hub_subscribe in subscription listing, status excluding poll fields, and callback config resolving pending subscriptions
