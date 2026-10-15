"""
Process-wide rate limiting helpers.

The background task queue runs several ingest workers concurrently
(ThreadPoolExecutor), so unsynchronised calls to YouTube's transcript
endpoint can fire in bursts and get the host IP temporarily banned
(HTTP 429). MinIntervalRateLimiter serialises those calls and enforces
a minimum spacing between them across all threads.
"""

from collections.abc import Callable
import threading
import time

from merlin.core.logging import logger


class MinIntervalRateLimiter:
    """Enforce a minimum interval between successive calls across threads.

    Thread-safe: callers block in ``wait()`` until at least ``min_interval``
    seconds have elapsed since the previous caller's slot. Each caller reserves
    its slot under the lock but sleeps *outside* it, so the cooldown methods
    below never queue behind a sleeping waiter.

    The limiter also exposes a process-wide *cooldown* circuit breaker. When the
    upstream signals a hard rate-limit / IP block, callers trip the cooldown via
    ``trip_cooldown()``; while ``in_cooldown()`` is true they should skip the
    request entirely (rather than keep hammering and prolonging the ban). A
    clean call clears it via ``clear_cooldown()``. Repeated trips with no
    intervening success escalate the cooldown by doubling, up to ``cooldown_max``.

    Optional ``load_state`` / ``save_state`` callables persist the cooldown
    across process restarts (a rebuild would otherwise forget an active ban and
    re-probe the blocked upstream). State is ``{"until": <unix time>,
    "current": <seconds>, "tripped": <bool>}``; it is loaded lazily on first
    use (never at construction, which happens at import time) and saved only
    when it changes. Persistence errors are logged and ignored.
    """

    def __init__(
        self,
        min_interval: float,
        name: str = "rate-limiter",
        cooldown_seconds: float = 0.0,
        cooldown_max: float = 0.0,
        load_state: Callable[[], dict | None] | None = None,
        save_state: Callable[[dict], None] | None = None,
    ):
        self.min_interval = max(0.0, float(min_interval))
        self.name = name
        self._cooldown_base = max(0.0, float(cooldown_seconds))
        self._cooldown_max = max(self._cooldown_base, float(cooldown_max))
        self._lock = threading.Lock()
        self._next_slot: float = 0.0
        self._cooldown_until: float = 0.0
        self._current_cooldown: float = self._cooldown_base
        self._tripped: bool = False
        self._load_state = load_state
        self._save_state = save_state
        self._loaded = load_state is None

    def wait(self) -> None:
        """Block until the configured interval since the last call has passed."""
        if self.min_interval <= 0:
            return
        with self._lock:
            now = time.monotonic()
            slot = max(now, self._next_slot)
            self._next_slot = slot + self.min_interval
        sleep_for = slot - now
        if sleep_for > 0:
            logger.debug(
                f"[{self.name}] throttling for {sleep_for:.2f}s "
                f"(min interval {self.min_interval:.2f}s)"
            )
            time.sleep(sleep_for)

    def in_cooldown(self) -> bool:
        """True if a rate-limit cooldown is currently active."""
        if self._cooldown_base <= 0:
            return False
        self._ensure_loaded()
        with self._lock:
            return time.monotonic() < self._cooldown_until

    def cooldown_remaining(self) -> float:
        """Seconds left in the active cooldown (0 if none)."""
        if self._cooldown_base <= 0:
            return 0.0
        self._ensure_loaded()
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
        self._ensure_loaded()
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
            state = self._snapshot(now)
            cooldown = self._current_cooldown
        self._persist(state)
        return cooldown

    def clear_cooldown(self) -> None:
        """Reset the cooldown and escalation after a successful call."""
        if self._cooldown_base <= 0:
            return
        self._ensure_loaded()
        with self._lock:
            changed = self._tripped or self._cooldown_until > 0
            self._cooldown_until = 0.0
            self._current_cooldown = self._cooldown_base
            self._tripped = False
            state = self._snapshot(time.monotonic())
        if changed:
            self._persist(state)

    # --- persistence --------------------------------------------------------- #

    def _snapshot(self, now: float) -> dict:
        """Current cooldown state in wall-clock terms (call under the lock)."""
        remaining = max(0.0, self._cooldown_until - now)
        return {
            "until": time.time() + remaining if remaining else 0.0,
            "current": self._current_cooldown,
            "tripped": self._tripped,
        }

    def _ensure_loaded(self) -> None:
        """Restore persisted state once, outside the lock (it may do I/O)."""
        if self._loaded:
            return
        try:
            state = self._load_state() if self._load_state else None
        except Exception as e:
            logger.warning(f"[{self.name}] could not load cooldown state: {e}")
            state = None
        with self._lock:
            if self._loaded:
                return
            self._loaded = True
            if not state:
                return
            remaining = float(state.get("until") or 0.0) - time.time()
            if remaining > 0:
                self._cooldown_until = time.monotonic() + remaining
            self._current_cooldown = min(
                max(float(state.get("current") or 0.0), self._cooldown_base),
                self._cooldown_max,
            )
            self._tripped = bool(state.get("tripped"))
        if remaining > 0:
            logger.info(
                f"[{self.name}] restored cooldown — {remaining / 60:.1f} min left"
            )

    def _persist(self, state: dict) -> None:
        if not self._save_state:
            return
        try:
            self._save_state(state)
        except Exception as e:
            logger.warning(f"[{self.name}] could not save cooldown state: {e}")
