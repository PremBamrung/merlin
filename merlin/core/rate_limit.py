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
    """

    def __init__(self, min_interval: float, name: str = "rate-limiter"):
        self.min_interval = max(0.0, float(min_interval))
        self.name = name
        self._lock = threading.Lock()
        self._last_call: float = 0.0

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
