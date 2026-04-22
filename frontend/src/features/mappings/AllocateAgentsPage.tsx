import { useCallback, useEffect, useMemo, useState } from "react";

import { listAgents } from "../agents/api";
import type { Agent } from "../agents/types";
import { ApiError } from "../../shared/api";
import { norm, SearchInput } from "../../shared/ui/SearchInput";
import { TableSkeleton } from "../../shared/ui/Skeleton";
import { useToast } from "../../shared/ui/ToastProvider";
import {
  createMapping,
  listUnmapped,
  type UnmappedClientRow,
} from "./api";

type Scope = "adp" | "sika";

function fmtRo(n: number): string {
  return new Intl.NumberFormat("ro-RO", { maximumFractionDigits: 0 }).format(n);
}

export default function AllocateAgentsPage() {
  const toast = useToast();
  const [scope, setScope] = useState<Scope>("sika");
  const [rows, setRows] = useState<UnmappedClientRow[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selection, setSelection] = useState<Record<string, string>>({});
  const [cheieDraft, setCheieDraft] = useState<Record<string, string>>({});
  const [savingFor, setSavingFor] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [u, a] = await Promise.all([listUnmapped(scope), listAgents()]);
      setRows(u);
      setAgents(a.filter((x) => x.active));
      setSelection({});
      setCheieDraft({});
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Eroare la încărcare");
    } finally {
      setLoading(false);
    }
  }, [scope]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const filtered = useMemo(() => {
    const q = norm(search);
    if (!q) return rows;
    return rows.filter((r) =>
      norm([r.clientOriginal, r.shipToOriginal, r.rawClient].join(" ")).includes(q),
    );
  }, [rows, search]);

  async function handleAllocate(row: UnmappedClientRow) {
    const agentId = selection[row.rawClient];
    if (!agentId) return;
    const agent = agents.find((a) => a.id === agentId);
    if (!agent) return;
    const cheie = (cheieDraft[row.rawClient] ?? row.rawClient).trim();
    if (!cheie) {
      toast.error("Cheia Finală nu poate fi goală");
      return;
    }
    setSavingFor(row.rawClient);
    try {
      await createMapping({
        source: row.source,
        clientOriginal: row.clientOriginal,
        shipToOriginal: row.shipToOriginal,
        cheieFinala: cheie,
        agentUnificat: agent.fullName,
      });
      toast.success(`Alocat "${row.rawClient}" → ${agent.fullName}`);
      setRows((prev) => prev.filter((r) => r.rawClient !== row.rawClient));
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Eroare la alocare");
    } finally {
      setSavingFor(null);
    }
  }

  const totalSales = useMemo(
    () => rows.reduce((sum, r) => sum + Number(r.totalSales || 0), 0),
    [rows],
  );

  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Alocare agenți — magazine nealocate</h2>
      <p style={styles.hint}>
        Lista e construită din <code style={code}>raw_sales</code> KA, filtrat
        pe sursă ({scope.toUpperCase()}), minus combinațiile deja acoperite în
        mapări. Alege un agent, ajustează <em>Cheia Finală</em> (magazinul
        canonic) și apasă <strong>Alocă</strong>. Se creează o intrare nouă
        în maparea Raf + backfill automat.
      </p>

      <div style={styles.toolbar}>
        <div style={{ display: "flex", gap: 8 }}>
          <ScopeButton active={scope === "adp"} onClick={() => setScope("adp")}>
            ADEPLAST
          </ScopeButton>
          <ScopeButton active={scope === "sika"} onClick={() => setScope("sika")}>
            SIKA
          </ScopeButton>
        </div>
        {rows.length > 0 && (
          <SearchInput
            value={search}
            onChange={setSearch}
            placeholder="Caută client / ship_to…"
            total={rows.length}
            visible={filtered.length}
          />
        )}
      </div>

      <div style={styles.summary}>
        <span>
          <strong>{rows.length}</strong> combinații nealocate
        </span>
        <span>
          Total vânzări afectate:{" "}
          <strong>{fmtRo(totalSales)} RON</strong>
        </span>
      </div>

      {error && <p style={{ color: "#b00020" }}>{error}</p>}

      {loading && rows.length === 0 ? (
        <TableSkeleton rows={8} cols={6} />
      ) : rows.length === 0 ? (
        <p style={{ padding: 24, textAlign: "center" }}>
          🎉 Toate magazinele din acest scope au deja un agent alocat.
        </p>
      ) : (
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={th}>Client Original</th>
              <th style={th}>Magazin (ship_to)</th>
              <th style={thNum}>Linii</th>
              <th style={thNum}>Total (RON)</th>
              <th style={{ ...th, minWidth: 220 }}>Cheie Finală (canonic)</th>
              <th style={{ ...th, minWidth: 240 }}>Agent</th>
              <th style={th}></th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((row) => {
              const saving = savingFor === row.rawClient;
              const picked = selection[row.rawClient] ?? "";
              const cheie = cheieDraft[row.rawClient] ?? row.rawClient;
              return (
                <tr key={row.rawClient}>
                  <td style={td}>{row.clientOriginal}</td>
                  <td style={td}>{row.shipToOriginal}</td>
                  <td style={tdNum}>{row.rowCount}</td>
                  <td style={tdNum}>{fmtRo(Number(row.totalSales || 0))}</td>
                  <td style={td}>
                    <input
                      value={cheie}
                      onChange={(e) =>
                        setCheieDraft((d) => ({
                          ...d,
                          [row.rawClient]: e.target.value,
                        }))
                      }
                      style={styles.input}
                      disabled={saving}
                    />
                  </td>
                  <td style={td}>
                    <select
                      value={picked}
                      onChange={(e) =>
                        setSelection((s) => ({
                          ...s,
                          [row.rawClient]: e.target.value,
                        }))
                      }
                      style={styles.select}
                      disabled={agents.length === 0 || saving}
                    >
                      <option value="">— alege agent —</option>
                      {agents.map((a) => (
                        <option key={a.id} value={a.id}>
                          {a.fullName}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td style={td}>
                    <button
                      onClick={() => handleAllocate(row)}
                      disabled={!picked || saving}
                      style={styles.btn}
                    >
                      {saving ? "…" : "Alocă"}
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}

function ScopeButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: "6px 14px",
        fontSize: 13,
        cursor: "pointer",
        background: active ? "#2563eb" : "transparent",
        color: active ? "#fff" : "#2563eb",
        border: "1px solid #2563eb",
        borderRadius: 4,
      }}
    >
      {children}
    </button>
  );
}

const styles: Record<string, React.CSSProperties> = {
  hint: {
    fontSize: 13,
    color: "var(--muted, #666)",
    marginTop: 0,
    marginBottom: 16,
  },
  toolbar: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 12,
    marginBottom: 8,
  },
  summary: {
    display: "flex",
    gap: 24,
    padding: "8px 12px",
    background: "var(--card, #f9fafb)",
    border: "1px solid var(--border, #e5e7eb)",
    borderRadius: 4,
    fontSize: 13,
    marginBottom: 12,
  },
  table: { borderCollapse: "collapse", width: "100%" },
  input: {
    width: "100%",
    padding: 6,
    fontSize: 12,
    border: "1px solid #ccc",
    borderRadius: 3,
  },
  select: {
    width: "100%",
    padding: 6,
    fontSize: 12,
    border: "1px solid #ccc",
    borderRadius: 3,
  },
  btn: {
    padding: "6px 14px",
    fontSize: 12,
    cursor: "pointer",
    background: "#2563eb",
    color: "#fff",
    border: "none",
    borderRadius: 3,
  },
};
const code: React.CSSProperties = {
  background: "rgba(148,163,184,0.15)",
  padding: "1px 4px",
  borderRadius: 3,
  fontSize: 12,
};
const th: React.CSSProperties = {
  textAlign: "left",
  padding: "8px 10px",
  borderBottom: "2px solid #333",
  fontSize: 12,
};
const thNum: React.CSSProperties = { ...th, textAlign: "right" };
const td: React.CSSProperties = {
  padding: "6px 10px",
  borderBottom: "1px solid #eee",
  fontSize: 12,
  verticalAlign: "middle",
};
const tdNum: React.CSSProperties = {
  ...td,
  textAlign: "right",
  fontVariantNumeric: "tabular-nums",
};
