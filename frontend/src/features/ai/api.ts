import { apiFetch } from "../../shared/api";
import type { Conversation, Message, SendMessageResponse } from "./types";

export function listConversations(): Promise<Conversation[]> {
  return apiFetch<Conversation[]>("/api/ai/conversations");
}

export function createConversation(title?: string): Promise<Conversation> {
  return apiFetch<Conversation>("/api/ai/conversations", {
    method: "POST",
    body: JSON.stringify({ title }),
  });
}

export function deleteConversation(id: string): Promise<void> {
  return apiFetch<void>(`/api/ai/conversations/${id}`, { method: "DELETE" });
}

export function listMessages(convId: string): Promise<Message[]> {
  return apiFetch<Message[]>(`/api/ai/conversations/${convId}/messages`);
}

export function sendMessage(convId: string, content: string): Promise<SendMessageResponse> {
  return apiFetch<SendMessageResponse>(`/api/ai/conversations/${convId}/messages`, {
    method: "POST",
    body: JSON.stringify({ content }),
  });
}
