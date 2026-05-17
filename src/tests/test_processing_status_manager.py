import logging
import uuid
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest
from beartype.roar import (
    BeartypeCallHintParamViolation,
    BeartypeCallHintReturnViolation,
)

from app.models import ProcessingJob
from podcast_processor.processing_status_manager import ProcessingStatusManager


@pytest.fixture(autouse=True)
def disable_beartype() -> Generator[None, None, None]:
    with patch("beartype.door.is_bearable", return_value=True):
        yield


@pytest.fixture
def mock_db_session() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_logger() -> logging.Logger:
    return logging.getLogger("test_logger")


@pytest.fixture
def status_manager(
    mock_db_session: MagicMock, mock_logger: logging.Logger
) -> ProcessingStatusManager:
    with patch("beartype.beartype", lambda x: x):
        return ProcessingStatusManager(db_session=mock_db_session, logger=mock_logger)


def test_generate_job_id(status_manager: ProcessingStatusManager) -> None:
    job_id = status_manager.generate_job_id()
    assert isinstance(job_id, str)
    assert uuid.UUID(job_id)


@patch("podcast_processor.processing_status_manager.writer_client")
def test_create_job(
    mock_writer_client: MagicMock,
    status_manager: ProcessingStatusManager,
    mock_db_session: MagicMock,
) -> None:
    mock_job = MagicMock()
    # Mocking type check is hard when decorator is already applied.
    # We will just patch the function to bypass beartype for the return value
    # ProcessingStatusManager.create_job = getattr(ProcessingStatusManager.create_job, '__wrapped__', ProcessingStatusManager.create_job)

    mock_db_session.get.return_value = mock_job

    post_guid = "test_guid"
    job_id = "test_job_id"

    with patch(
        "podcast_processor.processing_status_manager.cast", return_value=mock_job
    ):
        with patch.object(
            ProcessingStatusManager,
            "create_job",
            getattr(
                ProcessingStatusManager.create_job,
                "__wrapped__",
                ProcessingStatusManager.create_job,
            ),
        ):
            job = status_manager.create_job(post_guid=post_guid, job_id=job_id)

            mock_writer_client.action.assert_called_once()
            args, kwargs = mock_writer_client.action.call_args
            assert args[0] == "create_job"
            assert "job_data" in args[1]
            assert args[1]["job_data"]["id"] == job_id
            assert args[1]["job_data"]["post_guid"] == post_guid
            assert kwargs["wait"] is True

            mock_db_session.expire_all.assert_called_once()
            mock_db_session.get.assert_called_once_with(ProcessingJob, job_id)
            assert job == mock_job


@patch("podcast_processor.processing_status_manager.writer_client")
def test_create_job_failure(
    mock_writer_client: MagicMock,
    status_manager: ProcessingStatusManager,
    mock_db_session: MagicMock,
) -> None:
    mock_db_session.get.return_value = None

    post_guid = "test_guid"
    job_id = "test_job_id"

    with pytest.raises(RuntimeError, match=f"Failed to create job {job_id}"):
        with patch.object(
            ProcessingStatusManager,
            "create_job",
            getattr(
                ProcessingStatusManager.create_job,
                "__wrapped__",
                ProcessingStatusManager.create_job,
            ),
        ):
            status_manager.create_job(post_guid=post_guid, job_id=job_id)


@patch("podcast_processor.processing_status_manager.writer_client")
def test_cancel_existing_jobs(
    mock_writer_client: MagicMock,
    status_manager: ProcessingStatusManager,
    mock_db_session: MagicMock,
) -> None:
    post_guid = "test_guid"
    current_job_id = "test_job_id"

    status_manager.cancel_existing_jobs(post_guid, current_job_id)

    mock_writer_client.action.assert_called_once_with(
        "cancel_existing_jobs",
        {"post_guid": post_guid, "current_job_id": current_job_id},
        wait=True,
    )
    mock_db_session.expire_all.assert_called_once()


@patch("podcast_processor.processing_status_manager.object_session")
@patch("podcast_processor.processing_status_manager.writer_client")
def test_update_job_status(
    mock_writer_client: MagicMock,
    mock_object_session: MagicMock,
    status_manager: ProcessingStatusManager,
    mock_db_session: MagicMock,
    mock_logger: logging.Logger,
) -> None:
    mock_job = MagicMock()
    mock_job.id = "test_job_id"
    mock_job.total_steps = 4
    mock_job.post_guid = "test_post_guid"

    mock_object_session.return_value = mock_db_session

    with patch.object(mock_logger, "error") as mock_error:
        with patch.object(
            ProcessingStatusManager,
            "update_job_status",
            getattr(
                ProcessingStatusManager.update_job_status,
                "__wrapped__",
                ProcessingStatusManager.update_job_status,
            ),
        ):
            status_manager.update_job_status(mock_job, "failed", 1, "downloading")
            mock_error.assert_called_once()

    mock_writer_client.action.assert_called_once_with(
        "update_job_status",
        {
            "job_id": "test_job_id",
            "status": "failed",
            "step": 1,
            "step_name": "downloading",
            "progress": 25.0,
        },
        wait=True,
    )
    mock_db_session.expire_all.assert_called_once()


@patch("podcast_processor.processing_status_manager.writer_client")
def test_mark_cancelled(
    mock_writer_client: MagicMock,
    status_manager: ProcessingStatusManager,
    mock_db_session: MagicMock,
    mock_logger: logging.Logger,
) -> None:
    job_id = "test_job_id"
    error_message = "test_error"

    with patch.object(mock_logger, "info") as mock_info:
        status_manager.mark_cancelled(job_id, error_message)
        mock_info.assert_called_once_with(f"Successfully cancelled job {job_id}")

    mock_writer_client.action.assert_called_once_with(
        "mark_cancelled", {"job_id": job_id, "reason": error_message}, wait=True
    )
    mock_db_session.expire_all.assert_called_once()
