import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError } from "../../shared/api";
import { Skeleton, TableSkeleton } from "../../shared/ui/Skeleton";
import { listSales } from "../sales/api";
import type { Sale } from "../sales/types";
import { listProductAliases, listProducts } from "./api";
import type { Product, ProductAlias } from "./types";

export default function ProductDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [product, setProduct] = useState<Product | null>(null);
  const [aliases, setAliases] = useState<ProductAlias[]>([]);
  const [sales, setSales] = useState<Sale[]>([]);
  const [totalSales, setTotalSales] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const [products, allAliases, salesResp] = await Promise.all([
        listProducts(),
        listProductAliases(),
        listSales(1, 20, { productId: id }),
      ]);
      setProduct(products.find((p) => p.id === id) ?? null);
      setAliases(allAliases.filter((a) => a.productId === id));
      setSales(salesResp.items);
      setTotalSales(salesResp.total);
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
        <TableSkeleton rows={6} cols={5} />
      </div>
    </div>
  );
  if (error) return <p style={{ color: "#b00020" }}>{error}</p>;
  if (!product) return (
    <div>
      <p>Produs inexistent.</p>
      <Link to="/products">← Înapoi la produse</Link>
    </div>
  );

  const totalAmount = sales.reduce((sum, s) => sum + Number(s.amount), 0);
  const totalQty = sales.reduce((sum, s) => sum + Number(s.quantity ?? 0), 0);

  return (
    <div>
      <Link to="/products" style={styles.back}>← Toate produsele</Link>
      <h2 style={{ marginTop: 6 }}>{product.name}</h2>
      <div style={styles.metaRow}>
        <span style={styles.tag}>{product.code}</span>
        {product.category && <span style={styles.tag}>{product.category}</span>}
        {product.brand && <span style={styles.tag}>{product.brand}</span>}
        <span style={product.active ? styles.tag : styles.tagInactive}>
          {product.active ? "activ" : "inactiv"}
        </span>
      </div>

      <section style={styles.section}>
        <h3 style={styles.h3}>Coduri (alias-uri) ({aliases.length})</h3>
        {aliases.length === 0 ? (
          <p style={styles.empty}>Niciun cod mapat încă.</p>
        ) : (
          <ul style={styles.aliasList}>
            {aliases.map((a) => (
              <li key={a.id} style={styles.aliasRow}>
                <code>{a.rawCode}</code>
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
              Pe rândurile de mai jos: <strong>{totalAmount.toFixed(2)} lei</strong>
              {totalQty > 0 && <> · <strong>{totalQty.toFixed(2)} unități</strong></>}
            </p>
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={th}>Perioadă</th>
                  <th style={th}>Client</th>
                  <th style={th}>Agent</th>
                  <th style={{ ...th, textAlign: "right" }}>Cant.</th>
                  <th style={{ ...th, textAlign: "right" }}>Sumă</th>
                </tr>
              </thead>
              <tbody>
                {sales.map((s) => (
                  <tr key={s.id}>
                    <td style={td}>{s.year}-{String(s.month).padStart(2, "0")}</td>
                    <td style={td}>{s.client}</td>
                    <td style={td}>{s.agent ?? "—"}</td>
                    <td style={{ ...td, textAlign: "right" }}>
                      {s.quantity ? Number(s.quantity).toFixed(2) : "—"}
                    </td>
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
