"""
Tests for the writer's user-management actions (account creation, password
changes, role changes, deletion + token cascade, Discord upsert). These run the
real action functions against an in-memory DB inside an app context, mirroring
how the executor invokes them (the executor handles the commit).
"""

import pytest
from flask import Flask

from app.auth.passwords import verify_password
from app.extensions import db
from app.models import FeedAccessToken, User
from app.writer.actions.users import (
    create_user_action,
    delete_user_action,
    set_manual_feed_allowance_action,
    set_user_role_action,
    update_user_password_action,
    upsert_discord_user_action,
)


class TestCreateUser:
    def test_creates_user_lowercased_with_hashed_password(self, app: Flask) -> None:
        with app.app_context():
            result = create_user_action(
                {"username": "  Alice  ", "password": "pw123", "role": "admin"}
            )
            user = db.session.get(User, result["user_id"])
            assert user.username == "alice"
            assert user.role == "admin"
            assert user.password_hash != "pw123"
            assert verify_password("pw123", user.password_hash) is True

    @pytest.mark.parametrize(
        "params,message",
        [
            ({"password": "pw"}, "username is required"),
            ({"username": "bob"}, "password is required"),
            (
                {"username": "bob", "password": "pw", "role": "superuser"},
                "role must be",
            ),
        ],
    )
    def test_validation_errors(self, app: Flask, params: dict, message: str) -> None:
        with app.app_context():
            with pytest.raises(ValueError, match=message):
                create_user_action(params)

    def test_duplicate_username_rejected(self, app: Flask) -> None:
        with app.app_context():
            create_user_action({"username": "dup", "password": "pw"})
            with pytest.raises(ValueError, match="already exists"):
                create_user_action({"username": "dup", "password": "pw2"})


class TestUpdatePassword:
    def test_changes_password(self, app: Flask) -> None:
        with app.app_context():
            uid = create_user_action({"username": "u", "password": "old"})["user_id"]
            update_user_password_action({"user_id": uid, "new_password": "new"})
            user = db.session.get(User, uid)
            assert verify_password("new", user.password_hash) is True
            assert verify_password("old", user.password_hash) is False

    def test_missing_user_raises(self, app: Flask) -> None:
        with app.app_context():
            with pytest.raises(ValueError, match="not found"):
                update_user_password_action({"user_id": 9999, "new_password": "x"})


class TestSetRole:
    def test_changes_role(self, app: Flask) -> None:
        with app.app_context():
            uid = create_user_action({"username": "u", "password": "pw"})["user_id"]
            set_user_role_action({"user_id": uid, "role": "admin"})
            assert db.session.get(User, uid).role == "admin"

    def test_invalid_role_rejected(self, app: Flask) -> None:
        with app.app_context():
            uid = create_user_action({"username": "u", "password": "pw"})["user_id"]
            with pytest.raises(ValueError, match="role must be"):
                set_user_role_action({"user_id": uid, "role": "root"})


class TestDeleteUser:
    def test_deletes_user_and_cascades_tokens(self, app: Flask) -> None:
        with app.app_context():
            uid = create_user_action({"username": "u", "password": "pw"})["user_id"]
            db.session.add(
                FeedAccessToken(
                    token_id="t1", token_hash="h", user_id=uid, feed_id=None
                )
            )
            db.session.flush()

            result = delete_user_action({"user_id": uid})
            db.session.flush()  # executor commits; flush applies the staged deletes

            assert result["deleted"] is True
            assert db.session.get(User, uid) is None
            assert FeedAccessToken.query.filter_by(user_id=uid).count() == 0

    def test_delete_missing_user_is_noop(self, app: Flask) -> None:
        with app.app_context():
            assert delete_user_action({"user_id": 9999}) == {"deleted": False}


class TestSetManualFeedAllowance:
    def test_sets_and_clears_allowance(self, app: Flask) -> None:
        with app.app_context():
            uid = create_user_action({"username": "u", "password": "pw"})["user_id"]
            set_manual_feed_allowance_action({"user_id": uid, "allowance": 7})
            assert db.session.get(User, uid).manual_feed_allowance == 7

            set_manual_feed_allowance_action({"user_id": uid, "allowance": None})
            assert db.session.get(User, uid).manual_feed_allowance is None

    def test_non_integer_allowance_rejected(self, app: Flask) -> None:
        with app.app_context():
            uid = create_user_action({"username": "u", "password": "pw"})["user_id"]
            with pytest.raises(ValueError, match="must be an integer"):
                set_manual_feed_allowance_action({"user_id": uid, "allowance": "lots"})


class TestUpsertDiscordUser:
    def test_creates_new_discord_user(self, app: Flask) -> None:
        with app.app_context():
            result = upsert_discord_user_action(
                {"discord_id": "123", "discord_username": "Cool User"}
            )
            assert result["created"] is True
            user = db.session.get(User, result["user_id"])
            assert user.discord_id == "123"
            assert user.username == "cool_user"

    def test_updates_existing_discord_user(self, app: Flask) -> None:
        with app.app_context():
            first = upsert_discord_user_action(
                {"discord_id": "123", "discord_username": "Old Name"}
            )
            second = upsert_discord_user_action(
                {"discord_id": "123", "discord_username": "New Name"}
            )
            assert second["created"] is False
            assert second["user_id"] == first["user_id"]
            assert db.session.get(User, first["user_id"]).discord_username == "New Name"

    def test_registration_disabled_blocks_new_users(self, app: Flask) -> None:
        with app.app_context():
            with pytest.raises(ValueError, match="disabled"):
                upsert_discord_user_action(
                    {
                        "discord_id": "999",
                        "discord_username": "Nope",
                        "allow_registration": False,
                    }
                )

    def test_username_collision_is_disambiguated(self, app: Flask) -> None:
        with app.app_context():
            create_user_action({"username": "taken", "password": "pw"})
            result = upsert_discord_user_action(
                {"discord_id": "555", "discord_username": "Taken"}
            )
            assert db.session.get(User, result["user_id"]).username == "taken_1"
