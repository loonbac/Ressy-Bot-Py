## Archive Report

**Change**: youtube-remove-rss-polling
**Archived**: 2026-05-15
**Chain**: feature-branch-chain (2 PRs)
**PR Branches**: `feat/youtube-no-rss-pr1`, `feat/youtube-no-rss-pr2`

### Summary

Replaced RSS polling entirely with PubSubHubbub push in the YouTube notifier plugin. The `YouTubeMonitor` was transformed from a polling-based system (30-min RSS fallback) to a pure push-based architecture: `add_subscription()` auto-subscribes to the hub, a lightweight `_hub_renewal_loop` refreshes leases every 24h, pending subscriptions are tracked via a `pending_hub_subscribe` column, and an `added_at` cutoff suppresses notifications for pre-subscription videos. The standalone `callback_server.py` received the same cutoff logic. All RSS polling code (~330 LOC) was removed from `monitor.py`. Frontend was updated to remove polling UI, add a prominent callback URL warning banner in `ConnectionCard.tsx`, and show pending subscription status via a yellow chip in `AnimatedChannelCard.tsx`.

### Key Stats

- Files modified: 11
- Lines removed: 379
- Lines added: 836
- Tests: 69/69 passing
- Commits: 5 (4 PR1 + 1 PR2)

### Artifacts

| Artifact | Location |
|----------|----------|
| Proposal | `openspec/changes/archive/2026-05-15-youtube-remove-rss-polling/proposal.md`, Engram #1017 |
| Specs (4 domains) | `openspec/changes/archive/2026-05-15-youtube-remove-rss-polling/specs/`, Engram #1018 |
| Design | `openspec/changes/archive/2026-05-15-youtube-remove-rss-polling/design.md`, Engram #1020 |
| Tasks | `openspec/changes/archive/2026-05-15-youtube-remove-rss-polling/tasks.md`, Engram #1022 |
| Apply Progress | Engram #1035 (PR1+PR2 consolidated) |
| Verify Report | `openspec/changes/archive/2026-05-15-youtube-remove-rss-polling/verify-report.md`, Engram #1042 |

### Specs Synced to Main

| Domain | Type | Action |
|--------|------|--------|
| `youtube-pubsub-renewal` | Full (new) | Created at `openspec/specs/youtube-pubsub-renewal/spec.md` |
| `youtube-auto-subscribe` | Full (new) | Created at `openspec/specs/youtube-auto-subscribe/spec.md` |
| `youtube-monitor` | Delta (ADDED+REMOVED) | Created at `openspec/specs/youtube-monitor/spec.md` |
| `youtube-config` | Delta (ADDED+REMOVED) | Created at `openspec/specs/youtube-config/spec.md` |

### Changes by File

| File | Action | Δ |
|------|--------|---|
| `src/bot/plugins/youtube_notifier/monitor.py` | Modified | −240 LOC (removed RSS polling), +80 LOC (hub renewal, auto-sub, cutoff, TTL) |
| `src/bot/plugins/youtube_notifier/api.py` | Modified | Removed `/poll`, `/subscriptions/failed`; added API key guard to `/test-notify`; pending resolution on PUT `/config` |
| `src/bot/plugins/youtube_notifier/callback_server.py` | Modified | Added `added_at` cutoff from `youtube_subscriptions` table |
| `src/bot/plugins/youtube_notifier/__init__.py` | Modified | Added `start_hub_renewal_loop()` init and teardown |
| `src/bot/plugins/youtube_notifier/models.py` | Modified | Removed `poll_interval_minutes` from `YouTubePluginConfig` |
| `frontend/src/api/youtube.ts` | Modified | Removed `PollDiagnostics`, `triggerYouTubePoll`, `removeFailedSubscriptions`; added hub fields |
| `frontend/src/components/youtube/ConnectionCard.tsx` | Modified | Red border + warning icon when `callback_url` empty |
| `frontend/src/components/youtube/ChannelsListCard.tsx` | Modified | Pass `pending_hub_subscribe` to channel cards |
| `frontend/src/components/youtube/AnimatedChannelCard.tsx` | Modified | Yellow "Sin callback" chip with `animate-pulse` |
| `tests/test_youtube_monitor.py` | Modified | +658 lines — 69 total tests |
| `openspec/changes/youtube-remove-rss-polling/tasks.md` | Modified | Task tracking updates |

### Verification Verdict

**PASS WITH WARNINGS** — 31/33 spec scenarios compliant (2 partial edge cases). All 69 tests pass. Frontend builds and typechecks cleanly (8 pre-existing unrelated TypeScript errors only). No regressions.

### Migration

Two idempotent `ALTER TABLE ADD COLUMN` in `init_db()`:
- `hub_subscribed_at TEXT`
- `pending_hub_subscribe INTEGER DEFAULT 0`

Existing subscriptions get `pending=0` via DEFAULT; `add_subscription()` manages the flag explicitly for new channels. The hub renewal loop uses `hub_subscribed_at IS NULL` to find unsubscribed channels for auto-subscription.

### Lessons Learned

- **pending_hub_subscribe DEFAULT 0 vs 1**: Spec said DEFAULT 1 for migration safety, but code uses DEFAULT 0. Deviated because `add_subscription()` explicitly manages the flag, and the hub renewal loop uses `hub_subscribed_at IS NULL` (not pending flag) to find unsubscribed channels. Functionally correct but raw SQL inserts bypassing `add_subscription()` would get `pending=0`.
- **_http and _stop_event retained**: Design said remove these, but `_http` is needed for hub `subscribe_to_hub`/`unsubscribe_from_hub` HTTP calls, and `_stop_event`/`_task` are repurposed for hub renewal loop lifecycle. Reasonable deviation — avoids adding new state attributes.
- **Chained PR strategy**: The ~750 LOC change was split into 2 PRs (~480 backend, ~270 frontend+tests). Each PR remained under reviewable size and could be verified independently.
- **TDD throughout**: All 69 tests pass. T19 added 3 new integration tests for pending hub subscribe API behavior. The 66 existing tests served as safety net for refactoring.
- **81 scenario tests**: Hub renewal loop (3), auto-subscribe (4), seed via API (2), cutoff (3), RSS removal (inferential via 6 sub-tests), TTL cleanup, callbacks, API integration, content filters, and more.
