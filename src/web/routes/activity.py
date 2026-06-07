"""Activity feed — recent bot events shown in dashboard notifications dropdown."""

from __future__ import annotations

import collections
import itertools
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Request

router = APIRouter()

_MAX_EVENTS = 80

# Categories used by the frontend to pick icon + color
ALLOWED_KINDS = {
    "welcome",
    "blackboard",
    "youtube",
    "config",
    "scrape",
    "system",
    "music",
    "code_runner",
    "openrouter",
    "ai_chat",
    "videos",
}


class ActivityLog:
    """In-memory ring buffer of recent bot events."""

    def __init__(self, maxlen: int = _MAX_EVENTS) -> None:
        self._events: collections.deque[dict[str, Any]] = collections.deque(maxlen=maxlen)
        self._counter = itertools.count(1)

    def push(
        self,
        kind: str,
        title: str,
        detail: str = "",
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        entry = {
            "id": next(self._counter),
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "kind": kind if kind in ALLOWED_KINDS else "system",
            "title": title,
            "detail": detail,
            "meta": meta or {},
        }
        self._events.appendleft(entry)
        return entry

    def list(self, limit: int = 30) -> list[dict[str, Any]]:
        return list(itertools.islice(self._events, max(1, min(limit, _MAX_EVENTS))))

    def clear(self) -> None:
        self._events.clear()


_GLOBAL_LOG: ActivityLog | None = None


def get_log(app=None) -> ActivityLog:
    """Get or create the singleton activity log.

    If `app` is provided, also attach to `app.state.activity_log` for backward
    compatibility. The module-level singleton is what plugins use directly so
    they don't need an app reference.
    """
    global _GLOBAL_LOG
    if _GLOBAL_LOG is None:
        _GLOBAL_LOG = ActivityLog()
    if app is not None:
        app.state.activity_log = _GLOBAL_LOG
    return _GLOBAL_LOG


def push_event(
    kind: str,
    title: str,
    detail: str = "",
    meta: dict[str, Any] | None = None,
) -> None:
    """Convenience for plugins — push to global log."""
    try:
        get_log().push(kind=kind, title=title, detail=detail, meta=meta)
    except Exception:
        pass


@router.get("/activity")
async def list_activity(request: Request, limit: int = 30) -> dict[str, Any]:
    log = get_log(request.app)
    items = log.list(limit=limit)
    return {"items": items, "count": len(items)}
