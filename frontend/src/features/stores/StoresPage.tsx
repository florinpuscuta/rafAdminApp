import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "../../shared/api";
import { MergeDialog } from "../../shared/ui/MergeDialog";
import { norm, SearchInput } from "../../shared/ui/SearchInput";
import { TableSkeleton } from "../../shared/ui/Skeleton";
import { useToast } from "../../shared/ui/ToastProvider";
import { useBulkSelection } from "../../shared/ui/useBulkSelection";
import { useAuth } from "../auth/AuthContext";
import { bulkSetActiveStores, createStore, listStores, mergeStores } from "./api";
import type { Store } from "./types";

export default function StoresPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const toast = useToast();
  const [stores, setStores] = useState<Store[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mergeOpen, setMergeOpen] = useState(false);
  const [search, setSearch] = useState("");

  const [name, setName] = useState("");
  const [chain, setChain] = useState("");
  const [city, setCity] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setStores(await listStores());
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
      await createStore({
        name,
        chain: chain.trim() || null,
        city: city.trim() || null,
      });
      setName("");
      setChain("");
      setCity("");
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Eroare la creare");
    } finally {
      setSubmitting(false);
    }
  }

  const filtered = useMemo(() => {
    const q = norm(search);
    if (!q) return stores;
    return stores.filter((s) =>
      norm(`${s.name} ${s.chain ?? ""} ${s.city ?? ""}`).includes(q),
    );
  }, [stores, search]);

  const selection = useBulkSelection(filtered.map((s) => s.id));

  async function handleMerge(primaryId: string, duplicateIds: string[]) {
    try {
      const r = await mergeStores(primaryId, duplicateIds);
      toast.success(
        `Consolidate: ${r.mergedCount} magazine · ${r.aliasesReassigned} alias · ${r.salesReassigned} vânzări`,
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
      const r = await bulkSetActiveStores(ids, active);
      toast.success(`${r.updated} magazine ${active ? "activate" : "dezactivate"}`);
      selection.clear();
      await refresh();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Eroare");
    }
  }

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2 style={{ marginTop: 0 }}>Magazine canonice</h2>
        {isAdmin && stores.length >= 2 && (
          <button onClick={() => setMergeOpen(true)} style={styles.btn}>
            Consolidează duplicate
          </button>
        )}
      </div>

      {mergeOpen && (
        <MergeDialog
          title="Consolidează magazine duplicate"
          items={stores.map((s) => ({
            id: s.id,
            label: `${s.name}${s.chain ? ` · ${s.chain}` : ""}${s.city ? ` · ${s.city}` : ""}`,
          }))}
          onClose={() => setMergeOpen(false)}
          onMerge={handleMerge}
          entityNoun="magazine"
        />
      )}

      <form onSubmit={handleCreate} style={styles.form}>
        <strong>Adaugă magazin nou</strong>
        <div style={styles.row}>
          <input
            required
            placeholder="Nume (ex: Dedeman Bucuresti Pipera)"
            value={name}
            onChange={(e) => setName(e.target.value)}
            style={{ ...styles.input, flex: 2 }}
          />
          <input
            placeholder="Lanț (DEDEMAN)"
            value={chain}
            onChange={(e) => setChain(e.target.value)}
            style={{ ...styles.input, flex: 1 }}
          />
          <input
            placeholder="Oraș"
            value={city}
            onChange={(e) => setCity(e.target.value)}
            style={{ ...styles.input, flex: 1 }}
          />
          <button type="submit" disabled={submitting} style={styles.btn}>
            {submitting ? "Salvez…" : "Adaugă"}
          </button>
        </div>
      </form>

      {error && <p style={{ color: "#b00020" }}>{error}</p>}

      {stores.length > 0 && (
        <SearchInput
          value={search}
          onChange={setSearch}
          placeholder="Caută după nume, lanț sau oraș…"
          total={stores.length}
          visible={filtered.length}
        />
      )}

      {isAdmin && selection.count > 0 && (
        <div style={styles.bulkBar}>
          <span>{selection.count} selectate</span>
          <button onClick={() => handleBulkActive(true)} style={styles.bulkBtn}>Activează</button>
          <button onClick={() => handleBulkActive(false)} style={styles.bulkBtn}>Dezactivează</button>
          <button onClick={selection.clear} style={styles.bulkBtnGhost}>Anulează</button>
        </div>
      )}

      {loading && stores.length === 0 ? (
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
                  aria-label="Selectează toate"
                />
              </th>
            )}
            <th style={th}>Nume</th>
            <th style={th}>Lanț</th>
            <th style={th}>Oraș</th>
            <th style={th}>Activ</th>
            <th style={th}>Creat</th>
          </tr>
        </thead>
        <tbody>
          {stores.length === 0 ? (
            <tr><td colSpan={isAdmin ? 6 : 5} style={td}>Niciun magazin definit încă.</td></tr>
          ) : filtered.length === 0 ? (
            <tr><td colSpan={isAdmin ? 6 : 5} style={td}>Niciun rezultat pentru „{search}".</td></tr>
          ) : (
            filtered.map((s) => (
              <tr key={s.id} style={selection.isSelected(s.id) ? { background: "var(--accent-soft, #eff6ff)" } : undefined}>
                {isAdmin && (
                  <td style={td}>
                    <input
                      type="checkbox"
                      checked={selection.isSelected(s.id)}
                      onChange={() => selection.toggle(s.id)}
                      aria-label={`Selectează ${s.name}`}
                    />
                  </td>
                )}
                <td style={td}>
                  <Link to={`/stores/${s.id}`} style={linkStyle}>{s.name}</Link>
                </td>
                <td style={td}>{s.chain ?? "—"}</td>
                <td style={td}>{s.city ?? "—"}</td>
                <td style={td}>{s.active ? "da" : "nu"}</td>
                <td style={td}>{new Date(s.createdAt).toLocaleString("ro-RO")}</td>
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
  bulkBar: {
    display: "flex", alignItems: "center", gap: 10,
    padding: "8px 14px", marginBottom: 10,
    background: "var(--accent-soft, #eff6ff)",
    border: "1px solid var(--accent, #2563eb)", borderRadius: 6,
    fontSize: 13,
  },
  bulkBtn: {
    padding: "5px 12px", fontSize: 13, cursor: "pointer",
    background: "#2563eb", color: "#fff", border: "none", borderRadius: 4,
  },
  bulkBtnGhost: {
    padding: "5px 10px", fontSize: 12, cursor: "pointer",
    background: "transparent", color: "var(--fg-muted, #666)",
    border: "1px solid var(--border, #ccc)", borderRadius: 4,
    marginLeft: "auto",
  },
};
const linkStyle: React.CSSProperties = {
  color: "#2563eb", textDecoration: "none", fontWeight: 500,
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
