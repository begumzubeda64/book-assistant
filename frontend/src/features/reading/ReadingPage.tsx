import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ErrorState, Spinner } from "@/components/states";
import { friendlyError } from "@/services/errors";
import { getReading } from "@/services/reading";
import { saveProgress } from "@/services/progress";
import type { ReadingResult } from "@/types/reading";

type State =
  | { kind: "loading" }
  | { kind: "loaded"; reading: ReadingResult }
  | { kind: "error"; message: string };

export function ReadingPage() {
  const { readingId } = useParams();
  const [state, setState] = useState<State>({ kind: "loading" });

  const load = useCallback(async () => {
    if (!readingId) return;
    setState({ kind: "loading" });
    try {
      const reading = await getReading(readingId);
      setState({ kind: "loaded", reading });
      // Best-effort: record that the user opened this reading.
      void saveProgress(reading.book_id, {
        selected_duration: reading.target_minutes,
        selected_mode: reading.mode,
      }).catch(() => {});
    } catch (err) {
      setState({
        kind: "error",
        message: friendlyError(err, "We couldn't load this reading."),
      });
    }
  }, [readingId]);

  useEffect(() => {
    void load();
  }, [load]);

  if (state.kind === "loading") return <Spinner label="Loading reading…" />;
  if (state.kind === "error")
    return <ErrorState message={state.message} onRetry={() => void load()} />;

  const { reading } = state;

  return (
    <article className="mx-auto max-w-2xl">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="rounded-full bg-slate-900 px-3 py-1 font-medium text-white">
          {reading.target_minutes}-minute adaptive reading
        </span>
        <span className="rounded-full bg-slate-100 px-3 py-1 text-slate-600">
          {reading.mode.replace("_", " ")}
        </span>
        <span className="rounded-full bg-slate-100 px-3 py-1 text-slate-600">
          {reading.focus.replace(/_/g, " ")}
        </span>
        <span className="text-slate-400">~{reading.actual_words} words</span>
      </div>

      <div className="mt-6 whitespace-pre-line text-[17px] leading-relaxed text-slate-800">
        {reading.content}
      </div>

      {reading.source_refs.length > 0 && (
        <section className="mt-8 border-t border-slate-200 pt-4">
          <h2 className="text-sm font-medium text-slate-500">Sources</h2>
          <ul className="mt-2 space-y-1 text-sm text-slate-600">
            {reading.source_refs.map((ref, i) => (
              <li key={i}>
                {[
                  ref.chapter_title,
                  ref.section,
                  ref.page != null ? `p. ${ref.page}` : null,
                ]
                  .filter(Boolean)
                  .join(" · ") || "Source"}
              </li>
            ))}
          </ul>
        </section>
      )}

      <div className="mt-8 flex gap-3">
        <Link
          to={`/discussions/new?book=${encodeURIComponent(reading.book_id)}`}
          className="rounded-lg border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-slate-100"
        >
          Discuss this book
        </Link>
        <Link
          to="/library"
          className="rounded-lg border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-slate-100"
        >
          Back to library
        </Link>
      </div>
    </article>
  );
}
