"""
Tests for the writer subsystem's core engine: execute_model_command (the
CREATE/UPDATE/DELETE primitive) and CommandExecutor (action dispatch and
transaction atomicity).

AGENTS.md requires that *all* DB writes go through the writer, so this engine
is critical and was previously only ever mocked. These tests exercise it
against a real in-memory database.
"""

from typing import Any, Dict

import pytest
from flask import Flask

from app.extensions import db
from app.models import Feed
from app.writer.executor import CommandExecutor
from app.writer.protocol import WriteCommand, WriteCommandType, WriteResult


def _cmd(
    cmd_type: WriteCommandType, model: str | None, data: Dict[str, Any]
) -> WriteCommand:
    return WriteCommand(id="c1", type=cmd_type, model=model, data=data)


class TestExecuteModelCommand:
    def test_create_returns_new_id(self, app: Flask) -> None:
        from app.writer.model_ops import execute_model_command

        cmd = _cmd(WriteCommandType.CREATE, "Feed", {"title": "T", "rss_url": "u"})
        result = execute_model_command(cmd=cmd, model_cls=Feed, db_session=db.session)

        assert result.success is True
        assert result.data is not None and result.data["id"] is not None

    def test_update_sets_fields(self, app: Flask) -> None:
        from app.writer.model_ops import execute_model_command

        feed = Feed(title="old", rss_url="u")
        db.session.add(feed)
        db.session.commit()

        cmd = _cmd(WriteCommandType.UPDATE, "Feed", {"id": feed.id, "title": "new"})
        result = execute_model_command(cmd=cmd, model_cls=Feed, db_session=db.session)

        assert result.success is True
        assert db.session.get(Feed, feed.id).title == "new"

    def test_update_ignores_unknown_attrs_and_id(self, app: Flask) -> None:
        from app.writer.model_ops import execute_model_command

        feed = Feed(title="old", rss_url="u")
        db.session.add(feed)
        db.session.commit()
        original_id = feed.id

        cmd = _cmd(
            WriteCommandType.UPDATE,
            "Feed",
            {"id": original_id, "title": "new", "does_not_exist": 1},
        )
        result = execute_model_command(cmd=cmd, model_cls=Feed, db_session=db.session)

        assert result.success is True
        assert feed.id == original_id

    def test_update_missing_id_errors(self, app: Flask) -> None:
        from app.writer.model_ops import execute_model_command

        cmd = _cmd(WriteCommandType.UPDATE, "Feed", {"title": "x"})
        result = execute_model_command(cmd=cmd, model_cls=Feed, db_session=db.session)
        assert result.success is False
        assert "Missing 'id'" in (result.error or "")

    def test_update_not_found_errors(self, app: Flask) -> None:
        from app.writer.model_ops import execute_model_command

        cmd = _cmd(WriteCommandType.UPDATE, "Feed", {"id": 424242, "title": "x"})
        result = execute_model_command(cmd=cmd, model_cls=Feed, db_session=db.session)
        assert result.success is False
        assert "not found" in (result.error or "").lower()

    def test_delete_removes_record(self, app: Flask) -> None:
        from app.writer.model_ops import execute_model_command

        feed = Feed(title="gone", rss_url="u")
        db.session.add(feed)
        db.session.commit()
        feed_id = feed.id

        cmd = _cmd(WriteCommandType.DELETE, "Feed", {"id": feed_id})
        result = execute_model_command(cmd=cmd, model_cls=Feed, db_session=db.session)

        assert result.success is True
        # The primitive stages the delete; the executor commits. Flush to apply.
        db.session.flush()
        assert db.session.get(Feed, feed_id) is None

    def test_delete_missing_id_errors(self, app: Flask) -> None:
        from app.writer.model_ops import execute_model_command

        cmd = _cmd(WriteCommandType.DELETE, "Feed", {})
        result = execute_model_command(cmd=cmd, model_cls=Feed, db_session=db.session)
        assert result.success is False
        assert "Missing 'id'" in (result.error or "")


