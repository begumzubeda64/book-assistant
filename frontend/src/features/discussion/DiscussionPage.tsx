import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { useParams } from "react-router-dom";

import { BackLink } from "@/components/BackLink";
import { Markdown } from "@/components/Markdown";
import { ErrorState, Spinner } from "@/components/states";
import { useAuth } from "@/features/auth/useAuth";
import { friendlyError } from "@/services/errors";
import {
  getConversation,
  listPersonas,
  streamMessage,
} from "@/services/discussions";
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

function MessageBubble({
  message,
  // While true, show a caret and hold citations (the answer is still streaming).
  streaming = false,
}: {
  message: DiscussionMessage;
  streaming?: boolean;
}) {
  const isUser = message.role === "user";
  const shown = message.content;
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
            content={shown + (streaming ? " ▍" : "")}
            className="space-y-2 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5 [&_li]:mt-0.5 [&_strong]:font-semibold [&_em]:italic [&_h1]:text-base [&_h1]:font-semibold [&_h2]:font-semibold [&_a]:underline"
          />
        )}
        {!isUser && !streaming && <CitationList citations={message.citations} />}
      </div>
    </div>
  );
}

// How many most-recent messages to show before "load older".
const RECENT_WINDOW = 10;

// Placeholder titles the agent uses before a real topic is captured. While the
// title is still one of these, an instant client-derived title may replace it.
const GENERIC_TITLES = new Set([
  "",
  "general chat",
  "discussion",
  "new discussion",
]);

function isGenericTitle(title: string | null | undefined): boolean {
  return GENERIC_TITLES.has((title ?? "").trim().toLowerCase());
}

/**
 * A quick, client-side title derived from the question, shown the instant a
 * message is sent so the header updates in real time. It's a stop-gap: the
 * agent's smarter intent-based title replaces it when the answer returns.
 */
