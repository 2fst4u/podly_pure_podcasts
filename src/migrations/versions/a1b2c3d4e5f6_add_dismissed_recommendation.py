"""add dismissed_recommendation table

Revision ID: a1b2c3d4e5f6
Revises: e1325294473b
Create Date: 2026-05-30 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "e1325294473b"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "dismissed_recommendation",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("podcast_title", sa.Text(), nullable=False),
        sa.Column("podcast_rss_url", sa.Text(), nullable=True),
        sa.Column("dismissed_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_dismissed_recommendation_user_id",
        "dismissed_recommendation",
        ["user_id"],
    )


def downgrade():
    op.drop_index(
        "ix_dismissed_recommendation_user_id",
        table_name="dismissed_recommendation",
    )
    op.drop_table("dismissed_recommendation")
