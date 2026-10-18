import { useCallback, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { ErrorState } from "@/components/states";
import { useAuth } from "@/features/auth/useAuth";
import {
  generateReading,
  listReadings,
  type ReadingSummary,
} from "@/services/reading";
import { pollJob } from "@/services/jobs";
import { friendlyError, friendlyJobFailure } from "@/services/errors";
import { getUploadedBook } from "@/stores/uploadedBooks";
import {
  READING_FOCUSES,
  READING_MODES,
  type ReadingFocus,
  type ReadingMode,
} from "@/types/reading";

function modeLabel(value: string): string {
  return READING_MODES.find((m) => m.value === value)?.label ?? value;
}

function focusLabel(value: string): string {
  return READING_FOCUSES.find((f) => f.value === value)?.label ?? value;
}

function formatWhen(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

// Generation runs in the background; the page stays interactive so the user can
// navigate away freely. We track a non-blocking banner instead of a full-page
// takeover, and surface a "ready" nudge (with a reading id to open) when done.
type GenState =
  | { kind: "idle" }
  | { kind: "generating" }
  | { kind: "ready"; readingId: string }
  | { kind: "error"; message: string };

export function ReadingConfigPage() {
  const [params] = useSearchParams();
  const bookId = params.get("book") ?? "";
  const { user } = useAuth();

  const book = user ? getUploadedBook(user.userId, bookId) : undefined;

  const [mode, setMode] = useState<ReadingMode>("balanced_read");
  const [focus, setFocus] = useState<ReadingFocus>("key_ideas");
  const [gen, setGen] = useState<GenState>({ kind: "idle" });
  const [existing, setExisting] = useState<ReadingSummary[]>([]);

  const selectedMode = READING_MODES.find((m) => m.value === mode)!;

  const refreshExisting = useCallback(() => {
    if (!bookId) return;
    listReadings(bookId)
      .then(setExisting)
      .catch(() => setExisting([]));
  }, [bookId]);

  useEffect(() => {
    refreshExisting();
  }, [refreshExisting]);

  async function handleGenerate() {
    if (!bookId || gen.kind === "generating") return;
    setGen({ kind: "generating" });
    try {
      const job = await generateReading({
        book_id: bookId,
        duration_minutes: selectedMode.minutes,
        mode,
        focus,
      });
      // Dedupe: identical config returns the same job. If it's already done,
      // surface it as ready immediately.
      if (job.status === "COMPLETED") {
        setGen({ kind: "ready", readingId: job.job_id });
        refreshExisting();
        return;
      }
      // Poll in the BACKGROUND. The page stays interactive and we never force a
      // redirect — the user opens the reading when they choose.
      pollJob(job.job_id, { intervalMs: 3000, maxAttempts: 100 })
        .then((final) => {
          if (final.status === "FAILED") {
            setGen({ kind: "error", message: friendlyJobFailure("reading") });
          } else {
            setGen({ kind: "ready", readingId: job.job_id });
            refreshExisting();
          }
        })
        .catch((err: unknown) =>
          setGen({
            kind: "error",
            message: friendlyError(
              err,
              "We couldn't create this reading. Please try again.",
            ),
          }),
        );
    } catch (err) {
      setGen({
        kind: "error",
        message: friendlyError(
          err,
          "We couldn't create this reading. Please try again.",
        ),
      });
    }
  }

  if (!bookId) {
    return <ErrorState message="No book selected." />;
  }

  return (
    <div>
      <h1 className="text-xl font-semibold">Adaptive Reading</h1>
      <p className="mt-1 text-slate-500">
        {book ? book.title : "Selected book"} — choose how you want to read.
      </p>

      {/* Non-blocking generation status: the page stays usable; navigate away
          anytime and open the reading when it's ready. */}
      {gen.kind === "generating" && (
        <div className="mt-4 flex items-center gap-2 rounded-lg border border-slate-200 bg-white p-4 text-sm text-slate-600">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-slate-600" />
          <span>
            Creating your reading in the background — feel free to keep
            browsing. It&apos;ll appear in your readings below when ready. ☕
          </span>
        </div>
      )}
      {gen.kind === "ready" && (
        <div className="mt-4 flex items-center justify-between rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm">
          <span className="text-emerald-800">Your reading is ready.</span>
          <Link
            to={`/reading/${encodeURIComponent(gen.readingId)}`}
            className="rounded bg-emerald-700 px-3 py-1.5 font-medium text-white hover:bg-emerald-800"
          >
            Read now
          </Link>
        </div>
      )}
      {gen.kind === "error" && (
        <div className="mt-4">
          <ErrorState
            message={gen.message}
            onRetry={() => setGen({ kind: "idle" })}
          />
        </div>
      )}

      <section className="mt-6">
        <h2 className="text-sm font-medium text-slate-500">Reading depth</h2>
        <div className="mt-2 grid gap-3 sm:grid-cols-3">
          {READING_MODES.map((m) => (
            <button
              key={m.value}
              onClick={() => setMode(m.value)}
              className={`rounded-lg border p-4 text-left ${
                mode === m.value
                  ? "border-slate-900 bg-slate-900 text-white"
                  : "border-slate-200 bg-white hover:border-slate-300"
              }`}
            >
              <p className="font-medium">{m.label}</p>
              <p
                className={`mt-1 text-sm ${
                  mode === m.value ? "text-slate-200" : "text-slate-500"
                }`}
              >
                ~{m.minutes} minutes
              </p>
            </button>
          ))}
        </div>
      </section>

      <section className="mt-6">
        <h2 className="text-sm font-medium text-slate-500">Focus</h2>
        <select
          value={focus}
          onChange={(e) => setFocus(e.target.value as ReadingFocus)}
          className="mt-2 w-full rounded-lg border border-slate-300 px-3 py-2 sm:w-72"
        >
          {READING_FOCUSES.map((f) => (
            <option key={f.value} value={f.value}>
              {f.label}
            </option>
          ))}
        </select>
      </section>

      <button
        onClick={() => void handleGenerate()}
        disabled={gen.kind === "generating"}
        className="mt-8 rounded-lg bg-slate-900 px-5 py-2.5 font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-400"
      >
        {gen.kind === "generating"
          ? "Generating…"
          : `Generate ${selectedMode.minutes}-minute reading`}
      </button>

      {existing.length > 0 && (
        <section className="mt-10 border-t border-slate-200 pt-6">
          <h2 className="text-sm font-medium text-slate-500">
            Your readings for this book
          </h2>
          <ul className="mt-2 space-y-2">
            {existing.map((r) => (
              <li
                key={r.reading_id}
                className="flex items-center justify-between rounded-lg border border-slate-200 bg-white p-3"
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-slate-700">
                    {modeLabel(r.mode)} · {focusLabel(r.focus)}
                  </p>
                  <p className="text-xs text-slate-400">
                    {r.target_minutes}-minute read · generated{" "}
                    {formatWhen(r.created_at)}
                  </p>
                </div>
                <Link
                  to={`/reading/${encodeURIComponent(r.reading_id)}`}
                  className="shrink-0 rounded border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-100"
                >
                  View
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
