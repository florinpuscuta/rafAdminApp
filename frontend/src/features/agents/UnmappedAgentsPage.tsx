import { useCallback, useEffect, useState } from "react";

import { ApiError } from "../../shared/api";
import { useToast } from "../../shared/ui/ToastProvider";
import { createAgentAlias, listAgents, listUnmappedAgents } from "./api";
import type { Agent, UnmappedAgentRow } from "./types";

export default function UnmappedAgentsPage() {
  const toast = useToast();
  const [unmapped, setUnmapped] = useState<UnmappedAgentRow[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [selection, setSelection] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [savingFor, setSavingFor] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [u, a] = await Promise.all([listUnmappedAgents(), listAgents()]);
      setUnmapped(u);
      setAgents(a);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Eroare la încărcare");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function handleMap(rawAgent: string) {
    const agentId = selection[rawAgent];
    if (!agentId) return;
    setSavingFor(rawAgent);
    setError(null);
    try {
      await createAgentAlias({ rawAgent, agentId });
      toast.success(`Mapat "${rawAgent}"`);
      await refresh();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Eroare la mapare";
      toast.error(msg);
      setError(msg);
    } finally {
      setSavingFor(null);
    }
  }

  if (loading && unmapped.length === 0) return <p>Se încarcă…</p>;

  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Agenți nemapați</h2>
      <p style={styles.hint}>
        String-urile brute din Excel care nu-s încă legate de un agent canonic.
        Mapează inclusiv tipo-uri la același agent — o singură sursă de adevăr.
        {agents.length === 0 && (
          <>
            {" "}Momentan nu ai niciun agent — mergi la{" "}
            <a href="/agents">Agenți</a> ca să adaugi.
          </>
        )}
      </p>

      {error && <p style={{ color: "#b00020" }}>{error}</p>}

      {unmapped.length === 0 ? (
        <p>🎉 Toți agenții sunt mapați.</p>
      ) : (
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={th}>String brut (raw_agent)</th>
              <th style={thNum}>Linii</th>
              <th style={thNum}>Total (RON)</th>
              <th style={th}>Mapează la agent</th>
              <th style={th}></th>
            </tr>
          </thead>
          <tbody>
            {unmapped.map((row) => (
              <tr key={row.rawAgent}>
                <td style={td}><code>{row.rawAgent}</code></td>
                <td style={tdNum}>{row.rowCount}</td>
                <td style={tdNum}>{row.totalAmount}</td>
                <td style={td}>
                  <select
                    value={selection[row.rawAgent] ?? ""}
                    onChange={(e) =>
                      setSelection((s) => ({ ...s, [row.rawAgent]: e.target.value }))
                    }
                    style={styles.select}
                    disabled={agents.length === 0}
                  >
                    <option value="">— alege —</option>
                    {agents.map((a) => (
                      <option key={a.id} value={a.id}>
                        {a.fullName}
                      </option>
                    ))}
                  </select>
                </td>
                <td style={td}>
                  <button
                    onClick={() => handleMap(row.rawAgent)}
                    disabled={
                      !selection[row.rawAgent] || savingFor === row.rawAgent
                    }
                    style={styles.btn}
                  >
                    {savingFor === row.rawAgent ? "…" : "Mapează"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  hint: { fontSize: 14, color: "#555" },
  table: { borderCollapse: "collapse", width: "100%" },
  select: { padding: 6, fontSize: 13, minWidth: 220 },
  btn: { padding: "6px 12px", fontSize: 13, cursor: "pointer" },
};
const th: React.CSSProperties = {
  textAlign: "left",
  padding: "8px 12px",
  borderBottom: "2px solid #333",
  fontSize: 13,
};
const thNum: React.CSSProperties = { ...th, textAlign: "right" };
const td: React.CSSProperties = {
  padding: "6px 12px",
  borderBottom: "1px solid #eee",
  fontSize: 13,
};
const tdNum: React.CSSProperties = {
  ...td,
  textAlign: "right",
  fontVariantNumeric: "tabular-nums",
};
