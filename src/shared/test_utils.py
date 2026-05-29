"""
Shared configuration helpers for tests, kept in one place to avoid duplicate
test-config factories drifting apart.
"""

from typing import Any

from .config import Config, OutputConfig, ProcessingConfig


def create_standard_test_config(
    llm_api_key: str = "test-key",
    llm_max_input_tokens_per_call: int | None = None,
    num_segments_to_input_to_prompt: int = 400,
    max_overlap_segments: int = 30,
    **overrides: Any,
) -> Config:
    """
    Create a standardized configuration for testing and demos.

    Args:
        llm_api_key: API key for testing
        llm_max_input_tokens_per_call: Optional token limit
        num_segments_to_input_to_prompt: Number of segments per prompt
        max_overlap_segments: Maximum number of previously identified segments to carry forward
        **overrides: Any additional top-level ``Config`` fields to set/override.

    Returns:
        Configured Config object for testing
    """
    config_kwargs: dict[str, Any] = {
        "llm_api_key": llm_api_key,
        "llm_max_input_tokens_per_call": llm_max_input_tokens_per_call,
        "output": OutputConfig(
            fade_ms=2000,
            min_ad_segement_separation_seconds=60,
            min_ad_segment_length_seconds=14,
            min_confidence=0.7,
        ),
        "processing": ProcessingConfig(
            num_segments_to_input_to_prompt=num_segments_to_input_to_prompt,
            max_overlap_segments=max_overlap_segments,
        ),
    }
    config_kwargs.update(overrides)
    return Config(**config_kwargs)


def create_test_config(**overrides: Any) -> Config:
    """
    Create a test configuration with token rate limiting enabled by default.

    This is a thin wrapper over :func:`create_standard_test_config` that layers
    on the rate-limiting-oriented defaults used by the rate-limiting test
    modules, so both factories share a single underlying implementation.
    """
    rate_limiting_defaults: dict[str, Any] = {
        "llm_model": "anthropic/claude-3-5-sonnet-20240620",
        "llm_enable_token_rate_limiting": True,
        "llm_max_retry_attempts": 3,
        "llm_max_concurrent_calls": 2,
        "openai_timeout": 300,
        "openai_max_tokens": 4096,
        "num_segments_to_input_to_prompt": 30,
    }
    rate_limiting_defaults.update(overrides)
    return create_standard_test_config(**rate_limiting_defaults)
