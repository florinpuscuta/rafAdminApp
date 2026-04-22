import { useCallback, useEffect, useState } from "react";

import { ApiError } from "../../shared/api";
import { useToast } from "../../shared/ui/ToastProvider";
import { createProductAlias, listProducts, listUnmappedProducts } from "./api";
import type { Product, UnmappedProductRow } from "./types";

export default function UnmappedProductsPage() {
  const toast = useToast();
  const [unmapped, setUnmapped] = useState<UnmappedProductRow[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [selection, setSelection] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [savingFor, setSavingFor] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [u, p] = await Promise.all([listUnmappedProducts(), listProducts()]);
      setUnmapped(u);
      setProducts(p);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Eroare la încărcare");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function handleMap(rawCode: string) {
    const productId = selection[rawCode];
    if (!productId) return;
    setSavingFor(rawCode);
    setError(null);
    try {
      await createProductAlias({ rawCode, productId });
      toast.success(`Mapat "${rawCode}"`);
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
      <h2 style={{ marginTop: 0 }}>Produse nemapate</h2>
      <p style={styles.hint}>
        Coduri produs brute din Excel care nu-s încă legate de un produs canonic.
        {products.length === 0 && (
          <>
            {" "}Adaugă întâi produse în <a href="/products">Produse canonice</a>.
          </>
        )}
      </p>

      {error && <p style={{ color: "#b00020" }}>{error}</p>}

      {unmapped.length === 0 ? (
        <p>🎉 Toate codurile sunt mapate.</p>
      ) : (
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={th}>Cod brut</th>
              <th style={th}>Exemplu nume</th>
              <th style={thNum}>Linii</th>
              <th style={thNum}>Total (RON)</th>
              <th style={th}>Mapează la produs</th>
              <th style={th}></th>
            </tr>
          </thead>
          <tbody>
            {unmapped.map((row) => (
              <tr key={row.rawCode}>
                <td style={td}><code>{row.rawCode}</code></td>
                <td style={td}>{row.sampleName ?? "—"}</td>
                <td style={tdNum}>{row.rowCount}</td>
                <td style={tdNum}>{row.totalAmount}</td>
                <td style={td}>
                  <select
                    value={selection[row.rawCode] ?? ""}
                    onChange={(e) =>
                      setSelection((s) => ({ ...s, [row.rawCode]: e.target.value }))
                    }
                    style={styles.select}
                    disabled={products.length === 0}
                  >
                    <option value="">— alege —</option>
                    {products.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.code} — {p.name}
                      </option>
                    ))}
                  </select>
                </td>
                <td style={td}>
                  <button
                    onClick={() => handleMap(row.rawCode)}
                    disabled={!selection[row.rawCode] || savingFor === row.rawCode}
                    style={styles.btn}
                  >
                    {savingFor === row.rawCode ? "…" : "Mapează"}
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
  select: { padding: 6, fontSize: 13, minWidth: 260 },
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
