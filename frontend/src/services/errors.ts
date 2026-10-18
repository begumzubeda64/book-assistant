// Maps any thrown error (API errors, job failures, timeouts) to a short,
// user-friendly message. Raw backend strings and stack traces must never be
// shown to users; we key off stable error codes / HTTP status instead.

import { ApiRequestError } from "@/services/api";

const FRIENDLY_BY_CODE: Record<string, string> = {
  UNAUTHORIZED: "Please sign in again to continue.",
  FORBIDDEN: "You don't have access to this.",
  NOT_FOUND: "We couldn't find what you were looking for.",
  CONVERSATION_NOT_FOUND: "This conversation is no longer available.",
  VALIDATION_ERROR: "Some details weren't quite right. Please check and retry.",
  RATE_LIMITED: "You're going a bit fast. Please wait a moment and try again.",
  SERVICE_UNAVAILABLE: "This feature is temporarily unavailable. Please try again shortly.",
};

const FRIENDLY_BY_STATUS: Record<number, string> = {
  401: "Please sign in again to continue.",
  403: "You don't have access to this.",
  404: "We couldn't find what you were looking for.",
  429: "You're going a bit fast. Please wait a moment and try again.",
  500: "Something went wrong on our end. Please try again.",
  502: "The service is waking up. Please try again in a moment.",
  503: "The service is temporarily unavailable. Please try again shortly.",
  504: "That took too long. Please try again.",
};

/** A friendly message for any error, with a sensible default. */
export function friendlyError(
  err: unknown,
  fallback = "Something went wrong. Please try again.",
): string {
  if (err instanceof ApiRequestError) {
    return (
      FRIENDLY_BY_CODE[err.code] ??
      FRIENDLY_BY_STATUS[err.status] ??
      fallback
    );
  }
  // Timeouts and other non-API errors: never surface the raw text.
  return fallback;
}

/** A friendly message for a job that ended in FAILED. */
export function friendlyJobFailure(
  jobType: "reading" | "ingestion",
): string {
  return jobType === "reading"
    ? "We couldn't finish generating this reading. Please try again."
    : "We couldn't finish preparing this book. Please try uploading it again.";
}
