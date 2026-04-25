import { useEffect, useMemo, useState, type CSSProperties } from "react";

import { ApiError } from "../../shared/api";
import { bulkUpsert, getMatrix } from "./api";
import type {
  DRMatrixResponse,
  DRRuleIn,
  DRScope,
} from "./types";


const SCOPE_LABEL: Record<DRScope, string> = {
  adp: "Adeplast",
  sika: "Sika",
};


function cellKey(client: string, kind: string, key: string): string {
  return `${client}::${kind}::${key}`;
}


export default function DiscountRulesPage() {
  const [scope, setScope] = useState<DRScope>("adp");
  const [matrix, setMatrix] = useState<DRMatrixResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<Date | null>(null);
  const [busy, setBusy] = useState(false);
  // Edited state per cell — applies (true = primeste discount, false = exclus).
  const [edited, setEdited] = useState<Record<string, boolean>>({});

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const m = await getMatrix(scope);
      setMatrix(m);
      // Hidrat starea: default = true; cells din BD ne dau aplicabilitatea.
      const next: Record<string, boolean> = {};
      for (const cell of m.cells) {
        next[cellKey(cell.clientCanonical, cell.groupKind, cell.groupKey)] = cell.applies;
      }
      setEdited(next);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Eroare la incarcare");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scope]);

  function getCell(client: string, kind: string, key: string): boolean {
    const k = cellKey(client, kind, key);
    if (k in edited) return edited[k];
    return true; // default
  }

  function toggle(client: string, kind: string, key: string) {
    const k = cellKey(client, kind, key);
    setEdited((prev) => ({ ...prev, [k]: !(k in prev ? prev[k] : true) }));
  }

  async function save() {
    if (!matrix) return;
    setBusy(true);
    setError(null);
    try {
      // Trimitem TOATE celulele: backend decide insert/update/delete pe baza
      // valorii (default true -> delete; false -> upsert).
      const rules: DRRuleIn[] = [];
      for (const c of matrix.clients) {
        for (const g of matrix.groups) {
          rules.push({
            clientCanonical: c.canonical,
            groupKind: g.kind,
            groupKey: g.key,
            applies: getCell(c.canonical, g.kind, g.key),
          });
        }
      }
      await bulkUpsert(scope, rules);
      setSavedAt(new Date());
      await load();
    } catch (e) {
      if (e instanceof ApiError) setError(e.message);
      else if (e instanceof Error) setError(e.message);
      else setError("Eroare la salvare");
    } finally {
      setBusy(false);
    }
  }

  const dirty = useMemo(() => {
    if (!matrix) return false;
    const stored: Record<string, boolean> = {};
    for (const c of matrix.cells) {
      stored[cellKey(c.clientCanonical, c.groupKind, c.groupKey)] = c.applies;
    }
    for (const c of matrix.clients) {
      for (const g of matrix.groups) {
        const k = cellKey(c.canonical, g.kind, g.key);
        const cur = k in edited ? edited[k] : true;
        const old = k in stored ? stored[k] : true;
        if (cur !== old) return true;
      }
    }
    return false;
  }, [matrix, edited]);

  return (
    <div style={styles.page}>
      <div style={styles.sectionTitle}>Conditii Discount per Client KA</div>
      <div style={styles.sectionSubtitle}>
        Bifeaza grupele pe care fiecare client le include in discount-ul retroactiv.
        Default = bifat (primeste cota din storno). Debifeaza pentru grupele
        contractuale exclusiv (ex: Dedeman / Hornbach NU acorda discount pe
        EPS si Marca Privata).
      </div>

      <div style={styles.controls}>
        <div style={styles.tabs}>
          {(Object.keys(SCOPE_LABEL) as DRScope[]).map((k) => (
            <button
              key={k}
              type="button"
              onClick={() => setScope(k)}
              style={{ ...styles.tabBtn, ...(scope === k ? styles.tabBtnActive : {}) }}
            >
              {SCOPE_LABEL[k]}
            </button>
          ))}
        </div>
        <div style={{ flex: 1 }} />
        <button
          type="button"
          onClick={save}
          disabled={busy || !dirty}
          style={{ ...styles.primaryBtn, ...((!dirty || busy) ? styles.btnDisabled : {}) }}
        >
          {busy ? "Salveaza..." : dirty ? "Salveaza modificari" : "Nicio modificare"}
        </button>
      </div>

      {error && (
        <div style={styles.errorBox}>
          <strong>Eroare:</strong> {error}
        </div>
      )}

      {savedAt && !dirty && !error && (
        <div style={styles.successBox}>
          ✓ Salvat la {savedAt.toLocaleTimeString("ro-RO")}
        </div>
      )}

      {loading && <div style={styles.muted}>Se incarca...</div>}

      {!loading && matrix && matrix.clients.length === 0 && (
        <div style={styles.muted}>
          Nu exista clienti KA cu vanzari pentru scope-ul {SCOPE_LABEL[scope]}.
        </div>
      )}

      {!loading && matrix && matrix.clients.length > 0 && (
        <div style={styles.tableWrap}>
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={{ ...styles.th, textAlign: "left" }}>Grupa</th>
                {matrix.clients.map((c) => (
                  <th key={c.canonical} style={styles.thClient} title={c.canonical}>
                    {shortLabel(c.canonical)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {matrix.groups.map((g) => (
                <tr key={`${g.kind}::${g.key}`}>
                  <td style={{
                    ...styles.tdLabel,
                    fontWeight: g.kind === "private_label" ? 700 : 500,
                    color: g.kind === "private_label" ? "var(--orange)" : "var(--text)",
                  }}>
                    {g.label}
                    <span style={styles.codeBadge}>{g.key}</span>
                  </td>
                  {matrix.clients.map((c) => {
                    const v = getCell(c.canonical, g.kind, g.key);
                    return (
                      <td
                        key={c.canonical}
                        style={styles.tdCell}
                        onClick={() => toggle(c.canonical, g.kind, g.key)}
                      >
                        <span style={{
                          ...styles.checkbox,
                          background: v ? "var(--green)" : "var(--card)",
                          borderColor: v ? "var(--green)" : "var(--border)",
                          color: v ? "#0a0e17" : "var(--muted)",
                        }}>
                          {v ? "✓" : "✗"}
                        </span>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}


function shortLabel(canonical: string): string {
  // "DEDEMAN SRL" -> "DEDEMAN"; "LEROY MERLIN ROMANIA SRL" -> "LEROY"
  const upper = canonical.toUpperCase();
  if (upper.includes("DEDEMAN")) return "DEDEMAN";
  if (upper.includes("LEROY")) return "LEROY";
  if (upper.includes("HORNBACH")) return "HORNBACH";
  if (upper.includes("ALTEX")) return "ALTEX";
  if (upper.includes("BRICO")) return "BRICO";
  return canonical.split(" ")[0] ?? canonical;
}


const styles: Record<string, CSSProperties> = {
  page: { display: "flex", flexDirection: "column", gap: 16, maxWidth: 1100 },
  sectionTitle: { fontSize: 20, fontWeight: 700, color: "var(--text)" },
  sectionSubtitle: { fontSize: 13, color: "var(--muted)", lineHeight: 1.5, marginTop: -8 },
  controls: { display: "flex", gap: 12, alignItems: "center" },
  tabs: { display: "flex", gap: 6 },
  tabBtn: {
    background: "transparent",
    color: "var(--text)",
    border: "1px solid var(--border)",
    padding: "6px 16px",
    borderRadius: 6,
    fontSize: 13,
    fontWeight: 600,
    cursor: "pointer",
  },
  tabBtnActive: {
    background: "linear-gradient(135deg, #22d3ee, #06b6d4)",
    color: "#0a0e17",
    border: "none",
  },
  primaryBtn: {
    background: "linear-gradient(135deg, #22d3ee, #06b6d4)",
    color: "#0a0e17",
    border: "none",
    padding: "8px 22px",
    borderRadius: 8,
    fontSize: 13,
    fontWeight: 700,
    cursor: "pointer",
  },
  btnDisabled: { opacity: 0.45, cursor: "not-allowed" },
  errorBox: {
    background: "rgba(239,68,68,0.1)",
    border: "1px solid var(--red)",
    color: "var(--red)",
    padding: 12,
    borderRadius: 8,
    fontSize: 13,
  },
  successBox: {
    background: "rgba(34,197,94,0.08)",
    border: "1px solid var(--green)",
    color: "var(--green)",
    padding: 8,
    borderRadius: 6,
    fontSize: 12,
  },
  muted: { color: "var(--muted)", fontSize: 13 },
  tableWrap: {
    background: "var(--card)",
    border: "1px solid var(--border)",
    borderRadius: 10,
    overflow: "auto",
  },
  table: { width: "100%", borderCollapse: "collapse" },
  th: {
    position: "sticky", top: 0, zIndex: 1,
    background: "var(--card)",
    borderBottom: "1px solid var(--border)",
    padding: "10px 12px",
    fontSize: 11, fontWeight: 700,
    color: "var(--muted)",
    textTransform: "uppercase",
    letterSpacing: "0.04em",
  },
  thClient: {
    position: "sticky", top: 0, zIndex: 1,
    background: "var(--card)",
    borderBottom: "1px solid var(--border)",
    padding: "10px 12px",
    fontSize: 11, fontWeight: 700,
    color: "var(--cyan)",
    textTransform: "uppercase",
    letterSpacing: "0.04em",
    textAlign: "center",
    minWidth: 90,
  },
  tdLabel: {
    borderBottom: "1px solid rgba(255,255,255,0.04)",
    padding: "8px 12px",
    fontSize: 13,
    display: "flex",
    alignItems: "center",
    gap: 10,
  },
  codeBadge: {
    background: "rgba(255,255,255,0.05)",
    color: "var(--muted)",
    padding: "1px 6px",
    borderRadius: 4,
    fontSize: 10,
    fontFamily: "monospace",
  },
  tdCell: {
    borderBottom: "1px solid rgba(255,255,255,0.04)",
    padding: "8px 12px",
    textAlign: "center",
    cursor: "pointer",
  },
  checkbox: {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    width: 28, height: 28,
    borderRadius: 6,
    border: "1px solid",
    fontWeight: 800,
    fontSize: 14,
    transition: "background 0.1s, border-color 0.1s",
    userSelect: "none",
  },
};
