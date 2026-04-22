import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "../../shared/api";
import { useToast } from "../../shared/ui/ToastProvider";
import {
  createConversation,
  deleteConversation,
  listConversations,
  listMessages,
  sendMessage,
} from "./api";
import type { Conversation, Message } from "./types";

export default function ChatPage() {
  const toast = useToast();
  const [convs, setConvs] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [input, setInput] = useState("");
  const [provider, setProvider] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const refreshConvs = useCallback(async () => {
    try {
      const list = await listConversations();
      setConvs(list);
      if (list.length > 0 && !list.find((c) => c.id === activeId)) {
        setActiveId(list[0].id);
      } else if (list.length === 0) {
        setActiveId(null);
        setMessages([]);
      }
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Eroare");
    } finally {
      setLoading(false);
    }
  }, [activeId, toast]);

  useEffect(() => {
    refreshConvs();
  }, [refreshConvs]);

  useEffect(() => {
    if (!activeId) {
      setMessages([]);
      return;
    }
    listMessages(activeId)
      .then(setMessages)
      .catch((err) => toast.error(err instanceof ApiError ? err.message : "Eroare"));
  }, [activeId, toast]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages.length]);

  async function handleNewConv() {
    try {
      const c = await createConversation();
      await refreshConvs();
      setActiveId(c.id);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Eroare");
    }
  }

  async function handleDelete(id: string) {
    if (!window.confirm("Șterge conversația?")) return;
    try {
      await deleteConversation(id);
      if (activeId === id) setActiveId(null);
      await refreshConvs();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Eroare");
    }
  }

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim() || !activeId) return;
    const content = input;
    setInput("");
    setSending(true);
    try {
      const resp = await sendMessage(activeId, content);
      setMessages((prev) => [...prev, resp.userMessage, resp.assistantMessage]);
      setProvider(resp.provider);
      await refreshConvs();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Eroare la trimitere");
      setInput(content); // restore input
    } finally {
      setSending(false);
    }
  }

  if (loading && convs.length === 0) return <p>Se încarcă…</p>;

  return (
    <div>
      <h2 style={{ marginTop: 0 }}>AI Assistant</h2>
      <p style={{ color: "#666", fontSize: 13, marginTop: 0 }}>
        Întreabă despre datele de vânzări. Provider curent:{" "}
        <code>{provider ?? "—"}</code>
      </p>
      <div style={styles.layout}>
        <aside style={styles.sidebar}>
          <button onClick={handleNewConv} style={styles.newBtn}>
            + Conversație nouă
          </button>
          <div style={{ marginTop: 10 }}>
            {convs.length === 0 ? (
              <p style={{ color: "#888", fontSize: 13 }}>Nicio conversație.</p>
            ) : (
              convs.map((c) => {
                const isActive = c.id === activeId;
                return (
                  <div
                    key={c.id}
                    onClick={() => setActiveId(c.id)}
                    style={{
                      ...styles.convItem,
                      ...(isActive ? styles.convActive : {}),
                    }}
                  >
                    <div style={{ flex: 1, overflow: "hidden" }}>
                      <div
                        style={{
                          fontSize: 13,
                          fontWeight: isActive ? 600 : 400,
                          whiteSpace: "nowrap",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                        }}
                      >
                        {c.title}
                      </div>
                      <div style={{ fontSize: 11, color: "#888" }}>
                        {new Date(c.updatedAt).toLocaleString("ro-RO")}
                      </div>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDelete(c.id);
                      }}
                      style={styles.deleteBtn}
                    >
                      ×
                    </button>
                  </div>
                );
              })
            )}
          </div>
        </aside>

        <main style={styles.chat}>
          <div ref={scrollRef} style={styles.messages}>
            {!activeId ? (
              <p style={{ color: "#888", padding: 16 }}>
                Creează o conversație nouă ca să începi.
              </p>
            ) : messages.length === 0 ? (
              <p style={{ color: "#888", padding: 16 }}>
                Spune-mi cum te pot ajuta.
              </p>
            ) : (
              messages.map((m) => (
                <div
                  key={m.id}
                  style={{
                    ...styles.bubble,
                    ...(m.role === "user" ? styles.userBubble : styles.assistantBubble),
                  }}
                >
                  {m.content}
                </div>
              ))
            )}
          </div>
          <form onSubmit={handleSend} style={styles.inputBar}>
            <input
              type="text"
              placeholder={activeId ? "Scrie un mesaj…" : "Creează o conversație întâi"}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={!activeId || sending}
              style={styles.input}
            />
            <button
              type="submit"
              disabled={!activeId || sending || !input.trim()}
              style={styles.sendBtn}
            >
              {sending ? "…" : "Trimite"}
            </button>
          </form>
        </main>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  layout: {
    display: "grid",
    gridTemplateColumns: "240px 1fr",
    gap: 12,
    height: "calc(100vh - 200px)",
  },
  sidebar: {
    padding: 12,
    border: "1px solid #eee",
    borderRadius: 6,
    background: "#fff",
    overflowY: "auto",
  },
  newBtn: {
    width: "100%",
    padding: "8px 12px",
    fontSize: 13,
    cursor: "pointer",
    background: "#2563eb",
    color: "#fff",
    border: "none",
    borderRadius: 4,
  },
  convItem: {
    display: "flex",
    padding: "6px 8px",
    borderRadius: 4,
    cursor: "pointer",
    gap: 4,
  },
  convActive: { background: "#eff6ff" },
  deleteBtn: {
    padding: "2px 8px",
    cursor: "pointer",
    background: "transparent",
    border: "none",
    color: "#888",
  },
  chat: {
    display: "flex",
    flexDirection: "column",
    border: "1px solid #eee",
    borderRadius: 6,
    background: "#fff",
    overflow: "hidden",
  },
  messages: {
    flex: 1,
    overflowY: "auto",
    padding: 16,
    display: "flex",
    flexDirection: "column",
    gap: 10,
  },
  bubble: {
    maxWidth: "75%",
    padding: "10px 14px",
    borderRadius: 12,
    fontSize: 14,
    lineHeight: 1.4,
    whiteSpace: "pre-wrap",
  },
  userBubble: {
    alignSelf: "flex-end",
    background: "#2563eb",
    color: "#fff",
  },
  assistantBubble: {
    alignSelf: "flex-start",
    background: "#f1f5f9",
    color: "#222",
  },
  inputBar: {
    display: "flex",
    gap: 8,
    padding: 12,
    borderTop: "1px solid #eee",
    background: "#fafafa",
  },
  input: {
    flex: 1,
    padding: 8,
    fontSize: 14,
    border: "1px solid #ccc",
    borderRadius: 4,
  },
  sendBtn: {
    padding: "8px 16px",
    fontSize: 14,
    cursor: "pointer",
    background: "#2563eb",
    color: "#fff",
    border: "none",
    borderRadius: 4,
  },
};
