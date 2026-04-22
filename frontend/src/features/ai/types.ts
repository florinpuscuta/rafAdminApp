export interface Conversation {
  id: string;
  title: string;
  userId: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface Message {
  id: string;
  conversationId: string;
  role: "user" | "assistant" | "system";
  content: string;
  createdAt: string;
}

export interface SendMessageResponse {
  userMessage: Message;
  assistantMessage: Message;
  provider: string;
}
