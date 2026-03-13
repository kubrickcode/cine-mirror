"""저널 API 라우터."""

import base64
import binascii
import json
import logging
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import delete, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import get_current_user_id, get_session
from src.db.models import (
    director_cache,
    journal_entry,
    movie_cache,
    movie_director_cache,
    review,
)
from src.domain.rating import InvalidRatingError, validate_rating
from src.domain.status import (
    InvalidTransitionError,
    get_allowed_transitions,
    transition_status,
)
from src.events.publisher import publish_enrich_requested

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/journal", tags=["journal"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
UserIdDep = Annotated[UUID, Depends(get_current_user_id)]

JournalStatus = Literal["discovered", "prioritized", "watched"]


class CreateJournalRequest(BaseModel):
    """저널 항목 생성 요청."""

    tmdb_id: int


class DirectorItem(BaseModel):
    """감독 정보."""

    name: str
    tmdb_person_id: int


class MovieInfo(BaseModel):
    """영화 기본 정보."""

    korean_title: str | None
    original_title: str | None
    poster_path: str | None
    tmdb_id: int


class MovieDetailInfo(MovieInfo):
    """영화 상세 정보 (감독 포함)."""

    directors: list[DirectorItem]


class JournalEntryItem(BaseModel):
    """저널 항목 (목록용)."""

    created_at: datetime
    id: UUID
    movie: MovieInfo | None
    rating: float | None
    short_review: str | None
    status: JournalStatus
    tmdb_id: int
    updated_at: datetime


class JournalEntryDetail(BaseModel):
    """저널 항목 상세."""

    allowed_transitions: list[str]
    created_at: datetime
    id: UUID
    movie: MovieDetailInfo | None
    rating: float | None
    short_review: str | None
    status: JournalStatus
    tmdb_id: int
    updated_at: datetime


class JournalListResponse(BaseModel):
    """저널 목록 응답."""

    data: list[JournalEntryItem]
    has_next: bool
    next_cursor: str | None


class PatchJournalRequest(BaseModel):
    """저널 항목 부분 수정 요청."""

    rating: float | None = None
    short_review: str | None = Field(None, max_length=500)
    status: str | None = None


def _encode_cursor(updated_at: datetime, entry_id: UUID) -> str:
    raw = json.dumps({"id": str(entry_id), "updated_at": updated_at.isoformat()})
    return base64.urlsafe_b64encode(raw.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        data = json.loads(raw)
        return datetime.fromisoformat(data["updated_at"]), UUID(data["id"])
    except (binascii.Error, json.JSONDecodeError, KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=400, detail="유효하지 않은 cursor입니다."
        ) from exc


@router.post("", status_code=201, response_model=JournalEntryItem)
async def create_journal_entry(
    body: CreateJournalRequest,
    session: SessionDep,
    user_id: UserIdDep,
) -> JournalEntryItem:
    """영화를 저널에 추가한다.

    movie_cache에 해당 영화가 없으면 movie.enrich_requested 이벤트를 발행한다.
    같은 영화가 이미 저널에 있으면 409 Conflict.
    """
    cached = await session.execute(
        select(movie_cache.c.tmdb_id).where(movie_cache.c.tmdb_id == body.tmdb_id)
    )
    needs_enrichment = cached.scalar_one_or_none() is None

    stmt = (
        insert(journal_entry)
        .values(
            status="discovered",
            tmdb_id=body.tmdb_id,
            user_id=user_id,
        )
        .returning(
            journal_entry.c.created_at,
            journal_entry.c.id,
            journal_entry.c.rating,
            journal_entry.c.short_review,
            journal_entry.c.status,
            journal_entry.c.tmdb_id,
            journal_entry.c.updated_at,
        )
    )
    try:
        row = (await session.execute(stmt)).mappings().one()
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=409, detail="이미 저널에 추가된 영화입니다."
        ) from exc

    # Side effect: 커밋 성공 후 발행 — DB 롤백 시 불필요한 enrichment 요청 방지
    if needs_enrichment:
        await publish_enrich_requested(body.tmdb_id)

    return JournalEntryItem(
        created_at=row["created_at"],
        id=row["id"],
        movie=None,
        rating=float(row["rating"]) if row["rating"] is not None else None,
        short_review=row["short_review"],
        status=row["status"],
        tmdb_id=row["tmdb_id"],
        updated_at=row["updated_at"],
    )


