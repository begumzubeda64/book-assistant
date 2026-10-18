import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { Markdown } from "@/components/Markdown";
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

      <Markdown
        content={reading.content}
        className="mt-6 space-y-4 text-[17px] leading-relaxed text-slate-800 [&_h1]:text-xl [&_h1]:font-semibold [&_h2]:mt-6 [&_h2]:text-lg [&_h2]:font-semibold [&_h3]:mt-4 [&_h3]:font-medium [&_ul]:list-disc [&_ul]:pl-6 [&_ol]:list-decimal [&_ol]:pl-6 [&_li]:mt-1 [&_strong]:font-semibold [&_em]:italic [&_a]:text-slate-900 [&_a]:underline"
      />

      {reading.source_refs.length > 0 &&
        (() => {
          // A labelled reference (chapter/section) reads as real provenance.
          // When only page numbers exist, collapse them into one tidy line
          // instead of a stacked list of bare "p. N" entries.
          const labelled = reading.source_refs
            .map((ref) =>
              [ref.chapter_title, ref.section].filter(Boolean).join(" · "),
            )
            .filter(Boolean);
          const pages = reading.source_refs
            .map((ref) => ref.page)
            .filter((p): p is number => p != null);
          const uniquePages = [...new Set(pages)].sort((a, b) => a - b);

          return (
            <section className="mt-8 border-t border-slate-200 pt-4">
              <h2 className="text-sm font-medium text-slate-500">
                Drawn from your book
              </h2>
              {labelled.length > 0 ? (
                <ul className="mt-2 space-y-1 text-sm text-slate-600">
                  {labelled.map((l, i) => (
                    <li key={i}>{l}</li>
                  ))}
                </ul>
              ) : uniquePages.length > 0 ? (
                <p className="mt-2 text-sm text-slate-600">
                  {uniquePages.length === 1
                    ? `Page ${uniquePages[0]}`
                    : `Pages ${uniquePages.join(", ")}`}
                </p>
              ) : (
                <p className="mt-2 text-sm text-slate-500">
                  Condensed from across the book.
                </p>
              )}
            </section>
          );
        })()}

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
