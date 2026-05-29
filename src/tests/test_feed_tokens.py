"""
Tests for feed-access-token authentication (share links).

These cover the security-relevant negative paths of authenticate_feed_token:
unknown token, revoked token, wrong secret, missing user, feed mismatch, and
subscription enforcement for non-admins.
"""

import hashlib
from typing import Optional
from unittest.mock import patch

import pytest
from flask import Flask

from app.auth.feed_tokens import authenticate_feed_token
from app.extensions import db
from app.models import Feed, FeedAccessToken, User, UserFeed


def _hash(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def _make_user(role: str = "user", username: str = "u") -> User:
    user = User(username=username, role=role)
    user.set_password("pw")
    db.session.add(user)
    db.session.commit()
    return user


def _make_feed(title: str = "F") -> Feed:
    feed = Feed(title=title, rss_url=f"https://example.com/{title}.xml")
    db.session.add(feed)
    db.session.commit()
    return feed


def _make_token(
    *,
    user_id: int,
    secret: str,
    feed_id: Optional[int],
    token_id: str = "tok123",
    revoked: bool = False,
) -> FeedAccessToken:
    token = FeedAccessToken(
        token_id=token_id,
        token_hash=_hash(secret),
        feed_id=feed_id,
        user_id=user_id,
        revoked=revoked,
    )
    db.session.add(token)
    db.session.commit()
    return token


@pytest.fixture(autouse=True)
def _no_writer() -> None:
    """authenticate_feed_token fires a best-effort writer touch on success."""
    with patch("app.auth.feed_tokens.writer_client"):
        yield


def test_empty_token_id_returns_none(app: Flask) -> None:
    with app.app_context():
        assert authenticate_feed_token("", "secret", "/feed/1") is None


def test_unknown_token_returns_none(app: Flask) -> None:
    with app.app_context():
        assert authenticate_feed_token("missing", "secret", "/feed/1") is None


def test_revoked_token_returns_none(app: Flask) -> None:
    with app.app_context():
        user = _make_user()
        feed = _make_feed()
        _make_token(user_id=user.id, secret="s3cret", feed_id=feed.id, revoked=True)
        assert authenticate_feed_token("tok123", "s3cret", f"/feed/{feed.id}") is None


def test_wrong_secret_returns_none(app: Flask) -> None:
    with app.app_context():
        user = _make_user()
        feed = _make_feed()
        _make_token(user_id=user.id, secret="correct-secret", feed_id=feed.id)
        assert (
            authenticate_feed_token("tok123", "wrong-secret", f"/feed/{feed.id}")
            is None
        )


def test_missing_user_returns_none(app: Flask) -> None:
    with app.app_context():
        feed = _make_feed()
        # user_id points at a user that does not exist
        _make_token(user_id=9999, secret="s3cret", feed_id=feed.id)
        assert authenticate_feed_token("tok123", "s3cret", f"/feed/{feed.id}") is None


def test_feed_mismatch_returns_none(app: Flask) -> None:
    with app.app_context():
        admin = _make_user(role="admin")
        feed_a = _make_feed("A")
        feed_b = _make_feed("B")
        _make_token(user_id=admin.id, secret="s3cret", feed_id=feed_a.id)
        # Path references a different feed than the token is scoped to.
        assert authenticate_feed_token("tok123", "s3cret", f"/feed/{feed_b.id}") is None


def test_admin_with_valid_token_authenticates(app: Flask) -> None:
    with app.app_context():
        admin = _make_user(role="admin", username="admin")
        feed = _make_feed()
        _make_token(user_id=admin.id, secret="s3cret", feed_id=feed.id)

        result = authenticate_feed_token("tok123", "s3cret", f"/feed/{feed.id}")

        assert result is not None
        assert result.user.username == "admin"
        assert result.feed_id == feed.id


def test_non_admin_without_subscription_is_denied(app: Flask) -> None:
    with app.app_context():
        _make_feed("first")  # consume feed id 1 (which is always allowed)
        user = _make_user()
        feed = _make_feed("second")  # id 2, not the always-allowed feed 1
        _make_token(user_id=user.id, secret="s3cret", feed_id=feed.id)

        assert authenticate_feed_token("tok123", "s3cret", f"/feed/{feed.id}") is None


def test_non_admin_with_subscription_authenticates(app: Flask) -> None:
    with app.app_context():
        _make_feed("first")  # consume feed id 1
        user = _make_user()
        feed = _make_feed("second")
        _make_token(user_id=user.id, secret="s3cret", feed_id=feed.id)
        db.session.add(UserFeed(user_id=user.id, feed_id=feed.id))
        db.session.commit()

        result = authenticate_feed_token("tok123", "s3cret", f"/feed/{feed.id}")

        assert result is not None
        assert result.feed_id == feed.id
