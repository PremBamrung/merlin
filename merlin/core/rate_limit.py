"""
Process-wide rate limiting helpers.

The background task queue runs several ingest workers concurrently
(ThreadPoolExecutor), so unsynchronised calls to YouTube's transcript
endpoint can fire in bursts and get the host IP temporarily banned
(HTTP 429). MinIntervalRateLimiter serialises those calls and enforces
a minimum spacing between them across all threads.
"""

import threading
import time

from merlin.core.logging import logger


class MinIntervalRateLimiter:
    """Enforce a minimum interval between successive calls across threads.

    Thread-safe: callers block in ``wait()`` until at least ``min_interval``
    seconds have elapsed since the previous call returned from ``wait()``.

    The limiter also exposes a process-wide *cooldown* circuit breaker. When the
    upstream signals a hard rate-limit / IP block, callers trip the cooldown via
    ``trip_cooldown()``; while ``in_cooldown()`` is true they should skip the
    request entirely (rather than keep hammering and prolonging the ban). A
    clean call clears it via ``clear_cooldown()``. Repeated trips with no
    intervening success escalate the cooldown by doubling, up to ``cooldown_max``.
    """

    def __init__(
        self,
        min_interval: float,
        name: str = "rate-limiter",
        cooldown_seconds: float = 0.0,
        cooldown_max: float = 0.0,
    ):
        self.min_interval = max(0.0, float(min_interval))
        self.name = name
        self._cooldown_base = max(0.0, float(cooldown_seconds))
        self._cooldown_max = max(self._cooldown_base, float(cooldown_max))
        self._lock = threading.Lock()
        self._last_call: float = 0.0
        self._cooldown_until: float = 0.0
        self._current_cooldown: float = self._cooldown_base
        self._tripped: bool = False

    def wait(self) -> None:
        """Block until the configured interval since the last call has passed."""
        if self.min_interval <= 0:
            return
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_call
            sleep_for = self.min_interval - elapsed
            if sleep_for > 0:
                logger.debug(
                    f"[{self.name}] throttling for {sleep_for:.2f}s "
                    f"(min interval {self.min_interval:.2f}s)"
                )
                time.sleep(sleep_for)
            self._last_call = time.monotonic()

    def in_cooldown(self) -> bool:
        """True if a rate-limit cooldown is currently active."""
        if self._cooldown_base <= 0:
            return False
        with self._lock:
            return time.monotonic() < self._cooldown_until

    def cooldown_remaining(self) -> float:
        """Seconds left in the active cooldown (0 if none)."""
        if self._cooldown_base <= 0:
            return 0.0
        with self._lock:
            return max(0.0, self._cooldown_until - time.monotonic())

    def trip_cooldown(self) -> float:
        """Enter (or escalate) the cooldown after a rate-limit / IP block.

        A trip that arrives while a cooldown is *still active* is treated as a
        concurrent straggler from the same block event — the existing cooldown is
        left untouched and its remaining seconds are returned. A trip that lands
        *after* the previous cooldown expired (we recovered, retried, got blocked
        again) escalates the duration by doubling, up to ``cooldown_max``.
        Returns the seconds the caller should consider paused; 0 when cooldowns
        are disabled.
        """
        if self._cooldown_base <= 0:
            return 0.0
        with self._lock:
            now = time.monotonic()
            remaining = self._cooldown_until - now
            if remaining > 0:
                # Still cooling down: same burst, don't escalate or shorten.
                return remaining
            if self._tripped:
                self._current_cooldown = min(
                    self._current_cooldown * 2, self._cooldown_max
                )
            else:
                self._current_cooldown = self._cooldown_base
                self._tripped = True
            self._cooldown_until = now + self._current_cooldown
            return self._current_cooldown

    def clear_cooldown(self) -> None:
        """Reset the cooldown and escalation after a successful call."""
        if self._cooldown_base <= 0:
            return
        with self._lock:
            self._cooldown_until = 0.0
            self._current_cooldown = self._cooldown_base
            self._tripped = False
