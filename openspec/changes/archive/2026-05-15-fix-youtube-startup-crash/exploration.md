# Exploration: fix-youtube-startup-crash

## Current State

### The Crash

`src/__main__.py` line 62 calls `await monitor.start()` but `YouTubeMonitor` no longer has a `start()` method. This causes an `AttributeError` at bot startup.

### Root Cause Chain

1. **Commit `f1e87ff`** (T1-T4): Removed RSS polling infrastructure from `YouTubeMonitor`. The old `_polling_loop` + `start()`/`stop()` pair was replaced by `start_hub_renewal_loop()`/`stop()`. The `start()` method was deleted.

2. **Commit `0d2939e`** (T10-T12): The `setup()` function in `youtube_notifier/__init__.py` was updated to call `start_hub_renewal_loop()` internally after `init_db()`. This means the monitor loop is started inside `setup()` — not by the caller.

3. **`__main__.py` was never updated**. It still has the old contract:
   ```python
   monitor = await setup_youtube(bot, cm, app)
   await monitor.start()  # ← stale call, start() no longer exists
   ```

4. Result: `AttributeError: 'YouTubeMonitor' object has no attribute 'start'` — crashes the bot before any plugin loads fully.

### Secondary Fallouts

**`aiosqlite` event-loop-closed traceback**: The `_run_teardowns()` in `__main__.py` calls `monitor.close_db()` via the teardown callback registered in `setup()`. However, if the `await monitor.start()` line raises `AttributeError`, the exception propagates up and the `finally` block in `main_async` runs `_run_teardowns` while the asyncio event loop is still alive but the `monitor._http` (httpx client) and `monitor._db` (aiosqlite connection) may already be in a partial state. The aiosqlite "event-loop-closed" error is a *consequence* of the primary crash — it's triggered because the teardown path runs while the monitor object is in an incompletely-initialized state (the `close_db()` coroutine is called on a monitor whose background task may have been cancelled mid-flight). It is **not a separate bug** — it is secondary fallout.

## Affected Areas

- `src/__main__.py` — line 62 calls stale `monitor.start()`; also lines 59–62 need review for correct plugin initialization order
- `src/bot/plugins/youtube_notifier/__init__.py` — correctly calls `start_hub_renewal_loop()` internally; teardown callback registered correctly
- `src/bot/plugins/youtube_notifier/monitor.py` — `YouTubeMonitor.start()` was removed; `start_hub_renewal_loop()` is the replacement

## Approaches

### 1. Remove the stale `monitor.start()` call (Minimal Fix) — **Recommended**
Simply delete `await monitor.start()` from `__main__.py`. The monitor loop is already started inside `setup()`. This is a one-line fix that matches the current architecture.

- Pros: Minimal diff, no behavior change, aligns with plugin pattern
- Cons: None — this is correct
- Effort: Low

### 2. Update `monitor.start()` to call `start_hub_renewal_loop()`
Restore the `start()` method as a delegation wrapper: `async def start(self): await self.start_hub_renewal_loop()`. This keeps the old API contract alive for any other callers.

- Pros: Backward-compatible API, safer if other callers exist
- Cons: Hides the rename refactor; if tests mock `.start()` they may still pass incorrectly; adds a layer of indirection
- Effort: Low-Medium

### 3. Move startup orchestration fully into `setup()` (Clean Refactor)
Confirm all callers (only `__main__.py`) remove the external `start()` call. Treat `start_hub_renewal_loop()` as an implementation detail of `setup()`.

- Pros: Clean abstraction, `setup()` fully owns lifecycle
- Cons: Requires verifying no other call sites exist
- Effort: Medium

## Recommendation

**Approach 1 (Remove stale call)** is the minimal safe fix. Given the clear git history showing `start()` was renamed to `start_hub_renewal_loop()` in `f1e87ff` and `setup()` was updated to call it internally in `0d2939e`, the orphaned `await monitor.start()` in `__main__.py` is unambiguously a missed edit. No other call sites for `monitor.start()` exist in the codebase.

The `aiosqlite event-loop-closed` traceback is secondary fallout and requires no independent fix. Once the `AttributeError` is eliminated, the startup sequence completes normally and teardown runs on a properly initialized monitor.

## Risks

- If there are other call sites to `YouTubeMonitor.start()` not visible in the current branch, removing the call silently breaks them. (Search confirms no other call sites exist.)
- Any tests that directly call `YouTubeMonitor.start()` will break — they should be updated to use `start_hub_renewal_loop()` directly or rely on `setup()`.
- The aiosqlite error could theoretically occur on a *clean* shutdown if `close_db()` races with the event loop closing. Worth monitoring post-fix.

## Ready for Proposal

**Yes**. Root cause is confirmed: stale entrypoint contract. Fix is a one-liner. No independent spec needed — this is a bugfix whose scope is fully bounded by the affected files.

---

## Additional Notes

### Discord IDs
Not applicable to this change (YouTube plugin uses channel IDs internally, not Discord snowflakes in the affected code path).

### Testing
- Unit test `YouTubeMonitor` directly should be updated to call `start_hub_renewal_loop()` instead of `start()` if it tests the polling loop startup.
- A regression test verifying bot startup does NOT call `monitor.start()` could be added, but the grep confirming no call sites makes it low priority.

### Related Historical Bugs
This is the same pattern as the "WelcomeCog duplicado" and other missed-update bugs — when a method is renamed/refactored in the monitor, the entrypoint caller (`__main__.py`) was not updated in the same commit. Consider a convention: method renames in monitor classes require a companion `__main__.py` update in the same commit or an explicit task to track it.