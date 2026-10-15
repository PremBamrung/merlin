"""Unit tests for MinIntervalRateLimiter: slot spacing, the cooldown circuit
breaker not queuing behind sleeping waiters, and cooldown persistence."""

import threading
import time

from merlin.core.rate_limit import MinIntervalRateLimiter


def test_wait_spaces_calls_across_threads():
    limiter = MinIntervalRateLimiter(0.1)
    stamps = []

    def call():
        limiter.wait()
        stamps.append(time.monotonic())

    threads = [threading.Thread(target=call) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    stamps.sort()
    gaps = [b - a for a, b in zip(stamps, stamps[1:], strict=False)]
    assert all(g >= 0.09 for g in gaps), gaps


def test_trip_cooldown_does_not_wait_behind_a_sleeping_waiter():
    # Two waiters are queued (the second sleeps ~0.5s for its slot). A trip from
    # a third thread must take effect at once, not after those sleeps — before
    # the fix, wait() slept while holding the lock and the trip was delayed.
    limiter = MinIntervalRateLimiter(0.5, cooldown_seconds=60)
    limiter.wait()  # occupy the current slot
    waiter = threading.Thread(target=limiter.wait)
    waiter.start()
    time.sleep(0.05)  # let it reserve its slot and start sleeping

    start = time.monotonic()
    limiter.trip_cooldown()
    elapsed = time.monotonic() - start
    waiter.join()

    assert elapsed < 0.1
    assert limiter.in_cooldown()


def test_cooldown_escalates_and_clears():
    limiter = MinIntervalRateLimiter(0, cooldown_seconds=0.05, cooldown_max=0.15)
    assert limiter.trip_cooldown() == 0.05
    assert limiter.in_cooldown()
    time.sleep(0.06)
    assert limiter.trip_cooldown() == 0.1  # blocked again after recovering
    limiter.clear_cooldown()
    assert not limiter.in_cooldown()
    assert limiter.trip_cooldown() == 0.05  # escalation reset


def _store():
    box = {"state": None, "saves": 0}

    def load():
        return box["state"]

    def save(state):
        box["state"] = dict(state)
        box["saves"] += 1

    return box, load, save


def test_cooldown_survives_a_new_limiter_instance():
    box, load, save = _store()
    first = MinIntervalRateLimiter(
        0, cooldown_seconds=60, cooldown_max=240, load_state=load, save_state=save
    )
    first.trip_cooldown()
    assert box["state"]["tripped"] is True
    assert box["state"]["until"] > time.time() + 55

    # "Restart": a fresh limiter restores the active cooldown + escalation level.
    second = MinIntervalRateLimiter(
        0, cooldown_seconds=60, cooldown_max=240, load_state=load, save_state=save
    )
    assert second.in_cooldown()
    assert 55 < second.cooldown_remaining() <= 60


def test_restored_escalation_doubles_on_next_block():
    box, load, save = _store()
    # Persisted: a 120s cooldown that already expired, never cleared.
    box["state"] = {"until": time.time() - 1, "current": 120.0, "tripped": True}
    limiter = MinIntervalRateLimiter(
        0, cooldown_seconds=60, cooldown_max=480, load_state=load, save_state=save
    )
    assert not limiter.in_cooldown()
    assert limiter.trip_cooldown() == 240.0


def test_clear_only_saves_when_state_changes():
    box, load, save = _store()
    limiter = MinIntervalRateLimiter(
        0, cooldown_seconds=60, load_state=load, save_state=save
    )
    limiter.clear_cooldown()  # nothing to clear — no write per successful fetch
    assert box["saves"] == 0
    limiter.trip_cooldown()
    limiter.clear_cooldown()
    assert box["saves"] == 2
    assert box["state"] == {"until": 0.0, "current": 60.0, "tripped": False}


def test_load_is_lazy_and_persistence_errors_are_ignored():
    calls = []

    def load():
        calls.append("load")
        raise RuntimeError("no such table: app_state")

    def save(state):
        raise RuntimeError("database is locked")

    limiter = MinIntervalRateLimiter(
        0, cooldown_seconds=60, load_state=load, save_state=save
    )
    assert calls == []  # never at construction (import time)
    assert not limiter.in_cooldown()
    assert limiter.trip_cooldown() == 60
    assert limiter.in_cooldown()
    limiter.in_cooldown()
    assert calls == ["load"]  # loaded once
