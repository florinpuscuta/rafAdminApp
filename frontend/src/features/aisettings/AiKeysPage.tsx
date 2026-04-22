/**
 * Setări → Chei AI — permite configurarea cheilor pentru xAI Grok, Anthropic,
 * OpenAI, DeepSeek. Salvate per-tenant în `app_settings` (DB), folosite de
 * scraperul de prețuri și alte integrări AI din app.
 */
import { useCallback, useEffect, useState } from "react";

import { apiFetch, ApiError } from "../../shared/api";
import { useToast } from "../../shared/ui/ToastProvider";

type Provider = "xai" | "anthropic" | "openai" | "deepseek";

interface KeysResponse {
  ok: boolean;
  keys: Record<Provider, string | null>;
}

const PROVIDERS: Array<{
  id: Provider;
  label: string;
  icon: string;
  prefix: string;
  placeholder: string;
  desc: string;
  docUrl: string;
}> = [
  {
    id: "xai",
    label: "xAI Grok",
    icon: "🚀",
    prefix: "xai-",
    placeholder: "xai-...",
    desc: "Live search nativ. Recomandat pentru scraping prețuri.",
    docUrl: "https://x.ai/api",
  },
  {
    id: "anthropic",
    label: "Anthropic Claude",
    icon: "🤖",
    prefix: "sk-ant-",
    placeholder: "sk-ant-...",
    desc: "Claude Sonnet cu web_search. Calitate ridicată.",
    docUrl: "https://console.anthropic.com/settings/keys",
  },
  {
    id: "openai",
    label: "OpenAI GPT-4o",
    icon: "💬",
    prefix: "sk-",
    placeholder: "sk-...",
    desc: "Model gpt-4o-search-preview. Alternativă la Claude.",
    docUrl: "https://platform.openai.com/api-keys",
  },
  {
    id: "deepseek",
    label: "DeepSeek",
    icon: "🌐",
    prefix: "sk-",
    placeholder: "sk-...",
    desc: "Alternativă low-cost. Folosit de modulul de chat.",
    docUrl: "https://platform.deepseek.com",
  },
];