class TestCommandExecutor:
    def test_discovers_models(self, app: Flask) -> None:
        executor = CommandExecutor(app)
        assert "Feed" in executor.models
        assert executor.models["Feed"] is Feed

    def test_process_create_commits(self, app: Flask) -> None:
        executor = CommandExecutor(app)
        result = executor.process_command(
            _cmd(WriteCommandType.CREATE, "Feed", {"title": "C", "rss_url": "u"})
        )
        assert result.success is True
        # The write was committed and is visible outside the writer's context.
        assert Feed.query.filter_by(title="C").count() == 1

    def test_process_unknown_model_errors(self, app: Flask) -> None:
        executor = CommandExecutor(app)
        result = executor.process_command(
            _cmd(WriteCommandType.CREATE, "NopeModel", {})
        )
        assert result.success is False
        assert "Unknown model" in (result.error or "")

    def test_process_unknown_action_errors(self, app: Flask) -> None:
        executor = CommandExecutor(app)
        result = executor.process_command(
            _cmd(WriteCommandType.ACTION, None, {"action": "does_not_exist"})
        )
        assert result.success is False
        assert "Unknown action" in (result.error or "")

    def test_custom_action_runs_and_commits(self, app: Flask) -> None:
        executor = CommandExecutor(app)

        def _make_feed(params: Dict[str, Any]) -> Dict[str, Any]:
            feed = Feed(title=params["title"], rss_url="u")
            db.session.add(feed)
            db.session.flush()
            return {"feed_id": feed.id}

        executor.register_action("make_feed", _make_feed)
        result = executor.process_command(
            _cmd(
                WriteCommandType.ACTION,
                None,
                {"action": "make_feed", "params": {"title": "Z"}},
            )
        )

        assert result.success is True
        assert result.data is not None and "feed_id" in result.data
        assert Feed.query.filter_by(title="Z").count() == 1

    def test_action_exception_rolls_back(self, app: Flask) -> None:
        executor = CommandExecutor(app)

        def _boom(params: Dict[str, Any]) -> None:
            feed = Feed(title="should-not-persist", rss_url="u")
            db.session.add(feed)
            db.session.flush()
            raise ValueError("kaboom")

        executor.register_action("boom", _boom)
        result = executor.process_command(
            _cmd(WriteCommandType.ACTION, None, {"action": "boom"})
        )

        assert result.success is False
        assert "kaboom" in (result.error or "")
        # The partial write must have been rolled back.
        assert Feed.query.filter_by(title="should-not-persist").count() == 0

    def test_transaction_commits_all_on_success(self, app: Flask) -> None:
        executor = CommandExecutor(app)
        result = executor.process_command(
            _cmd(
                WriteCommandType.TRANSACTION,
                None,
                {
                    "commands": [
                        {
                            "id": "a",
                            "type": "create",
                            "model": "Feed",
                            "data": {"title": "t1", "rss_url": "u1"},
                        },
                        {
                            "id": "b",
                            "type": "create",
                            "model": "Feed",
                            "data": {"title": "t2", "rss_url": "u2"},
                        },
                    ]
                },
            )
        )
        assert result.success is True
        assert Feed.query.filter(Feed.title.in_(["t1", "t2"])).count() == 2

    def test_transaction_rolls_back_all_on_failure(self, app: Flask) -> None:
        executor = CommandExecutor(app)
        result = executor.process_command(
            _cmd(
                WriteCommandType.TRANSACTION,
                None,
                {
                    "commands": [
                        {
                            "id": "a",
                            "type": "create",
                            "model": "Feed",
                            "data": {"title": "atomic", "rss_url": "u1"},
                        },
                        # Second op fails (unknown model) -> whole transaction must roll back.
                        {"id": "b", "type": "create", "model": "BadModel", "data": {}},
                    ]
                },
            )
        )
        assert result.success is False
        assert "Transaction failed" in (result.error or "")
        # The first create must NOT have persisted (atomicity).
        assert Feed.query.filter_by(title="atomic").count() == 0
