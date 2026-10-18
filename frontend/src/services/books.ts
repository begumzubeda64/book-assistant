import { apiFetch } from "@/services/api";
import type { BookMetadata, BookSearchResults } from "@/types/books";

export function searchBooks(
  query: string,
  limit = 20,
): Promise<BookSearchResults> {
  const params = new URLSearchParams({ q: query, limit: String(limit) });
  return apiFetch<BookSearchResults>(`/api/v1/books/search?${params}`);
}

export function getBook(bookId: string): Promise<BookMetadata> {
  return apiFetch<BookMetadata>(`/api/v1/books/${encodeURIComponent(bookId)}`);
}

/** Delete all of the user's content for a book (returns 204). */
export function deleteBook(bookId: string): Promise<void> {
  return apiFetch<void>(`/api/v1/books/${encodeURIComponent(bookId)}`, {
    method: "DELETE",
  });
}
