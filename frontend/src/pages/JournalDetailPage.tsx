import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { useNavigate, useParams } from "react-router";
import {
  deleteJournalEntry,
  getJournalEntry,
  patchJournalEntry,
} from "../api/journal";
import { StarRating } from "../components/StarRating";
import { STATUS_LABEL, STATUS_TRANSITION_LABEL } from "../utils/journalStatus";

const POLLING_INTERVAL_MS = 3000;
// enrichment 대기 최대 60초
const ENRICHMENT_TIMEOUT_MS = 60_000;

export function JournalDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [shortReviewDraft, setShortReviewDraft] = useState<string | null>(null);
  const [isEditingReview, setIsEditingReview] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  // enrichment 폴링 시작 시각 — movie=null 응답을 받은 첫 시점을 기준으로 타임아웃 측정
  const enrichmentStartRef = useRef<number | null>(null);

  const {
    data: entry,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["journal", id],
    queryFn: () => getJournalEntry(id!),
    refetchInterval: (query) => {
      if (query.state.data?.movie != null) return false;

      if (enrichmentStartRef.current === null) {
        enrichmentStartRef.current = Date.now();
      }
      if (Date.now() - enrichmentStartRef.current > ENRICHMENT_TIMEOUT_MS) {
        return false;
      }
      return POLLING_INTERVAL_MS;
    },
  });

  const patchMutation = useMutation({
    mutationFn: (data: Parameters<typeof patchJournalEntry>[1]) =>
      patchJournalEntry(id!, data),
    onSuccess: (updated) => {
      queryClient.setQueryData(["journal", id], updated);
      queryClient.invalidateQueries({ queryKey: ["journal"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteJournalEntry(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["journal"] });
      navigate("/journal");
    },
  });

  if (isLoading) {
    return <div className="text-center py-12 text-gray-400">불러오는 중...</div>;
  }

  if (isError || !entry) {
    return (
      <div className="text-center py-12 text-gray-400">
        항목을 불러올 수 없습니다.
      </div>
    );
  }

  const title =
    entry.movie?.korean_title ??
    entry.movie?.original_title ??
    `TMDB #${entry.tmdb_id}`;

  // 서버가 권위적 소스 — 허용 전이를 로컬 복사본 없이 응답값으로 결정
  const allowedTransitions = entry.allowed_transitions;

  function handleReviewSave() {
    patchMutation.mutate({ short_review: shortReviewDraft });
    setIsEditingReview(false);
    setShortReviewDraft(null);
  }

  function handleReviewCancel() {
    setIsEditingReview(false);
    setShortReviewDraft(null);
  }

  return (
    <div>
      <button
        onClick={() => navigate("/journal")}
        className="text-sm text-gray-500 hover:text-gray-700 mb-6"
      >
        ← 저널 목록
      </button>

      <div className="bg-white rounded-lg border border-gray-200 p-6 space-y-6">
        {entry.movie == null ? (
          <div>
            <div className="animate-pulse space-y-3">
              <div className="h-6 bg-gray-200 rounded w-3/4" />
              <div className="h-4 bg-gray-200 rounded w-1/2" />
            </div>
            <p className="text-sm text-gray-400 mt-4">
              영화 정보를 불러오는 중입니다...
            </p>
          </div>
        ) : (
          <div className="flex gap-6">
            {entry.movie.poster_path && (
              <img
                src={`https://image.tmdb.org/t/p/w185${entry.movie.poster_path}`}
                alt={title}
                className="w-32 rounded flex-shrink-0"
              />
            )}
            <div className="flex-1">
              <h1 className="text-2xl font-bold text-gray-900 mb-1">{title}</h1>
              {entry.movie.korean_title &&
                entry.movie.original_title &&
                entry.movie.korean_title !== entry.movie.original_title && (
                  <p className="text-gray-500 mb-3">
                    {entry.movie.original_title}
                  </p>
                )}
              {entry.movie.directors.length > 0 && (
                <p className="text-sm text-gray-600 mb-3">
                  감독: {entry.movie.directors.map((d) => d.name).join(", ")}
                </p>
              )}
            </div>
          </div>
        )}

        {/* 상태 */}
        <div>
          <p className="text-sm font-medium text-gray-500 mb-2">상태</p>
          <div className="flex items-center gap-2 flex-wrap">
            <span className="inline-block text-sm bg-gray-100 text-gray-600 px-3 py-1 rounded-full">
              {STATUS_LABEL[entry.status] ?? entry.status}
            </span>
            {allowedTransitions.map((nextStatus) => (
              <button
                key={nextStatus}
                type="button"
                disabled={patchMutation.isPending}
                onClick={() => patchMutation.mutate({ status: nextStatus })}
                className="text-sm bg-blue-50 text-blue-600 hover:bg-blue-100 px-3 py-1 rounded-full disabled:opacity-50"
              >
                {STATUS_TRANSITION_LABEL[nextStatus] ?? nextStatus}
              </button>
            ))}
          </div>
          {patchMutation.isError && (
            <p className="text-xs text-red-500 mt-1">
              변경에 실패했습니다. 다시 시도해 주세요.
            </p>
          )}
        </div>

        {/* 별점 */}
        <div>
          <p className="text-sm font-medium text-gray-500 mb-2">평점</p>
          <StarRating
            value={entry.rating}
            onChange={(rating) => patchMutation.mutate({ rating })}
          />
        </div>

        {/* 한줄평 */}
        <div>
          <p className="text-sm font-medium text-gray-500 mb-2">한줄평</p>
          {isEditingReview ? (
            <div className="space-y-2">
              <textarea
                value={shortReviewDraft ?? ""}
                onChange={(e) => setShortReviewDraft(e.target.value)}
                maxLength={500}
                rows={3}
                className="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-blue-400"
                placeholder="한줄평을 입력하세요 (최대 500자)"
                autoFocus
              />
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={handleReviewSave}
                  disabled={patchMutation.isPending}
                  className="text-sm bg-blue-600 text-white px-3 py-1 rounded hover:bg-blue-700 disabled:opacity-50"
                >
                  저장
                </button>
                <button
                  type="button"
                  onClick={handleReviewCancel}
                  className="text-sm text-gray-500 hover:text-gray-700 px-3 py-1"
                >
                  취소
                </button>
              </div>
            </div>
          ) : (
            <div className="flex items-start gap-2">
              <p
                className={
                  entry.short_review
                    ? "text-gray-700 text-sm"
                    : "text-gray-400 text-sm"
                }
              >
                {entry.short_review ?? "한줄평이 없습니다."}
              </p>
              <button
                type="button"
                onClick={() => {
                  setShortReviewDraft(entry.short_review ?? "");
                  setIsEditingReview(true);
                }}
                className="text-xs text-blue-500 hover:text-blue-700 flex-shrink-0"
              >
                편집
              </button>
              {entry.short_review && (
                <button
                  type="button"
                  onClick={() => patchMutation.mutate({ short_review: null })}
                  className="text-xs text-gray-400 hover:text-red-500 flex-shrink-0"
                >
                  삭제
                </button>
              )}
            </div>
          )}
        </div>

        {/* 삭제 */}
        <div className="pt-4 border-t border-gray-100">
          {showDeleteConfirm ? (
            <div className="flex items-center gap-3">
              <p className="text-sm text-gray-600">정말 삭제하시겠습니까?</p>
              <button
                type="button"
                onClick={() => deleteMutation.mutate()}
                disabled={deleteMutation.isPending}
                className="text-sm bg-red-600 text-white px-3 py-1 rounded hover:bg-red-700 disabled:opacity-50"
              >
                삭제
              </button>
              <button
                type="button"
                onClick={() => setShowDeleteConfirm(false)}
                className="text-sm text-gray-500 hover:text-gray-700"
              >
                취소
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setShowDeleteConfirm(true)}
              className="text-sm text-red-500 hover:text-red-700"
            >
              저널에서 삭제
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