export default function AiKeysPage() {
  const toast = useToast();
  const [keys, setKeys] = useState<Record<Provider, string | null>>({
    xai: null, anthropic: null, openai: null, deepseek: null,
  });
  const [drafts, setDrafts] = useState<Record<Provider, string>>({
    xai: "", anthropic: "", openai: "", deepseek: "",
  });
  const [loading, setLoading] = useState(true);
  const [savingProvider, setSavingProvider] = useState<Provider | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await apiFetch<KeysResponse>("/api/settings/ai-keys");
      setKeys(r.keys);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Eroare la încărcare");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleSave = async (provider: Provider) => {
    const key = drafts[provider].trim();
    setSavingProvider(provider);
    try {
      await apiFetch("/api/settings/ai-keys", {
        method: "PUT",
        body: JSON.stringify({ provider, key: key || null }),
      });
      toast.success(key ? "Cheie salvată" : "Cheie ștearsă");
      setDrafts((d) => ({ ...d, [provider]: "" }));
      await load();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Eroare");
    } finally {
      setSavingProvider(null);
    }
  };

  const handleDelete = async (provider: Provider) => {
    if (!window.confirm(`Ștergi cheia pentru ${provider}?`)) return;
    setSavingProvider(provider);
    try {
      await apiFetch("/api/settings/ai-keys", {
        method: "PUT",
        body: JSON.stringify({ provider, key: null }),
      });
      toast.success("Ștearsă");
      await load();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Eroare");
    } finally {
      setSavingProvider(null);
    }
  };

  return (
    <div style={{ padding: "4px 4px 20px", color: "var(--text)", maxWidth: 900 }}>
      <h1 style={{ margin: "0 0 8px", fontSize: 20, fontWeight: 600 }}>🔑 Chei AI</h1>
      <p style={{ fontSize: 13, color: "var(--muted)", marginBottom: 20 }}>
        Cheile sunt stocate per-tenant în baza de date și folosite de modulele
        care au nevoie de AI (scraping prețuri, chat, etc.). Nu sunt expuse
        în frontend — se afișează doar primele/ultimele caractere pentru verificare.
      </p>

      {error && (
        <div style={{ color: "var(--red)", background: "rgba(220,38,38,0.08)", padding: 12, borderRadius: 6, marginBottom: 16 }}>
          {error}
        </div>
      )}

      {loading && !Object.values(keys).some(Boolean) ? (
        <div style={{ color: "var(--muted)", padding: 16 }}>Se încarcă…</div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {PROVIDERS.map((p) => {
            const current = keys[p.id];
            const isSaving = savingProvider === p.id;
            return (
              <div key={p.id} style={{
                background: "var(--card)",
                border: "1px solid var(--border)",
                borderRadius: 10, padding: 16,
                display: "flex", flexDirection: "column", gap: 10,
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                  <span style={{ fontSize: 20 }}>{p.icon}</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 700, fontSize: 14 }}>{p.label}</div>
                    <div style={{ fontSize: 11, color: "var(--muted)" }}>{p.desc}</div>
                  </div>
                  <a href={p.docUrl} target="_blank" rel="noreferrer"
                    style={{ fontSize: 11, color: "var(--accent)", textDecoration: "none" }}>
                    📖 Obține cheie →
                  </a>
                </div>

                {current ? (
                  <div style={{
                    display: "flex", alignItems: "center", gap: 10,
                    padding: "8px 12px", background: "rgba(34,197,94,0.08)",
                    border: "1px solid rgba(34,197,94,0.25)",
                    borderRadius: 6, fontSize: 12,
                  }}>
                    <span style={{ color: "var(--green)" }}>✅ Configurat</span>
                    <code style={{ fontFamily: "monospace", color: "var(--muted)" }}>{current}</code>
                    <button onClick={() => handleDelete(p.id)} disabled={isSaving}
                      style={{
                        marginLeft: "auto", padding: "4px 10px", fontSize: 11,
                        background: "transparent", color: "var(--red)",
                        border: "1px solid var(--red)", borderRadius: 4, cursor: "pointer",
                      }}>
                      🗑️ Șterge
                    </button>
                  </div>
                ) : (
                  <div style={{ fontSize: 11, color: "var(--muted)" }}>
                    ⚠️ Neconfigurat — nu va fi folosit
                  </div>
                )}

                <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <input
                    type="password"
                    placeholder={current ? "Lasă gol ca să păstrezi cheia actuală" : p.placeholder}
                    value={drafts[p.id]}
                    onChange={(e) => setDrafts((d) => ({ ...d, [p.id]: e.target.value }))}
                    style={{
                      flex: 1, padding: "8px 12px",
                      background: "var(--bg)", color: "var(--text)",
                      border: "1px solid var(--border)", borderRadius: 6,
                      fontSize: 13, fontFamily: "monospace",
                    }}
                  />
                  <button onClick={() => handleSave(p.id)}
                    disabled={isSaving || !drafts[p.id].trim()}
                    style={{
                      padding: "8px 16px",
                      background: "var(--accent)", color: "#fff",
                      border: "none", borderRadius: 6, cursor: "pointer",
                      fontSize: 13, fontWeight: 600,
                      opacity: !drafts[p.id].trim() ? 0.4 : 1,
                    }}>
                    {isSaving ? "…" : current ? "Actualizează" : "Salvează"}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      <div style={{
        marginTop: 24, padding: 14, fontSize: 12, color: "var(--muted)",
        background: "var(--bg-elevated)", borderRadius: 8,
        border: "1px solid var(--border)",
      }}>
        💡 <b>Ordine priorității</b>: când lansezi "Actualizează cu AI" pe Prețuri
        Comparative fără să alegi explicit un provider, se folosește în ordinea:
        xAI Grok → Anthropic → OpenAI. DB e verificat întâi, apoi env vars
        (legacy fallback).
      </div>
    </div>
  );
}
