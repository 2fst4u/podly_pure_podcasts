"""
Unit tests for the TokenRateLimiter class and the module-level helpers
(get_rate_limiter / configure_rate_limiter_for_model).

This is the canonical home for TokenRateLimiter behavior. AdClassifier's
*integration* with the limiter lives in
test_ad_classifier_rate_limiting_integration.py.
"""

import threading
import time
from typing import Generator
from unittest.mock import patch

import pytest

import podcast_processor.token_rate_limiter as trl_module
from podcast_processor.token_rate_limiter import (
    TokenRateLimiter,
    configure_rate_limiter_for_model,
    get_rate_limiter,
)


@pytest.fixture(autouse=True)
def reset_rate_limiter_singleton() -> Generator[None, None, None]:
    """Reset the module-level singleton so model-config tests don't leak state."""
    trl_module._RATE_LIMITER = None
    yield
    trl_module._RATE_LIMITER = None


class TestTokenRateLimiter:
    """Test cases for the TokenRateLimiter class."""

    def test_initialization(self) -> None:
        limiter = TokenRateLimiter()
        assert limiter.tokens_per_minute == 30000
        assert limiter.window_seconds == 60
        assert len(limiter.token_usage) == 0

        limiter = TokenRateLimiter(tokens_per_minute=15000, window_minutes=2)
        assert limiter.tokens_per_minute == 15000
        assert limiter.window_seconds == 120

    def test_count_tokens_estimates_four_chars_per_token(self) -> None:
        """count_tokens uses a deterministic chars//4 estimate."""
        limiter = TokenRateLimiter()

        assert limiter.count_tokens([], "gpt-4") == 0

        # "Hello world" is 11 chars -> 11 // 4 == 2
        assert (
            limiter.count_tokens([{"role": "user", "content": "Hello world"}], "gpt-4")
            == 2
        )

        # Sum across messages: 28 + 31 == 59 chars -> 14 tokens
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is the weather like today?"},
        ]
        expected = (len(messages[0]["content"]) + len(messages[1]["content"])) // 4
        assert limiter.count_tokens(messages, "gpt-4") == expected

    def test_count_tokens_missing_content_is_zero(self) -> None:
        """A message without a 'content' key contributes 0, not an error."""
        limiter = TokenRateLimiter()
        assert limiter.count_tokens([{"role": "user"}], "gpt-4") == 0

    def test_count_tokens_large_message(self) -> None:
        limiter = TokenRateLimiter()
        large_content = "word " * 10000  # 50000 chars
        tokens = limiter.count_tokens(
            [{"role": "user", "content": large_content}], "gpt-4"
        )
        assert tokens == len(large_content) // 4

    def test_count_tokens_uses_conservative_fallback_on_error(self) -> None:
        """If the estimation raises, count_tokens returns the 1000-token fallback."""
        limiter = TokenRateLimiter()
        # Force the internal sum(...) to raise so the except branch is exercised.
        with patch("builtins.sum", side_effect=RuntimeError("boom")):
            result = limiter.count_tokens([{"role": "user", "content": "hi"}], "gpt-4")
        assert result == 1000

    def test_cleanup_old_usage(self) -> None:
        limiter = TokenRateLimiter(tokens_per_minute=1000, window_minutes=1)
        current_time = time.time()

        limiter.token_usage.append((current_time - 120, 100))  # 2 minutes ago
        limiter.token_usage.append((current_time - 30, 200))
        limiter.token_usage.append((current_time - 10, 300))

        limiter._cleanup_old_usage(current_time)

        assert len(limiter.token_usage) == 2
        assert limiter.token_usage[0][1] == 200
        assert limiter.token_usage[1][1] == 300

    def test_get_current_usage_only_counts_within_window(self) -> None:
        limiter = TokenRateLimiter(tokens_per_minute=1000, window_minutes=1)
        current_time = time.time()

        limiter.token_usage.append((current_time - 120, 100))  # outside window
        limiter.token_usage.append((current_time - 61, 50))  # just outside (>60s)
        limiter.token_usage.append((current_time - 59, 40))  # just inside
        limiter.token_usage.append((current_time - 10, 300))  # inside

        assert limiter._get_current_usage(current_time) == 340

    def test_check_rate_limit_within_limits(self) -> None:
        limiter = TokenRateLimiter(tokens_per_minute=1000)
        can_proceed, wait_seconds = limiter.check_rate_limit(
            [{"role": "user", "content": "Short message"}], "gpt-4"
        )
        assert can_proceed is True
        assert wait_seconds == 0.0

    def test_check_rate_limit_exceeds_limits(self) -> None:
        limiter = TokenRateLimiter(tokens_per_minute=100)
        current_time = time.time()
        limiter.token_usage.append((current_time - 30, 90))

        can_proceed, wait_seconds = limiter.check_rate_limit(
            [
                {
                    "role": "user",
                    "content": "This is a longer message that should exceed the token limit",
                }
            ],
            "gpt-4",
        )
        assert can_proceed is False
        assert wait_seconds > 0

    def test_check_rate_limit_zero_token_request_at_capacity_proceeds(self) -> None:
        """A zero-token request at exactly the limit is allowed through."""
        limiter = TokenRateLimiter(tokens_per_minute=100, window_minutes=1)
        limiter.token_usage.append((time.time() - 30, 100))

        can_proceed, wait_seconds = limiter.check_rate_limit([], "gpt-4")
        assert can_proceed is True
        assert wait_seconds == 0.0

    def test_record_usage(self) -> None:
        limiter = TokenRateLimiter()
        messages = [{"role": "user", "content": "Test message"}]  # 12 chars -> 3 tokens

        limiter.record_usage(messages, "gpt-4")

        assert len(limiter.token_usage) == 1
        timestamp, token_count = limiter.token_usage[-1]
        assert timestamp > 0
        assert token_count == len("Test message") // 4

    def test_wait_if_needed_no_wait_records_usage(self) -> None:
        limiter = TokenRateLimiter(tokens_per_minute=10000)
        with patch("time.sleep") as mock_sleep:
            limiter.wait_if_needed(
                [{"role": "user", "content": "Short message"}], "gpt-4"
            )
            mock_sleep.assert_not_called()
        assert len(limiter.token_usage) == 1

    def test_wait_if_needed_sleeps_then_records(self) -> None:
        """When over the limit, wait_if_needed sleeps AND still records the new usage."""
        limiter = TokenRateLimiter(tokens_per_minute=50)
        limiter.token_usage.append((time.time() - 10, 45))

        with patch("time.sleep") as mock_sleep:
            limiter.wait_if_needed(
                [{"role": "user", "content": "This message should trigger waiting"}],
                "gpt-4",
            )
            mock_sleep.assert_called_once()
            assert mock_sleep.call_args[0][0] > 0

        # The original record plus the newly recorded usage.
        assert len(limiter.token_usage) == 2

    def test_get_usage_stats(self) -> None:
        limiter = TokenRateLimiter(tokens_per_minute=1000)
        current_time = time.time()
        limiter.token_usage.append((current_time - 30, 200))
        limiter.token_usage.append((current_time - 10, 300))

        stats = limiter.get_usage_stats()
        assert stats == {
            "current_usage": 500,
            "limit": 1000,
            "usage_percentage": 50.0,
            "window_seconds": 60,
            "active_records": 2,
        }

    def test_thread_safety_records_every_call(self) -> None:
        """Concurrent wait_if_needed calls must not drop any appends (lock works)."""
        limiter = TokenRateLimiter(tokens_per_minute=10_000_000)
        messages = [{"role": "user", "content": "Test message"}]

        def worker() -> None:
            for _ in range(50):
                limiter.wait_if_needed(messages, "gpt-4")

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert len(limiter.token_usage) == 8 * 50


