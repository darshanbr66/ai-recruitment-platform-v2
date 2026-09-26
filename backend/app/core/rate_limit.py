"""A small in-process sliding-window rate limiter.

The project had no rate-limiting infrastructure, and adding Redis solely for
this would be a new dependency (CLAUDE.md § 5: none without a stated reason).
State is per process, so on a multi-instance deployment each instance enforces
its own budget — acceptable for the public assistant's cost/abuse control, and
the reason a global cap sits beside the per-client one. Move to Redis (already
planned for Arq, CLAUDE.md § 3) if a shared budget is ever needed.
"""

import time
from collections import deque

from starlette.requests import Request

# Bounds memory: keys tracked at once. Beyond this, idle keys are swept first;
# if still full, the oldest-idle key is evicted (its holder just gets a fresh
# window — failing open for one client beats unbounded growth).
_MAX_KEYS = 10_000


class SlidingWindowRateLimiter:
    def __init__(self, *, limit: int, window_seconds: float = 60.0) -> None:
        self.limit = limit
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = {}

    def allow(self, key: str, *, now: float | None = None) -> bool:
        """Records a hit and returns True if `key` is within its budget;
        returns False (recording nothing) once the window is full."""
        now = time.monotonic() if now is None else now
        cutoff = now - self.window

        hits = self._hits.get(key)
        if hits is None:
            if len(self._hits) >= _MAX_KEYS:
                self._sweep(cutoff)
            hits = self._hits.setdefault(key, deque())
        while hits and hits[0] <= cutoff:
            hits.popleft()

        if len(hits) >= self.limit:
            return False
        hits.append(now)
        return True

    def reset(self) -> None:
        self._hits.clear()

    def _sweep(self, cutoff: float) -> None:
        for key in [k for k, hits in self._hits.items() if not hits or hits[-1] <= cutoff]:
            del self._hits[key]
        if len(self._hits) >= _MAX_KEYS:
            oldest = min(self._hits, key=lambda k: self._hits[k][-1])
            del self._hits[oldest]


def client_key(request: Request) -> str:
    """Behind Render's proxy `request.client` is the proxy, so the caller's
    address is the first `X-Forwarded-For` entry. That header is
    client-controlled at its left end, so a per-client budget alone can be
    dodged by rotating it — every caller pairs it with a harder limit
    (a global budget, or the database-backed per-email limits)."""
    forwarded = request.headers.get("x-forwarded-for", "")
    first = forwarded.split(",")[0].strip()
    if first:
        return first
    return request.client.host if request.client else "unknown"
