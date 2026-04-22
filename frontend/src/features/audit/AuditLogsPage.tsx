import { useCallback, useEffect, useState } from "react";

import { ApiError } from "../../shared/api";
import { TableSkeleton } from "../../shared/ui/Skeleton";
import { useToast } from "../../shared/ui/ToastProvider";
import {
  downloadAuditCsv,
  listAuditEventTypes,
  listAuditLogs,
  type AuditFilters,
} from "./api";
import type { AuditLog } from "./types";

const PAGE_SIZE = 50;

const EVENT_COLOR: Record<string, string> = {
  "auth.login.success": "#0a7f2e",
  "auth.login.failed": "#b00020",
  "auth.logout": "#666",
  "auth.password_changed": "#2563eb",
  "auth.password_reset_requested": "#9333ea",
  "auth.password_reset_completed": "#2563eb",
  "tenant.created": "#9333ea",
  "user.created": "#2563eb",
  "alias.store.created": "#0a7f2e",
  "alias.agent.created": "#0a7f2e",
  "alias.product.created": "#0a7f2e",
  "sales.batch_imported": "#2563eb",
  "sales.batch_deleted": "#b00020",
};

export default function AuditLogsPage() {
  const toast = useToast();
  const [items, setItems] = useState<AuditLog[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [availableTypes, setAvailableTypes] = useState<string[]>([]);
  const [filters, setFilters] = useState<AuditFilters>({});
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(
    async (nextPage: number, nextFilters: AuditFilters) => {
      setLoading(true);
      setError(null);
      try {
        const data = await listAuditLogs(nextPage, PAGE_SIZE, nextFilters);
        setItems(data.items);
        setTotal(data.total);
        setPage(data.page);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Eroare");
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  useEffect(() => {
    refresh(1, {});
    listAuditEventTypes().then(setAvailableTypes).catch(() => void 0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function updateFilter(patch: Partial<AuditFilters>) {
    const next = { ...filters, ...patch };
    // Curăță string-urile goale
    (Object.keys(next) as (keyof AuditFilters)[]).forEach((k) => {
      if (!next[k]) delete next[k];
    });
    setFilters(next);
    refresh(1, next);
  }

  async function handleExport() {
    setExporting(true);
    try {
      await downloadAuditCsv(filters);
      toast.success("Export pornit — verifică descărcările.");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Export a eșuat");
    } finally {
      setExporting(false);
    }
  }

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const hasFilters = Object.keys(filters).length > 0;

  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Audit log</h2>
      <p style={{ color: "var(--fg-muted, #666)", fontSize: 14, marginTop: 0 }}>
        Istoric imuabil de evenimente sensibile — doar admin.
      </p>

      <div style={styles.filterBar}>
        <label style={styles.label}>
          Eveniment
          <select
            value={filters.eventType ?? ""}
            onChange={(e) => updateFilter({ eventType: e.target.value || undefined })}
            style={styles.select}
          >
            <option value="">toate ({availableTypes.length})</option>
            {availableTypes.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </label>

        <label style={styles.label}>
          Prefix
          <input
            type="text"
            placeholder="ex: auth."
            value={filters.eventPrefix ?? ""}
            onChange={(e) => updateFilter({ eventPrefix: e.target.value || undefined })}
            style={styles.input}
          />
        </label>

        <label style={styles.label}>
          De la
          <input
            type="date"
            value={filters.since ?? ""}
            onChange={(e) => updateFilter({ since: e.target.value || undefined })}
            style={styles.input}
          />
        </label>

        <label style={styles.label}>
          Până la
          <input
            type="date"
            value={filters.until ?? ""}
            onChange={(e) => updateFilter({ until: e.target.value || undefined })}
            style={styles.input}
          />
        </label>

        {hasFilters && (
          <button onClick={() => { setFilters({}); refresh(1, {}); }} style={styles.clearBtn}>
            Șterge filtrele
          </button>
        )}

        <button onClick={handleExport} disabled={exporting} style={styles.exportBtn}>
          {exporting ? "Exportă…" : "Export CSV"}
        </button>
      </div>

      <div style={styles.pageBar}>
        <span>Total: <strong>{total}</strong></span>
        <div>
          <button
            onClick={() => refresh(page - 1, filters)}
            disabled={page <= 1 || loading}
            style={styles.pageBtn}
          >
            ←
          </button>
          <span style={{ margin: "0 8px", fontSize: 14 }}>
            {page} / {totalPages}
          </span>
          <button
            onClick={() => refresh(page + 1, filters)}
            disabled={page >= totalPages || loading}
            style={styles.pageBtn}
          >
            →
          </button>
        </div>
      </div>

      {error && <p style={{ color: "#b00020" }}>{error}</p>}

      {loading && items.length === 0 ? (
        <TableSkeleton rows={8} cols={6} />
      ) : (
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={th}>Data</th>
              <th style={th}>Eveniment</th>
              <th style={th}>User</th>
              <th style={th}>Țintă</th>
              <th style={th}>IP</th>
              <th style={th}>Detalii</th>
            </tr>
          </thead>
          <tbody>
            {items.length === 0 ? (
              <tr><td colSpan={6} style={td}>Niciun eveniment.</td></tr>
            ) : (
              items.map((it) => (
                <tr key={it.id}>
                  <td style={td}>{new Date(it.createdAt).toLocaleString("ro-RO")}</td>
                  <td style={td}>
                    <span
                      style={{
                        ...styles.badge,
                        background: EVENT_COLOR[it.eventType] ?? "#666",
                      }}
                    >
                      {it.eventType}
                    </span>
                  </td>
                  <td style={td}>{it.userId ? it.userId.slice(0, 8) + "…" : "—"}</td>
                  <td style={td}>
                    {it.targetType ? `${it.targetType}:${(it.targetId ?? "").slice(0, 8)}…` : "—"}
                  </td>
                  <td style={{ ...td, fontVariantNumeric: "tabular-nums" }}>
                    {it.ipAddress ?? "—"}
                  </td>
                  <td style={{ ...td, fontSize: 11, color: "var(--fg-muted, #666)" }}>
                    {it.eventMetadata ? (
                      <code>{JSON.stringify(it.eventMetadata)}</code>
                    ) : "—"}
                  </td>
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
  filterBar: {
    display: "flex",
    alignItems: "flex-end",
    gap: 12,
    padding: "10px 12px",
    background: "var(--bg-elevated, #fafafa)",
    border: "1px solid var(--border, #eee)",
    borderRadius: 6,
    marginBottom: 12,
    flexWrap: "wrap",
  },
  pageBar: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "6px 4px",
    fontSize: 13,
    marginBottom: 8,
  },
  label: { display: "flex", flexDirection: "column", gap: 3, fontSize: 12, color: "var(--fg-muted, #666)" },
  select: { padding: 6, fontSize: 13, border: "1px solid var(--border, #ccc)", borderRadius: 4, minWidth: 200 },
  input: { padding: "5px 8px", fontSize: 13, border: "1px solid var(--border, #ccc)", borderRadius: 4 },
  clearBtn: {
    padding: "6px 10px", fontSize: 12, cursor: "pointer",
    background: "transparent", border: "1px solid var(--border, #ccc)", borderRadius: 4,
    color: "var(--fg-muted, #666)",
  },
  exportBtn: {
    padding: "6px 12px", fontSize: 13, cursor: "pointer",
    background: "#2563eb", color: "#fff", border: "none", borderRadius: 4,
    marginLeft: "auto",
  },
  pageBtn: { padding: "4px 10px", fontSize: 13, cursor: "pointer" },
  table: { borderCollapse: "collapse", width: "100%" },
  badge: {
    display: "inline-block",
    padding: "2px 8px",
    borderRadius: 3,
    color: "#fff",
    fontSize: 11,
    fontFamily: "monospace",
  },
};
const th: React.CSSProperties = {
  textAlign: "left",
  padding: "8px 12px",
  borderBottom: "2px solid var(--border, #333)",
  fontSize: 13,
};
const td: React.CSSProperties = {
  padding: "6px 12px",
  borderBottom: "1px solid var(--border, #eee)",
  fontSize: 13,
};
