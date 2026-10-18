import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { ErrorState, Spinner } from "@/components/states";
import { friendlyError } from "@/services/errors";
import { getBook } from "@/services/books";
import type { BookMetadata } from "@/types/books";

type State =
  | { kind: "loading" }
  | { kind: "loaded"; book: BookMetadata }
  | { kind: "error"; message: string };

export function BookDetailPage() {
  const { bookId } = useParams();
  const [state, setState] = useState<State>({ kind: "loading" });

  const load = useCallback(async () => {
    if (!bookId) return;
    setState({ kind: "loading" });
    try {
      const book = await getBook(bookId);
      setState({ kind: "loaded", book });
    } catch (err) {
      setState({
        kind: "error",
        message: friendlyError(err, "We couldn't load this book."),
      });
    }
  }, [bookId]);

  useEffect(() => {
    void load();
  }, [load]);

  if (state.kind === "loading") return <Spinner label="Loading book…" />;
  if (state.kind === "error")
    return <ErrorState message={state.message} onRetry={() => void load()} />;

  const { book } = state;

  return (
    <div>
      <div className="flex gap-6">
        {book.cover_url ? (
          <img
            src={book.cover_url}
            alt=""
            className="h-48 w-32 flex-shrink-0 rounded object-cover shadow-sm"
          />
        ) : (
          <div className="flex h-48 w-32 flex-shrink-0 items-center justify-center rounded bg-slate-100 text-xs text-slate-400">
            No cover
          </div>
        )}
        <div className="min-w-0">
          <h1 className="text-2xl font-semibold">{book.title}</h1>
          <p className="mt-1 text-slate-600">
            {book.authors.join(", ") || "Unknown author"}
          </p>
          {book.published_date && (
            <p className="mt-1 text-sm text-slate-400">
              Published {book.published_date}
            </p>
          )}
          {book.reading_estimate.minutes != null && (
            <p className="mt-3 inline-block rounded bg-slate-100 px-2 py-1 text-sm text-slate-600">
              Original reading time: ~{book.reading_estimate.minutes} min
            </p>
          )}
          {book.categories.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-1">
              {book.categories.map((c) => (
                <span
                  key={c}
                  className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600"
                >
                  {c}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      {book.description && (
        <section className="mt-6">
          <h2 className="text-sm font-medium text-slate-500">Description</h2>
          <p className="mt-1 whitespace-pre-line text-slate-700">
            {book.description}
          </p>
        </section>
      )}

      <section className="mt-6 grid gap-4 sm:grid-cols-2">
        <div>
          <h2 className="text-sm font-medium text-slate-500">Identifiers</h2>
          <ul className="mt-1 text-sm text-slate-600">
            {book.identifiers.isbn_13 && <li>ISBN-13: {book.identifiers.isbn_13}</li>}
            {book.identifiers.isbn_10 && <li>ISBN-10: {book.identifiers.isbn_10}</li>}
            <li className="text-slate-400">Source: {book.provider}</li>
          </ul>
        </div>
        {book.links.length > 0 && (
          <div>
            <h2 className="text-sm font-medium text-slate-500">Links</h2>
            <ul className="mt-1 space-y-1 text-sm">
              {book.links.map((link) => (
                <li key={link.url}>
                  <a
                    href={link.url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-slate-700 underline hover:text-slate-900"
                  >
                    {link.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>

      <section className="mt-8 rounded-lg border border-slate-200 bg-white p-4">
        <h2 className="font-medium">Read this book with Book Companion</h2>
        <p className="mt-1 text-sm text-slate-500">
          To generate an adaptive reading or discuss this book, upload a PDF you
          are authorized to use. These external links are for discovery only.
        </p>
        <a
          href="/library"
          className="mt-3 inline-block rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800"
        >
          Go to My Library to upload
        </a>
      </section>
    </div>
  );
}
