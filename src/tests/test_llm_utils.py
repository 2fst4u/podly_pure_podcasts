import pytest

from shared.llm_utils import model_uses_max_completion_tokens


def test_model_uses_max_completion_tokens() -> None:
    # Arrange & Act & Assert

    # Test None case
    assert model_uses_max_completion_tokens(None) is False

    # Test empty string
    assert model_uses_max_completion_tokens("") is False

    # Test matching models
    assert model_uses_max_completion_tokens("gpt-4o") is True
    assert model_uses_max_completion_tokens("gpt-5") is True
    assert model_uses_max_completion_tokens("o1-preview") is True
    assert model_uses_max_completion_tokens("chatgpt-4o-latest") is True
    assert model_uses_max_completion_tokens("GPT-4O") is True  # Case insensitive

    # Test non-matching models
    assert model_uses_max_completion_tokens("gpt-3.5-turbo") is False
    assert model_uses_max_completion_tokens("gpt-4-turbo") is False
    assert model_uses_max_completion_tokens("claude-3-opus") is False
