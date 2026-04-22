import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { ApiError } from "../../shared/api";
import { PasswordStrength } from "../../shared/ui/PasswordStrength";
import { confirmPasswordReset } from "./api";

export default function ResetPasswordPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const token = params.get("token") ?? "";
  const [newPassword, setNewPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!token) {
    return (
      <div style={styles.wrap}>
        <div style={styles.form}>
          <h1 style={styles.title}>Link invalid</h1>
          <p style={{ fontSize: 14 }}>Link-ul de resetare nu are un token. Cere unul nou.</p>
          <p style={styles.alt}>
            <Link to="/forgot-password">Cere link de resetare</Link>
          </p>
        </div>
      </div>
    );
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (newPassword !== confirm) {
      setError("Parolele nu se potrivesc");
      return;
    }
    setSubmitting(true);
    try {
      await confirmPasswordReset(token, newPassword);
      navigate("/login", {
        replace: true,
        state: { flash: "Parola a fost resetată. Te poți autentifica." },
      });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Eroare");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div style={styles.wrap}>
      <form onSubmit={handleSubmit} style={styles.form}>
        <h1 style={styles.title}>Setează parolă nouă</h1>
        <label style={styles.label}>
          Parolă nouă (min 8 caractere)
          <input
            type="password"
            required
            minLength={8}
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            style={styles.input}
          />
          <PasswordStrength password={newPassword} />
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
          {submitting ? "Se salvează…" : "Resetează parola"}
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
  alt: { fontSize: 14, textAlign: "center", margin: 0 },
};
