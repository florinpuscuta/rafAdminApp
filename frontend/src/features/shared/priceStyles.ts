/**
 * Stiluri comune pentru toate paginile din secțiunea Prețuri.
 * Asigură cursivitate vizuală între meniuri (Preturi Comparative / Adeplast
 * Kross / Pret 3 Net / Propuneri / KA vs Retail).
 */
import type { CSSProperties } from "react";

export const priceStyles: Record<string, CSSProperties> = {
  page: {
    padding: "4px 4px 20px",
    color: "var(--text)",
    zoom: 0.80 as unknown as number,
  },
  header: {
    display: "flex",
    alignItems: "center",
    gap: 10,
    flexWrap: "wrap",
    marginBottom: 16,
  },
  title: {
    margin: 0,
    fontSize: 18,
    fontWeight: 600,
    color: "var(--text)",
    letterSpacing: -0.2,
  },
  headerActions: {
    marginLeft: "auto",
    display: "flex",
    alignItems: "center",
    gap: 8,
    flexWrap: "wrap",
  },
  card: {
    background: "var(--card)",
    border: "1px solid var(--border)",
    borderRadius: 8,
    padding: 14,
    marginBottom: 12,
    overflowX: "auto",
  },
  cardHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 10,
    flexWrap: "wrap",
    gap: 10,
  },
  cardTitle: {
    margin: 0,
    fontSize: 14,
    fontWeight: 600,
    color: "var(--text)",
  },
  subtitle: {
    fontSize: 12,
    color: "var(--muted)",
  },
  tabBar: {
    display: "flex",
    gap: 4,
    flexWrap: "wrap",
  },
  tabBase: {
    padding: "8px 18px",
    border: "1px solid var(--border)",
    borderRadius: "8px 8px 0 0",
    cursor: "pointer",
    fontSize: 13,
    fontWeight: 500,
  },
  tabActive: {
    background: "var(--card)",
    color: "var(--accent)",
    borderBottom: "none",
    fontWeight: 700,
  },
  tabInactive: {
    background: "var(--bg-elevated)",
    color: "var(--muted)",
  },
  panel: {
    background: "var(--card)",
    border: "1px solid var(--border)",
    borderRadius: "0 8px 8px 8px",
    padding: 14,
    overflowX: "auto",
  },
  table: {
    width: "100%",
    borderCollapse: "collapse",
    fontSize: 13,
  },
  th: {
    padding: "10px 8px",
    textAlign: "left",
    color: "var(--muted)",
    fontSize: 11,
    fontWeight: 600,
    borderBottom: "1px solid var(--border)",
    letterSpacing: 0.4,
    textTransform: "uppercase",
    background: "var(--bg-elevated)",
    whiteSpace: "nowrap",
  },
  thNum: {
    padding: "10px 8px",
    textAlign: "right",
    color: "var(--muted)",
    fontSize: 11,
    fontWeight: 600,
    borderBottom: "1px solid var(--border)",
    letterSpacing: 0.4,
    textTransform: "uppercase",
    background: "var(--bg-elevated)",
    whiteSpace: "nowrap",
  },
  td: {
    padding: "8px",
    fontSize: 13,
    color: "var(--text)",
    borderBottom: "1px solid var(--border)",
  },
  tdNum: {
    padding: "8px",
    fontSize: 13,
    color: "var(--text)",
    borderBottom: "1px solid var(--border)",
    textAlign: "right",
    fontVariantNumeric: "tabular-nums",
  },
  tdStrong: {
    padding: "8px",
    fontSize: 13,
    fontWeight: 600,
    color: "var(--text)",
    borderBottom: "1px solid var(--border)",
  },
  totalRow: {
    borderTop: "2px solid var(--border)",
    background: "var(--accent-soft)",
  },
  select: {
    padding: "7px 10px",
    background: "var(--bg-elevated)",
    color: "var(--text)",
    border: "1px solid var(--border)",
    borderRadius: 6,
    fontSize: 12,
  },
  input: {
    padding: "7px 12px",
    background: "var(--bg)",
    color: "var(--text)",
    border: "1px solid var(--border)",
    borderRadius: 6,
    fontSize: 13,
  },
  btn: {
    padding: "7px 14px",
    background: "var(--accent)",
    color: "#fff",
    border: "none",
    borderRadius: 6,
    cursor: "pointer",
    fontSize: 12,
    fontWeight: 600,
  },
  btnGhost: {
    padding: "7px 14px",
    background: "transparent",
    color: "var(--text)",
    border: "1px solid var(--border)",
    borderRadius: 6,
    cursor: "pointer",
    fontSize: 12,
  },
  loading: { color: "var(--muted)", padding: 20 },
  error: {
    color: "var(--red)",
    background: "rgba(220,38,38,0.08)",
    padding: 12,
    borderRadius: 6,
    marginBottom: 12,
  },
  emptyState: {
    textAlign: "center",
    padding: 30,
    color: "var(--muted)",
    fontSize: 13,
  },
};

/** Format număr RO cu 0-2 zecimale. */
export function fmtPriceRo(n: number | null | undefined): string | null {
  if (n == null || n === 0) return null;
  return new Intl.NumberFormat("ro-RO", {
    minimumFractionDigits: 2, maximumFractionDigits: 2,
  }).format(n);
}

/** Format cu mii separate, 0 zecimale. */
export function fmtIntRo(n: number | null | undefined): string {
  if (n == null) return "—";
  return new Intl.NumberFormat("ro-RO", { maximumFractionDigits: 0 }).format(n);
}
