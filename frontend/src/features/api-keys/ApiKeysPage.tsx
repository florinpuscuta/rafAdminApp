import { useCallback, useEffect, useState, type FormEvent } from "react";

import { ApiError } from "../../shared/api";
import { createApiKey, listApiKeys, revokeApiKey } from "./api";
import type { ApiKey } from "./types";

export default function ApiKeysPage() {
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [newSecret, setNewSecret] = useState<string | null>(null);
  const [rowBusy, setRowBusy] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setKeys(await listApiKeys());
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Eroare");
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
    setNewSecret(null);
    setSubmitting(true);
    try {
      const resp = await createApiKey(name);
      setNewSecret(resp.secret);
      setName("");
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Eroare");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRevoke(key: ApiKey) {
    if (!window.confirm(`Revocă cheia "${key.name}"? Orice integrare cu această cheie va înceta să funcționeze.`)) return;
    setRowBusy(key.id);
    try {
      await revokeApiKey(key.id);
      await refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Eroare");
    } finally {
      setRowBusy(null);
    }
  }

  async function handleCopy(secret: string) {
    try {
      await navigator.clipboard.writeText(secret);
    } catch {
      /* clipboard API may be blocked — user can select & copy manually */
    }
  }

  return (
    <div>
      <h2 style={{ marginTop: 0 }}>API keys</h2>
      <p style={{ color: "#666", fontSize: 14, marginTop: 0 }}>
        Pentru acces programatic la API. Trimite cheia în header-ul <code>X-API-Key</code>.
      </p>

      <form onSubmit={handleCreate} style={styles.form}>
        <strong>Generează cheie nouă</strong>
        <div style={styles.row}>
          <input
            required
            placeholder="Nume (ex: CI pipeline, Zapier, ETL script)"
            value={name}
            onChange={(e) => setName(e.target.value)}
            style={{ ...styles.input, flex: 2 }}
          />
          <button type="submit" disabled={submitting} style={styles.btn}>
            {submitting ? "…" : "Generează"}
          </button>
        </div>
      </form>

      {newSecret && (
        <div style={styles.secretBox}>
          <strong>Salvează acum — n-o mai poți vedea niciodată:</strong>
          <div style={styles.secretRow}>
            <code style={styles.secretCode}>{newSecret}</code>
            <button onClick={() => handleCopy(newSecret)} style={styles.smallBtn}>
              Copiază
            </button>
            <button onClick={() => setNewSecret(null)} style={styles.smallBtn}>
              Am salvat
            </button>
          </div>
        </div>
      )}

      {error && <p style={{ color: "#b00020" }}>{error}</p>}

      <table style={styles.table}>
        <thead>
          <tr>
            <th style={th}>Nume</th>
            <th style={th}>Prefix</th>
            <th style={th}>Status</th>
            <th style={th}>Ultima folosire</th>
            <th style={th}>Creat</th>
            <th style={th}></th>
          </tr>
        </thead>
        <tbody>
          {loading && keys.length === 0 ? (
            <tr><td colSpan={6} style={td}>Se încarcă…</td></tr>
          ) : keys.length === 0 ? (
            <tr><td colSpan={6} style={td}>Nicio cheie. Generează una mai sus.</td></tr>
          ) : (
            keys.map((k) => {
              const revoked = k.revokedAt !== null;
              return (
                <tr key={k.id} style={revoked ? { color: "#999" } : undefined}>
                  <td style={td}>{k.name}</td>
                  <td style={{ ...td, fontFamily: "monospace", fontSize: 12 }}>
                    {k.prefix}…
                  </td>
                  <td style={td}>
                    {revoked ? (
                      <span style={{ color: "#b00020" }}>revocată</span>
                    ) : (
                      <span style={{ color: "#0a7f2e" }}>activă</span>
                    )}
                  </td>
                  <td style={td}>
                    {k.lastUsedAt ? new Date(k.lastUsedAt).toLocaleString("ro-RO") : "—"}
                  </td>
                  <td style={td}>{new Date(k.createdAt).toLocaleString("ro-RO")}</td>
                  <td style={td}>
                    {!revoked && (
                      <button
                        onClick={() => handleRevoke(k)}
                        disabled={rowBusy === k.id}
                        style={{ ...styles.smallBtn, color: "#b00020" }}
                      >
                        Revocă
                      </button>
                    )}
                  </td>
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
    marginBottom: 16,
    display: "flex",
    flexDirection: "column",
    gap: 10,
  },
  row: { display: "flex", gap: 8 },
  input: { padding: 8, fontSize: 14, border: "1px solid #ccc", borderRadius: 4 },
  btn: { padding: "8px 16px", fontSize: 14, cursor: "pointer" },
  secretBox: {
    padding: 14,
    background: "#fff6e5",
    border: "1px solid #f0c674",
    borderRadius: 6,
    marginBottom: 16,
    fontSize: 14,
  },
  secretRow: { display: "flex", gap: 8, alignItems: "center", marginTop: 8 },
  secretCode: {
    flex: 1,
    padding: "8px 12px",
    background: "#fff",
    border: "1px solid #e5d394",
    borderRadius: 4,
    fontSize: 13,
    userSelect: "all",
  },
  smallBtn: {
    padding: "4px 10px",
    fontSize: 12,
    cursor: "pointer",
    background: "#fff",
    border: "1px solid #d0d0d0",
    borderRadius: 3,
  },
  table: { borderCollapse: "collapse", width: "100%" },
};
const th: React.CSSProperties = {
  textAlign: "left",
  padding: "8px 12px",
  borderBottom: "2px solid #333",
  fontSize: 13,
};
const td: React.CSSProperties = {
  padding: "6px 12px",
  borderBottom: "1px solid #eee",
  fontSize: 13,
};
