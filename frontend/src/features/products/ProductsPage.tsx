import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "../../shared/api";
import { MergeDialog } from "../../shared/ui/MergeDialog";
import { norm, SearchInput } from "../../shared/ui/SearchInput";
import { TableSkeleton } from "../../shared/ui/Skeleton";
import { useToast } from "../../shared/ui/ToastProvider";
import { useBulkSelection } from "../../shared/ui/useBulkSelection";
import { useAuth } from "../auth/AuthContext";
import { bulkSetActiveProducts, createProduct, listProducts, mergeProducts } from "./api";
import type { Product } from "./types";

export default function ProductsPage() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const toast = useToast();
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mergeOpen, setMergeOpen] = useState(false);
  const [search, setSearch] = useState("");

  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [category, setCategory] = useState("");
  const [brand, setBrand] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setProducts(await listProducts());
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
      await createProduct({
        code,
        name,
        category: category.trim() || null,
        brand: brand.trim() || null,
      });
      setCode("");
      setName("");
      setCategory("");
      setBrand("");
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Eroare la creare");
    } finally {
      setSubmitting(false);
    }
  }

  const filtered = useMemo(() => {
    const q = norm(search);
    if (!q) return products;
    return products.filter((p) =>
      norm(`${p.code} ${p.name} ${p.category ?? ""} ${p.brand ?? ""}`).includes(q),
    );
  }, [products, search]);

  const selection = useBulkSelection(filtered.map((p) => p.id));

  async function handleMerge(primaryId: string, duplicateIds: string[]) {
    try {
      const r = await mergeProducts(primaryId, duplicateIds);
      toast.success(
        `Consolidate: ${r.mergedCount} produse · ${r.aliasesReassigned} alias · ${r.salesReassigned} vânzări`,
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
      const r = await bulkSetActiveProducts(ids, active);
      toast.success(`${r.updated} produse ${active ? "activate" : "dezactivate"}`);
      selection.clear();
      await refresh();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Eroare");
    }
  }

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2 style={{ marginTop: 0 }}>Produse canonice</h2>
        {isAdmin && products.length >= 2 && (
          <button onClick={() => setMergeOpen(true)} style={styles.btn}>
            Consolidează duplicate
          </button>
        )}
      </div>

      {mergeOpen && (
        <MergeDialog
          title="Consolidează produse duplicate"
          items={products.map((p) => ({
            id: p.id,
            label: `${p.code} · ${p.name}${p.category ? ` · ${p.category}` : ""}`,
          }))}
          onClose={() => setMergeOpen(false)}
          onMerge={handleMerge}
          entityNoun="produse"
        />
      )}

      <form onSubmit={handleCreate} style={styles.form}>
        <strong>Adaugă produs nou</strong>
        <div style={styles.row}>
          <input
            required
            placeholder="Cod (SKU canonic)"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            style={{ ...styles.input, flex: 1 }}
          />
          <input
            required
            placeholder="Nume"
            value={name}
            onChange={(e) => setName(e.target.value)}
            style={{ ...styles.input, flex: 2 }}
          />
          <input
            placeholder="Categorie"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            style={{ ...styles.input, flex: 1 }}
          />
          <input
            placeholder="Brand"
            value={brand}
            onChange={(e) => setBrand(e.target.value)}
            style={{ ...styles.input, flex: 1 }}
          />
          <button type="submit" disabled={submitting} style={styles.btn}>
            {submitting ? "Salvez…" : "Adaugă"}
          </button>
        </div>
      </form>

      {error && <p style={{ color: "#b00020" }}>{error}</p>}

      {products.length > 0 && (
        <SearchInput
          value={search}
          onChange={setSearch}
          placeholder="Caută după cod, nume, categorie sau brand…"
          total={products.length}
          visible={filtered.length}
        />
      )}

      {isAdmin && selection.count > 0 && (
        <div style={bulkStyles.bar}>
          <span>{selection.count} selectate</span>
          <button onClick={() => handleBulkActive(true)} style={bulkStyles.btn}>Activează</button>
          <button onClick={() => handleBulkActive(false)} style={bulkStyles.btn}>Dezactivează</button>
          <button onClick={selection.clear} style={bulkStyles.btnGhost}>Anulează</button>
        </div>
      )}

      {loading && products.length === 0 ? (
        <TableSkeleton rows={6} cols={7} />
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
            <th style={th}>Cod</th>
            <th style={th}>Nume</th>
            <th style={th}>Categorie</th>
            <th style={th}>Brand</th>
            <th style={th}>Activ</th>
            <th style={th}>Creat</th>
          </tr>
        </thead>
        <tbody>
          {products.length === 0 ? (
            <tr><td colSpan={isAdmin ? 7 : 6} style={td}>Niciun produs definit încă.</td></tr>
          ) : filtered.length === 0 ? (
            <tr><td colSpan={isAdmin ? 7 : 6} style={td}>Niciun rezultat pentru „{search}".</td></tr>
          ) : (
            filtered.map((p) => (
              <tr key={p.id} style={selection.isSelected(p.id) ? { background: "var(--accent-soft, #eff6ff)" } : undefined}>
                {isAdmin && (
                  <td style={td}>
                    <input
                      type="checkbox"
                      checked={selection.isSelected(p.id)}
                      onChange={() => selection.toggle(p.id)}
                      aria-label={`Selectează ${p.name}`}
                    />
                  </td>
                )}
                <td style={td}><code>{p.code}</code></td>
                <td style={td}>
                  <Link to={`/products/${p.id}`} style={linkStyle}>{p.name}</Link>
                </td>
                <td style={td}>{p.category ?? "—"}</td>
                <td style={td}>{p.brand ?? "—"}</td>
                <td style={td}>{p.active ? "da" : "nu"}</td>
                <td style={td}>{new Date(p.createdAt).toLocaleString("ro-RO")}</td>
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
