import { useState, type FormEvent } from "react";

import { EmptyState, ErrorState, Spinner } from "@/components/states";
import { BookCard } from "@/features/books/BookCard";
import { friendlyError } from "@/services/errors";
import { searchBooks } from "@/services/books";
import type { BookMetadata } from "@/types/books";

type State =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "loaded"; books: BookMetadata[]; query: string }
  | { kind: "error"; message: string };

export function DiscoverPage() {
  const [input, setInput] = useState("");
  const [state, setState] = useState<State>({ kind: "idle" });

  async function runSearch(query: string) {
    const trimmed = query.trim();
    if (!trimmed) return;
    setState({ kind: "loading" });
    try {
      const results = await searchBooks(trimmed);
      setState({ kind: "loaded", books: results.items, query: trimmed });
    } catch (err) {
      setState({
        kind: "error",
        message: friendlyError(err, "Search didn't work. Please try again."),
      });
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    void runSearch(input);
  }

  return (
    <div>
      <h1 className="text-xl font-semibold">Discover Books</h1>
      <p className="mt-1 text-slate-500">Search by title, author, or ISBN.</p>

      <form onSubmit={onSubmit} className="mt-4 flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="e.g. Sapiens, Yuval Noah Harari, 9780062316097"
          className="flex-1 rounded-lg border border-slate-300 px-3 py-2 focus:border-slate-500 focus:outline-none"
        />
        <button
          type="submit"
          className="rounded-lg bg-slate-900 px-4 py-2 font-medium text-white hover:bg-slate-800"
        >
          Search
        </button>
      </form>

      <div className="mt-6">
        {state.kind === "loading" && <Spinner label="Searching…" />}
        {state.kind === "error" && (
          <ErrorState message={state.message} onRetry={() => void runSearch(input)} />
        )}
        {state.kind === "loaded" && state.books.length === 0 && (
          <EmptyState title="No books found">
            Try a different title, author, or ISBN.
          </EmptyState>
        )}
        {state.kind === "loaded" && state.books.length > 0 && (
          <div className="grid gap-3 sm:grid-cols-2">
            {state.books.map((book) => (
              <BookCard key={book.book_id} book={book} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
