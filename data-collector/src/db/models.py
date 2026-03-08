"""SQLAlchemy Core table definitions."""

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from src.db.metadata import metadata


movie_search_index = Table(
    "movie_search_index",
    metadata,
    Column("tmdb_id", Integer, primary_key=True),
    Column("indexed_at", DateTime(timezone=True), nullable=False, server_default=text("NOW()")),
    Column("korean_title", String(500), nullable=True),
    Column("original_title", String(500), nullable=False),
    Column("popularity", Float, nullable=False),
)

movie = Table(
    "movie",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("enriched_at", DateTime(timezone=True), nullable=True),
    Column("expires_at", DateTime(timezone=True), nullable=True),
    Column("poster_path", String(500), nullable=True),
    Column("tmdb_id", Integer, nullable=False),
    Column("tmdb_metadata", JSONB, nullable=True),
    UniqueConstraint("tmdb_id", name="uq_movie_tmdb_id"),
)

director = Table(
    "director",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")),
    Column("name", String(500), nullable=False),
    Column("tmdb_person_id", Integer, nullable=False),
    UniqueConstraint("tmdb_person_id", name="uq_director_tmdb_person_id"),
)

movie_director = Table(
    "movie_director",
    metadata,
    Column("director_id", UUID(as_uuid=True), ForeignKey("director.id", ondelete="CASCADE"), primary_key=True),
    Column("movie_id", UUID(as_uuid=True), ForeignKey("movie.id", ondelete="CASCADE"), primary_key=True),
)
