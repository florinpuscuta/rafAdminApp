import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";

import { apiFetch, ApiError, getToken } from "../../shared/api";
import { useToast } from "../../shared/ui/ToastProvider";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

interface BulkInviteResult {
  invited: number;
  skipped: number;
  errors: string[];
}

interface Invitation {
  id: string;
  email: string;
  role: string;
  invitedByUserId: string | null;
  expiresAt: string;
  acceptedAt: string | null;
  createdAt: string;
}

const ROLES = ["admin", "manager", "member", "viewer"];

export default function InvitationsPanel() {
  const toast = useToast();
  const [items, setItems] = useState<Invitation[]>([]);
  const [loading, setLoading] = useState(true);
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("member");
  const [submitting, setSubmitting] = useState(false);
  const [bulkResult, setBulkResult] = useState<BulkInviteResult | null>(null);
  const [bulkBusy, setBulkBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const list = await apiFetch<Invitation[]>("/api/auth/invitations");
      setItems(list);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Eroare");
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await apiFetch<Invitation>("/api/auth/invitations", {
        method: "POST",
        body: JSON.stringify({ email, role }),
      });
      toast.success(`Invitație trimisă către ${email}`);
      setEmail("");
      setRole("member");
      await refresh();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Eroare");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleBulkUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setBulkBusy(true);
    setBulkResult(null);
    try {
      const token = getToken();
      const form = new FormData();
      form.append("file", file);
      const resp = await fetch(`${API_URL}/api/auth/invitations/bulk-import`, {
        method: "POST",
        body: form,
        headers: token ? { Authorization: `Bearer ${token}` } : undefined,
      });
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}));
        const msg = data?.detail?.message ?? "Eroare la import";
        throw new ApiError(resp.status, msg);
      }
      const result = (await resp.json()) as BulkInviteResult;
      setBulkResult(result);
      toast.success(`Invitații trimise: ${result.invited} · skip: ${result.skipped}`);
      await refresh();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Eroare la import");
    } finally {
      setBulkBusy(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  return (
    <div style={styles.wrap}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <strong>Invitații</strong>
        <label style={styles.bulkBtn}>
          {bulkBusy ? "Import…" : "Import CSV"}
          <input
            ref={fileRef}
            type="file"
            accept=".csv,text/csv"
            disabled={bulkBusy}
            onChange={handleBulkUpload}
            style={{ display: "none" }}
          />
        </label>
      </div>
      <p style={styles.hint}>
        CSV cu coloanele <code>email,role</code>. Role-uri: admin, manager, member, viewer. Max 500 linii.
      </p>
      {bulkResult && (
        <div style={styles.bulkResult}>
          Invitate: <strong>{bulkResult.invited}</strong> ·
          ignorate: <strong>{bulkResult.skipped}</strong>
          {bulkResult.errors.length > 0 && (
            <details style={{ marginTop: 4 }}>
              <summary>{bulkResult.errors.length} erori</summary>
              <ul style={{ margin: "4px 0 0 16px", fontSize: 12 }}>
                {bulkResult.errors.map((e, i) => <li key={i}>{e}</li>)}
              </ul>
            </details>
          )}
        </div>
      )}
      <form onSubmit={handleCreate} style={styles.form}>
        <input
          type="email"
          placeholder="email@exemplu.ro"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          style={{ ...styles.input, flex: 2 }}
        />
        <select
          value={role}
          onChange={(e) => setRole(e.target.value)}
          style={{ ...styles.input, flex: 1 }}
        >
          {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
        </select>
        <button type="submit" disabled={submitting} style={styles.btn}>
          {submitting ? "…" : "Trimite invitație"}
        </button>
      </form>

      {loading && items.length === 0 ? (
        <p style={{ fontSize: 13, color: "#888" }}>Se încarcă…</p>
      ) : items.length === 0 ? (
        <p style={{ fontSize: 13, color: "#888" }}>Nicio invitație trimisă.</p>
      ) : (
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={th}>Email</th>
              <th style={th}>Rol</th>
              <th style={th}>Stare</th>
              <th style={th}>Expiră</th>
              <th style={th}>Trimisă</th>
            </tr>
          </thead>
          <tbody>
            {items.map((inv) => {
              const now = Date.now();
              const expired = new Date(inv.expiresAt).getTime() < now;
              const accepted = !!inv.acceptedAt;
              const status = accepted
                ? { label: "acceptată", color: "#0a7f2e" }
                : expired
                ? { label: "expirată", color: "#b00020" }
                : { label: "activă", color: "#2563eb" };
              return (
                <tr key={inv.id}>
                  <td style={td}>{inv.email}</td>
                  <td style={td}>{inv.role}</td>
                  <td style={{ ...td, color: status.color }}>{status.label}</td>
                  <td style={td}>{new Date(inv.expiresAt).toLocaleString("ro-RO")}</td>
                  <td style={td}>{new Date(inv.createdAt).toLocaleString("ro-RO")}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  wrap: { padding: 16, border: "1px solid var(--border, #eee)", borderRadius: 6, marginBottom: 16, background: "var(--bg-elevated, #fff)", display: "flex", flexDirection: "column", gap: 10 },
  form: { display: "flex", gap: 8 },
  input: { padding: 8, fontSize: 14, border: "1px solid #ccc", borderRadius: 4 },
  btn: { padding: "8px 16px", fontSize: 14, cursor: "pointer" },
  table: { borderCollapse: "collapse", width: "100%" },
  bulkBtn: {
    padding: "6px 12px", fontSize: 12, cursor: "pointer",
    background: "var(--bg-elevated, #fff)", border: "1px solid var(--border, #d0d0d0)", borderRadius: 4,
  },
  hint: { margin: 0, fontSize: 11, color: "var(--fg-muted, #888)" },
  bulkResult: {
    padding: "8px 12px", background: "#e6ffed", border: "1px solid #a6d8a8",
    borderRadius: 4, fontSize: 13, color: "#065f13",
  },
};
const th: React.CSSProperties = { textAlign: "left", padding: "6px 10px", borderBottom: "2px solid #333", fontSize: 12 };
const td: React.CSSProperties = { padding: "4px 10px", fontSize: 13, borderBottom: "1px solid #eee" };
