/**
 * Playwright — capturi live ale fiecărui meniu din aplicație.
 * La click pe buton, parcurge toate paginile, face screenshot la fiecare,
 * le pune într-un Word one-after-another (landscape A4 per pagină).
 */
import { useRef, useState } from "react";

import { getToken } from "../../shared/api";

interface Chapter {
  id: string;
  label: string;
  status: "pending" | "done";
}

export default function PlaywrightReportPage() {
  const [running, setRunning] = useState(false);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [genError, setGenError] = useState<string | null>(null);
  const [lastFile, setLastFile] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  async function start() {
    setGenError(null);
    setLastFile(null);
    setChapters([]);
    setRunning(true);

    const ac = new AbortController();
    abortRef.current = ac;
    try {
      const apiBase = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
      const resp = await fetch(
        `${apiBase}/api/monthly-report/screenshots/stream`,
        {
          headers: { Authorization: `Bearer ${getToken() ?? ""}` },
          signal: ac.signal,
        },
      );
      if (!resp.ok || !resp.body) {
        const txt = await resp.text();
        throw new Error(txt || `HTTP ${resp.status}`);
      }
      const reader = resp.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        let nl: number;
        while ((nl = buffer.indexOf("\n")) !== -1) {
          const line = buffer.slice(0, nl).trim();
          buffer = buffer.slice(nl + 1);
          if (!line) continue;
          try {
            handleEvent(JSON.parse(line));
          } catch {
            /* skip */
          }
        }
      }
    } catch (e) {
      if ((e as Error).name !== "AbortError") {
        setGenError(e instanceof Error ? e.message : "Eroare");
      }
    } finally {
      setRunning(false);
      abortRef.current = null;
    }
  }

  function handleEvent(ev: {
    kind: string;
    items?: { id: string; label: string }[];
    id?: string;
    filename?: string;
    docx_b64?: string;
    message?: string;
  }) {
    if (ev.kind === "chapters" && ev.items) {
      setChapters(ev.items.map((i) => ({ ...i, status: "pending" })));
    } else if (ev.kind === "step" && ev.id) {
      setChapters((prev) =>
        prev.map((c) => (c.id === ev.id ? { ...c, status: "done" } : c)),
      );
    } else if (ev.kind === "result" && ev.docx_b64 && ev.filename) {
      const byteStr = atob(ev.docx_b64);
      const bytes = new Uint8Array(byteStr.length);
      for (let i = 0; i < byteStr.length; i++) bytes[i] = byteStr.charCodeAt(i);
      const blob = new Blob([bytes], {
        type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = ev.filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      setLastFile(ev.filename);
    } else if (ev.kind === "error") {
      setGenError(ev.message || "Eroare necunoscută");
    }
  }

  function cancel() {
    abortRef.current?.abort();
  }

  const doneCount = chapters.filter((c) => c.status === "done").length;
  const totalCount = chapters.length;
  const progressPct = totalCount > 0 ? Math.round((doneCount / totalCount) * 100) : 0;

  return (
    <div style={styles.page}>
      <h1 style={styles.title}>📸 Playwright — Capturi Pagini</h1>
      <p style={styles.sub}>
        Apasă butonul și un browser intern (Chromium headless) va parcurge
        fiecare meniu din aplicație, va face screenshot și va construi un Word
        cu toate capturile una după alta. Fiecare pagină în landscape A4.
      </p>

      <div style={styles.card}>
        <button
          type="button"
          onClick={running ? cancel : start}
          style={{
            ...styles.btn,
            background: running ? "var(--red)" : "var(--accent)",
          }}
        >
          {running ? "✗ Oprește capturarea" : "📸 Generează capturi din toate meniurile"}
        </button>

        {genError && <div style={styles.error}>⚠ {genError}</div>}
        {lastFile && !genError && (
          <div style={styles.ok}>✓ Descărcat: {lastFile}</div>
        )}
        {!running && chapters.length === 0 && (
          <div style={{ fontSize: 12, color: "var(--muted)" }}>
            Durează ~3 minute pentru ~35 pagini. Vezi live ce pagini sunt capturate.
          </div>
        )}
      </div>

      {chapters.length > 0 && (
        <div style={styles.checklistCard}>
          <div style={styles.progressHeader}>
            <span style={styles.progressLabel}>
              Progres: {doneCount} / {totalCount} pagini
            </span>
            <span style={styles.progressPct}>{progressPct}%</span>
          </div>
          <div style={styles.progressBarOuter}>
            <div style={{ ...styles.progressBarInner, width: `${progressPct}%` }} />
          </div>

          <ul style={styles.list}>
            {chapters.map((c) => {
              const isDone = c.status === "done";
              return (
                <li key={c.id} style={styles.item}>
                  <span
                    style={{
                      ...styles.checkbox,
                      background: isDone ? "var(--green)" : "transparent",
                      borderColor: isDone ? "var(--green)" : "var(--border)",
                    }}
                  >
                    {isDone ? "✓" : ""}
                  </span>
                  <span
                    style={{
                      fontSize: 13,
                      color: isDone ? "var(--text)" : "var(--muted)",
                      fontWeight: isDone ? 500 : 400,
                    }}
                  >
                    {c.label}
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: { padding: "8px 4px 20px", color: "var(--text)", maxWidth: 760 },
  title: { margin: "0 0 6px", fontSize: 20, fontWeight: 700, letterSpacing: -0.2 },
  sub: { margin: "0 0 16px", fontSize: 13, color: "var(--muted)", lineHeight: 1.5 },
  card: {
    background: "var(--card)", border: "1px solid var(--border)",
    borderRadius: 12, padding: 16, display: "flex",
    flexDirection: "column", gap: 12, marginBottom: 16,
  },
  btn: {
    padding: "12px 16px", fontSize: 14, fontWeight: 700,
    color: "#fff", border: "none", borderRadius: 10,
    minHeight: 44, cursor: "pointer",
  },
  error: {
    padding: "8px 12px", borderRadius: 8, fontSize: 13,
    background: "rgba(220, 38, 38, 0.08)", color: "var(--red)",
    border: "1px solid rgba(220, 38, 38, 0.2)",
  },
  ok: {
    padding: "8px 12px", borderRadius: 8, fontSize: 13,
    background: "rgba(5, 150, 105, 0.08)", color: "var(--green)",
    border: "1px solid rgba(5, 150, 105, 0.2)",
  },
  checklistCard: {
    background: "var(--card)", border: "1px solid var(--border)",
    borderRadius: 12, padding: 16,
  },
  progressHeader: {
    display: "flex", justifyContent: "space-between",
    alignItems: "baseline", marginBottom: 8,
  },
  progressLabel: { fontSize: 12, fontWeight: 600, color: "var(--muted)" },
  progressPct: { fontSize: 16, fontWeight: 700, color: "var(--accent)" },
  progressBarOuter: {
    height: 6, background: "rgba(148,163,184,0.15)",
    borderRadius: 3, overflow: "hidden", marginBottom: 14,
  },
  progressBarInner: {
    height: "100%", background: "var(--accent)",
    transition: "width 0.3s ease",
  },
  list: {
    listStyle: "none", margin: 0, padding: 0,
    display: "flex", flexDirection: "column", gap: 6,
  },
  item: { display: "flex", alignItems: "center", gap: 10 },
  checkbox: {
    display: "inline-flex", alignItems: "center", justifyContent: "center",
    width: 20, height: 20, borderRadius: 4,
    border: "1.5px solid", fontSize: 12, fontWeight: 700,
    flex: "0 0 auto", color: "#fff",
  },
};
