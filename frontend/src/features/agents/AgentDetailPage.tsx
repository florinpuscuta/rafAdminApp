import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError } from "../../shared/api";
import { Skeleton, TableSkeleton } from "../../shared/ui/Skeleton";
import { listAssignments } from "../assignments/api";
import { listSales } from "../sales/api";
import type { Sale } from "../sales/types";
import { listStores } from "../stores/api";
import type { Store } from "../stores/types";
import { listAgentAliases, listAgents } from "./api";
import type { Agent, AgentAlias } from "./types";

export default function AgentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [agent, setAgent] = useState<Agent | null>(null);
  const [aliases, setAliases] = useState<AgentAlias[]>([]);
  const [sales, setSales] = useState<Sale[]>([]);
  const [totalSales, setTotalSales] = useState(0);
  const [assignedStores, setAssignedStores] = useState<Store[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const [agents, allAliases, salesResp, assigns, stores] = await Promise.all([
        listAgents(),
        listAgentAliases(),
        listSales(1, 20, { agentId: id }),
        listAssignments(),
        listStores(),
      ]);
      setAgent(agents.find((a) => a.id === id) ?? null);
      setAliases(allAliases.filter((a) => a.agentId === id));
      setSales(salesResp.items);
      setTotalSales(salesResp.total);
      const myStoreIds = new Set(assigns.filter((x) => x.agentId === id).map((x) => x.storeId));
      setAssignedStores(stores.filter((s) => myStoreIds.has(s.id)));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Eroare la încărcare");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) return (
    <div>
      <Skeleton width={240} height={26} style={{ marginBottom: 12 }} />
      <TableSkeleton rows={3} cols={3} />
      <div style={{ marginTop: 20 }}>
        <TableSkeleton rows={6} cols={4} />
      </div>
    </div>
  );
  if (error) return <p style={{ color: "#b00020" }}>{error}</p>;
  if (!agent) return (
    <div>
      <p>Agent inexistent.</p>
      <Link to="/agents">← Înapoi la agenți</Link>
    </div>
  );

  const totalAmount = sales.reduce((sum, s) => sum + Number(s.amount), 0);

  return (
    <div>
      <Link to="/agents" style={styles.back}>← Toți agenții</Link>
      <h2 style={{ marginTop: 6 }}>{agent.fullName}</h2>
      <div style={styles.metaRow}>
        {agent.email && <span style={styles.tag}>{agent.email}</span>}
        {agent.phone && <span style={styles.tag}>{agent.phone}</span>}
        <span style={agent.active ? styles.tag : styles.tagInactive}>
          {agent.active ? "activ" : "inactiv"}
        </span>
      </div>

      <section style={styles.section}>
        <h3 style={styles.h3}>Magazine acoperite ({assignedStores.length})</h3>
        {assignedStores.length === 0 ? (
          <p style={styles.empty}>Niciun magazin atribuit.</p>
        ) : (
          <ul style={styles.aliasList}>
            {assignedStores.map((s) => (
              <li key={s.id} style={styles.aliasRow}>
                <Link to={`/stores/${s.id}`} style={styles.link}>{s.name}</Link>
                {s.chain && <span style={styles.aliasDate}>{s.chain}</span>}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section style={styles.section}>
        <h3 style={styles.h3}>Alias-uri ({aliases.length})</h3>
        {aliases.length === 0 ? (
          <p style={styles.empty}>Niciun alias înregistrat.</p>
        ) : (
          <ul style={styles.aliasList}>
            {aliases.map((a) => (
              <li key={a.id} style={styles.aliasRow}>
                <code>{a.rawAgent}</code>
                <span style={styles.aliasDate}>
                  {new Date(a.resolvedAt).toLocaleDateString("ro-RO")}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section style={styles.section}>
        <h3 style={styles.h3}>
          Vânzări recente ({totalSales} total · {sales.length} afișate)
        </h3>
        {sales.length === 0 ? (
          <p style={styles.empty}>Nicio vânzare înregistrată.</p>
        ) : (
          <>
            <p style={styles.summary}>
              Total pe rândurile de mai jos: <strong>{totalAmount.toFixed(2)} lei</strong>
            </p>
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={th}>Perioadă</th>
                  <th style={th}>Client</th>
                  <th style={th}>Produs</th>
                  <th style={{ ...th, textAlign: "right" }}>Sumă</th>
                </tr>
              </thead>
              <tbody>
                {sales.map((s) => (
                  <tr key={s.id}>
                    <td style={td}>{s.year}-{String(s.month).padStart(2, "0")}</td>
                    <td style={td}>{s.client}</td>
                    <td style={td}>{s.productName ?? s.productCode ?? "—"}</td>
                    <td style={{ ...td, textAlign: "right" }}>
                      {Number(s.amount).toFixed(2)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </section>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  back: { color: "#2563eb", textDecoration: "none", fontSize: 13 },
  link: { color: "#2563eb", textDecoration: "none" },
  metaRow: { display: "flex", gap: 8, marginBottom: 20, flexWrap: "wrap" },
  tag: {
    padding: "3px 10px", background: "#eff6ff", color: "#1e40af",
    borderRadius: 12, fontSize: 12, fontWeight: 500,
  },
  tagInactive: {
    padding: "3px 10px", background: "#f3f4f6", color: "#6b7280",
    borderRadius: 12, fontSize: 12,
  },
  section: { marginBottom: 28 },
  h3: { fontSize: 15, margin: "0 0 10px", borderBottom: "1px solid var(--border, #eee)", paddingBottom: 6 },
  aliasList: { listStyle: "none", margin: 0, padding: 0 },
  aliasRow: {
    display: "flex", justifyContent: "space-between",
    padding: "6px 10px", borderBottom: "1px solid var(--border, #f3f4f6)",
    fontSize: 13,
  },
  aliasDate: { color: "var(--fg-muted, #888)", fontSize: 12 },
  empty: { color: "var(--fg-muted, #888)", fontSize: 13, fontStyle: "italic" },
  summary: { fontSize: 13, margin: "0 0 8px", color: "var(--fg-muted, #555)" },
  table: { borderCollapse: "collapse", width: "100%" },
};
const th: React.CSSProperties = {
  textAlign: "left", padding: "6px 10px",
  borderBottom: "2px solid var(--border, #333)", fontSize: 13,
};
const td: React.CSSProperties = {
  padding: "5px 10px",
  borderBottom: "1px solid var(--border, #eee)", fontSize: 13,
};
