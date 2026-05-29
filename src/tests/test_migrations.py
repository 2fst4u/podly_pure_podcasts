"""
Test that all Alembic migrations have been created for every model change.

This prevents the class of bug where a column is added to a SQLAlchemy model
but no migration is written to add it to the database, causing runtime errors.

The test:
1. Applies every migration in sequence to a fresh in-memory SQLite database.
2. Uses Alembic's autogenerate comparison to check the migrated schema matches
   the SQLAlchemy model metadata exactly.
3. Fails if any table or column is present in the models but absent from the DB
   (or vice-versa), which means a migration file is missing.
"""

import os

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from flask import Flask
from flask_migrate import Migrate, upgrade

from app.extensions import db

# Import every model so its table is registered in db.metadata before comparison.
import app.models  # noqa: F401


MIGRATIONS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "migrations")
)


@pytest.fixture(scope="module")
def migrated_engine():
    """Create a fresh in-memory DB and run all migrations against it."""
    test_app = Flask(__name__)
    test_app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    test_app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(test_app)
    Migrate(test_app, db, directory=MIGRATIONS_DIR)

    with test_app.app_context():
        upgrade()
        # Yield the engine while still inside the app context so it stays open.
        yield db.engine


def test_no_missing_migrations(migrated_engine):
    """
    The migrated schema must exactly match the SQLAlchemy model metadata.

    Any diff means either a migration is missing (model has a column the DB
    doesn't) or a migration was applied that doesn't match the current models.
    """
    with migrated_engine.connect() as conn:
        migration_ctx = MigrationContext.configure(
            conn,
            opts={
                # compare_type=False avoids SQLite false-positives where e.g.
                # BOOLEAN is stored as INTEGER — we care about missing columns,
                # not minor type representation differences.
                "compare_type": False,
                "render_as_batch": True,
            },
        )
        diffs = compare_metadata(migration_ctx, db.metadata)

    # Alembic tracks its own version table; it's not in our models and that's fine.
    actionable = [
        d
        for d in diffs
        if not (
            isinstance(d, tuple)
            and len(d) >= 2
            and getattr(d[1], "name", None) == "alembic_version"
        )
    ]

    assert actionable == [], (
        "Schema drift detected — a migration is probably missing.\n"
        "Differences between applied migrations and SQLAlchemy models:\n"
        + "\n".join(f"  {d}" for d in actionable)
    )
