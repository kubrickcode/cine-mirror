import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { searchMovies, type MovieSearchItem } from "../api/search";

const DEBOUNCE_MS = 300;

export function SearchPage() {
  const [inputValue, setInputValue] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(inputValue.trim());
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [inputValue]);

  const { data: results = [], isFetching } = useQuery({
    queryKey: ["movies", "search", debouncedQuery],
    queryFn: () => searchMovies(debouncedQuery),
    enabled: debouncedQuery.length > 0,
    staleTime: 30_000,
  });

  const showDropdown = debouncedQuery.length > 0;

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">영화 검색</h1>

      <div className="relative">
        <input
          type="text"
          role="combobox"
          placeholder="영화 제목을 입력하세요 (한글 또는 영문)"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          className="w-full px-4 py-3 border border-gray-300 rounded-lg text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          aria-label="영화 검색"
          aria-autocomplete="list"
          aria-expanded={showDropdown && results.length > 0}
          aria-controls="search-listbox"
        />

        {showDropdown && (
          <div
            id="search-listbox"
            role="listbox"
            aria-label="검색 결과"
            className={`absolute top-full left-0 right-0 z-10 mt-1 bg-white border border-gray-200 rounded-lg shadow-lg overflow-hidden transition-opacity ${isFetching ? "opacity-60" : "opacity-100"}`}
          >
            {isFetching && results.length === 0 && (
              <div className="px-4 py-3 text-sm text-gray-500">검색 중…</div>
            )}
            {!isFetching && results.length === 0 && (
              <div className="px-4 py-3 text-sm text-gray-500">
                검색 결과가 없습니다.
              </div>
            )}
            {results.map((movie) => (
              <MovieResultItem key={movie.tmdb_id} movie={movie} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function MovieResultItem({ movie }: { movie: MovieSearchItem }) {
  const displayTitle = movie.korean_title ?? movie.original_title;
  const subTitle =
    movie.korean_title && movie.korean_title !== movie.original_title
      ? movie.original_title
      : null;

  return (
    <div
      role="option"
      aria-selected={false}
      tabIndex={0}
      className="px-4 py-3 hover:bg-gray-50 cursor-pointer border-b border-gray-100 last:border-0 focus:outline-none focus:bg-gray-50"
    >
      <div className="font-medium text-gray-900">{displayTitle}</div>
      {subTitle && (
        <div className="text-sm text-gray-500 mt-0.5">{subTitle}</div>
      )}
    </div>
  );
}
