import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { listJournalEntries, type JournalEntryItem } from "../api/journal";
import { STATUS_LABEL } from "../utils/journalStatus";

export function JournalPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["journal"],
    queryFn: () => listJournalEntries(),
  });

  const entries = data?.data ?? [];

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">내 영화 저널</h1>
        <Link to="/search" className="text-sm text-blue-600 hover:text-blue-800">
          + 영화 추가
        </Link>
      </div>

      {isLoading && (
        <div className="text-center py-12 text-gray-400">불러오는 중...</div>
      )}

      {isError && (
        <div className="text-center py-12 text-red-400">
          저널을 불러올 수 없습니다. 잠시 후 다시 시도해 주세요.
        </div>
      )}

      {!isLoading && !isError && entries.length === 0 && (
        <div className="text-center py-12 text-gray-400">
          <p>아직 기록된 영화가 없습니다.</p>
          <Link to="/search" className="text-blue-600 mt-2 inline-block">
            영화 검색하기
          </Link>
        </div>
      )}

      <ul className="space-y-3">
        {entries.map((entry) => (
          <JournalEntryCard key={entry.id} entry={entry} />
        ))}
      </ul>
    </div>
  );
}

function JournalEntryCard({ entry }: { entry: JournalEntryItem }) {
  const title =
    entry.movie?.korean_title ??
    entry.movie?.original_title ??
    `TMDB #${entry.tmdb_id}`;

  return (
    <li>
      <Link
        to={`/journal/${entry.id}`}
        className="block p-4 bg-white rounded-lg border border-gray-200 hover:border-gray-300 transition-colors"
      >
        <div className="flex items-start gap-4">
          {entry.movie?.poster_path ? (
            <img
              src={`https://image.tmdb.org/t/p/w92${entry.movie.poster_path}`}
              alt={title}
              className="w-12 rounded flex-shrink-0"
            />
          ) : (
            <div className="w-12 h-16 bg-gray-100 rounded flex-shrink-0" />
          )}
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 mb-1">
              <span className="font-medium text-gray-900 truncate">{title}</span>
              <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded-full flex-shrink-0">
                {STATUS_LABEL[entry.status] ?? entry.status}
              </span>
            </div>
            {entry.rating != null && (
              <div className="text-sm text-yellow-500">★ {entry.rating}</div>
            )}
            {entry.short_review && (
              <p className="text-sm text-gray-500 mt-1 truncate">{entry.short_review}</p>
            )}
          </div>
        </div>
      </Link>
    </li>
  );
}
