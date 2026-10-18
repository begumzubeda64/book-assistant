import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { useParams } from "react-router-dom";

import { BackLink } from "@/components/BackLink";
import { Markdown } from "@/components/Markdown";
import { ErrorState, Spinner } from "@/components/states";
import { useAuth } from "@/features/auth/useAuth";
import { friendlyError } from "@/services/errors";
import { getConversation, postMessage } from "@/services/discussions";
import { getUploadedBook } from "@/stores/uploadedBooks";
import type { Citation, DiscussionMessage } from "@/types/discussions";

type LoadState =
  | { kind: "loading" }
  | { kind: "loaded" }
  | { kind: "error"; message: string };

function CitationList({ citations }: { citations: Citation[] }) {
  if (citations.length === 0) return null;
  // Prefer labelled references (chapter/section). When only page numbers exist,
  // show them as one tidy "Pages 1, 2, 3" line instead of bare "p. 1 | p. 2".
  const labelled = citations
    .map((c) => [c.chapter_title, c.section].filter(Boolean).join(" · "))
    .filter(Boolean);
  const pages = citations
    .map((c) => c.page)
    .filter((p): p is number => p != null);
  const uniquePages = [...new Set(pages)].sort((a, b) => a - b);

  let label: string;
  if (labelled.length > 0) {
    label = [...new Set(labelled)].join("  ·  ");
  } else if (uniquePages.length === 1) {
    label = `Page ${uniquePages[0]}`;
  } else if (uniquePages.length > 1) {
    label = `Pages ${uniquePages.join(", ")}`;
  } else {
    label = "Drawn from the book";
  }

  return (
    <div className="mt-2 border-t border-slate-200 pt-2 text-xs text-slate-500">
      <span className="font-medium">Sources: </span>
      {label}
    </div>
  );
}

function MessageBubble({ message }: { message: DiscussionMessage }) {
  const isUser = message.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-2 ${
          isUser
            ? "bg-slate-900 text-white"
            : "border border-slate-200 bg-white text-slate-800"
        }`}
      >
        {isUser ? (
          <p className="whitespace-pre-line">{message.content}</p>
        ) : (
          <Markdown
            content={message.content}
            className="space-y-2 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5 [&_li]:mt-0.5 [&_strong]:font-semibold [&_em]:italic [&_h1]:text-base [&_h1]:font-semibold [&_h2]:font-semibold [&_a]:underline"
          />
        )}
        {!isUser && <CitationList citations={message.citations} />}
      </div>
    </div>
  );
}

// How many most-recent messages to show before "load older".
const RECENT_WINDOW = 10;

export function DiscussionPage() {
  const { conversationId } = useParams();
  const { user } = useAuth();
  const [messages, setMessages] = useState<DiscussionMessage[]>([]);
  const [bookId, setBookId] = useState<string>("");
  const [title, setTitle] = useState<string | null>(null);
  const [load, setLoad] = useState<LoadState>({ kind: "loading" });
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [askError, setAskError] = useState<string | null>(null);
  const [showAll, setShowAll] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const bookTitle =
    (user && bookId && getUploadedBook(user.userId, bookId)?.title) || null;

  const fetchConversation = useCallback(async () => {
    if (!conversationId) return;
    setLoad({ kind: "loading" });
    try {
      const conv = await getConversation(conversationId);
      setMessages(conv.messages);
      setBookId(conv.book_id);
      setTitle(conv.title ?? null);
      setLoad({ kind: "loaded" });
    } catch (err) {
      setLoad({
        kind: "error",
        message: friendlyError(err, "We couldn't load this discussion."),
      });
    }
  }, [conversationId]);

  useEffect(() => {
    void fetchConversation();
  }, [fetchConversation]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, asking]);

  async function ask(event: FormEvent) {
    event.preventDefault();
    const text = question.trim();
    if (!text || !conversationId || asking) return;

    setAskError(null);
    setAsking(true);
    // Optimistically show the user's question.
    const optimistic: DiscussionMessage = {
      message_id: `local-${Date.now()}`,
      role: "user",
      content: text,
      citations: [],
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, optimistic]);
    setQuestion("");

    try {
      await postMessage(conversationId, { question: text });
      // Reconcile with the server so the thread reflects the persisted history
      // (both the question and the grounded answer), not just local optimism.
      // The title is (re)generated over the opening turns, so refresh it too.
      const conv = await getConversation(conversationId);
      setMessages(conv.messages);
      setTitle(conv.title ?? null);
    } catch (err) {
      // Roll back the optimistic question on failure.
      setMessages((prev) => prev.filter((m) => m.message_id !== optimistic.message_id));
      setQuestion(text);
      setAskError(friendlyError(err, "We couldn't get an answer. Please try again."));
    } finally {
      setAsking(false);
    }
  }

  if (load.kind === "loading") return <Spinner label="Loading discussion…" />;
  if (load.kind === "error")
    return <ErrorState message={load.message} onRetry={() => void fetchConversation()} />;

  return (
    <div className="mx-auto flex h-[calc(100vh-9rem)] max-w-2xl flex-col">
      <BackLink
        to={`/discussions/new?book=${encodeURIComponent(bookId)}`}
        label="Back to discussions"
      />
      <h1 className="mt-2 truncate text-lg font-semibold">
        {title || "New discussion"}
      </h1>
      <p className="truncate text-sm text-slate-400">
        {bookTitle ?? "Your book"}
      </p>

      <div className="mt-4 flex-1 space-y-3 overflow-y-auto pr-1">
        {messages.length === 0 && (
          <p className="text-sm text-slate-400">
            Ask a question about this book. Answers are grounded in the book with
            source references.
          </p>
        )}
        {!showAll && messages.length > RECENT_WINDOW && (
          <div className="flex justify-center">
            <button
              onClick={() => setShowAll(true)}
              className="rounded-full border border-slate-200 px-3 py-1 text-xs text-slate-500 hover:bg-slate-50"
            >
              Load earlier messages
            </button>
          </div>
        )}
        {(showAll ? messages : messages.slice(-RECENT_WINDOW)).map((m) => (
          <MessageBubble key={m.message_id} message={m} />
        ))}
        {asking && (
          <div className="flex justify-start">
            <div className="rounded-2xl border border-slate-200 bg-white px-4 py-2">
              <Spinner label="Thinking…" />
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {askError && (
        <div className="mt-2">
          <ErrorState message={askError} />
        </div>
      )}

      <form onSubmit={ask} className="mt-3 flex gap-2">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask about this book…"
          disabled={asking}
          className="flex-1 rounded-lg border border-slate-300 px-3 py-2 focus:border-slate-500 focus:outline-none disabled:bg-slate-50"
        />
        <button
          type="submit"
          disabled={asking || !question.trim()}
          className="rounded-lg bg-slate-900 px-4 py-2 font-medium text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          Send
        </button>
      </form>
    </div>
  );
}
