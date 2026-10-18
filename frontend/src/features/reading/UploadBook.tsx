import { useRef, useState } from "react";

import { ErrorState } from "@/components/states";
import { useAuth } from "@/features/auth/useAuth";
import { ingestBook, presignUpload, uploadToS3 } from "@/services/uploads";
import { pollJob } from "@/services/jobs";
import { friendlyError, friendlyJobFailure } from "@/services/errors";
import { addUploadedBook, removeUploadedBook } from "@/stores/uploadedBooks";
import type { JobStatus } from "@/types/jobs";

const MAX_BYTES = 50 * 1024 * 1024;

type Step =
  | { kind: "form" }
  | { kind: "uploading"; label: string }
  | { kind: "processing"; status: JobStatus; progress: number }
  | { kind: "done" }
  | { kind: "error"; message: string };

export function UploadBook({ onUploaded }: { onUploaded: () => void }) {
  const { user } = useAuth();
  const [title, setTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [authorized, setAuthorized] = useState(false);
  const [step, setStep] = useState<Step>({ kind: "form" });
  const fileInput = useRef<HTMLInputElement>(null);

  function reset() {
    setTitle("");
    setFile(null);
    setAuthorized(false);
    setStep({ kind: "form" });
    if (fileInput.current) fileInput.current.value = "";
  }

  async function handleUpload() {
    if (!file || !authorized || !user) return;
    if (file.type !== "application/pdf") {
      setStep({ kind: "error", message: "Only PDF files are supported." });
      return;
    }
    if (file.size > MAX_BYTES) {
      setStep({ kind: "error", message: "File exceeds the 50 MB limit." });
      return;
    }

    try {
      setStep({ kind: "uploading", label: "Preparing upload…" });
      const presigned = await presignUpload({
        filename: file.name,
        content_type: "application/pdf",
        size_bytes: file.size,
        authorized_confirmation: authorized,
      });

      setStep({ kind: "uploading", label: "Uploading to secure storage…" });
      await uploadToS3(presigned, file);

      setStep({ kind: "uploading", label: "Starting ingestion…" });
      const job = await ingestBook(presigned.book_id, {
        object_key: presigned.object_key,
      });

      addUploadedBook(user.userId, {
        bookId: presigned.book_id,
        title: title.trim() || file.name.replace(/\.pdf$/i, ""),
        ingestionJobId: job.job_id,
        uploadedAt: new Date().toISOString(),
      });

      setStep({ kind: "processing", status: job.status, progress: 0 });
      const final = await pollJob(job.job_id, {
        intervalMs: 3000,
        maxAttempts: 120, // ~6 min: ingestion includes GraphRAG build
        onUpdate: (j) =>
          setStep({ kind: "processing", status: j.status, progress: j.progress }),
      });

      if (final.status === "FAILED") {
        // Don't leave a broken book in the library.
        removeUploadedBook(user.userId, presigned.book_id);
        onUploaded();
        setStep({ kind: "error", message: friendlyJobFailure("ingestion") });
        return;
      }
      setStep({ kind: "done" });
      onUploaded();
    } catch (err) {
      setStep({
        kind: "error",
        message: friendlyError(err, "We couldn't upload this book. Please try again."),
      });
    }
  }

  if (step.kind === "done") {
    return (
      <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4">
        <p className="font-medium text-emerald-800">Book ready</p>
        <p className="mt-1 text-sm text-emerald-700">
          Ingestion complete. You can now generate a reading or start a discussion
          from your library.
        </p>
        <button
          onClick={reset}
          className="mt-3 rounded border border-emerald-300 px-3 py-1 text-sm text-emerald-800 hover:bg-emerald-100"
        >
          Upload another
        </button>
      </div>
    );
  }

  if (step.kind === "uploading" || step.kind === "processing") {
    const label =
      step.kind === "uploading" ? step.label : "Preparing your book…";
    return (
      <div className="rounded-lg border border-slate-200 bg-white p-4">
        <div className="flex items-center gap-2 text-slate-600">
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-slate-600" />
          <span className="text-sm">{label}</span>
        </div>
        <p className="mt-2 text-xs text-slate-400">
          We&apos;re getting your book ready. This can take a little while — you
          can keep browsing and come back.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <h2 className="font-medium">Upload an authorized PDF</h2>
      {step.kind === "error" && (
        <div className="mt-3">
          <ErrorState message={step.message} onRetry={() => setStep({ kind: "form" })} />
        </div>
      )}

      <div className="mt-3 space-y-3">
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="Title (optional)"
          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
        />
        <input
          ref={fileInput}
          type="file"
          accept="application/pdf"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="block w-full text-sm text-slate-600 file:mr-3 file:rounded file:border-0 file:bg-slate-100 file:px-3 file:py-1.5 file:text-slate-700"
        />
        <label className="flex items-start gap-2 text-sm text-slate-600">
          <input
            type="checkbox"
            checked={authorized}
            onChange={(e) => setAuthorized(e.target.checked)}
            className="mt-0.5"
          />
          <span>
            I confirm I am authorized to use this content (I own it or have the
            right to upload it).
          </span>
        </label>
        <button
          onClick={() => void handleUpload()}
          disabled={!file || !authorized}
          className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          Upload &amp; ingest
        </button>
      </div>
    </div>
  );
}
