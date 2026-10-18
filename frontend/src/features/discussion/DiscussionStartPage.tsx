import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { BackLink } from "@/components/BackLink";
import { ErrorState, Spinner } from "@/components/states";
import { useAuth } from "@/features/auth/useAuth";
import { friendlyError } from "@/services/errors";
import {
  createConversation,
  listConversations,
  listPersonas,
  type ConversationSummary,
} from "@/services/discussions";
import { getUploadedBook } from "@/stores/uploadedBooks";
import type { PersonaOption } from "@/types/discussions";

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
  const [personas, setPersonas] = useState<PersonaOption[]>([]);
  const [persona, setPersona] = useState<string>("");
  const [starting, setStarting] = useState(false);

  const bookTitle =
    (user && bookId && getUploadedBook(user.userId, bookId)?.title) || "your book";

  const personaLabel = useCallback(
    (id: string | null) =>
      personas.find((p) => p.id === id)?.label ?? null,
    [personas],
  );

  const startNew = useCallback(async () => {
    if (!bookId || starting) return;
    setStarting(true);
    setError(null);
    try {
      const conv = await createConversation({
        book_id: bookId,
        persona: persona || undefined,
      });
      navigate(`/discussions/${encodeURIComponent(conv.conversation_id)}`, {
        replace: true,
      });
    } catch (err) {
      setStarting(false);
      setError(friendlyError(err, "We couldn't start this discussion."));
    }
  }, [bookId, starting, persona, navigate]);

  useEffect(() => {
    if (!bookId) {
      setLoading(false);
      return;
    }
    Promise.all([listConversations(bookId), listPersonas()])
      .then(([convos, personaList]) => {
        setExisting(convos);
        setPersonas(personaList.items);
        setPersona(personaList.default);
        setLoading(false);
      })
      .catch((err: unknown) => {
        setLoading(false);
        setError(friendlyError(err, "We couldn't load your discussions."));
      });
  }, [bookId]);

  if (!bookId) return <ErrorState message="No book selected." />;
  if (error) return <ErrorState message={error} />;
  if (loading) return <Spinner label="Loading…" />;

  const selected = personas.find((p) => p.id === persona);

  return (
    <div className="mx-auto max-w-2xl">
      <BackLink to="/library" label="Back to library" />
      <h1 className="mt-2 text-xl font-semibold">Discuss {bookTitle}</h1>
      <p className="mt-1 text-slate-500">
        Pick a voice and start a new discussion, or continue a previous one.
      </p>

      {existing.length > 0 && (
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
                  {personaLabel(c.persona) && (
                    <>{personaLabel(c.persona)} · </>
                  )}
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
      )}

      <section className="mt-8">
        <h2 className="text-sm font-medium text-slate-500">
          Discussion voice
        </h2>
        <div className="mt-2 grid gap-2 sm:grid-cols-2">
          {personas.map((p) => (
            <button
              key={p.id}
              type="button"
              onClick={() => setPersona(p.id)}
              className={`rounded-lg border p-3 text-left ${
                persona === p.id
                  ? "border-slate-900 bg-slate-900 text-white"
                  : "border-slate-200 bg-white hover:border-slate-300"
              }`}
            >
              <p className="text-sm font-medium">{p.label}</p>
              <p
                className={`mt-0.5 text-xs ${
                  persona === p.id ? "text-slate-200" : "text-slate-500"
                }`}
              >
                {p.description}
              </p>
            </button>
          ))}
        </div>
      </section>

      <button
        onClick={() => void startNew()}
        disabled={starting}
        className="mt-6 rounded-lg bg-slate-900 px-5 py-2.5 font-medium text-white hover:bg-slate-800 disabled:opacity-50"
      >
        {starting
          ? "Starting…"
          : `Start ${selected ? `a ${selected.label}` : "a new"} discussion`}
      </button>
    </div>
  );
}
