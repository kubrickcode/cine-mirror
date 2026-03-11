"""SQLAlchemy Core 테이블 정의."""

from sqlalchemy import (
    NUMERIC,
    CheckConstraint,
    Column,
    Float,
    ForeignKey,
    Integer,
    PrimaryKeyConstraint,
    String,
    Table,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import TIMESTAMP, UUID

from src.db.metadata import metadata

_now = text("NOW()")
_gen_uuid = text("gen_random_uuid()")

app_user = Table(
    "app_user",
    metadata,
    Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=_now),
    Column("display_name", String(100), nullable=False),
    Column("email", String(255), nullable=False),
    Column("id", UUID(as_uuid=True), nullable=False, server_default=_gen_uuid),
    PrimaryKeyConstraint("id"),
    UniqueConstraint("email"),
)

movie_search_cache = Table(
    "movie_search_cache",
    metadata,
    Column("korean_title", String(500)),
    Column("original_title", String(500), nullable=False),
    Column("popularity", Float, nullable=False),
    Column("synced_at", TIMESTAMP(timezone=True), nullable=False),
    Column("tmdb_id", Integer, nullable=False),
    PrimaryKeyConstraint("tmdb_id"),
)

movie_cache = Table(
    "movie_cache",
    metadata,
    Column("enriched_at", TIMESTAMP(timezone=True)),
    Column("korean_title", String(500)),
    Column("original_title", String(500)),
    Column("poster_path", String(500)),
    Column("synced_at", TIMESTAMP(timezone=True), nullable=False, server_default=_now),
    Column("tmdb_id", Integer, nullable=False),
    PrimaryKeyConstraint("tmdb_id"),
)

director_cache = Table(
    "director_cache",
    metadata,
    Column("name", String(500), nullable=False),
    Column("synced_at", TIMESTAMP(timezone=True), nullable=False, server_default=_now),
    Column("tmdb_person_id", Integer, nullable=False),
    PrimaryKeyConstraint("tmdb_person_id"),
)

movie_director_cache = Table(
    "movie_director_cache",
    metadata,
    Column(
        "director_tmdb_person_id",
        Integer,
        ForeignKey("director_cache.tmdb_person_id"),
        nullable=False,
    ),
    Column(
        "movie_tmdb_id",
        Integer,
        ForeignKey("movie_cache.tmdb_id"),
        nullable=False,
    ),
    PrimaryKeyConstraint("director_tmdb_person_id", "movie_tmdb_id"),
)

_rating_check = (
    "rating IS NULL OR (rating >= 0.0 AND rating <= 5.0 AND MOD(rating * 2, 1) = 0)"
)
_status_check = "status IN ('discovered', 'prioritized', 'watched')"

journal_entry = Table(
    "journal_entry",
    metadata,
    Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=_now),
    Column("id", UUID(as_uuid=True), nullable=False, server_default=_gen_uuid),
    Column("rating", NUMERIC(2, 1)),
    Column("short_review", String(500)),
    Column("status", String(20), nullable=False),
    Column("tmdb_id", Integer, nullable=False),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=_now),
    Column("user_id", UUID(as_uuid=True), ForeignKey("app_user.id"), nullable=False),
    Column("watched_at", TIMESTAMP(timezone=True)),
    CheckConstraint(_status_check, name="ck_journal_entry_status"),
    CheckConstraint(_rating_check, name="ck_journal_entry_rating"),
    PrimaryKeyConstraint("id"),
    UniqueConstraint("user_id", "tmdb_id"),
)

review = Table(
    "review",
    metadata,
    Column("content", Text, nullable=False),
    Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=_now),
    Column("id", UUID(as_uuid=True), nullable=False, server_default=_gen_uuid),
    Column(
        "journal_entry_id",
        UUID(as_uuid=True),
        ForeignKey("journal_entry.id"),
        nullable=False,
    ),
    Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=_now),
    PrimaryKeyConstraint("id"),
    UniqueConstraint("journal_entry_id"),
)