@router.get("", response_model=JournalListResponse)
async def list_journal_entries(
    session: SessionDep,
    user_id: UserIdDep,
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    status: Annotated[JournalStatus | None, Query()] = None,
) -> JournalListResponse:
    """저널 항목 목록 (커서 기반 페이지네이션, updated_at DESC)."""
    je = journal_entry
    mc = movie_cache

    query = (
        select(
            je.c.created_at,
            je.c.id,
            je.c.rating,
            je.c.short_review,
            je.c.status,
            je.c.tmdb_id,
            je.c.updated_at,
            mc.c.korean_title.label("movie_korean_title"),
            mc.c.original_title.label("movie_original_title"),
            mc.c.poster_path.label("movie_poster_path"),
            mc.c.tmdb_id.label("movie_tmdb_id"),
        )
        .select_from(je.outerjoin(mc, je.c.tmdb_id == mc.c.tmdb_id))
        .where(je.c.user_id == user_id)
        .order_by(je.c.updated_at.desc(), je.c.id.desc())
        .limit(limit + 1)
    )

    if status is not None:
        query = query.where(je.c.status == status)

    if cursor is not None:
        cursor_updated_at, cursor_id = _decode_cursor(cursor)
        query = query.where(
            (je.c.updated_at < cursor_updated_at)
            | ((je.c.updated_at == cursor_updated_at) & (je.c.id < cursor_id))
        )

    rows = (await session.execute(query)).mappings().all()
    has_next = len(rows) > limit
    page_rows = rows[:limit]

    items = [
        JournalEntryItem(
            created_at=row["created_at"],
            id=row["id"],
            movie=MovieInfo(
                korean_title=row["movie_korean_title"],
                original_title=row["movie_original_title"],
                poster_path=row["movie_poster_path"],
                tmdb_id=row["tmdb_id"],
            )
            if row["movie_tmdb_id"] is not None
            else None,
            rating=float(row["rating"]) if row["rating"] is not None else None,
            short_review=row["short_review"],
            status=row["status"],
            tmdb_id=row["tmdb_id"],
            updated_at=row["updated_at"],
        )
        for row in page_rows
    ]

    next_cursor = (
        _encode_cursor(page_rows[-1]["updated_at"], page_rows[-1]["id"])
        if has_next
        else None
    )

    return JournalListResponse(data=items, has_next=has_next, next_cursor=next_cursor)


@router.get("/{entry_id}", response_model=JournalEntryDetail)
async def get_journal_entry(
    entry_id: UUID,
    session: SessionDep,
    user_id: UserIdDep,
) -> JournalEntryDetail:
    """저널 항목 상세 조회 (movie_cache + director_cache LEFT JOIN)."""
    row = await _fetch_entry_row(session, entry_id, user_id)
    if row is None:
        raise HTTPException(status_code=404, detail="저널 항목을 찾을 수 없습니다.")

    directors = await _fetch_directors(session, row["tmdb_id"])
    return _build_entry_detail(row, directors)


async def _fetch_entry_row(
    session: AsyncSession, entry_id: UUID, user_id: UUID
) -> dict | None:
    """저널 항목 + movie_cache 조인 행을 조회한다."""
    je = journal_entry
    mc = movie_cache
    row = (
        await session.execute(
            select(
                je.c.created_at,
                je.c.id,
                je.c.rating,
                je.c.short_review,
                je.c.status,
                je.c.tmdb_id,
                je.c.updated_at,
                mc.c.korean_title.label("movie_korean_title"),
                mc.c.original_title.label("movie_original_title"),
                mc.c.poster_path.label("movie_poster_path"),
                mc.c.tmdb_id.label("movie_tmdb_id"),
            )
            .select_from(je.outerjoin(mc, je.c.tmdb_id == mc.c.tmdb_id))
            .where(je.c.id == entry_id, je.c.user_id == user_id)
        )
    ).mappings().one_or_none()
    return dict(row) if row is not None else None


