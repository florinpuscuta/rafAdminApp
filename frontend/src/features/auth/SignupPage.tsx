import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ApiError } from "../../shared/api";
import { PasswordStrength } from "../../shared/ui/PasswordStrength";
import { useAuth } from "./AuthContext";

export default function SignupPage() {
  const { signup } = useAuth();
  const navigate = useNavigate();
  const [tenantName, setTenantName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await signup({ tenantName, email, password });
      navigate("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Eroare necunoscută");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div style={styles.wrap}>
      <form onSubmit={handleSubmit} style={styles.form}>
        <h1 style={styles.title}>Creează cont nou</h1>
        <label style={styles.label}>
          Nume organizație
          <input
            required
            minLength={2}
            value={tenantName}
            onChange={(e) => setTenantName(e.target.value)}
            style={styles.input}
          />
        </label>
        <label style={styles.label}>
          Email
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            style={styles.input}
          />
        </label>
        <label style={styles.label}>
          Parolă (min 8 caractere)
          <input
            type="password"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            style={styles.input}
          />
          <PasswordStrength password={password} />
        </label>
        {error && <div style={styles.error}>{error}</div>}
        <button type="submit" disabled={submitting} style={styles.btn}>
          {submitting ? "Se trimite…" : "Creează cont"}
        </button>
        <p style={styles.alt}>
          Ai deja cont? <Link to="/login">Autentifică-te</Link>
        </p>
      </form>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  wrap: {
    display: "flex",
    justifyContent: "center",
    alignItems: "flex-start",
    minHeight: "100vh",
    padding: "48px 20px",
    background: "var(--bg)",
  },
  form: {
    display: "flex",
    flexDirection: "column",
    gap: 14,
    width: "100%",
    maxWidth: 380,
    padding: 24,
    background: "var(--card)",
    border: "1px solid var(--border)",
    borderRadius: 14,
    boxShadow: "0 10px 30px rgba(15,23,42,0.06)",
  },
  title: {
    margin: "0 0 4px",
    fontSize: 22,
    fontWeight: 700,
    letterSpacing: "-0.02em",
    color: "var(--text)",
  },
  label: {
    display: "flex",
    flexDirection: "column",
    gap: 6,
    fontSize: 13,
    fontWeight: 500,
    color: "var(--text)",
  },
  input: {
    padding: "10px 12px",
    fontSize: 14,
    border: "1px solid var(--border)",
    borderRadius: 8,
    background: "var(--card)",
    color: "var(--text)",
    outline: "none",
    fontFamily: "inherit",
  },
  error: {
    color: "#b00020",
    fontSize: 13,
    padding: "8px 12px",
    background: "rgba(220,38,38,0.08)",
    border: "1px solid rgba(220,38,38,0.2)",
    borderRadius: 6,
  },
  btn: {
    padding: "11px 16px",
    fontSize: 14,
    fontWeight: 600,
    cursor: "pointer",
    background: "var(--accent)",
    color: "#fff",
    border: "none",
    borderRadius: 8,
    marginTop: 4,
    boxShadow: "0 1px 2px rgba(15,23,42,0.08)",
    transition: "filter 0.12s ease, transform 0.08s ease",
  },
  alt: {
    fontSize: 13,
    textAlign: "center",
    margin: "4px 0 0",
    color: "var(--muted)",
  },
};
