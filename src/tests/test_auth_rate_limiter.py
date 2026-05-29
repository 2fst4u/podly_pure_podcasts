"""
Unit tests for the brute-force login throttle (FailureRateLimiter).

This protects the login endpoint, so the warm-up window, exponential backoff,
cap, success reset, and expiry behaviour are all security-relevant.
"""

from datetime import datetime, timedelta

from app.auth.rate_limiter import FailureRateLimiter, FailureState


def test_warm_up_attempts_are_not_blocked() -> None:
    limiter = FailureRateLimiter(warm_up_attempts=3)

    assert limiter.register_failure("ip") == 0  # attempt 1
    assert limiter.register_failure("ip") == 0  # attempt 2
    assert limiter.register_failure("ip") == 0  # attempt 3
    assert limiter.retry_after("ip") is None


def test_backoff_grows_exponentially_after_warm_up() -> None:
    limiter = FailureRateLimiter(warm_up_attempts=3, max_backoff_seconds=1000)

    for _ in range(3):  # exhaust warm-up
        limiter.register_failure("ip")

    assert limiter.register_failure("ip") == 2  # attempt 4 -> 2^1
    assert limiter.register_failure("ip") == 4  # attempt 5 -> 2^2
    assert limiter.register_failure("ip") == 8  # attempt 6 -> 2^3


def test_backoff_is_capped() -> None:
    limiter = FailureRateLimiter(warm_up_attempts=0, max_backoff_seconds=5)

    backoffs = [limiter.register_failure("ip") for _ in range(6)]
    # 2,4,5,5,5,5 -> never exceeds the cap
    assert max(backoffs) == 5
    assert backoffs[-1] == 5


def test_register_success_clears_state() -> None:
    limiter = FailureRateLimiter(warm_up_attempts=0)
    limiter.register_failure("ip")
    limiter.register_failure("ip")
    assert limiter.retry_after("ip") is not None

    limiter.register_success("ip")
    assert limiter.retry_after("ip") is None


def test_retry_after_reports_remaining_then_expires() -> None:
    storage: dict[str, FailureState] = {}
    limiter = FailureRateLimiter(storage=storage, warm_up_attempts=0)

    limiter.register_failure("ip")
    remaining = limiter.retry_after("ip")
    assert remaining is not None and remaining > 0

    # Simulate the block window having elapsed.
    storage["ip"].blocked_until = datetime.utcnow() - timedelta(seconds=1)
    assert limiter.retry_after("ip") is None
    # Expired entries are cleaned up.
    assert "ip" not in storage


def test_unknown_key_has_no_retry_after() -> None:
    limiter = FailureRateLimiter()
    assert limiter.retry_after("never-seen") is None


def test_stale_entries_are_pruned() -> None:
    storage: dict[str, FailureState] = {}
    limiter = FailureRateLimiter(storage=storage)

    storage["old"] = FailureState(
        attempts=1,
        blocked_until=None,
        last_attempt=datetime.utcnow() - timedelta(hours=2),
    )
    # Registering any failure triggers pruning of entries older than 1 hour.
    limiter.register_failure("fresh")

    assert "old" not in storage
    assert "fresh" in storage


def test_failures_are_tracked_per_key() -> None:
    limiter = FailureRateLimiter(warm_up_attempts=0)
    limiter.register_failure("a")
    assert limiter.retry_after("a") is not None
    assert limiter.retry_after("b") is None
