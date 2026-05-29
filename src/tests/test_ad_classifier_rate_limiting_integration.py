"""
Integration tests for how AdClassifier wires in rate limiting and retry/backoff.

The TokenRateLimiter itself is unit-tested in test_token_rate_limiter.py; this
module focuses on AdClassifier's use of it and on the retry/error-classification
logic in AdClassifier._call_model / _handle_retryable_error.
"""

from typing import Any, Generator
from unittest.mock import Mock, patch

import pytest
from litellm.types.utils import Choices, Message, ModelResponse

import podcast_processor.token_rate_limiter as trl_module
from app.models import ModelCall
from podcast_processor.ad_classifier import AdClassifier
from podcast_processor.token_rate_limiter import TokenRateLimiter
from shared.test_utils import create_test_config


@pytest.fixture(autouse=True)
def reset_rate_limiter_singleton() -> Generator[None, None, None]:
    trl_module._RATE_LIMITER = None
    yield
    trl_module._RATE_LIMITER = None


def _make_classifier(config: Any) -> AdClassifier:
    with patch("podcast_processor.ad_classifier.db.session") as mock_session:
        return AdClassifier(config=config, db_session=mock_session)


class TestAdClassifierRateLimiterWiring:
    """The rate limiter should be created (or not) based on config."""

    def test_rate_limiter_initialization_enabled(self) -> None:
        classifier = _make_classifier(create_test_config())
        assert isinstance(classifier.rate_limiter, TokenRateLimiter)
        assert classifier.rate_limiter.tokens_per_minute == 30000  # Anthropic default

    def test_rate_limiter_initialization_disabled(self) -> None:
        classifier = _make_classifier(
            create_test_config(llm_enable_token_rate_limiting=False)
        )
        assert classifier.rate_limiter is None

    def test_rate_limiter_custom_limit(self) -> None:
        classifier = _make_classifier(
            create_test_config(llm_max_input_tokens_per_minute=15000)
        )
        assert classifier.rate_limiter is not None
        assert classifier.rate_limiter.tokens_per_minute == 15000

    def test_rate_limiter_uses_model_specific_limit(self) -> None:
        classifier = _make_classifier(create_test_config(llm_model="gpt-4o-mini"))
        assert classifier.rate_limiter is not None
        assert classifier.rate_limiter.tokens_per_minute == 200000


class TestCallModelUsesRateLimiter:
    @patch("podcast_processor.ad_classifier.writer_client")
    @patch("podcast_processor.ad_classifier.litellm")
    def test_call_model_waits_records_and_returns_content(
        self, mock_litellm: Mock, mock_writer: Mock
    ) -> None:
        """_call_model goes through the rate limiter and returns the LLM content.

        Uses a real litellm Choices/Message response so the
        `assert isinstance(..., Choices)` contract in the source is genuinely
        exercised (no isinstance monkeypatching).
        """
        mock_writer.update.return_value = Mock(success=True)

        classifier = _make_classifier(create_test_config())
        classifier.rate_limiter = Mock(spec=TokenRateLimiter)
        classifier.rate_limiter.get_usage_stats.return_value = {
            "current_usage": 1000,
            "limit": 30000,
            "usage_percentage": 3.3,
        }

        response = ModelResponse(
            choices=[
                Choices(index=0, message=Message(role="assistant", content="cleaned"))
            ]
        )
        mock_litellm.completion.return_value = response

        model_call = ModelCall(
            id=1,
            model_name="anthropic/claude-3-5-sonnet-20240620",
            prompt="user prompt",
            status="pending",
        )

        result = classifier._call_model(model_call, "system prompt")

        assert result == "cleaned"
        classifier.rate_limiter.wait_if_needed.assert_called_once()

        completion_kwargs = mock_litellm.completion.call_args[1]
        assert completion_kwargs["model"] == "anthropic/claude-3-5-sonnet-20240620"
        roles = [m["role"] for m in completion_kwargs["messages"]]
        assert roles == ["system", "user"]
        # The success status is persisted through the writer.
        assert any(
            call.args[2].get("status") == "success"
            for call in mock_writer.update.call_args_list
        )

    @patch("podcast_processor.ad_classifier.writer_client")
    @patch("podcast_processor.ad_classifier.litellm")
    def test_call_model_non_retryable_error_marks_permanent_and_raises(
        self, mock_litellm: Mock, mock_writer: Mock
    ) -> None:
        mock_writer.update.return_value = Mock(success=True)
        classifier = _make_classifier(create_test_config())
        classifier.rate_limiter = None

        mock_litellm.completion.side_effect = Exception("Invalid API key (401)")

        model_call = ModelCall(id=7, model_name="m", prompt="p", status="pending")

        with pytest.raises(Exception, match="Invalid API key"):
            classifier._call_model(model_call, "system prompt")

        assert model_call.status == "failed_permanent"
        # litellm should only be tried once (no retry on a non-retryable error).
        assert mock_litellm.completion.call_count == 1

    @patch("time.sleep")
    @patch("podcast_processor.ad_classifier.writer_client")
    @patch("podcast_processor.ad_classifier.litellm")
    def test_call_model_retries_then_succeeds(
        self, mock_litellm: Mock, mock_writer: Mock, mock_sleep: Mock
    ) -> None:
        mock_writer.update.return_value = Mock(success=True)
        classifier = _make_classifier(create_test_config(llm_max_retry_attempts=3))
        classifier.rate_limiter = None

        good = ModelResponse(
            choices=[Choices(index=0, message=Message(role="assistant", content="ok"))]
        )
        mock_litellm.completion.side_effect = [
            Exception("HTTP 429 rate limit exceeded"),
            good,
        ]

        model_call = ModelCall(id=9, model_name="m", prompt="p", status="pending")
        result = classifier._call_model(model_call, "system prompt")

        assert result == "ok"
        assert mock_litellm.completion.call_count == 2
        mock_sleep.assert_called_once()  # backed off once before the retry


