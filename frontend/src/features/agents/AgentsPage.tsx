import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "../../shared/api";
import { MergeDialog } from "../../shared/ui/MergeDialog";
import { norm, SearchInput } from "../../shared/ui/SearchInput";
import { TableSkeleton } from "../../shared/ui/Skeleton";
import { useToast } from "../../shared/ui/ToastProvider";
import { useBulkSelection } from "../../shared/ui/useBulkSelection";
import { useAuth } from "../auth/AuthContext";
import { bulkSetActiveAgents, createAgent, listAgents, mergeAgents } from "./api";
import type { Agent } from "./types";

export default function AgentsPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const toast = useToast();
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mergeOpen, setMergeOpen] = useState(false);
  const [search, setSearch] = useState("");

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setAgents(await listAgents());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Eroare la încărcare");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await createAgent({
        fullName,
        email: email.trim() || null,
        phone: phone.trim() || null,
      });
      setFullName("");
      setEmail("");
      setPhone("");
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Eroare la creare");
    } finally {
      setSubmitting(false);
    }
  }

  const filtered = useMemo(() => {
    const q = norm(search);
    if (!q) return agents;
    return agents.filter((a) =>
      norm(`${a.fullName} ${a.email ?? ""} ${a.phone ?? ""}`).includes(q),
    );
  }, [agents, search]);

  const selection = useBulkSelection(filtered.map((a) => a.id));

  async function handleMerge(primaryId: string, duplicateIds: string[]) {
    try {
      const r = await mergeAgents(primaryId, duplicateIds);
      toast.success(
        `Consolidat: ${r.mergedCount} agenți · ${r.aliasesReassigned} alias · ${r.salesReassigned} vânzări`,
      );
      await refresh();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Eroare la consolidare");
      throw err;
    }
  }

  async function handleBulkActive(active: boolean) {
    const ids = Array.from(selection.selected);
    if (ids.length === 0) return;
    try {
      const r = await bulkSetActiveAgents(ids, active);
      toast.success(`${r.updated} agenți ${active ? "activați" : "dezactivați"}`);
      selection.clear();
      await refresh();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Eroare");
    }
  }

  return (
    <div className="agent-section">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2 style={{ marginTop: 0 }}>Agenți canonici</h2>
        {isAdmin && agents.length >= 2 && (
          <button onClick={() => setMergeOpen(true)} style={styles.btn}>
            Consolidează duplicate
          </button>
        )}
      </div>

      {mergeOpen && (
        <MergeDialog
          title="Consolidează agenți duplicat"
          items={agents.map((a) => ({
            id: a.id,
            label: `${a.fullName}${a.email ? ` · ${a.email}` : ""}`,
          }))}
          onClose={() => setMergeOpen(false)}
          onMerge={handleMerge}
          entityNoun="agenți"
        />
      )}

      <form onSubmit={handleCreate} style={styles.form}>
        <strong>Adaugă agent nou</strong>
        <div style={styles.row}>
          <input
            required
            placeholder="Nume complet"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            style={{ ...styles.input, flex: 2 }}
          />
          <input
            type="email"
            placeholder="Email (opțional)"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            style={{ ...styles.input, flex: 2 }}
          />
          <input
            placeholder="Telefon (opțional)"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            style={{ ...styles.input, flex: 1 }}
          />
          <button type="submit" disabled={submitting} style={styles.btn}>
            {submitting ? "Salvez…" : "Adaugă"}
          </button>
        </div>
      </form>

      {error && <p style={{ color: "#b00020" }}>{error}</p>}

      {agents.length > 0 && (
        <SearchInput
          value={search}
          onChange={setSearch}
          placeholder="Caută după nume, email sau telefon…"
          total={agents.length}
          visible={filtered.length}
        />
      )}

      {isAdmin && selection.count > 0 && (
        <div style={bulkStyles.bar}>
          <span>{selection.count} selectați</span>
          <button onClick={() => handleBulkActive(true)} style={bulkStyles.btn}>Activează</button>
          <button onClick={() => handleBulkActive(false)} style={bulkStyles.btn}>Dezactivează</button>
          <button onClick={selection.clear} style={bulkStyles.btnGhost}>Anulează</button>
        </div>
      )}

      {loading && agents.length === 0 ? (
        <TableSkeleton rows={6} cols={6} />
      ) : (
      <table style={styles.table}>
        <thead>
          <tr>
            {isAdmin && (
              <th style={{ ...th, width: 28 }}>
                <input
                  type="checkbox"
                  checked={selection.allVisibleSelected}
                  onChange={selection.toggleAll}
                  aria-label="Selectează toți"
                />
              </th>
            )}
            <th style={th}>Nume</th>
            <th style={th}>Email</th>
            <th style={th}>Telefon</th>
            <th style={th}>Activ</th>
            <th style={th}>Creat</th>
          </tr>
        </thead>
        <tbody>
          {agents.length === 0 ? (
            <tr><td colSpan={isAdmin ? 6 : 5} style={td}>Niciun agent definit încă.</td></tr>
          ) : filtered.length === 0 ? (
            <tr><td colSpan={isAdmin ? 6 : 5} style={td}>Niciun rezultat pentru „{search}".</td></tr>
          ) : (
            filtered.map((a) => (
              <tr key={a.id} style={selection.isSelected(a.id) ? { background: "var(--accent-soft, #eff6ff)" } : undefined}>
                {isAdmin && (
                  <td style={td}>
                    <input
                      type="checkbox"
                      checked={selection.isSelected(a.id)}
                      onChange={() => selection.toggle(a.id)}
                      aria-label={`Selectează ${a.fullName}`}
                    />
                  </td>
                )}
                <td style={td}>
                  <Link to={`/agents/${a.id}`} style={linkStyle}>{a.fullName}</Link>
                </td>
                <td style={td}>{a.email ?? "—"}</td>
                <td style={td}>{a.phone ?? "—"}</td>
                <td style={td}>{a.active ? "da" : "nu"}</td>
                <td style={td}>{new Date(a.createdAt).toLocaleString("ro-RO")}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  form: {
    padding: 16,
    background: "#fafafa",
    border: "1px solid #eee",
    borderRadius: 6,
    marginBottom: 20,
    display: "flex",
    flexDirection: "column",
    gap: 10,
  },
  row: { display: "flex", gap: 8 },
  input: { padding: 8, fontSize: 14, border: "1px solid #ccc", borderRadius: 4 },
  btn: { padding: "8px 16px", fontSize: 14, cursor: "pointer" },
  table: { borderCollapse: "collapse", width: "100%" },
};
const linkStyle: React.CSSProperties = {
  color: "#2563eb", textDecoration: "none", fontWeight: 500,
};
const bulkStyles: Record<string, React.CSSProperties> = {
  bar: {
    display: "flex", alignItems: "center", gap: 10,
    padding: "8px 14px", marginBottom: 10,
    background: "var(--accent-soft, #eff6ff)",
    border: "1px solid var(--accent, #2563eb)", borderRadius: 6,
    fontSize: 13,
  },
  btn: {
    padding: "5px 12px", fontSize: 13, cursor: "pointer",
    background: "#2563eb", color: "#fff", border: "none", borderRadius: 4,
  },
  btnGhost: {
    padding: "5px 10px", fontSize: 12, cursor: "pointer",
    background: "transparent", color: "var(--fg-muted, #666)",
    border: "1px solid var(--border, #ccc)", borderRadius: 4,
    marginLeft: "auto",
  },
};
const th: React.CSSProperties = {
  textAlign: "left",
  padding: "8px 12px",
  borderBottom: "2px solid #333",
  fontSize: 13,
};
const td: React.CSSProperties = {
  padding: "6px 12px",
  borderBottom: "1px solid #eee",
  fontSize: 13,
};
