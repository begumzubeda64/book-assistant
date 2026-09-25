import { apiFetch } from "@/services/api";
import type {
  Conversation,
  ConversationCreated,
  CreateConversationRequest,
  DiscussionMessage,
  PostMessageRequest,
} from "@/types/discussions";

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

export function postMessage(
  conversationId: string,
  request: PostMessageRequest,
): Promise<DiscussionMessage> {
  return apiFetch<DiscussionMessage>(
    `/api/v1/discussions/${encodeURIComponent(conversationId)}/messages`,
    { method: "POST", body: JSON.stringify(request) },
  );
}