class TestGlobalRateLimiter:
    """Test cases for the module-level singleton helpers."""

    def test_get_rate_limiter_singleton(self) -> None:
        limiter1 = get_rate_limiter(5000)
        limiter2 = get_rate_limiter(5000)
        assert limiter1 is limiter2
        assert limiter1.tokens_per_minute == 5000

    def test_get_rate_limiter_recreated_for_different_limit(self) -> None:
        limiter1 = get_rate_limiter(5000)
        limiter2 = get_rate_limiter(8000)
        assert limiter1 is not limiter2
        assert limiter2.tokens_per_minute == 8000

    @pytest.mark.parametrize(
        "model,expected_limit",
        [
            ("anthropic/claude-3-5-sonnet-20240620", 30000),
            ("anthropic/claude-sonnet-4-20250514", 30000),
            ("gpt-4o-mini", 200000),
            ("gpt-4o", 150000),
            ("gpt-4", 40000),
            ("gemini/gemini-3-flash-preview", 60000),
            ("gemini/gemini-2.5-flash", 60000),
            ("unknown/model-name", 30000),  # falls back to default
            ("some-prefix/gpt-4o/some-suffix", 150000),  # substring match
        ],
    )
    def test_configure_rate_limiter_for_model(
        self, model: str, expected_limit: int
    ) -> None:
        limiter = configure_rate_limiter_for_model(model)
        assert limiter.tokens_per_minute == expected_limit

    def test_configure_rate_limiter_is_case_sensitive(self) -> None:
        """Matching is a plain substring check, so an upper-case name misses and defaults."""
        limiter = configure_rate_limiter_for_model("GPT-4O-MINI")
        assert limiter.tokens_per_minute == 30000
