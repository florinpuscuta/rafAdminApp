import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { apiFetch, ApiError } from "../../shared/api";
import type { AuthResponse } from "./types";
import { useAuth } from "./AuthContext";

export default function AcceptInvitePage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { refreshUser } = useAuth();
  const token = params.get("token") ?? "";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!token) {
    return (
      <div style={styles.wrap}>
        <div style={styles.form}>
          <h1>Link invalid</h1>
          <p>Link-ul de invitație nu are token.</p>
          <p><Link to="/login">Înapoi la login</Link></p>
        </div>
      </div>
    );
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (password !== confirm) {
      setError("Parolele nu se potrivesc");
      return;
    }
    setSubmitting(true);
    try {
      const resp = await apiFetch<AuthResponse>("/api/auth/invitations/accept", {
        method: "POST",
        body: JSON.stringify({ token, password }),
      });
      const { setToken, setRefreshToken } = await import("../../shared/api");
      setToken(resp.accessToken);
      setRefreshToken(resp.refreshToken);
      await refreshUser();
      navigate("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Eroare");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div style={styles.wrap}>
      <form onSubmit={handleSubmit} style={styles.form}>
        <h1 style={styles.title}>Acceptă invitația</h1>
        <p style={{ fontSize: 14, color: "#555", margin: 0 }}>
          Setează-ți parola pentru a finaliza crearea contului.
        </p>
        <label style={styles.label}>
          Parolă (min 8)
          <input
            type="password"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            style={styles.input}
          />
        </label>
        <label style={styles.label}>
          Confirmă parola
          <input
            type="password"
            required
            minLength={8}
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            style={styles.input}
          />
        </label>
        {error && <div style={styles.error}>{error}</div>}
        <button type="submit" disabled={submitting} style={styles.btn}>
          {submitting ? "Se salvează…" : "Acceptă și intră"}
        </button>
      </form>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  wrap: { display: "flex", justifyContent: "center", padding: 48 },
  form: { display: "flex", flexDirection: "column", gap: 12, width: 360 },
  title: { margin: 0 },
  label: { display: "flex", flexDirection: "column", gap: 4, fontSize: 14 },
  input: { padding: 8, fontSize: 14, border: "1px solid #ccc", borderRadius: 4 },
  error: { color: "#b00020", fontSize: 14 },
  btn: { padding: "10px 16px", fontSize: 14, cursor: "pointer" },
};
