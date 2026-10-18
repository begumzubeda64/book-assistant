// Mirrors backend src/schemas/discussions.py

export type MessageRole = "user" | "assistant";

export interface Citation {
  chunk_id?: string | null;
  chapter_title?: string | null;
  section?: string | null;
  page?: number | null;
}

export interface DiscussionMessage {
  message_id: string;
  role: MessageRole;
  content: string;
  citations: Citation[];
  created_at: string;
}

export interface Conversation {
  conversation_id: string;
  book_id: string;
  title?: string | null;
  persona?: string | null;
  messages: DiscussionMessage[];
  created_at: string;
  updated_at: string;
}

export interface ConversationCreated {
  conversation_id: string;
  book_id: string;
}

export interface CreateConversationRequest {
  book_id: string;
  title?: string | null;
  persona?: string | null;
}

export interface PersonaOption {
  id: string;
  label: string;
  description: string;
}

export interface PostMessageRequest {
  question: string;
}
