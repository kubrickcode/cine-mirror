"""add movie enrichment fields

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-09 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "movie",
        sa.Column(
            "is_not_found",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("FALSE"),
        ),
    )
    op.add_column(
        "movie",
        sa.Column("korean_title", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("movie", "korean_title")
    op.drop_column("movie", "is_not_found")
