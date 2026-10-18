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
