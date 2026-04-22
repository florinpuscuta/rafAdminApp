import { useCallback, useEffect, useState } from "react";

import { ApiError } from "../../shared/api";
import { useToast } from "../../shared/ui/ToastProvider";
import { createAlias, listStores, listSuggestions, listUnmapped } from "./api";
import type { Store, SuggestedMatch, UnmappedClientRow } from "./types";

export default function UnmappedStoresPage() {
  const toast = useToast();
  const [unmapped, setUnmapped] = useState<UnmappedClientRow[]>([]);
  const [stores, setStores] = useState<Store[]>([]);
  const [suggestions, setSuggestions] = useState<Record<string, SuggestedMatch | undefined>>({});
  const [selection, setSelection] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [savingFor, setSavingFor] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [u, s, suggs] = await Promise.all([
        listUnmapped(),
        listStores(),
        listSuggestions(),
      ]);
      setUnmapped(u);
      setStores(s);
      const suggMap: Record<string, SuggestedMatch | undefined> = {};
      for (const row of suggs) {
        suggMap[row.rawClient] = row.suggestions[0]; // best match
      }
      setSuggestions(suggMap);
      // Pre-populate selection cu cele mai bune sugestii dacă scor > 0.6
      setSelection((prev) => {
        const next = { ...prev };
        for (const row of suggs) {
          const top = row.suggestions[0];
          if (top && top.score >= 0.6 && !next[row.rawClient]) {
            next[row.rawClient] = top.storeId;
          }
        }
        return next;
      });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Eroare la încărcare");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function handleMap(rawClient: string) {
    const storeId = selection[rawClient];
    if (!storeId) return;
    setSavingFor(rawClient);
    setError(null);
    try {
      await createAlias({ rawClient, storeId });
      toast.success(`Mapat "${rawClient}"`);
      await refresh();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Eroare la mapare";
      toast.error(msg);
      setError(msg);
    } finally {
      setSavingFor(null);
    }
  }

  if (loading && unmapped.length === 0) {
    return <p>Se încarcă…</p>;
  }

  return (
    <div>
      <h2 style={{ marginTop: 0 }}>Clienți nemapați</h2>
      <p style={styles.hint}>
        String-urile brute din Excel care nu-s încă legate de un magazin canonic.
        Alege un magazin existent din dropdown și apasă "Mapează".
        {stores.length === 0 && (
          <>
            {" "}Momentan nu ai niciun magazin definit — mergi la{" "}
            <a href="/stores">Magazine</a> ca să adaugi.
          </>
        )}
      </p>

      {error && <p style={{ color: "#b00020" }}>{error}</p>}

      {unmapped.length === 0 ? (
        <p>🎉 Toate string-urile brute sunt mapate.</p>
      ) : (
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={th}>String brut (raw_client)</th>
              <th style={thNum}>Linii</th>
              <th style={thNum}>Total (RON)</th>
              <th style={th}>Mapează la magazin</th>
              <th style={th}></th>
            </tr>
          </thead>
          <tbody>
            {unmapped.map((row) => {
              const sugg = suggestions[row.rawClient];
              return (
              <tr key={row.rawClient}>
                <td style={td}>
                  <code>{row.rawClient}</code>
                  {sugg && (
                    <div style={{ fontSize: 11, color: "#2563eb", marginTop: 2 }}>
                      💡 sugerat: <strong>{sugg.storeName}</strong>
                      {" "}<span style={{ color: "#666" }}>({Math.round(sugg.score * 100)}% match)</span>
                    </div>
                  )}
                </td>
                <td style={tdNum}>{row.rowCount}</td>
                <td style={tdNum}>{row.totalAmount}</td>
                <td style={td}>
                  <select
                    value={selection[row.rawClient] ?? ""}
                    onChange={(e) =>
                      setSelection((s) => ({ ...s, [row.rawClient]: e.target.value }))
                    }
                    style={styles.select}
                    disabled={stores.length === 0}
                  >
                    <option value="">— alege —</option>
                    {stores.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.name}
                        {s.chain ? ` (${s.chain})` : ""}
                      </option>
                    ))}
                  </select>
                </td>
                <td style={td}>
                  <button
                    onClick={() => handleMap(row.rawClient)}
                    disabled={
                      !selection[row.rawClient] || savingFor === row.rawClient
                    }
                    style={styles.btn}
                  >
                    {savingFor === row.rawClient ? "…" : "Mapează"}
                  </button>
                </td>
              </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  hint: { fontSize: 14, color: "#555" },
  table: { borderCollapse: "collapse", width: "100%" },
  select: { padding: 6, fontSize: 13, minWidth: 240 },
  btn: { padding: "6px 12px", fontSize: 13, cursor: "pointer" },
};
const th: React.CSSProperties = {
  textAlign: "left",
  padding: "8px 12px",
  borderBottom: "2px solid #333",
  fontSize: 13,
};
const thNum: React.CSSProperties = { ...th, textAlign: "right" };
const td: React.CSSProperties = {
  padding: "6px 12px",
  borderBottom: "1px solid #eee",
  fontSize: 13,
};
const tdNum: React.CSSProperties = {
  ...td,
  textAlign: "right",
  fontVariantNumeric: "tabular-nums",
};
