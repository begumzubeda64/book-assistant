import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { ErrorState } from "@/components/states";
import { useAuth } from "@/features/auth/useAuth";
import { generateReading } from "@/services/reading";
import { pollJob } from "@/services/jobs";
import { getUploadedBook } from "@/stores/uploadedBooks";
import {
  READING_FOCUSES,
  READING_MODES,
  type ReadingFocus,
  type ReadingMode,
} from "@/types/reading";

type State =
  | { kind: "form" }
  | { kind: "generating"; label: string }
  | { kind: "error"; message: string };

export function ReadingConfigPage() {
  const [params] = useSearchParams();
  const bookId = params.get("book") ?? "";
  const { user } = useAuth();
  const navigate = useNavigate();

  const book = user ? getUploadedBook(user.userId, bookId) : undefined;

  const [mode, setMode] = useState<ReadingMode>("balanced_read");
  const [focus, setFocus] = useState<ReadingFocus>("key_ideas");
  const [state, setState] = useState<State>({ kind: "form" });

  const selectedMode = READING_MODES.find((m) => m.value === mode)!;

  async function handleGenerate() {
    if (!bookId) return;
    setState({ kind: "generating", label: "Creating your reading…" });
    try {
      const job = await generateReading({
        book_id: bookId,
        duration_minutes: selectedMode.minutes,
        mode,
        focus,
      });
      const final = await pollJob(job.job_id, {
        onUpdate: (j) =>
          setState({
            kind: "generating",
            label:
              j.status === "QUEUED"
                ? "Queued…"
                : `Generating… ${j.progress}%`,
          }),
      });
      if (final.status === "FAILED") {
        setState({
          kind: "error",
          message: `Generation failed (${final.error_code ?? "unknown"}).`,
        });
        return;
      }
      // reading_id == job_id
      navigate(`/reading/${encodeURIComponent(job.job_id)}`);
    } catch (err) {
      setState({
        kind: "error",
        message: err instanceof Error ? err.message : "Generation failed",
      });
    }
  }

  if (!bookId) {
    return <ErrorState message="No book selected." />;
  }

  if (state.kind === "generating") {
    return (
      <div className="rounded-lg border border-slate-200 bg-white p-6">
        <div className="flex items-center gap-2 text-slate-600">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-slate-600" />
          <span className="text-sm">{state.label}</span>
        </div>
        <p className="mt-2 text-xs text-slate-400">
          We&apos;re condensing the book into coherent prose — this runs in the
          background.
        </p>
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-xl font-semibold">Adaptive Reading</h1>
      <p className="mt-1 text-slate-500">
        {book ? book.title : "Selected book"} — choose how you want to read.
      </p>

      {state.kind === "error" && (
        <div className="mt-4">
          <ErrorState
            message={state.message}
            onRetry={() => setState({ kind: "form" })}
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
        className="mt-8 rounded-lg bg-slate-900 px-5 py-2.5 font-medium text-white hover:bg-slate-800"
      >
        Generate {selectedMode.minutes}-minute reading
      </button>
    </div>
  );
}
