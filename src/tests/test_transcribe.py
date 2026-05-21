import logging
from typing import Any
from unittest.mock import MagicMock

import pytest
from openai.types.audio.transcription_segment import TranscriptionSegment

# from pytest_mock import MockerFixture


def test_remote_transcribe(mocker: Any) -> None:
    # import here instead of the toplevel because torch is not installed properly in CI.
    mocker.patch.dict("sys.modules", {"torch": MagicMock(), "whisper": MagicMock()})
    from podcast_processor.transcribe import (  # pylint: disable=import-outside-toplevel
        OpenAIWhisperTranscriber,
    )
    from shared.config import (  # pylint: disable=import-outside-toplevel
        RemoteWhisperConfig,
    )

    logger = logging.getLogger("global_logger")
    config = RemoteWhisperConfig(api_key="test-key")

    transcriber = OpenAIWhisperTranscriber(logger, config)

    # Mock file operations
    mocker.patch("builtins.open", mocker.mock_open(read_data="test audio data"))
    mocker.patch("pathlib.Path.exists", return_value=True)
    mocker.patch(
        "podcast_processor.transcribe.split_audio", return_value=[("test.mp3", 0)]
    )
    mocker.patch("shutil.rmtree")

    mock_transcription = MagicMock()

    mock_transcription.segments = [
        TranscriptionSegment(
            id=1,
            avg_logprob=2,
            seek=6,
            temperature=7,
            text="This is a test segment.",
            tokens=[],
            compression_ratio=3,
            no_speech_prob=4,
            start=0.0,
            end=1.0,
        ),
        TranscriptionSegment(
            id=2,
            avg_logprob=2,
            seek=6,
            temperature=7,
            text="This is another test segment.",
            tokens=[],
            compression_ratio=3,
            no_speech_prob=4,
            start=1.0,
            end=2.0,
        ),
    ]

    mocker.patch.object(
        transcriber.openai_client.audio.transcriptions,
        "create",
        return_value=mock_transcription,
    )

    transcription = transcriber.transcribe("file.mp3")
    assert len(transcription) == 2
    assert transcription[0].text == "This is a test segment."


def test_local_transcribe(mocker: Any) -> None:
    # import here instead of the toplevel because torch is not installed properly in CI.
    mock_whisper = MagicMock()
    mock_model = MagicMock()
    mock_model.transcribe.return_value = {
        "segments": [
            {
                "id": 1,
                "seek": 0,
                "start": 0.0,
                "end": 1.0,
                "text": "This is a test segment.",
                "tokens": [],
                "temperature": 0.0,
                "avg_logprob": -0.1,
                "compression_ratio": 1.0,
                "no_speech_prob": 0.05,
            }
        ]
    }
    mock_whisper.load_model.return_value = mock_model
    mock_whisper.available_models.return_value = ["base.en"]
    mocker.patch.dict("sys.modules", {"torch": MagicMock(), "whisper": mock_whisper})

    from podcast_processor.transcribe import (  # pylint: disable=import-outside-toplevel
        LocalWhisperTranscriber,
    )

    logger = logging.getLogger("global_logger")
    transcriber = LocalWhisperTranscriber(logger, "base.en")

    transcription = transcriber.transcribe("src/tests/file.mp3")
    assert len(transcription) == 1
    assert transcription[0].text == "This is a test segment."


def test_groq_transcribe(mocker: Any) -> None:
    # import here instead of the toplevel because dependencies aren't installed properly in CI.
    mocker.patch.dict("sys.modules", {"torch": MagicMock(), "whisper": MagicMock()})
    from podcast_processor.transcribe import (  # pylint: disable=import-outside-toplevel
        GroqWhisperTranscriber,
    )
    from shared.config import (  # pylint: disable=import-outside-toplevel
        GroqWhisperConfig,
    )

    # Mock file operations
    mocker.patch("builtins.open", mocker.mock_open(read_data="test audio data"))
    mocker.patch("pathlib.Path.exists", return_value=True)
    mocker.patch(
        "podcast_processor.transcribe.split_audio", return_value=[("test.mp3", 0)]
    )
    mocker.patch("shutil.rmtree")

    logger = logging.getLogger("global_logger")
    config = GroqWhisperConfig(
        api_key="test_key", model="whisper-large-v3-turbo", language="en"
    )

    transcriber = GroqWhisperTranscriber(logger, config)

    # Mock the groq client call
    mock_transcription = MagicMock()
    mock_transcription.segments = [
        {"start": 0.0, "end": 1.0, "text": "This is a test segment."},
        {"start": 1.0, "end": 2.0, "text": "This is another test segment."},
    ]
    mocker.patch.object(
        transcriber.client.audio.transcriptions,
        "create",
        return_value=mock_transcription,
    )

    transcription = transcriber.transcribe("test.mp3")

    assert len(transcription) == 2
    assert transcription[0].text == "This is a test segment."
    assert transcription[1].text == "This is another test segment."


def test_offset(mocker: Any) -> None:
    # import here instead of the toplevel because torch is not installed properly in CI.
    mocker.patch.dict("sys.modules", {"torch": MagicMock(), "whisper": MagicMock()})
    from podcast_processor.transcribe import (  # pylint: disable=import-outside-toplevel
        OpenAIWhisperTranscriber,
    )

    assert OpenAIWhisperTranscriber.add_offset_to_segments(
        [
            TranscriptionSegment(
                id=1,
                avg_logprob=2,
                seek=6,
                temperature=7,
                text="hi",
                tokens=[],
                compression_ratio=3,
                no_speech_prob=4,
                start=12.345,
                end=45.678,
            )
        ],
        123,
    ) == [
        TranscriptionSegment(
            id=1,
            avg_logprob=2,
            seek=6,
            temperature=7,
            text="hi",
            tokens=[],
            compression_ratio=3,
            no_speech_prob=4,
            start=12.468,
            end=45.800999999999995,
        )
    ]
