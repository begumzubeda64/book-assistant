import { apiFetch } from "@/services/api";
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
