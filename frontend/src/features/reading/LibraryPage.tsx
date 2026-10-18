import { useCallback, useEffect, useState } from "react";

import { EmptyState } from "@/components/states";
import { useAuth } from "@/features/auth/useAuth";
import { LibraryBookRow } from "@/features/reading/LibraryBookRow";
import { UploadBook } from "@/features/reading/UploadBook";
import { listUploadedBooks, type UploadedBook } from "@/stores/uploadedBooks";

export function LibraryPage() {
  const { user } = useAuth();
  const [books, setBooks] = useState<UploadedBook[]>([]);

  const refresh = useCallback(() => {
    if (user) setBooks(listUploadedBooks(user.userId));
  }, [user]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return (
    <div>
      <h1 className="text-xl font-semibold">My Library</h1>
      <p className="mt-1 text-slate-500">
        Upload authorized PDFs, then generate readings or start discussions.
      </p>

      <div className="mt-4">
        <UploadBook onUploaded={refresh} />
      </div>

      <h2 className="mt-8 text-sm font-medium text-slate-500">Your books</h2>
      <div className="mt-2">
        {books.length === 0 ? (
          <EmptyState title="No books yet">
            Upload a PDF above to get started.
          </EmptyState>
        ) : (
          <ul className="space-y-2">
            {books.map((book) => (
              <LibraryBookRow
                key={book.bookId}
                book={book}
                onRemoved={refresh}
              />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
