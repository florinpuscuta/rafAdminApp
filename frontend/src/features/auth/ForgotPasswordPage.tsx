import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "../../shared/api";
import { requestPasswordReset } from "./api";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await requestPasswordReset(email);
      setDone(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Eroare");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div style={styles.wrap}>
      {done ? (
        <div style={styles.form}>
          <h1 style={styles.title}>Verifică-ți email-ul</h1>
          <p style={{ fontSize: 14, color: "#555" }}>
            Dacă adresa <strong>{email}</strong> există în sistem, am trimis un link de resetare.
            Link-ul e valid 30 de minute și poate fi folosit o singură dată.
          </p>
          <p style={styles.alt}>
            <Link to="/login">Înapoi la autentificare</Link>
          </p>
        </div>
      ) : (
        <form onSubmit={handleSubmit} style={styles.form}>
          <h1 style={styles.title}>Am uitat parola</h1>
          <p style={{ fontSize: 14, color: "#555", margin: 0 }}>
            Îți trimitem pe email un link de resetare.
          </p>
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
          {error && <div style={styles.error}>{error}</div>}
          <button type="submit" disabled={submitting} style={styles.btn}>
            {submitting ? "Se trimite…" : "Trimite link"}
          </button>
          <p style={styles.alt}>
            <Link to="/login">Înapoi la autentificare</Link>
          </p>
        </form>
      )}
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
