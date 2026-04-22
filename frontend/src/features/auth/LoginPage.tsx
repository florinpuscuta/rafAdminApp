import { useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { ApiError } from "../../shared/api";
import { RateLimitCountdown } from "../../shared/ui/RateLimitCountdown";
import { useAuth } from "./AuthContext";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const flash = (location.state as { flash?: string } | null)?.flash ?? null;
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [totpCode, setTotpCode] = useState("");
  const [needsTotp, setNeedsTotp] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [rateLimitedUntil, setRateLimitedUntil] = useState<number | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login({ email, password, totpCode: needsTotp ? totpCode : undefined });
      navigate("/");
    } catch (err) {
      if (err instanceof ApiError && err.code === "rate_limited" && err.retryAfter) {
        setRateLimitedUntil(err.retryAfter);
        setError(err.message);
      } else if (err instanceof ApiError && err.code === "totp_required") {
        setNeedsTotp(true);
        setError("Introdu codul de 6 cifre din aplicația de autentificare.");
      } else if (err instanceof ApiError && err.code === "invalid_totp") {
        setError("Cod 2FA invalid.");
      } else {
        setError(err instanceof ApiError ? err.message : "Eroare necunoscută");
      }
    } finally {
      setSubmitting(false);
    }
  }

  const blocked = rateLimitedUntil != null;

  return (
    <div style={styles.wrap}>
      <form onSubmit={handleSubmit} style={styles.form}>
        <h1 style={styles.title}>Autentificare</h1>
        {flash && <div style={styles.flash}>{flash}</div>}
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
          Parolă
          <input
            type="password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            style={styles.input}
          />
        </label>
        {needsTotp && (
          <label style={styles.label}>
            Cod 2FA (6 cifre)
            <input
              type="text"
              required
              value={totpCode}
              onChange={(e) => setTotpCode(e.target.value)}
              maxLength={6}
              pattern="[0-9]{6}"
              autoFocus
              style={{ ...styles.input, fontFamily: "monospace", fontSize: 18, letterSpacing: 4 }}
            />
          </label>
        )}
        {error && (
          <div style={styles.error}>
            {error}
            {blocked && rateLimitedUntil != null && (
              <div style={{ marginTop: 4, fontSize: 13 }}>
                <RateLimitCountdown
                  seconds={rateLimitedUntil}
                  onExpire={() => { setRateLimitedUntil(null); setError(null); }}
                />
              </div>
            )}
          </div>
        )}
        <button type="submit" disabled={submitting || blocked} style={styles.btn}>
          {submitting ? "Se trimite…" : blocked ? "Blocat…" : "Intră"}
        </button>
        <p style={styles.alt}>
          N-ai cont? <Link to="/signup">Creează unul</Link>
          {" · "}
          <Link to="/forgot-password">Am uitat parola</Link>
        </p>
        <p style={{ ...styles.alt, fontSize: 11, color: "#888" }}>
          <Link to="/privacy" style={{ color: "#888" }}>Confidențialitate</Link>
          {" · "}
          <Link to="/terms" style={{ color: "#888" }}>Termeni</Link>
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
    maxWidth: 360,
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
  flash: {
    padding: "10px 12px",
    background: "rgba(5,150,105,0.08)",
    border: "1px solid rgba(5,150,105,0.25)",
    borderRadius: 6,
    fontSize: 13,
    color: "#065f13",
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
