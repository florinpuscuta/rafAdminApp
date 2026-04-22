import { useState, type FormEvent } from "react";

import { ApiError, apiFetch } from "../../shared/api";
import { useToast } from "../../shared/ui/ToastProvider";
import { useAuth } from "./AuthContext";

interface SetupResponse {
  secret: string;
  provisioningUri: string;
}

export default function TwoFactorSetupForm() {
  const toast = useToast();
  const { user, refreshUser } = useAuth();
  const enabled = user?.totpEnabled ?? false;

  const [setup, setSetup] = useState<SetupResponse | null>(null);
  const [code, setCode] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleStartSetup() {
    setSubmitting(true);
    try {
      const resp = await apiFetch<SetupResponse>("/api/auth/2fa/setup", { method: "POST" });
      setSetup(resp);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Eroare");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleEnable(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await apiFetch<void>("/api/auth/2fa/enable", {
        method: "POST",
        body: JSON.stringify({ code }),
      });
      toast.success("2FA activat ✓");
      setSetup(null);
      setCode("");
      await refreshUser();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Cod invalid");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDisable(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await apiFetch<void>("/api/auth/2fa/disable", {
        method: "POST",
        body: JSON.stringify({ code }),
      });
      toast.success("2FA dezactivat");
      setCode("");
      await refreshUser();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Cod invalid");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div style={styles.wrap}>
      <strong>Autentificare în 2 pași (TOTP)</strong>
      {enabled ? (
        <>
          <p style={{ fontSize: 13, color: "#065f13", margin: "6px 0" }}>
            ✓ 2FA e activ pentru contul tău.
          </p>
          <form onSubmit={handleDisable} style={styles.row}>
            <input
              type="text"
              placeholder="Cod 6 cifre ca să dezactivezi"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              maxLength={6}
              pattern="[0-9]{6}"
              style={styles.input}
            />
            <button type="submit" disabled={submitting || code.length !== 6} style={styles.btnDanger}>
              Dezactivează 2FA
            </button>
          </form>
        </>
      ) : setup ? (
        <>
          <p style={{ fontSize: 13, margin: "6px 0" }}>
            Scanează QR-ul (Google Authenticator / 1Password / Authy) sau introdu manual:
          </p>
          <div style={styles.secretBox}>
            <code>{setup.secret}</code>
          </div>
          <p style={{ fontSize: 13 }}>
            <a href={setup.provisioningUri} style={{ color: "#2563eb" }}>
              otpauth:// link (deschide în app)
            </a>
          </p>
          <form onSubmit={handleEnable} style={styles.row}>
            <input
              type="text"
              placeholder="Cod 6 cifre"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              maxLength={6}
              pattern="[0-9]{6}"
              required
              style={styles.input}
            />
            <button type="submit" disabled={submitting || code.length !== 6} style={styles.btn}>
              Activează
            </button>
          </form>
        </>
      ) : (
        <>
          <p style={{ fontSize: 13, color: "#555", margin: "6px 0" }}>
            Protejează contul cu un cod temporar din aplicația ta de autentificare.
          </p>
          <button onClick={handleStartSetup} disabled={submitting} style={styles.btn}>
            Pornește configurarea 2FA
          </button>
        </>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  wrap: {
    padding: 14,
    border: "1px solid #eee",
    borderRadius: 6,
    background: "#fff",
    marginBottom: 16,
  },
  row: { display: "flex", gap: 8, marginTop: 8 },
  input: { padding: 8, fontSize: 14, border: "1px solid #ccc", borderRadius: 4, width: 140, fontFamily: "monospace" },
  btn: { padding: "8px 16px", fontSize: 14, cursor: "pointer" },
  btnDanger: { padding: "8px 16px", fontSize: 14, cursor: "pointer", color: "#b00020", border: "1px solid #b00020", background: "#fff", borderRadius: 4 },
  secretBox: {
    padding: "8px 12px",
    background: "#f8fafc",
    border: "1px solid #e2e8f0",
    borderRadius: 4,
    fontFamily: "monospace",
    fontSize: 13,
    wordBreak: "break-all",
    userSelect: "all",
    margin: "8px 0",
  },
};
