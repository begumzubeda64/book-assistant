import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { BackLink } from "@/components/BackLink";
import { ErrorState, Spinner } from "@/components/states";
import { useAuth } from "@/features/auth/useAuth";
import { friendlyError } from "@/services/errors";
import {
  createConversation,
  listConversations,
  type ConversationSummary,
} from "@/services/discussions";
import { getUploadedBook } from "@/stores/uploadedBooks";

function formatWhen(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function DiscussionStartPage() {
  const [params] = useSearchParams();
  const bookId = params.get("book") ?? "";
  const navigate = useNavigate();
  const { user } = useAuth();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [existing, setExisting] = useState<ConversationSummary[]>([]);
  const [starting, setStarting] = useState(false);
  const autoStarted = useRef(false);

  const bookTitle =
    (user && bookId && getUploadedBook(user.userId, bookId)?.title) || "your book";

  const startNew = useCallback(async () => {
    if (!bookId || starting) return;
    setStarting(true);
    setError(null);
    try {
      const conv = await createConversation({ book_id: bookId });
      navigate(`/discussions/${encodeURIComponent(conv.conversation_id)}`, {
        replace: true,
      });
    } catch (err) {
      setStarting(false);
      setError(friendlyError(err, "We couldn't start this discussion."));
    }
  }, [bookId, starting, navigate]);

  useEffect(() => {
    if (!bookId) {
      setLoading(false);
      return;
    }
    listConversations(bookId)
      .then((convos) => {
        setExisting(convos);
        setLoading(false);
        // No prior discussion for this book: start one automatically.
        if (convos.length === 0 && !autoStarted.current) {
          autoStarted.current = true;
          void startNew();
        }
      })
      .catch((err: unknown) => {
        setLoading(false);
        setError(friendlyError(err, "We couldn't load your discussions."));
      });
  }, [bookId, startNew]);

  if (!bookId) return <ErrorState message="No book selected." />;
  if (error) return <ErrorState message={error} />;
  if (loading || (existing.length === 0 && starting))
    return <Spinner label="Opening discussion…" />;

  // Existing conversations: let the user continue one or start fresh.
  return (
    <div className="mx-auto max-w-2xl">
      <BackLink to="/library" label="Back to library" />
      <h1 className="mt-2 text-xl font-semibold">Discuss {bookTitle}</h1>
      <p className="mt-1 text-slate-500">
        Continue a previous discussion or start a new one.
      </p>

      <ul className="mt-4 space-y-2">
        {existing.map((c) => (
          <li
            key={c.conversation_id}
            className="flex items-center justify-between rounded-lg border border-slate-200 bg-white p-3"
          >
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-slate-700">
                {c.title || "Discussion"}
              </p>
              <p className="text-xs text-slate-400">
                Last active {formatWhen(c.updated_at)}
              </p>
            </div>
            <Link
              to={`/discussions/${encodeURIComponent(c.conversation_id)}`}
              className="shrink-0 rounded bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800"
            >
              Continue
            </Link>
          </li>
        ))}
      </ul>

      <button
        onClick={() => void startNew()}
        disabled={starting}
        className="mt-4 rounded-lg border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-slate-100 disabled:opacity-50"
      >
        {starting ? "Starting…" : "Start a new discussion"}
      </button>
    </div>
  );
}