class TestRetryClassification:
    """_is_retryable_error and the backoff schedule in _handle_retryable_error."""

    @pytest.mark.parametrize(
        "message",
        [
            "HTTP 429: Rate limit exceeded",
            "rate_limit_error: too many requests",
            "RateLimitError: Request rate limit exceeded",
            "Service temporarily unavailable (503)",
            "service unavailable",
            "Error 503: Service unavailable",
            "rate limit reached",
        ],
    )
    def test_retryable_errors(self, message: str) -> None:
        classifier = _make_classifier(create_test_config())
        assert classifier._is_retryable_error(Exception(message)) is True

    @pytest.mark.parametrize(
        "error",
        [
            Exception("Invalid API key (401)"),
            Exception("Bad request (400)"),
            Exception("Forbidden (403)"),
            ValueError("Invalid input format"),
            Exception("Model not found (404)"),
            Exception("Connection timeout"),
            # NOTE: AdClassifier intentionally does NOT treat a bare 500 as
            # retryable (unlike LLMErrorClassifier). Pin that behavior here.
            Exception("Internal server error (500)"),
        ],
    )
    def test_non_retryable_errors(self, error: Exception) -> None:
        classifier = _make_classifier(create_test_config())
        assert classifier._is_retryable_error(error) is False

    def test_internal_server_error_instance_is_retryable(self) -> None:
        from litellm.exceptions import InternalServerError

        classifier = _make_classifier(create_test_config())
        err = InternalServerError("boom", llm_provider="test", model="test")
        assert classifier._is_retryable_error(err) is True

    @patch("podcast_processor.ad_classifier.writer_client")
    @patch("time.sleep")
    def test_backoff_progression(self, mock_sleep: Any, mock_writer: Mock) -> None:
        mock_writer.update.return_value = Mock(success=True)
        classifier = _make_classifier(create_test_config())
        model_call = ModelCall(id=1, error_message=None)

        rate_limit_error = Exception("rate_limit_error: too many requests")
        for attempt in range(3):
            classifier._handle_retryable_error(
                model_call_obj=model_call,
                error=rate_limit_error,
                attempt=attempt,
                current_attempt_num=attempt + 1,
            )
        assert [c[0][0] for c in mock_sleep.call_args_list] == [60, 120, 240]

        mock_sleep.reset_mock()
        regular_error = Exception("Internal server error")
        for attempt in range(3):
            classifier._handle_retryable_error(
                model_call_obj=model_call,
                error=regular_error,
                attempt=attempt,
                current_attempt_num=attempt + 1,
            )
        assert [c[0][0] for c in mock_sleep.call_args_list] == [1, 2, 4]
