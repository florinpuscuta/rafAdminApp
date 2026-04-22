/**
 * Pagina "Raport Word" — formular simplu (an + lună opțională + lanț opțional),
 * un buton "Generează" care declanșează POST /api/rapoarte/word și descarcă
 * fișierul docx rezultat.
 *
 * Stil: identic cu AnalizaPeLuniPage (card + CSS vars pentru light/dark theme).
 */
import { useState } from "react";

import { ApiError } from "../../shared/api";
import { generateRapoartWord, saveDocx } from "./api";

const MONTHS_RO = [
  "Ianuarie", "Februarie", "Martie", "Aprilie", "Mai", "Iunie",
  "Iulie", "August", "Septembrie", "Octombrie", "Noiembrie", "Decembrie",
];

export default function RapoartWordPage() {
  const currentYear = new Date().getFullYear();
  const [year, setYear] = useState<number>(currentYear);
  const [month, setMonth] = useState<number | "">("");
  const [chain, setChain] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastFilename, setLastFilename] = useState<string | null>(null);

  async function handleGenerate() {
    setLoading(true);
    setError(null);
    setLastFilename(null);
    try {
      const result = await generateRapoartWord({
        year,
        month: month === "" ? undefined : month,
        chain: chain.trim() || undefined,
      });
      saveDocx(result);
      setLastFilename(result.filename);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Eroare la generarea raportului",
      );
    } finally {
      setLoading(false);
    }
  }

  const yearOptions = [currentYear, currentYear - 1, currentYear - 2, currentYear - 3];

  return (
    <div style={styles.page}>
      <div style={styles.headerRow}>
        <h1 style={styles.title}>Raport Word</h1>
      </div>

      <div style={styles.card}>
        <p style={styles.intro}>
          Generează un raport Word (.docx) pentru luna și filtrele selectate.
          Raportul conține KPI-uri, top lanțuri/magazine/agenți/produse și
          comparația vânzări lunare față de anul precedent.
        </p>

        <div style={styles.formRow}>
          <label style={styles.label}>
            An
            <select
              value={year}
              onChange={(e) => setYear(Number(e.target.value))}
              style={styles.select}
            >
              {yearOptions.map((y) => (
                <option key={y} value={y}>{y}</option>
              ))}
            </select>
          </label>

          <label style={styles.label}>
            Luna (opțional)
            <select
              value={month}
              onChange={(e) =>
                setMonth(e.target.value === "" ? "" : Number(e.target.value))
              }
              style={styles.select}
            >
              <option value="">Toată anul</option>
              {MONTHS_RO.map((name, idx) => (
                <option key={idx + 1} value={idx + 1}>{name}</option>
              ))}
            </select>
          </label>

          <label style={styles.label}>
            Lanț (opțional)
            <input
              type="text"
              value={chain}
              onChange={(e) => setChain(e.target.value)}
              placeholder="ex. Dedeman"
              style={styles.input}
            />
          </label>
        </div>

        <div style={styles.actions}>
          <button
            onClick={handleGenerate}
            disabled={loading}
            style={{
              ...styles.primaryBtn,
              opacity: loading ? 0.6 : 1,
              cursor: loading ? "progress" : "pointer",
            }}
          >
            {loading ? "Se generează…" : "Generează Word"}
          </button>
        </div>

        {error && <div style={styles.error}>{error}</div>}
        {lastFilename && !error && (
          <div style={styles.success}>
            Descărcat: <code>{lastFilename}</code>
          </div>
        )}
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: {
    padding: "4px 4px 12px",
    color: "var(--text)",
  },
  headerRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 12,
    marginBottom: 12,
    flexWrap: "wrap",
  },
  title: {
    margin: 0,
    fontSize: 17,
    fontWeight: 600,
    color: "var(--text)",
    letterSpacing: -0.2,
  },
  card: {
    background: "var(--card)",
    border: "1px solid var(--border)",
    borderRadius: 8,
    padding: 16,
    boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
  },
  intro: {
    margin: "0 0 16px",
    fontSize: 13,
    color: "var(--muted)",
    lineHeight: 1.6,
    maxWidth: 640,
  },
  formRow: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
    gap: 12,
    marginBottom: 16,
  },
  label: {
    display: "flex",
    flexDirection: "column",
    gap: 6,
    fontSize: 12,
    fontWeight: 600,
    color: "var(--muted)",
    textTransform: "uppercase",
    letterSpacing: 0.4,
  },
  select: {
    padding: "7px 10px",
    fontSize: 13,
    background: "var(--bg-elevated)",
    color: "var(--text)",
    border: "1px solid var(--border)",
    borderRadius: 6,
    cursor: "pointer",
    textTransform: "none",
    fontWeight: 400,
    letterSpacing: 0,
  },
  input: {
    padding: "7px 10px",
    fontSize: 13,
    background: "var(--bg-elevated)",
    color: "var(--text)",
    border: "1px solid var(--border)",
    borderRadius: 6,
    textTransform: "none",
    fontWeight: 400,
    letterSpacing: 0,
  },
  actions: {
    display: "flex",
    gap: 8,
  },
  primaryBtn: {
    padding: "9px 18px",
    fontSize: 13,
    fontWeight: 600,
    background: "var(--accent)",
    color: "#fff",
    border: "none",
    borderRadius: 6,
  },
  error: {
    marginTop: 12,
    color: "var(--red)",
    padding: 10,
    background: "rgba(220, 38, 38, 0.08)",
    borderRadius: 6,
    fontSize: 13,
  },
  success: {
    marginTop: 12,
    color: "var(--green)",
    padding: 10,
    background: "rgba(5, 150, 105, 0.08)",
    borderRadius: 6,
    fontSize: 13,
  },
};
