import logging
from unittest.mock import MagicMock, patch

from podcast_processor.llm_model_call_utils import (
    extract_litellm_content,
    render_prompt_and_upsert_model_call,
    try_update_model_call,
    try_upsert_model_call,
)


def test_extract_litellm_content_with_message_content() -> None:
    class Message:
        content = "test content"

    class Choice:
        message = Message()

    class Response:
        choices = [Choice()]

    assert extract_litellm_content(Response()) == "test content"


def test_extract_litellm_content_with_text() -> None:
    class Choice:
        text = "test text"

    class Response:
        choices = [Choice()]

    assert extract_litellm_content(Response()) == "test text"


def test_extract_litellm_content_empty() -> None:
    assert extract_litellm_content(None) == ""

    class ResponseEmptyChoices:
        choices = []

    assert extract_litellm_content(ResponseEmptyChoices()) == ""

    class ChoiceEmpty:
        pass

    class ResponseEmptyChoice:
        choices = [ChoiceEmpty()]

    assert extract_litellm_content(ResponseEmptyChoice()) == ""


@patch("podcast_processor.llm_model_call_utils.writer_client.action")
def test_try_upsert_model_call_success(mock_action: MagicMock) -> None:
    mock_response = MagicMock()
    mock_response.success = True
    mock_response.data = {"model_call_id": 123}
    mock_action.return_value = mock_response

    logger = logging.getLogger("test")

    model_call_id = try_upsert_model_call(
        post_id=1,
        first_seq_num=0,
        last_seq_num=10,
        model_name="test_model",
        prompt="test prompt",
        logger=logger,
        log_prefix="test",
    )

    assert model_call_id == 123
    mock_action.assert_called_once_with(
        "upsert_model_call",
        {
            "post_id": 1,
            "model_name": "test_model",
            "first_segment_sequence_num": 0,
            "last_segment_sequence_num": 10,
            "prompt": "test prompt",
        },
        wait=True,
    )


def test_try_upsert_model_call_missing_args() -> None:
    logger = logging.getLogger("test")
    assert (
        try_upsert_model_call(
            post_id=None,
            first_seq_num=0,
            last_seq_num=10,
            model_name="test",
            prompt="test",
            logger=logger,
            log_prefix="test",
        )
        is None
    )


@patch("podcast_processor.llm_model_call_utils.writer_client.action")
def test_try_upsert_model_call_exception(mock_action: MagicMock) -> None:
    mock_action.side_effect = Exception("test error")
    logger = logging.getLogger("test")
    with patch.object(logger, "warning") as mock_warning:
        model_call_id = try_upsert_model_call(
            post_id=1,
            first_seq_num=0,
            last_seq_num=10,
            model_name="test_model",
            prompt="test prompt",
            logger=logger,
            log_prefix="test_prefix",
        )

        assert model_call_id is None
        mock_warning.assert_called_once()
        assert "test error" in str(mock_warning.call_args)


@patch("podcast_processor.llm_model_call_utils.writer_client.update")
def test_try_update_model_call_success(mock_update: MagicMock) -> None:
    logger = logging.getLogger("test")

    try_update_model_call(
        model_call_id=123,
        status="completed",
        response="test response",
        error_message=None,
        logger=logger,
        log_prefix="test",
    )

    mock_update.assert_called_once_with(
        "ModelCall",
        123,
        {
            "status": "completed",
            "response": "test response",
            "error_message": None,
            "retry_attempts": 1,
        },
        wait=True,
    )


@patch("podcast_processor.llm_model_call_utils.writer_client.update")
def test_try_update_model_call_none_id(mock_update: MagicMock) -> None:
    logger = logging.getLogger("test")
    try_update_model_call(
        model_call_id=None,
        status="completed",
        response="test response",
        error_message=None,
        logger=logger,
        log_prefix="test",
    )
    mock_update.assert_not_called()


@patch("podcast_processor.llm_model_call_utils.writer_client.update")
def test_try_update_model_call_exception(mock_update: MagicMock) -> None:
    mock_update.side_effect = Exception("update error")
    logger = logging.getLogger("test")

    with patch.object(logger, "warning") as mock_warning:
        try_update_model_call(
            model_call_id=123,
            status="completed",
            response="test response",
            error_message=None,
            logger=logger,
            log_prefix="test_prefix",
        )

        mock_warning.assert_called_once()
        assert "update error" in str(mock_warning.call_args)


@patch("podcast_processor.llm_model_call_utils.try_upsert_model_call")
def test_render_prompt_and_upsert_model_call(mock_try_upsert: MagicMock) -> None:
    mock_try_upsert.return_value = 123
    mock_template = MagicMock()
    mock_template.render.return_value = "rendered prompt"
    logger = logging.getLogger("test")

    prompt, model_call_id = render_prompt_and_upsert_model_call(
        template=mock_template,
        ad_start=1.0,
        ad_end=5.0,
        confidence=0.9,
        context_segments=["seg1", "seg2"],
        post_id=1,
        first_seq_num=0,
        last_seq_num=10,
        model_name="test_model",
        logger=logger,
        log_prefix="test",
    )

    assert prompt == "rendered prompt"
    assert model_call_id == 123
    mock_template.render.assert_called_once_with(
        ad_start=1.0,
        ad_end=5.0,
        ad_confidence=0.9,
        context_segments=["seg1", "seg2"],
    )
    mock_try_upsert.assert_called_once_with(
        post_id=1,
        first_seq_num=0,
        last_seq_num=10,
        model_name="test_model",
        prompt="rendered prompt",
        logger=logger,
        log_prefix="test",
    )
