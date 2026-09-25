import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { getProgress } from "@/services/progress";
import type { UploadedBook } from "@/stores/uploadedBooks";
import { READING_MODES } from "@/types/reading";
import type { ProgressResponse } from "@/types/progress";

function modeLabel(mode: string | null | undefined): string | null {
  if (!mode) return null;
  return READING_MODES.find((m) => m.value === mode)?.label ?? mode;
}

export function LibraryBookRow({ book }: { book: UploadedBook }) {
  const [progress, setProgress] = useState<ProgressResponse | null>(null);

  useEffect(() => {
    let cancelled = false;
    getProgress(book.bookId)
      .then((p) => {
        if (!cancelled) setProgress(p);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [book.bookId]);

  const resumeLabel = modeLabel(progress?.selected_mode);

  return (
    <li className="flex items-center justify-between rounded-lg border border-slate-200 bg-white p-3">
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
      <div className="flex gap-2 text-sm">
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
          Discuss
        </Link>
      </div>
    </li>
  );
}
