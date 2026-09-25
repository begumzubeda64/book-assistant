import { Link } from "react-router-dom";

import type { BookMetadata } from "@/types/books";

export function BookCard({ book }: { book: BookMetadata }) {
  return (
    <Link
      to={`/books/${encodeURIComponent(book.book_id)}`}
      className="flex gap-3 rounded-lg border border-slate-200 bg-white p-3 hover:border-slate-300 hover:shadow-sm"
    >
      {book.cover_url ? (
        <img
          src={book.cover_url}
          alt=""
          className="h-24 w-16 flex-shrink-0 rounded object-cover"
        />
      ) : (
        <div className="flex h-24 w-16 flex-shrink-0 items-center justify-center rounded bg-slate-100 text-xs text-slate-400">
          No cover
        </div>
      )}
      <div className="min-w-0">
        <p className="truncate font-medium">{book.title}</p>
        <p className="truncate text-sm text-slate-500">
          {book.authors.join(", ") || "Unknown author"}
        </p>
        {book.reading_estimate.minutes != null && (
          <p className="mt-1 text-xs text-slate-400">
            ~{book.reading_estimate.minutes} min to read the original
          </p>
        )}
      </div>
    </Link>
  );
}