async def _fetch_directors(session: AsyncSession, tmdb_id: int) -> list[DirectorItem]:
    """movie의 감독 목록을 조회한다."""
    dc = director_cache
    mdc = movie_director_cache
    rows = (
        await session.execute(
            select(dc.c.name, dc.c.tmdb_person_id)
            .select_from(
                mdc.join(dc, mdc.c.director_tmdb_person_id == dc.c.tmdb_person_id)
            )
            .where(mdc.c.movie_tmdb_id == tmdb_id)
        )
    ).mappings().all()
    return [
        DirectorItem(name=r["name"], tmdb_person_id=r["tmdb_person_id"])
        for r in rows
    ]


def _build_entry_detail(row: dict, directors: list[DirectorItem]) -> JournalEntryDetail:
    """DB 행 + 감독 목록으로 JournalEntryDetail을 생성한다."""
    movie_detail = (
        MovieDetailInfo(
            directors=directors,
            korean_title=row["movie_korean_title"],
            original_title=row["movie_original_title"],
            poster_path=row["movie_poster_path"],
            tmdb_id=row["tmdb_id"],
        )
        if row["movie_tmdb_id"] is not None
        else None
    )
    return JournalEntryDetail(
        allowed_transitions=get_allowed_transitions(row["status"]),
        created_at=row["created_at"],
        id=row["id"],
        movie=movie_detail,
        rating=float(row["rating"]) if row["rating"] is not None else None,
        short_review=row["short_review"],
        status=row["status"],
        tmdb_id=row["tmdb_id"],
        updated_at=row["updated_at"],
    )


@router.patch("/{entry_id}", response_model=JournalEntryDetail)
async def patch_journal_entry(
    entry_id: UUID,
    body: PatchJournalRequest,
    session: SessionDep,
    user_id: UserIdDep,
) -> JournalEntryDetail:
    """저널 항목을 부분 수정한다 (status, rating, short_review).

    상태 전이 규칙 위반 시 422 + 허용 전이 목록 반환.
    평점 규칙 위반 시 422.
    """
    row = await _fetch_entry_row(session, entry_id, user_id)
    if row is None:
        raise HTTPException(status_code=404, detail="저널 항목을 찾을 수 없습니다.")

    patch_fields: dict[str, object] = {}
    provided = body.model_fields_set

    if "status" in provided:
        if body.status is None:
            raise HTTPException(
                status_code=422,
                detail={"message": "status는 null일 수 없습니다."},
            )
        try:
            new_status = transition_status(row["status"], body.status)
        except InvalidTransitionError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "message": str(exc),
                    "allowed_transitions": exc.allowed,
                },
            ) from exc
        patch_fields["status"] = new_status

    if "rating" in provided:
        try:
            validate_rating(body.rating)
        except InvalidRatingError as exc:
            raise HTTPException(
                status_code=422,
                detail={"message": str(exc)},
            ) from exc
        patch_fields["rating"] = body.rating

    if "short_review" in provided:
        patch_fields["short_review"] = body.short_review

    if patch_fields:
        patch_fields["updated_at"] = text("NOW()")
        await session.execute(
            update(journal_entry)
            .where(
                journal_entry.c.id == entry_id,
                journal_entry.c.user_id == user_id,
            )
            .values(**patch_fields)
        )
        await session.commit()
        # 업데이트 후 최신 상태를 movie_cache 조인으로 재조회
        row = await _fetch_entry_row(session, entry_id, user_id)
        if row is None:
            raise HTTPException(status_code=404, detail="저널 항목을 찾을 수 없습니다.")

    directors = await _fetch_directors(session, row["tmdb_id"])
    return _build_entry_detail(row, directors)


@router.delete("/{entry_id}", status_code=204)
async def delete_journal_entry(
    entry_id: UUID,
    session: SessionDep,
    user_id: UserIdDep,
) -> None:
    """저널 항목 + 연관 review를 cascade 삭제한다."""
    row = (
        await session.execute(
            select(journal_entry.c.id).where(
                journal_entry.c.id == entry_id,
                journal_entry.c.user_id == user_id,
            )
        )
    ).mappings().one_or_none()

    if row is None:
        raise HTTPException(status_code=404, detail="저널 항목을 찾을 수 없습니다.")

    # Constraint: review.journal_entry_id FK에 ON DELETE CASCADE 없음 — 수동 삭제
    await session.execute(
        delete(review).where(review.c.journal_entry_id == entry_id)
    )
    await session.execute(
        delete(journal_entry).where(journal_entry.c.id == entry_id)
    )
    await session.commit()
