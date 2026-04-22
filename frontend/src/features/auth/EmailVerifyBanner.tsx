import { useState } from "react";

import { ApiError } from "../../shared/api";
import { resendEmailVerify } from "./api";
import { useAuth } from "./AuthContext";

export default function EmailVerifyBanner() {
  const { user } = useAuth();
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!user || user.emailVerified) return null;

  async function handleResend() {
    setSending(true);
    setError(null);
    try {
      await resendEmailVerify();
      setSent(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Eroare");
    } finally {
      setSending(false);
    }
  }

  return (
    <div style={styles.wrap}>
      <span style={styles.dot} aria-hidden />
      <span style={styles.text}>
        Verifică adresa de email pentru a debloca funcționalitățile complete.
      </span>
      {sent ? (
        <span style={styles.sent}>Link retrimis</span>
      ) : (
        <button onClick={handleResend} disabled={sending} style={styles.btn}>
          {sending ? "…" : "Retrimite link"}
        </button>
      )}
      {error && <span style={styles.error}>{error}</span>}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  wrap: {
    display: "flex",
    alignItems: "center",
    flexWrap: "wrap",
    padding: "6px 14px",
    background: "rgba(251, 191, 36, 0.12)",
    borderBottom: "1px solid rgba(217, 119, 6, 0.25)",
    fontSize: 12,
    gap: 8,
    color: "var(--text)",
  },
  dot: {
    display: "inline-block",
    width: 6,
    height: 6,
    borderRadius: 999,
    background: "#d97706",
    flexShrink: 0,
  },
  text: { flex: 1, fontSize: 12, lineHeight: 1.4 },
  btn: {
    padding: "3px 10px",
    fontSize: 11,
    fontWeight: 500,
    cursor: "pointer",
    background: "transparent",
    border: "1px solid rgba(217, 119, 6, 0.5)",
    borderRadius: 4,
    color: "#b45309",
  },
  sent: { color: "#065f13", fontSize: 12 },
  error: { color: "#b00020", fontSize: 12, marginLeft: 6 },
};
