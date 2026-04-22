import { useCallback, useEffect, useState, type FormEvent } from "react";

import { ApiError, setToken } from "../../shared/api";
import { TableSkeleton } from "../../shared/ui/Skeleton";
import { useAuth } from "../auth/AuthContext";
import ChangePasswordForm from "../auth/ChangePasswordForm";
import TwoFactorSetupForm from "../auth/TwoFactorSetupForm";
import type { User } from "../auth/types";
import {
  createUser,
  deleteUser,
  impersonateUser,
  listUsers,
  updateUser,
  type CreateUserPayload,
} from "./api";
import InvitationsPanel from "./InvitationsPanel";

const ROLES: CreateUserPayload["role"][] = ["admin", "manager", "member", "viewer"];

export default function UsersPage() {
  const { user: currentUser } = useAuth();
  const isAdmin = currentUser?.role === "admin";

  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<CreateUserPayload["role"]>("member");
  const [submitting, setSubmitting] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [rowBusy, setRowBusy] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setUsers(await listUsers());
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
    setFeedback(null);
    setSubmitting(true);
    try {
      const u = await createUser({ email, password, role });
      setFeedback(
        `User creat: ${u.email} (${u.role}). Comunică-i parola pe un canal sigur.`,
      );
      setEmail("");
      setPassword("");
      setRole("member");
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Eroare la creare");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRoleChange(u: User, newRole: CreateUserPayload["role"]) {
    if (u.role === newRole) return;
    setRowBusy(u.id);
    setError(null);
    try {
      await updateUser(u.id, { role: newRole });
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Eroare la modificare");
    } finally {
      setRowBusy(null);
    }
  }

  async function handleToggleActive(u: User) {
    setRowBusy(u.id);
    setError(null);
    try {
      await updateUser(u.id, { active: !u.active });
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Eroare");
    } finally {
      setRowBusy(null);
    }
  }

  async function handleImpersonate(u: User) {
    if (!window.confirm(`View-as ${u.email}? Înapoi la propriul cont cu butonul din banner.`)) return;
    try {
      const resp = await impersonateUser(u.id);
      // salvăm access token ca principal; refresh token rămâne cel original
      // (la logout/refresh va reveni la admin). Banner vizibil în Shell.
      setToken(resp.accessToken);
      sessionStorage.setItem("adeplast_impersonating", u.email);
      window.location.href = "/";
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Eroare");
    }
  }

  async function handleDelete(u: User) {
    if (!window.confirm(`Șterge permanent utilizatorul ${u.email}?`)) return;
    setRowBusy(u.id);
    setError(null);
    try {
      await deleteUser(u.id);
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Eroare la ștergere");
    } finally {
      setRowBusy(null);
    }
  }

  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Utilizatori</h2>

      <ChangePasswordForm />
      <TwoFactorSetupForm />
      {isAdmin && <InvitationsPanel />}

      {isAdmin && (
        <form onSubmit={handleCreate} style={styles.form}>
          <strong>Adaugă utilizator nou</strong>
          <div style={styles.row}>
            <input
              required
              type="email"
              placeholder="Email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              style={{ ...styles.input, flex: 2 }}
            />
            <input
              required
              type="text"
              placeholder="Parolă temporară (min 8)"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              minLength={8}
              style={{ ...styles.input, flex: 2 }}
            />
            <select
              value={role}
              onChange={(e) => setRole(e.target.value as CreateUserPayload["role"])}
              style={{ ...styles.input, flex: 1 }}
            >
              {ROLES.map((r) => (
                <option key={r} value={r}>{r}</option>
              ))}
            </select>
            <button type="submit" disabled={submitting} style={styles.btn}>
              {submitting ? "Creez…" : "Adaugă"}
            </button>
          </div>
          {feedback && <div style={styles.feedback}>{feedback}</div>}
        </form>
      )}

      {error && <p style={{ color: "#b00020" }}>{error}</p>}

      <table style={{ borderCollapse: "collapse", width: "100%" }}>
        <thead>
          <tr>
            <th style={th}>Email</th>
            <th style={th}>Rol</th>
            <th style={th}>Activ</th>
            <th style={th}>Email verificat</th>
            <th style={th}>Creat</th>
            <th style={th}>Ultima autentificare</th>
            {isAdmin && <th style={th}>Acțiuni</th>}
          </tr>
        </thead>
        <tbody>
          {loading && users.length === 0 ? (
            <tr>
              <td colSpan={isAdmin ? 7 : 6} style={{ padding: 0 }}>
                <TableSkeleton rows={4} cols={isAdmin ? 7 : 6} />
              </td>
            </tr>
          ) : (
            users.map((u) => {
              const isSelf = u.id === currentUser?.id;
              const busy = rowBusy === u.id;
              return (
                <tr key={u.id} style={!u.active ? { color: "#aaa" } : undefined}>
                  <td style={td}>
                    {u.email}
                    {isSelf && <span style={styles.youTag}> (tu)</span>}
                  </td>
                  <td style={td}>
                    {isAdmin && !isSelf ? (
                      <select
                        value={u.role}
                        disabled={busy}
                        onChange={(e) =>
                          handleRoleChange(u, e.target.value as CreateUserPayload["role"])
                        }
                        style={styles.inlineSelect}
                      >
                        {ROLES.map((r) => (
                          <option key={r} value={r}>{r}</option>
                        ))}
                      </select>
                    ) : (
                      u.role
                    )}
                  </td>
                  <td style={td}>{u.active ? "da" : "nu"}</td>
                  <td style={td}>{u.emailVerified ? "✓" : "—"}</td>
                  <td style={td}>{new Date(u.createdAt).toLocaleString("ro-RO")}</td>
                  <td style={td}>
                    {u.lastLoginAt ? new Date(u.lastLoginAt).toLocaleString("ro-RO") : "—"}
                  </td>
                  {isAdmin && (
                    <td style={td}>
                      {!isSelf && (
                        <>
                          <button
                            onClick={() => handleToggleActive(u)}
                            disabled={busy}
                            style={styles.smallBtn}
                          >
                            {u.active ? "Dezactivează" : "Activează"}
                          </button>{" "}
                          <button
                            onClick={() => handleImpersonate(u)}
                            disabled={busy || !u.active}
                            style={styles.smallBtn}
                            title="View as"
                          >
                            View as
                          </button>{" "}
                          <button
                            onClick={() => handleDelete(u)}
                            disabled={busy}
                            style={{ ...styles.smallBtn, color: "#b00020" }}
                          >
                            Șterge
                          </button>
                        </>
                      )}
                    </td>
                  )}
                </tr>
              );
            })
          )}
        </tbody>
      </table>
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
  feedback: {
    padding: "8px 12px",
    background: "#e6ffed",
    border: "1px solid #a6d8a8",
    borderRadius: 4,
    fontSize: 13,
    color: "#065f13",
  },
  youTag: { color: "#888", fontSize: 12, marginLeft: 6 },
  inlineSelect: { padding: "3px 6px", fontSize: 13 },
  smallBtn: {
    padding: "4px 10px",
    fontSize: 12,
    cursor: "pointer",
    background: "#fff",
    border: "1px solid #d0d0d0",
    borderRadius: 3,
  },
};
const th: React.CSSProperties = {
  textAlign: "left",
  padding: "8px 12px",
  borderBottom: "2px solid #333",
  fontSize: 14,
};
const td: React.CSSProperties = {
  padding: "6px 12px",
  borderBottom: "1px solid #eee",
  fontSize: 14,
};
