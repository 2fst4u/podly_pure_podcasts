"""
Fixtures for pytest tests in the tests directory.
"""

import logging
import sys
from typing import Generator
from unittest.mock import MagicMock

import pytest
from flask import Flask

from app.extensions import db
from shared.config import Config
from shared.test_utils import create_standard_test_config

# Set up whisper and torch mocks
whisper_mock = MagicMock()
whisper_mock.available_models.return_value = [
    "tiny",
    "base",
    "small",
    "medium",
    "large",
]
whisper_mock.load_model.return_value = MagicMock()
whisper_mock.load_model.return_value.transcribe.return_value = {"segments": []}

torch_mock = MagicMock()

# Pre-mock the modules to avoid imports during test collection
sys.modules["whisper"] = whisper_mock
sys.modules["torch"] = torch_mock


@pytest.fixture
def app() -> Generator[Flask, None, None]:
    """Create a Flask app for testing."""
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    with app.app_context():
        db.init_app(app)
        db.create_all()
        yield app


@pytest.fixture
def test_config() -> Config:
    return create_standard_test_config()


@pytest.fixture
def test_logger() -> logging.Logger:
    return logging.getLogger("test_logger")


@pytest.fixture
def mock_db_session() -> MagicMock:
    """Create a mock database session"""
    mock_session = MagicMock()
    mock_session.add = MagicMock()
    mock_session.add_all = MagicMock()
    mock_session.commit = MagicMock()
    mock_session.rollback = MagicMock()
    return mock_session
