import { api } from "./client";

export interface MovieInfo {
  korean_title: string | null;
  original_title: string | null;
  poster_path: string | null;
  tmdb_id: number;
}

export interface DirectorItem {
  name: string;
  tmdb_person_id: number;
}

export interface MovieDetailInfo extends MovieInfo {
  directors: DirectorItem[];
}

export interface JournalEntryItem {
  created_at: string;
  id: string;
  movie: MovieInfo | null;
  rating: number | null;
  short_review: string | null;
  status: string;
  tmdb_id: number;
  updated_at: string;
}

export interface JournalEntryDetail extends Omit<JournalEntryItem, "movie"> {
  movie: MovieDetailInfo | null;
}

export interface JournalListResponse {
  data: JournalEntryItem[];
  has_next: boolean;
  next_cursor: string | null;
}

export async function addToJournal(tmdbId: number): Promise<JournalEntryItem> {
  return api.post("journal", { json: { tmdb_id: tmdbId } }).json<JournalEntryItem>();
}

export async function listJournalEntries(params?: {
  cursor?: string;
  limit?: number;
  status?: string;
}): Promise<JournalListResponse> {
  const searchParams: Record<string, string | number> = {};
  if (params?.cursor) searchParams["cursor"] = params.cursor;
  if (params?.limit) searchParams["limit"] = params.limit;
  if (params?.status) searchParams["status"] = params.status;

  return api.get("journal", { searchParams }).json<JournalListResponse>();
}

export async function getJournalEntry(id: string): Promise<JournalEntryDetail> {
  return api.get(`journal/${id}`).json<JournalEntryDetail>();
}
