// Client-side record of books for which the user has started an adaptive
// reading. Backend reading *results* only appear once generation completes, but
// the user expects the Library to reflect "Continue reading" the moment they
// kick off generation. We track that intent locally (per user) so the Library
// updates instantly, independent of backend job propagation.

const KEY_PREFIX = "bc:reading-started:";

function key(userId: string): string {
  return `${KEY_PREFIX}${userId}`;
}

function read(userId: string): string[] {
  try {
    const raw = localStorage.getItem(key(userId));
    return raw ? (JSON.parse(raw) as string[]) : [];
  } catch {
    return [];
  }
}

/** Mark that the user has started a reading for this book. */
export function markReadingStarted(userId: string, bookId: string): void {
  const existing = read(userId);
  if (existing.includes(bookId)) return;
  localStorage.setItem(key(userId), JSON.stringify([bookId, ...existing]));
}

/** Whether the user has started (or has) a reading for this book. */
export function hasStartedReading(userId: string, bookId: string): boolean {
  return read(userId).includes(bookId);
}

/** Forget a book's reading activity (e.g. when the book is removed). */
export function clearReadingStarted(userId: string, bookId: string): void {
  const next = read(userId).filter((id) => id !== bookId);
  localStorage.setItem(key(userId), JSON.stringify(next));
}

// --- Pending (in-flight) readings -----------------------------------------
//
// A reading that is still generating has no backend result yet, so it can't
// appear in the server-backed list. We persist the in-flight readings per user
// (jobId + config) so the config page can show a "preparing…" row that survives
// navigation, until the job completes (then it's removed and the real,
// viewable reading from the backend takes its place).

export interface PendingReading {
  jobId: string;
  bookId: string;
  mode: string;
  focus: string;
  minutes: number;
  startedAt: string;
}

const PENDING_PREFIX = "bc:reading-pending:";

function pendingKey(userId: string): string {
  return `${PENDING_PREFIX}${userId}`;
}

function readPending(userId: string): PendingReading[] {
  try {
    const raw = localStorage.getItem(pendingKey(userId));
    return raw ? (JSON.parse(raw) as PendingReading[]) : [];
  } catch {
    return [];
  }
}

function writePending(userId: string, items: PendingReading[]): void {
  localStorage.setItem(pendingKey(userId), JSON.stringify(items));
}

/** Record an in-flight reading (replaces any with the same jobId). */
export function addPendingReading(
  userId: string,
  pending: PendingReading,
): void {
  const rest = readPending(userId).filter((p) => p.jobId !== pending.jobId);
  writePending(userId, [pending, ...rest]);
}

/** Pending readings for a book (newest first). */
export function listPendingReadings(
  userId: string,
  bookId: string,
): PendingReading[] {
  return readPending(userId).filter((p) => p.bookId === bookId);
}

/** Remove an in-flight reading once it completes/fails. */
export function removePendingReading(userId: string, jobId: string): void {
  writePending(
    userId,
    readPending(userId).filter((p) => p.jobId !== jobId),
  );
}

/** Drop all pending readings for a book (e.g. when the book is removed). */
export function clearPendingReadings(userId: string, bookId: string): void {
  writePending(
    userId,
    readPending(userId).filter((p) => p.bookId !== bookId),
  );
}
