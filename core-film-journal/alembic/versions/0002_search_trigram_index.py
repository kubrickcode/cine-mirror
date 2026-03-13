"""movie_search_cache ILIKE 성능을 위한 pg_trgm GIN 인덱스

leading wildcard 패턴(%query%)은 B-tree 인덱스를 활용할 수 없으므로
pg_trgm 확장과 GIN 인덱스를 추가하여 full-table scan을 방지한다.

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-13

"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_movie_search_cache_korean_title_trgm
        ON movie_search_cache
        USING GIN (korean_title gin_trgm_ops)
        WHERE korean_title IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_movie_search_cache_original_title_trgm
        ON movie_search_cache
        USING GIN (original_title gin_trgm_ops)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_movie_search_cache_korean_title_trgm")
    op.execute("DROP INDEX IF EXISTS ix_movie_search_cache_original_title_trgm")