function quickTitleFromQuestion(question: string): string {
  const cleaned = question
    .replace(/[^\p{L}\p{N}\s'-]/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
  if (!cleaned) return "New discussion";
  const words = cleaned.split(" ").slice(0, 5).join(" ");
  const title = words.length > 48 ? `${words.slice(0, 48).trim()}…` : words;
  // Capitalize the first letter for a tidy label.
  return title.charAt(0).toUpperCase() + title.slice(1);
}

export function DiscussionPage() {
  const { conversationId } = useParams();
  const { user } = useAuth();
  const [messages, setMessages] = useState<DiscussionMessage[]>([]);
  const [bookId, setBookId] = useState<string>("");
  const [title, setTitle] = useState<string | null>(null);
  const [personaLabel, setPersonaLabel] = useState<string | null>(null);
  const [load, setLoad] = useState<LoadState>({ kind: "loading" });
  const [question, setQuestion] = useState("");
  const [asking, setAsking] = useState(false);
  const [askError, setAskError] = useState<string | null>(null);
  const [showAll, setShowAll] = useState(false);
  // Real streaming: text arrives from the backend over SSE. We buffer the
  // incoming tokens and reveal them at a comfortable, readable pace (not in
  // instant bursts) via a render loop.
  const [streaming, setStreaming] = useState(false);
  const [streamShown, setStreamShown] = useState("");
  const streamBufferRef = useRef("");
  const streamDoneRef = useRef(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const bookTitle =
    (user && bookId && getUploadedBook(user.userId, bookId)?.title) || null;

  // The answer to the last turn is still being generated server-side when the
  // most recent persisted message is the user's (no assistant reply yet). This
  // covers returning to the chat mid-generation: the question shows, with a
  // "generating…" indicator, even though this browser isn't the one streaming.
  const lastMessage = messages[messages.length - 1];
  const awaitingAnswer =
    !streaming && !asking && lastMessage?.role === "user";

  const fetchConversation = useCallback(async () => {
    if (!conversationId) return;
    setLoad({ kind: "loading" });
    try {
      const conv = await getConversation(conversationId);
      setMessages(conv.messages);
      setBookId(conv.book_id);
      setTitle(conv.title ?? null);
      // Map the persona id to its human label for the header (best-effort).
      if (conv.persona) {
        listPersonas()
          .then(({ items }) => {
            const match = items.find((p) => p.id === conv.persona);
            setPersonaLabel(match?.label ?? null);
          })
          .catch(() => {});
      } else {
        setPersonaLabel(null);
      }
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
  }, [messages, asking, streamShown]);

  // If we returned mid-generation (last message is the user's, answer still
  // being produced server-side), poll the thread so the answer appears once it
  // lands — without a manual refresh.
  useEffect(() => {
    if (!awaitingAnswer || !conversationId) return;
    const timer = window.setInterval(() => {
      getConversation(conversationId)
        .then((conv) => {
          setMessages(conv.messages);
          if (conv.title) setTitle(conv.title);
        })
        .catch(() => {});
    }, 3000);
    return () => window.clearInterval(timer);
  }, [awaitingAnswer, conversationId]);

  // Paced reveal loop: SSE deltas land in streamBufferRef; this moves a few
  // characters at a time into the visible text at a steady, readable rate so
  // bursts don't dump instantly. When the backend is done and the buffer is
  // drained, it reconciles the thread from the DB (authoritative) and stops.
  const finishStream = useCallback(async () => {
    setStreaming(false);
    setStreamShown("");
    streamBufferRef.current = "";
    streamDoneRef.current = false;
    if (!conversationId) return;
    try {
      const conv = await getConversation(conversationId);
      setMessages(conv.messages);
      if (conv.title) setTitle(conv.title);
    } catch {
      // Keep whatever is shown; a later load will reconcile.
    }
  }, [conversationId]);

  useEffect(() => {
    if (!streaming) return;
    // ~45 chars/sec feels like comfortable reading, not a data dump.
    const timer = window.setInterval(() => {
      const buffered = streamBufferRef.current;
      if (buffered.length > 0) {
        const step = Math.min(3, buffered.length);
        setStreamShown((s) => s + buffered.slice(0, step));
        streamBufferRef.current = buffered.slice(step);
      } else if (streamDoneRef.current) {
        window.clearInterval(timer);
        void finishStream();
      }
    }, 60);
    return () => window.clearInterval(timer);
  }, [streaming, finishStream]);

  async function ask(event: FormEvent) {
    event.preventDefault();
    const text = question.trim();
    if (!text || !conversationId || asking || streaming) return;

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

    // Instant title feedback while no real title exists yet.
    const titleBeforeSend = title;
    if (isGenericTitle(titleBeforeSend)) {
      setTitle(quickTitleFromQuestion(text));
    }

    // Prepare the streaming view.
    streamBufferRef.current = "";
    streamDoneRef.current = false;
    setStreamShown("");
    setStreaming(true);

    try {
      await streamMessage(conversationId, { question: text }, (ev) => {
        if (ev.type === "delta") {
          streamBufferRef.current += ev.text;
        } else if (ev.type === "final") {
          if (ev.title) setTitle(ev.title);
          // Signal the reveal loop to drain the buffer then reconcile.
          streamDoneRef.current = true;
        } else {
          streamDoneRef.current = true;
          setAskError("We couldn't get an answer. Please try again.");
        }
      });
      // In case the stream closed without a final frame, make sure we finish.
      streamDoneRef.current = true;
    } catch (err) {
      // Roll back the optimistic question + instant title on failure.
      setMessages((prev) =>
        prev.filter((m) => m.message_id !== optimistic.message_id),
      );
      setTitle(titleBeforeSend);
      setQuestion(text);
      setStreaming(false);
      setStreamShown("");
      streamBufferRef.current = "";
      streamDoneRef.current = false;
      setAskError(
        friendlyError(err, "We couldn't get an answer. Please try again."),
      );
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
      <div className="mt-2 flex items-center gap-2">
        <h1 className="truncate text-lg font-semibold">
          {title || "New discussion"}
        </h1>
        {personaLabel && (
          <span className="shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
            {personaLabel}
          </span>
        )}
      </div>
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
        {/* Live streaming assistant bubble (real tokens, paced reveal). */}
        {streaming && streamShown.length > 0 && (
          <MessageBubble
            message={{
              message_id: "streaming",
              role: "assistant",
              content: streamShown,
              citations: [],
              created_at: new Date().toISOString(),
            }}
            streaming
          />
        )}
        {/* Waiting for the first token (this session), OR returning to a turn
            whose answer is still generating server-side. */}
        {((asking && (!streaming || streamShown.length === 0)) ||
          awaitingAnswer) && (
          <div className="flex justify-start">
            <div className="rounded-2xl border border-slate-200 bg-white px-4 py-2">
              <Spinner label="Generating the answer…" />
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
