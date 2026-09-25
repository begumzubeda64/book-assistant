// Client-side registry of the user's uploaded books.
//
// The MVP backend has no "list my books" endpoint; uploads are tracked here
// (localStorage) so the Library can list them and link to reading/discussion.
// Keyed per user so switching accounts doesn't leak entries.

export interface UploadedBook {
  bookId: string;
  title: string;
  ingestionJobId: string;
  uploadedAt: string;
}

const KEY_PREFIX = "bc:uploaded-books:";

function key(userId: string): string {
  return `${KEY_PREFIX}${userId}`;
}

export function listUploadedBooks(userId: string): UploadedBook[] {
  try {
    const raw = localStorage.getItem(key(userId));
    return raw ? (JSON.parse(raw) as UploadedBook[]) : [];
  } catch {
    return [];
  }
}

export function addUploadedBook(userId: string, book: UploadedBook): void {
  const existing = listUploadedBooks(userId).filter(
    (b) => b.bookId !== book.bookId,
  );
  const next = [book, ...existing];
  localStorage.setItem(key(userId), JSON.stringify(next));
}

export function getUploadedBook(
  userId: string,
  bookId: string,
): UploadedBook | undefined {
  return listUploadedBooks(userId).find((b) => b.bookId === bookId);
}
