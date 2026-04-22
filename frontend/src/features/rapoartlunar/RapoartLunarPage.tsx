/**
 * Raport Lunar Management — generator .docx cu checklist live.
 *
 * Backend streaming NDJSON: fiecare capitol primește un eveniment când e gata.
 * UI afișează pas cu pas ce s-a făcut (✓) și ce se lucrează (◌).
 */
import { useRef, useState } from "react";

import { getToken } from "../../shared/api";

const MONTHS_RO = [
  "Ianuarie", "Februarie", "Martie", "Aprilie", "Mai", "Iunie",
  "Iulie", "August", "Septembrie", "Octombrie", "Noiembrie", "Decembrie",
];

interface Chapter {
  id: string;
  label: string;
  status: "pending" | "done";
}

export default function RapoartLunarPage() {
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [running, setRunning] = useState(false);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [genError, setGenError] = useState<string | null>(null);
  const [lastFile, setLastFile] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const yearOptions = [
    now.getFullYear(), now.getFullYear() - 1, now.getFullYear() - 2,
  ];

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
        `${apiBase}/api/monthly-report/full/stream?year=${year}&month=${month}`,
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
            const ev = JSON.parse(line);
            handleEvent(ev);
          } catch {
            /* skip malformed */
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
    status?: string;
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
      // Download docx din base64
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
      <h1 style={styles.title}>Raport Lunar Management</h1>
      <p style={styles.sub}>
        Alege luna și apasă butonul — vezi live fiecare capitol pe măsură ce
        este pregătit, apoi descarci documentul Word.
      </p>

      <div style={styles.card}>
        <div style={styles.row}>
          <label style={styles.label}>
            <span style={styles.labelTxt}>Luna</span>
            <select
              value={month}
              onChange={(e) => setMonth(Number(e.target.value))}
              style={styles.select}
              disabled={running}
            >
              {MONTHS_RO.map((name, idx) => (
                <option key={idx + 1} value={idx + 1}>{name}</option>
              ))}
            </select>
          </label>
          <label style={styles.label}>
            <span style={styles.labelTxt}>Anul</span>
            <select
              value={year}
              onChange={(e) => setYear(Number(e.target.value))}
              style={styles.select}
              disabled={running}
            >
              {yearOptions.map((y) => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
          </label>
        </div>

        <button
          type="button"
          onClick={running ? cancel : start}
          style={{
            ...styles.btn,
            background: running ? "var(--red)" : "var(--accent)",
          }}
        >
          {running
            ? "✗ Oprește generarea"
            : `⬇ Generează raport ${MONTHS_RO[month - 1]} ${year}`}
        </button>

        {genError && <div style={styles.error}>⚠ {genError}</div>}
        {lastFile && !genError && (
          <div style={styles.ok}>✓ Descărcat: {lastFile}</div>
        )}
      </div>

      {chapters.length > 0 && (
        <div style={styles.checklistCard}>
          <div style={styles.progressHeader}>
            <span style={styles.progressLabel}>
              Progres: {doneCount} / {totalCount}
            </span>
            <span style={styles.progressPct}>{progressPct}%</span>
          </div>
          <div style={styles.progressBarOuter}>
            <div
              style={{
                ...styles.progressBarInner,
                width: `${progressPct}%`,
              }}
            />
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
                      color: "#fff",
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
  page: { padding: "8px 4px 20px", color: "var(--text)", maxWidth: 720 },
  title: { margin: "0 0 6px", fontSize: 20, fontWeight: 700, letterSpacing: -0.2 },
  sub: { margin: "0 0 16px", fontSize: 13, color: "var(--muted)", lineHeight: 1.5 },
  card: {
    background: "var(--card)", border: "1px solid var(--border)",
    borderRadius: 12, padding: 16, display: "flex",
    flexDirection: "column", gap: 14, marginBottom: 16,
  },
  row: { display: "flex", gap: 12, flexWrap: "wrap" },
  label: { display: "flex", flexDirection: "column", gap: 4, flex: "1 1 160px", minWidth: 0 },
  labelTxt: {
    fontSize: 11, fontWeight: 600, color: "var(--muted)",
    textTransform: "uppercase", letterSpacing: 0.4,
  },
  select: {
    padding: "9px 12px", fontSize: 14,
    background: "var(--bg-elevated, #fff)", color: "var(--text)",
    border: "1px solid var(--border)", borderRadius: 8,
    cursor: "pointer", width: "100%",
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
    flex: "0 0 auto",
  },
};
