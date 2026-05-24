import pytest

from app.auth.passwords import hash_password, verify_password


def test_hash_password():
    # Arrange
    password = "supersecretpassword123!"

    # Act
    hashed = hash_password(password)

    # Assert
    assert hashed != password
    assert type(hashed) == str
    assert hashed.startswith("$2b$")  # bcrypt identifier


def test_verify_password_correct():
    # Arrange
    password = "supersecretpassword123!"
    hashed = hash_password(password)

    # Act
    is_valid = verify_password(password, hashed)

    # Assert
    assert is_valid is True


def test_verify_password_incorrect():
    # Arrange
    password = "supersecretpassword123!"
    incorrect_password = "wrongpassword"
    hashed = hash_password(password)

    # Act
    is_valid = verify_password(incorrect_password, hashed)

    # Assert
    assert is_valid is False


def test_verify_password_value_error():
    # Arrange
    password = "supersecretpassword123!"
    invalid_hash = "not_a_valid_hash"

    # Act
    is_valid = verify_password(password, invalid_hash)

    # Assert
    assert is_valid is False
