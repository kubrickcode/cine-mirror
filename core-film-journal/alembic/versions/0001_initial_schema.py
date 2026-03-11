"""초기 스키마 생성 + seed 사용자 삽입

Revision ID: 0001
Revises:
Create Date: 2026-03-11

"""

from __future__ import annotations

import uuid
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Constraint: seed 사용자 ID를 고정하여 인증 stub이 항상 동일한 user_id를 참조할 수 있게 한다.
SEED_USER_ID = "00000000-0000-0000-0000-000000000001"
SEED_USER_EMAIL = "seed@cine-mirror.local"
SEED_USER_DISPLAY_NAME = "기본 사용자"


def upgrade() -> None:
    op.create_table(
        "app_user",
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("id", UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )

    op.create_table(
        "movie_search_cache",
        sa.Column("korean_title", sa.String(500)),
        sa.Column("original_title", sa.String(500), nullable=False),
        sa.Column("popularity", sa.Float, nullable=False),
        sa.Column("synced_at", TIMESTAMP(timezone=True), nullable=False),
        sa.Column("tmdb_id", sa.Integer, nullable=False),
        sa.PrimaryKeyConstraint("tmdb_id"),
    )

    op.create_table(
        "movie_cache",
        sa.Column("enriched_at", TIMESTAMP(timezone=True)),
        sa.Column("korean_title", sa.String(500)),
        sa.Column("original_title", sa.String(500)),
        sa.Column("poster_path", sa.String(500)),
        sa.Column("synced_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("tmdb_id", sa.Integer, nullable=False),
        sa.PrimaryKeyConstraint("tmdb_id"),
    )

    op.create_table(
        "director_cache",
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("synced_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("tmdb_person_id", sa.Integer, nullable=False),
        sa.PrimaryKeyConstraint("tmdb_person_id"),
    )

    op.create_table(
        "movie_director_cache",
        sa.Column("director_tmdb_person_id", sa.Integer, sa.ForeignKey("director_cache.tmdb_person_id"), nullable=False),
        sa.Column("movie_tmdb_id", sa.Integer, sa.ForeignKey("movie_cache.tmdb_id"), nullable=False),
        sa.PrimaryKeyConstraint("director_tmdb_person_id", "movie_tmdb_id"),
    )

    op.create_table(
        "journal_entry",
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("id", UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("rating", sa.NUMERIC(2, 1)),
        sa.Column("short_review", sa.String(500)),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("tmdb_id", sa.Integer, nullable=False),
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("app_user.id"), nullable=False),
        sa.Column("watched_at", TIMESTAMP(timezone=True)),
        sa.CheckConstraint("status IN ('discovered', 'prioritized', 'watched')", name="ck_journal_entry_status"),
        sa.CheckConstraint(
            "rating IS NULL OR (rating >= 0.0 AND rating <= 5.0 AND MOD(rating * 2, 1) = 0)",
            name="ck_journal_entry_rating",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "tmdb_id"),
    )

    op.create_table(
        "review",
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("id", UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "journal_entry_id",
            UUID(as_uuid=True),
            sa.ForeignKey("journal_entry.id"),
            nullable=False,
        ),
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("journal_entry_id"),
    )

    # Side effect: seed 사용자를 삽입하여 인증 stub이 항상 유효한 user_id를 참조할 수 있게 한다.
    op.execute(
        sa.text(
            "INSERT INTO app_user (id, display_name, email) VALUES (:id, :display_name, :email)"
        ).bindparams(
            sa.bindparam("id", value=uuid.UUID(SEED_USER_ID), type_=UUID(as_uuid=True)),
            sa.bindparam("display_name", value=SEED_USER_DISPLAY_NAME),
            sa.bindparam("email", value=SEED_USER_EMAIL),
        )
    )


def downgrade() -> None:
    op.drop_table("review")
    op.drop_table("journal_entry")
    op.drop_table("movie_director_cache")
    op.drop_table("director_cache")
    op.drop_table("movie_cache")
    op.drop_table("movie_search_cache")
    op.drop_table("app_user")
