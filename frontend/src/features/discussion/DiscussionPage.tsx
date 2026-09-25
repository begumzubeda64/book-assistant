import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { useParams } from "react-router-dom";

import { ErrorState, Spinner } from "@/components/states";
import { getConversation, postMessage } from "@/services/discussions";
import type { Citation, DiscussionMessage } from "@/types/discussions";

type LoadState =
  | { kind: "loading" }
  | { kind: "loaded" }
  | { kind: "error"; message: string };

function CitationList({ citations }: { citations: Citation[] }) {
  if (citations.length === 0) return null;
  return (
    <div className="mt-2 border-t border-slate-200 pt-2 text-xs text-slate-500">
      <span className="font-medium">Sources: </span>
      {citations
        .map((c) =>
          [c.chapter_title, c.section, c.page != null ? `p. ${c.page}` : null]
            .filter(Boolean)
            .join(" · "),
        )
        .filter(Boolean)
        .join("  |  ") || "referenced from the book"}
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
        <p className="whitespace-pre-line">{message.content}</p>
        {!isUser && <CitationList citations={message.citations} />}
      </div>
    </div>
  );
}

export function DiscussionPage() {
  const { conversationId } = useParams();
  const [messages, setMessages] = useState<DiscussionMessage[]>([]);
  const [bookId, setBookId] = useState<string>("");
  const [load, setLoad] = useState<LoadState>({ kind: "loading" });
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [askError, setAskError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const fetchConversation = useCallback(async () => {
    if (!conversationId) return;
    setLoad({ kind: "loading" });
    try {
      const conv = await getConversation(conversationId);
      setMessages(conv.messages);
      setBookId(conv.book_id);
      setLoad({ kind: "loaded" });
    } catch (err) {
      setLoad({
        kind: "error",
        message: err instanceof Error ? err.message : "Failed to load discussion",
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
      const answer = await postMessage(conversationId, { question: text });
      setMessages((prev) => [...prev, answer]);
    } catch (err) {
      setAskError(err instanceof Error ? err.message : "Failed to get an answer");
    } finally {
      setAsking(false);
    }
  }

  if (load.kind === "loading") return <Spinner label="Loading discussion…" />;
  if (load.kind === "error")
    return <ErrorState message={load.message} onRetry={() => void fetchConversation()} />;

  return (
    <div className="mx-auto flex h-[calc(100vh-9rem)] max-w-2xl flex-col">
      <h1 className="text-lg font-semibold">Discussion</h1>
      <p className="text-sm text-slate-400">Book: {bookId}</p>

      <div className="mt-4 flex-1 space-y-3 overflow-y-auto pr-1">
        {messages.length === 0 && (
          <p className="text-sm text-slate-400">
            Ask a question about this book. Answers are grounded in the book with
            source references.
          </p>
        )}
        {messages.map((m) => (
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
