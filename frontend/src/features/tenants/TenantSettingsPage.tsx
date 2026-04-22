import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError, clearAuth } from "../../shared/api";
import { useAuth } from "../auth/AuthContext";
import { deactivateCurrentTenant, getCurrentTenant, updateCurrentTenant } from "./api";
import type { Tenant } from "./types";

export default function TenantSettingsPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const isAdmin = user?.role === "admin";

  const [tenant, setTenant] = useState<Tenant | null>(null);
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    getCurrentTenant()
      .then((t) => {
        setTenant(t);
        setName(t.name);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : "Eroare"))
      .finally(() => setLoading(false));
  }, []);

  async function handleSave(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setFeedback(null);
    setSubmitting(true);
    try {
      const t = await updateCurrentTenant(name);
      setTenant(t);
      setFeedback("Setările au fost salvate.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Eroare la salvare");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDeactivate() {
    const confirmText = `Dezactivează organizația "${tenant?.name}"? După dezactivare, nimeni nu se mai poate autentifica. Poți reactiva doar prin DB direct.`;
    if (!window.confirm(confirmText)) return;
    setSubmitting(true);
    try {
      await deactivateCurrentTenant();
      clearAuth();
      navigate("/login", {
        replace: true,
        state: { flash: "Organizația a fost dezactivată." },
      });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Eroare");
      setSubmitting(false);
    }
  }

  if (loading) return <p>Se încarcă…</p>;
  if (!tenant) return <p style={{ color: "#b00020" }}>{error ?? "Tenant inexistent"}</p>;

  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Setări organizație</h2>

      <form onSubmit={handleSave} style={styles.form}>
        <label style={styles.label}>
          Nume
          <input
            type="text"
            required
            minLength={2}
            value={name}
            disabled={!isAdmin}
            onChange={(e) => setName(e.target.value)}
            style={styles.input}
          />
        </label>
        <label style={styles.label}>
          Slug (read-only)
          <input value={tenant.slug} disabled style={{ ...styles.input, color: "#888" }} />
        </label>
        <label style={styles.label}>
          Creat la
          <input
            value={new Date(tenant.createdAt).toLocaleString("ro-RO")}
            disabled
            style={{ ...styles.input, color: "#888" }}
          />
        </label>

        {error && <div style={styles.error}>{error}</div>}
        {feedback && <div style={styles.feedback}>{feedback}</div>}

        {isAdmin && (
          <div>
            <button type="submit" disabled={submitting} style={styles.btn}>
              {submitting ? "Salvez…" : "Salvează"}
            </button>
          </div>
        )}
      </form>

      {isAdmin && (
        <div style={styles.danger}>
          <h3 style={{ marginTop: 0, color: "#b00020" }}>Zonă periculoasă</h3>
          <p style={{ fontSize: 14 }}>
            Dezactivarea organizației invalidează accesul TUTUROR utilizatorilor din ea.
            Operațiunea e soft — datele rămân în DB, dar login-ul e blocat.
          </p>
          <button
            onClick={handleDeactivate}
            disabled={submitting}
            style={styles.dangerBtn}
          >
            Dezactivează organizația
          </button>
        </div>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  form: {
    padding: 20,
    background: "#fff",
    border: "1px solid #eee",
    borderRadius: 6,
    display: "flex",
    flexDirection: "column",
    gap: 14,
    maxWidth: 500,
  },
  label: { display: "flex", flexDirection: "column", gap: 4, fontSize: 14 },
  input: { padding: 8, fontSize: 14, border: "1px solid #ccc", borderRadius: 4 },
  btn: { padding: "8px 18px", fontSize: 14, cursor: "pointer" },
  error: { color: "#b00020", fontSize: 13 },
  feedback: {
    padding: "6px 10px",
    background: "#e6ffed",
    border: "1px solid #a6d8a8",
    borderRadius: 4,
    fontSize: 13,
    color: "#065f13",
  },
  danger: {
    marginTop: 24,
    padding: 16,
    border: "1px solid #f5a2a8",
    borderRadius: 6,
    background: "#fff8f8",
    maxWidth: 500,
  },
  dangerBtn: {
    padding: "8px 16px",
    fontSize: 14,
    cursor: "pointer",
    background: "#fff",
    border: "1px solid #b00020",
    color: "#b00020",
    borderRadius: 4,
  },
};
