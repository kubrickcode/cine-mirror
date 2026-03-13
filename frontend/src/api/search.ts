import { api } from "./client";

export interface MovieSearchItem {
  korean_title: string | null;
  original_title: string;
  popularity: number;
  tmdb_id: number;
}

export async function searchMovies(
  query: string,
  limit = 10
): Promise<MovieSearchItem[]> {
  if (!query.trim()) return [];

  return api
    .get("movies/search", { searchParams: { q: query, limit } })
    .json<MovieSearchItem[]>();
}
