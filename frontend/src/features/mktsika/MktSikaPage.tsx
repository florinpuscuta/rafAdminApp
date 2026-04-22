import { useEffect, useState } from "react";

import { ApiError } from "../../shared/api";
import { getMktSika } from "./api";
import type { MktSikaResponse } from "./types";

export default function MktSikaPage() {
  const [data, setData] = useState<MktSikaResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getMktSika()
      .then((r) => {
        if (!cancelled) setData(r);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : "Eroare la încărcare");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div style={styles.page}>
      <div style={styles.headerRow}>
        <h1 style={styles.title}>Acțiuni SIKA</h1>
      </div>

      {error && <div style={styles.error}>{error}</div>}

      <div style={styles.card}>
        <div style={styles.cardHeader}>
          <h2 style={styles.cardTitle}>Listă acțiuni SIKA</h2>
        </div>

        {loading ? (
          <div style={styles.loading}>Se încarcă…</div>
        ) : (
          <>
            {data?.notice && <div style={styles.notice}>{data.notice}</div>}
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={styles.th}>ID</th>
                  <th style={styles.th}>Titlu</th>
                  <th style={styles.th}>Luna</th>
                  <th style={styles.th}>Note</th>
                </tr>
              </thead>
              <tbody>
                {(!data?.items || data.items.length === 0) && (
                  <tr>
                    <td colSpan={4} style={styles.empty}>
                      În dezvoltare — nu există încă DB schema
                    </td>
                  </tr>
                )}
                {data?.items.map((it) => (
                  <tr key={it.id}>
                    <td style={styles.td}>{it.id}</td>
                    <td style={styles.td}>{it.title}</td>
                    <td style={styles.td}>{it.luna ?? "—"}</td>
                    <td style={styles.td}>{it.notes ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: { padding: "4px 4px 12px", color: "var(--text)" },
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
  error: {
    color: "var(--red)",
    padding: 12,
    background: "rgba(220, 38, 38, 0.08)",
    borderRadius: 6,
    marginBottom: 12,
  },
  loading: { color: "var(--muted)", padding: 12 },
  card: {
    background: "var(--card)",
    border: "1px solid var(--border)",
    borderRadius: 8,
    padding: 16,
    marginBottom: 12,
    boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
  },
  cardHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 12,
  },
  cardTitle: {
    margin: 0,
    fontSize: 14,
    fontWeight: 600,
    color: "var(--text)",
    letterSpacing: 0.1,
  },
  notice: {
    padding: "8px 12px",
    marginBottom: 12,
    background: "var(--accent-soft)",
    color: "var(--text)",
    borderRadius: 6,
    fontSize: 13,
    border: "1px solid var(--border)",
  },
  table: { width: "100%", borderCollapse: "collapse" },
  th: {
    textAlign: "left",
    padding: "6px 8px",
    fontSize: 10.5,
    fontWeight: 600,
    color: "var(--muted)",
    borderBottom: "1px solid var(--border)",
    letterSpacing: 0.4,
    textTransform: "uppercase",
    whiteSpace: "nowrap",
  },
  td: {
    padding: "7px 8px",
    fontSize: 13,
    color: "var(--text)",
    borderBottom: "1px solid var(--border)",
    whiteSpace: "nowrap",
  },
  empty: {
    padding: "20px 8px",
    textAlign: "center",
    color: "var(--muted)",
    fontSize: 13,
    fontStyle: "italic",
  },
};
