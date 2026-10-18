import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { useAuth } from "@/features/auth/useAuth";
import { deleteBook } from "@/services/books";
import { listConversations } from "@/services/discussions";
import { friendlyError } from "@/services/errors";
import { getProgress } from "@/services/progress";
import { removeUploadedBook, type UploadedBook } from "@/stores/uploadedBooks";
import { READING_MODES } from "@/types/reading";
import type { ProgressResponse } from "@/types/progress";

function modeLabel(mode: string | null | undefined): string | null {
  if (!mode) return null;
  return READING_MODES.find((m) => m.value === mode)?.label ?? mode;
}

export function LibraryBookRow({
  book,
  onRemoved,
}: {
  book: UploadedBook;
  onRemoved?: () => void;
}) {
  const { user } = useAuth();
  const [progress, setProgress] = useState<ProgressResponse | null>(null);
  const [hasDiscussions, setHasDiscussions] = useState(false);
  const [removing, setRemoving] = useState(false);
  const [removeError, setRemoveError] = useState<string | null>(null);

  async function handleRemove() {
    if (!user) return;
    const ok = window.confirm(
      `Remove "${book.title}"? This permanently deletes the book and its readings and discussions. This can't be undone.`,
    );
    if (!ok) return;
    setRemoving(true);
    setRemoveError(null);
    try {
      await deleteBook(book.bookId);
      removeUploadedBook(user.userId, book.bookId);
      onRemoved?.();
    } catch (err) {
      setRemoving(false);
      setRemoveError(
        friendlyError(err, "We couldn't remove this book. Please try again."),
      );
    }
  }

  useEffect(() => {
    let cancelled = false;
    getProgress(book.bookId)
      .then((p) => {
        if (!cancelled) setProgress(p);
      })
      .catch(() => {});
    // Does this book already have discussions? If so, offer a "Discussions"
    // shortcut to the thread list.
    listConversations(book.bookId)
      .then((convos) => {
        if (!cancelled) setHasDiscussions(convos.length > 0);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [book.bookId]);

  const resumeLabel = modeLabel(progress?.selected_mode);

  return (
    <li className="rounded-lg border border-slate-200 bg-white p-3">
      <div className="flex items-center justify-between">
        <div className="min-w-0">
          <p className="truncate font-medium">{book.title}</p>
          <p className="text-xs text-slate-400">
            Uploaded {new Date(book.uploadedAt).toLocaleDateString()}
            {progress && (
              <>
                {" · "}
                {progress.completed
                  ? "Completed"
                  : resumeLabel
                    ? `Last read: ${resumeLabel}`
                    : "In progress"}
              </>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <Link
            to={`/reading/new?book=${encodeURIComponent(book.bookId)}`}
            className="rounded bg-slate-900 px-3 py-1.5 font-medium text-white hover:bg-slate-800"
          >
            {progress && !progress.completed ? "Continue reading" : "Read"}
          </Link>
          <Link
            to={`/discussions/new?book=${encodeURIComponent(book.bookId)}`}
            className="rounded border border-slate-300 px-3 py-1.5 text-slate-700 hover:bg-slate-100"
          >
            {hasDiscussions ? "Discussions" : "Discuss"}
          </Link>
          <button
            onClick={() => void handleRemove()}
            disabled={removing}
            aria-label="Remove"
            title="Remove"
            className="group relative flex h-9 w-9 items-center justify-center rounded-full text-slate-400 hover:bg-rose-50 hover:text-rose-600 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {removing ? (
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-slate-500" />
            ) : (
              <>
                <svg
                  viewBox="0 0 20 20"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  className="h-4 w-4"
                  aria-hidden="true"
                >
                  <path d="M5 5l10 10M15 5L5 15" />
                </svg>
                <span className="pointer-events-none absolute -top-7 right-0 whitespace-nowrap rounded bg-slate-900 px-2 py-0.5 text-xs text-white opacity-0 transition-opacity group-hover:opacity-100">
                  Remove
                </span>
              </>
            )}
          </button>
        </div>
      </div>
      {removeError && (
        <p className="mt-2 text-xs text-rose-600">{removeError}</p>
      )}
    </li>
  );
}
