import { useQuery } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router";
import { getJournalEntry } from "../api/journal";
import { STATUS_LABEL } from "../utils/journalStatus";

const POLLING_INTERVAL_MS = 3000;
const MAX_ENRICHMENT_POLL_COUNT = 20; // 최대 60초 (3초 × 20)

export function JournalDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const { data: entry, isLoading, isError } = useQuery({
    queryKey: ["journal", id],
    queryFn: () => getJournalEntry(id!),
    // enrichment 미완료 시 최대 MAX_ENRICHMENT_POLL_COUNT회 폴링
    refetchInterval: (query) => {
      if (query.state.data?.movie != null) return false;
      if ((query.state.fetchFailureCount ?? 0) >= MAX_ENRICHMENT_POLL_COUNT) return false;
      return POLLING_INTERVAL_MS;
    },
  });

  if (isLoading) {
    return <div className="text-center py-12 text-gray-400">불러오는 중...</div>;
  }

  if (isError || !entry) {
    return (
      <div className="text-center py-12 text-gray-400">항목을 불러올 수 없습니다.</div>
    );
  }

  const title =
    entry.movie?.korean_title ??
    entry.movie?.original_title ??
    `TMDB #${entry.tmdb_id}`;

  return (
    <div>
      <button
        onClick={() => navigate("/journal")}
        className="text-sm text-gray-500 hover:text-gray-700 mb-6"
      >
        ← 저널 목록
      </button>

      <div className="bg-white rounded-lg border border-gray-200 p-6">
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
                  <p className="text-gray-500 mb-3">{entry.movie.original_title}</p>
                )}
              {entry.movie.directors.length > 0 && (
                <p className="text-sm text-gray-600 mb-3">
                  감독: {entry.movie.directors.map((d) => d.name).join(", ")}
                </p>
              )}
              <span className="inline-block text-sm bg-gray-100 text-gray-600 px-3 py-1 rounded-full">
                {STATUS_LABEL[entry.status] ?? entry.status}
              </span>
              {entry.rating != null && (
                <p className="mt-3 text-yellow-500">★ {entry.rating}</p>
              )}
              {entry.short_review && (
                <p className="mt-3 text-gray-700">{entry.short_review}</p>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
