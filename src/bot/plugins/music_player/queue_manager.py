from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Track:
    url: str
    title: str = "Unknown"
    requester_id: str = ""
    requester_name: str = ""
    duration_seconds: int = 0
    thumbnail_url: str = ""


class TrackQueue:
    """FIFO queue per guild."""

    def __init__(self):
        self._queue: list[Track] = []
        self._current: Optional[Track] = None
        self._loop: bool = False

    @property
    def is_empty(self) -> bool:
        return len(self._queue) == 0

    @property
    def length(self) -> int:
        return len(self._queue)

    @property
    def current(self) -> Optional[Track]:
        return self._current

    @property
    def total_duration(self) -> int:
        return sum(t.duration_seconds for t in self._queue)

    @property
    def upcoming(self) -> list[Track]:
        return self._queue.copy()

    @property
    def loop(self) -> bool:
        return self._loop

    @loop.setter
    def loop(self, value: bool) -> None:
        self._loop = value

    def add(self, track: Track) -> None:
        self._queue.append(track)

    def pop(self) -> Optional[Track]:
        if self.is_empty:
            return None
        return self._queue.pop(0)

    def remove(self, index: int) -> bool:
        if index < 0 or index >= len(self._queue):
            return False
        self._queue.pop(index)
        return True

    def clear(self) -> None:
        self._queue.clear()

    def set_current(self, track: Optional[Track]) -> None:
        self._current = track
