"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-03-08 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "movie_search_index",
        sa.Column("tmdb_id", sa.Integer(), nullable=False),
        sa.Column(
            "indexed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("NOW()"),
            nullable=False,
        ),
        sa.Column("korean_title", sa.String(500), nullable=True),
        sa.Column("original_title", sa.String(500), nullable=False),
        sa.Column("popularity", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("tmdb_id"),
    )

    op.create_table(
        "movie",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("enriched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            # Application sets this to enriched_at + CACHE_TTL_DAYS on every upsert.
            nullable=True,
        ),
        sa.Column("poster_path", sa.String(500), nullable=True),
        sa.Column("tmdb_id", sa.Integer(), nullable=False),
        sa.Column("tmdb_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tmdb_id", name="uq_movie_tmdb_id"),
    )

    op.create_table(
        "director",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("tmdb_person_id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tmdb_person_id", name="uq_director_tmdb_person_id"),
    )

    op.create_table(
        "movie_director",
        sa.Column("director_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("movie_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["director_id"], ["director.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["movie_id"], ["movie.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("director_id", "movie_id"),
    )

    # Index on expires_at for cache refresh scheduler queries (WHERE expires_at < NOW() + 7d)
    # Constraint: Partial indexes require IMMUTABLE predicates; NOW() is STABLE so a plain
    # index is used instead — the WHERE clause is applied at query time.
    op.create_index("idx_movies_expires_soon", "movie", ["expires_at"])


def downgrade() -> None:
    op.drop_index("idx_movies_expires_soon", table_name="movie")
    op.drop_table("movie_director")
    op.drop_table("director")
    op.drop_table("movie")
    op.drop_table("movie_search_index")
