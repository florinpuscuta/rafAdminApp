import { useCallback, useEffect, useState } from "react";

import { ApiError } from "../../shared/api";
import { useToast } from "../../shared/ui/ToastProvider";
import { listAgents } from "../agents/api";
import type { Agent } from "../agents/types";
import { listStores } from "../stores/api";
import type { Store } from "../stores/types";
import { assign, listAssignments, unassign, type Assignment } from "./api";

export default function AssignmentsPage() {
  const toast = useToast();
  const [stores, setStores] = useState<Store[]>([]);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, a, asn] = await Promise.all([
        listStores(),
        listAgents(),
        listAssignments(),
      ]);
      setStores(s);
      setAgents(a);
      setAssignments(asn);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Eroare");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  function isAssigned(agentId: string, storeId: string): boolean {
    return assignments.some((a) => a.agentId === agentId && a.storeId === storeId);
  }

  async function toggle(agentId: string, storeId: string) {
    const key = `${agentId}:${storeId}`;
    setBusy(key);
    try {
      if (isAssigned(agentId, storeId)) {
        await unassign(agentId, storeId);
      } else {
        await assign(agentId, storeId);
      }
      await refresh();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Eroare");
    } finally {
      setBusy(null);
    }
  }

  if (loading && stores.length === 0) return <p>Se încarcă…</p>;
  if (error) return <p style={{ color: "#b00020" }}>{error}</p>;

  if (stores.length === 0 || agents.length === 0) {
    return (
      <div>
        <h2 style={{ marginTop: 0 }}>Asignare agenți la magazine</h2>
        <p style={{ color: "#666" }}>
          Ai nevoie de cel puțin un agent și un magazin canonic pentru a asigna.
          {stores.length === 0 && " Creează întâi magazine."}
          {agents.length === 0 && " Creează întâi agenți."}
        </p>
      </div>
    );
  }

  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Asignare agenți la magazine</h2>
      <p style={{ color: "#666", fontSize: 14, marginTop: 0 }}>
        Bifează cine acoperă fiecare magazin. Un magazin poate fi asignat la
        mai mulți agenți (de ex. team coverage).
      </p>

      <div style={styles.wrap}>
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.thStore}>Magazin / Agent</th>
              {agents.map((a) => (
                <th key={a.id} style={styles.thAgent}>
                  <div style={{ transform: "rotate(-35deg)", whiteSpace: "nowrap" }}>
                    {a.fullName}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {stores.map((s) => (
              <tr key={s.id}>
                <td style={styles.tdStore}>
                  {s.name}
                  {s.chain && (
                    <div style={{ fontSize: 11, color: "#888" }}>{s.chain}</div>
                  )}
                </td>
                {agents.map((a) => {
                  const on = isAssigned(a.id, s.id);
                  const key = `${a.id}:${s.id}`;
                  return (
                    <td key={a.id} style={styles.tdCell}>
                      <input
                        type="checkbox"
                        checked={on}
                        disabled={busy === key}
                        onChange={() => toggle(a.id, s.id)}
                      />
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  wrap: {
    overflow: "auto",
    background: "#fff",
    border: "1px solid #eee",
    borderRadius: 6,
  },
  table: { borderCollapse: "collapse", minWidth: "100%" },
  thStore: {
    position: "sticky",
    left: 0,
    background: "#fafafa",
    padding: "12px 14px",
    borderBottom: "2px solid #333",
    fontSize: 13,
    textAlign: "left",
    minWidth: 200,
  },
  thAgent: {
    padding: "12px 8px",
    borderBottom: "2px solid #333",
    fontSize: 12,
    minWidth: 60,
    height: 120,
    verticalAlign: "bottom",
  },
  tdStore: {
    position: "sticky",
    left: 0,
    background: "#fff",
    padding: "8px 14px",
    borderBottom: "1px solid #eee",
    fontSize: 13,
    minWidth: 200,
  },
  tdCell: {
    padding: "8px",
    borderBottom: "1px solid #eee",
    textAlign: "center",
  },
};
