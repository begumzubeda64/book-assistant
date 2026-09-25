import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { ErrorState, Spinner } from "@/components/states";
import { createConversation } from "@/services/discussions";

export function DiscussionStartPage() {
  const [params] = useSearchParams();
  const bookId = params.get("book") ?? "";
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const started = useRef(false);

  useEffect(() => {
    if (!bookId || started.current) return;
    started.current = true;
    createConversation({ book_id: bookId })
      .then((conv) =>
        navigate(`/discussions/${encodeURIComponent(conv.conversation_id)}`, {
          replace: true,
        }),
      )
      .catch((err: unknown) =>
        setError(err instanceof Error ? err.message : "Could not start discussion"),
      );
  }, [bookId, navigate]);

  if (!bookId) return <ErrorState message="No book selected." />;
  if (error) return <ErrorState message={error} />;
  return <Spinner label="Starting discussion…" />;
}
