import { apiBaseUrl, apiFetch, ApiRequestError, getAuthToken } from "@/services/api";
import type {
  Conversation,
  ConversationCreated,
  CreateConversationRequest,
  DiscussionMessage,
  PersonaOption,
  PostMessageRequest,
} from "@/types/discussions";

// Personas are static for the session; cache after first fetch.
let personaCache: { items: PersonaOption[]; default: string } | null = null;

export async function listPersonas(): Promise<{
  items: PersonaOption[];
  default: string;
}> {
  if (personaCache) return personaCache;
  const res = await apiFetch<{ items: PersonaOption[]; default: string }>(
    "/api/v1/discussions/personas",
  );
  personaCache = res;
  return res;
}

export function createConversation(
  request: CreateConversationRequest,
): Promise<ConversationCreated> {
  return apiFetch<ConversationCreated>("/api/v1/discussions", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export function getConversation(
  conversationId: string,
): Promise<Conversation> {
  return apiFetch<Conversation>(
    `/api/v1/discussions/${encodeURIComponent(conversationId)}`,
  );
}

export interface ConversationSummary {
  conversation_id: string;
  book_id: string;
  title: string | null;
  persona: string | null;
  message_count: number;
  updated_at: string;
}

export async function listConversations(
  bookId: string,
): Promise<ConversationSummary[]> {
  const params = new URLSearchParams({ book_id: bookId });
  const res = await apiFetch<{ items: ConversationSummary[] }>(
    `/api/v1/discussions?${params}`,
  );
  return res.items;
}

export function postMessage(
  conversationId: string,
  request: PostMessageRequest,
): Promise<DiscussionMessage> {
  return apiFetch<DiscussionMessage>(
    `/api/v1/discussions/${encodeURIComponent(conversationId)}/messages`,
    { method: "POST", body: JSON.stringify(request) },
  );
}

export interface StreamDelta {
  type: "delta";
  text: string;
}

export interface StreamFinal {
  type: "final";
  message_id?: string;
  title?: string | null;
  citations?: unknown[];
}

export type StreamEvent = StreamDelta | StreamFinal | { type: "error" };

/**
 * Stream a grounded answer via Server-Sent Events. Calls `onEvent` for each
 * parsed event (token deltas, then a final event). Uses fetch streaming (not
 * EventSource) so we can POST a body and attach the bearer token. The returned
 * promise resolves when the stream closes; pass an AbortSignal to stop reading
 * (the backend still completes + persists the answer regardless).
 */
export async function streamMessage(
  conversationId: string,
  request: PostMessageRequest,
  onEvent: (event: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const token = await getAuthToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "text/event-stream",
  };
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(
    `${apiBaseUrl}/api/v1/discussions/${encodeURIComponent(
      conversationId,
    )}/messages/stream`,
    { method: "POST", headers, body: JSON.stringify(request), signal },
  );
  if (!res.ok || !res.body) {
    throw new ApiRequestError(res.status, {
      code: "STREAM_ERROR",
      message: res.statusText,
    });
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  // SSE frames are separated by a blank line; each frame has "data:" lines.
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      for (const line of frame.split("\n")) {
        const trimmed = line.trimStart();
        if (!trimmed.startsWith("data:")) continue;
        const data = trimmed.slice(5).trim();
        if (!data) continue;
        try {
          onEvent(JSON.parse(data) as StreamEvent);
        } catch {
          // Ignore malformed frames.
        }
      }
    }
  }
}
