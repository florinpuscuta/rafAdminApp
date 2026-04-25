import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError } from "../../shared/api";
import { TableSkeleton } from "../../shared/ui/Skeleton";
import {
  deleteBatch,
  downloadSalesExport,
  importSales,
  listBatches,
  listSales,
} from "./api";
import type { ImportBatch, ImportResponse, Sale } from "./types";

const PAGE_SIZE = 50;

export default function SalesPage() {
  const [items, setItems] = useState<Sale[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<ImportResponse | null>(null);
  const [batches, setBatches] = useState<ImportBatch[]>([]);
  const [deletingBatch, setDeletingBatch] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const refreshBatches = useCallback(async () => {
    try {
      setBatches(await listBatches());
    } catch {
      /* ignorăm — eroarea principală iese prin refresh() */
    }
  }, []);

  const refresh = useCallback(
    async (nextPage = page) => {
      setLoading(true);
      setError(null);
      try {
        const data = await listSales(nextPage, PAGE_SIZE);
        setItems(data.items);
        setTotal(data.total);
        setPage(data.page);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Eroare la încărcare");
      } finally {
        setLoading(false);
      }
    },
    [page],
  );

  useEffect(() => {
    refresh(1);
    refreshBatches();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setImporting(true);
    setImportResult(null);
    setError(null);
    try {
      const result = await importSales(file);
      setImportResult(result);
      await Promise.all([refresh(1), refreshBatches()]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Eroare la import");
    } finally {
      setImporting(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function handleExport() {
    setError(null);
    try {
      await downloadSalesExport();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Eroare la export");
    }
  }

  async function handleDeleteBatch(batch: ImportBatch) {
    const msg = `Ștergi import-ul "${batch.filename}" și cele ${batch.insertedRows} linii asociate? Acțiunea nu poate fi anulată.`;
    if (!window.confirm(msg)) return;
    setDeletingBatch(batch.id);
    setError(null);
    try {
      await deleteBatch(batch.id);
      await Promise.all([refresh(1), refreshBatches()]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Eroare la ștergere");
    } finally {
      setDeletingBatch(null);
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <h2 style={{ marginTop: 0 }}>Vânzări</h2>
        <button onClick={handleExport} style={{ padding: "6px 14px", fontSize: 13, cursor: "pointer" }}>
          ↓ Export Excel
        </button>
      </div>

      <section style={styles.uploadBox}>
        <strong>Import Excel (.xlsx)</strong>
        <p style={styles.hint}>
          Coloane așteptate: <code>year, month, client, channel, product_code, product_name, category_code, amount, quantity, agent</code>.
          Obligatorii: <code>year, month, client, amount</code>.
        </p>
        <input
          ref={fileInputRef}
          type="file"
          accept=".xlsx"
          onChange={handleFileChange}
          disabled={importing}
        />
        {importing && <span style={{ marginLeft: 8 }}>Se încarcă…</span>}
        {importResult && (
          <div style={styles.importResult}>
            Inserate: <strong>{importResult.inserted}</strong> · Ignorate:{" "}
            <strong>{importResult.skipped}</strong>
            {importResult.errors.length > 0 && (
              <ul style={{ margin: "6px 0 0 16px" }}>
                {importResult.errors.map((err, i) => (
                  <li key={i} style={{ color: "#b00020", fontSize: 13 }}>
                    {err}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </section>

      {batches.length > 0 && (
        <section style={styles.historyBox}>
          <strong>Import-uri ({batches.length})</strong>
          <table style={styles.historyTable}>
            <thead>
              <tr>
                <th style={styles.thHist}>Fișier</th>
                <th style={styles.thHist}>Data</th>
                <th style={styles.thHistNum}>Inserate</th>
                <th style={styles.thHistNum}>Ignorate</th>
                <th style={styles.thHist}></th>
              </tr>
            </thead>
            <tbody>
              {batches.map((b) => (
                <tr key={b.id}>
                  <td style={styles.tdHist}><code>{b.filename}</code></td>
                  <td style={styles.tdHist}>{new Date(b.createdAt).toLocaleString("ro-RO")}</td>
                  <td style={styles.tdHistNum}>{b.insertedRows}</td>
                  <td style={styles.tdHistNum}>{b.skippedRows}</td>
                  <td style={styles.tdHist}>
                    <button
                      onClick={() => handleDeleteBatch(b)}
                      disabled={deletingBatch === b.id}
                      style={styles.deleteBtn}
                    >
                      {deletingBatch === b.id ? "Șterg…" : "Șterge import"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      {error && <p style={{ color: "#b00020" }}>{error}</p>}

      <div style={styles.tableWrap}>
        <div style={styles.tableHeader}>
          <span>Total: <strong>{total}</strong> linii</span>
          <div>
            <button
              onClick={() => refresh(page - 1)}
              disabled={page <= 1 || loading}
              style={styles.pageBtn}
            >
              ←
            </button>
            <span style={{ margin: "0 8px", fontSize: 14 }}>
              {page} / {totalPages}
            </span>
            <button
              onClick={() => refresh(page + 1)}
              disabled={page >= totalPages || loading}
              style={styles.pageBtn}
            >
              →
            </button>
          </div>
        </div>
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>An</th>
              <th style={styles.th}>Luna</th>
              <th style={styles.th}>Client</th>
              <th style={styles.th}>Canal</th>
              <th style={styles.th}>Cod produs</th>
              <th style={styles.th}>Produs</th>
              <th style={styles.thNum}>Cantitate</th>
              <th style={styles.thNum}>Valoare</th>
              <th className="agent-private" style={styles.th}>Agent</th>
            </tr>
          </thead>
          <tbody>
            {loading && items.length === 0 ? (
              <tr>
                <td colSpan={9} style={{ padding: 0 }}>
                  <TableSkeleton rows={8} cols={9} />
                </td>
              </tr>
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={9} style={styles.td}>
                  Niciun rând — încarcă un fișier Excel.
                </td>
              </tr>
            ) : (
              items.map((s) => (
                <tr key={s.id}>
                  <td style={styles.td}>{s.year}</td>
                  <td style={styles.td}>{s.month}</td>
                  <td style={styles.td}>{s.client}</td>
                  <td style={styles.td}>{s.channel ?? "—"}</td>
                  <td style={styles.td}>{s.productCode ?? "—"}</td>
                  <td style={styles.td}>{s.productName ?? "—"}</td>
                  <td style={styles.tdNum}>{s.quantity ?? "—"}</td>
                  <td style={styles.tdNum}>{s.amount}</td>
                  <td className="agent-private" style={styles.td}>{s.agent ?? "—"}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  historyBox: {
    padding: 12,
    border: "1px solid #eee",
    borderRadius: 6,
    marginBottom: 16,
    background: "#fff",
  },
  historyTable: { borderCollapse: "collapse", width: "100%", marginTop: 8 },
  thHist: {
    textAlign: "left",
    padding: "6px 10px",
    borderBottom: "1px solid #eee",
    fontSize: 12,
    color: "#666",
  },
  thHistNum: {
    textAlign: "right",
    padding: "6px 10px",
    borderBottom: "1px solid #eee",
    fontSize: 12,
    color: "#666",
  },
  tdHist: { padding: "6px 10px", fontSize: 13, borderBottom: "1px solid #f5f5f5" },
  tdHistNum: {
    padding: "6px 10px",
    fontSize: 13,
    borderBottom: "1px solid #f5f5f5",
    textAlign: "right",
    fontVariantNumeric: "tabular-nums",
  },
  deleteBtn: {
    padding: "4px 10px",
    fontSize: 12,
    cursor: "pointer",
    background: "#fff",
    border: "1px solid #d0d0d0",
    borderRadius: 4,
    color: "#b00020",
  },
  uploadBox: {
    padding: 16,
    border: "1px dashed #bbb",
    borderRadius: 6,
    marginBottom: 16,
    background: "#fafafa",
  },
  hint: { fontSize: 13, color: "#555", margin: "6px 0 10px" },
  importResult: { marginTop: 10, fontSize: 14 },
  tableWrap: { border: "1px solid #eee", borderRadius: 6 },
  tableHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "8px 12px",
    borderBottom: "1px solid #eee",
    fontSize: 14,
  },
  pageBtn: { padding: "4px 10px", fontSize: 14, cursor: "pointer" },
  table: { borderCollapse: "collapse", width: "100%" },
  th: {
    textAlign: "left",
    padding: "8px 12px",
    borderBottom: "2px solid #333",
    fontSize: 13,
  },
  thNum: {
    textAlign: "right",
    padding: "8px 12px",
    borderBottom: "2px solid #333",
    fontSize: 13,
  },
  td: { padding: "6px 12px", borderBottom: "1px solid #eee", fontSize: 13 },
  tdNum: {
    padding: "6px 12px",
    borderBottom: "1px solid #eee",
    fontSize: 13,
    textAlign: "right",
    fontVariantNumeric: "tabular-nums",
  },
};
