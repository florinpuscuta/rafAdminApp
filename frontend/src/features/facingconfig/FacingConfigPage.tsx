import { useEffect, useMemo, useState } from "react";

import { ApiError, apiFetch } from "../../shared/api";
import { useToast } from "../../shared/ui/ToastProvider";

interface Raion {
  id: string;
  name: string;
  sortOrder: number;
  active: boolean;
  parentId: string | null;
}

interface Brand {
  id: string;
  name: string;
  color: string;
  isOwn: boolean;
  sortOrder: number;
  active: boolean;
}

interface CompetitorEntry {
  raionId: string;
  ownBrandId: string;
  competitorBrandId: string;
  sortOrder?: number;
}

interface ConfigResponse {
  ok: boolean;
  raioane: Raion[];
  brands: Brand[];
}

interface MatrixResponse {
  ok: boolean;
  entries: CompetitorEntry[];
}

function matrixKey(raionId: string, ownId: string, compId: string): string {
  return `${raionId}::${ownId}::${compId}`;
}

export default function FacingConfigPage() {
  const toast = useToast();
  const [raioane, setRaioane] = useState<Raion[]>([]);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [matrix, setMatrix] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [selectedOwnId, setSelectedOwnId] = useState<string>("");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      try {
        const [cfg, mx] = await Promise.all([
          apiFetch<ConfigResponse>("/api/marketing/facing/config"),
          apiFetch<MatrixResponse>("/api/marketing/facing/raion-competitors"),
        ]);
        if (cancelled) return;
        setRaioane(cfg.raioane);
        setBrands(cfg.brands);
        const s = new Set<string>();
        for (const e of mx.entries) {
          s.add(matrixKey(e.raionId, e.ownBrandId, e.competitorBrandId));
        }
        setMatrix(s);
        // Default la primul brand propriu
        const firstOwn = cfg.brands.find((b) => b.isOwn && b.active);
        if (firstOwn) setSelectedOwnId(firstOwn.id);
      } catch (err) {
        toast.error(err instanceof ApiError ? err.message : "Eroare încărcare");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const ownBrands = useMemo(
    () => brands.filter((b) => b.isOwn && b.active).sort((a, b) => a.sortOrder - b.sortOrder),
    [brands],
  );
  const subRaioane = useMemo(
    () => raioane.filter((r) => r.parentId != null && r.active).sort((a, b) => a.sortOrder - b.sortOrder),
    [raioane],
  );
  const parentMap = useMemo(() => {
    const m: Record<string, Raion> = {};
    for (const r of raioane) if (r.parentId == null) m[r.id] = r;
    return m;
  }, [raioane]);
  const competitorBrands = useMemo(
    () => brands
      .filter((b) => b.active && b.id !== selectedOwnId)
      .sort((a, b) => a.sortOrder - b.sortOrder),
    [brands, selectedOwnId],
  );

  function toggle(raionId: string, compId: string) {
    if (!selectedOwnId) return;
    const k = matrixKey(raionId, selectedOwnId, compId);
    setMatrix((prev) => {
      const n = new Set(prev);
      n.has(k) ? n.delete(k) : n.add(k);
      return n;
    });
  }

  async function handleSave() {
    setSaving(true);
    try {
      const entries: CompetitorEntry[] = [];
      for (const k of matrix) {
        const [raionId, ownBrandId, competitorBrandId] = k.split("::");
        entries.push({ raionId, ownBrandId, competitorBrandId });
      }
      await apiFetch("/api/marketing/facing/raion-competitors", {
        method: "POST",
        body: JSON.stringify({ entries }),
      });
      toast.success("Salvat");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Eroare salvare");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <div style={{ padding: 20, color: "var(--muted)" }}>Se încarcă…</div>;
  }

  const selectedOwn = ownBrands.find((b) => b.id === selectedOwnId);

  return (
    <div style={styles.page}>
      <div style={styles.header}>
        <h1 style={styles.title}>Config Concurențe per Sub-raion</h1>
        <button
          type="button" data-wide="true"
          onClick={handleSave}
          disabled={saving}
          style={{ color: saving ? "var(--muted)" : "var(--accent)" }}
        >
          {saving ? "Salvez…" : "💾 Salvează"}
        </button>
      </div>

      <div style={styles.helpBox}>
        Pentru fiecare <b>brand propriu</b>, bifează pe fiecare rând (sub-raion)
        ce branduri concurează cu el la acel sub-raion. Modificările se aplică
        la Dash Face Tracker după Salvează.
      </div>

      <div style={styles.ownSelector}>
        <span style={{ color: "var(--muted)", fontSize: 13 }}>Brand propriu:</span>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {ownBrands.map((b) => (
            <button
              key={b.id}
              type="button" data-wide="true"
              data-active={b.id === selectedOwnId ? "true" : undefined}
              onClick={() => setSelectedOwnId(b.id)}
              style={{
                color: b.id === selectedOwnId ? "#fff" : b.color,
                borderColor: b.color,
                background: b.id === selectedOwnId ? b.color : "#fff",
              }}
            >
              {b.name}
            </button>
          ))}
        </div>
      </div>

      {!selectedOwn ? (
        <div style={styles.empty}>Niciun brand propriu configurat.</div>
      ) : (
        <div style={styles.tableWrap}>
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={{ ...styles.th, textAlign: "left", minWidth: 160 }}>
                  Sub-raion
                </th>
                {competitorBrands.map((b) => (
                  <th key={b.id} style={{ ...styles.th, minWidth: 70 }} title={b.name}>
                    <span style={{
                      display: "inline-flex", flexDirection: "column",
                      alignItems: "center", gap: 3,
                    }}>
                      <span style={{
                        width: 10, height: 10, borderRadius: 2,
                        background: b.color,
                      }} />
                      <span style={{ fontSize: 10 }}>{b.name}</span>
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {subRaioane.map((r) => {
                const parent = r.parentId ? parentMap[r.parentId] : null;
                return (
                  <tr key={r.id}>
                    <td style={styles.tdName}>
                      <div style={{ fontSize: 10, color: "var(--muted)" }}>
                        {parent?.name ?? ""}
                      </div>
                      <div style={{ fontWeight: 600 }}>{r.name}</div>
                    </td>
                    {competitorBrands.map((b) => {
                      const k = matrixKey(r.id, selectedOwnId, b.id);
                      const checked = matrix.has(k);
                      return (
                        <td key={b.id} style={styles.tdCell}>
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={() => toggle(r.id, b.id)}
                            style={{ width: 18, height: 18, cursor: "pointer" }}
                          />
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  page: { padding: "4px 4px 20px", color: "var(--text)" },
  header: {
    display: "flex", justifyContent: "space-between", alignItems: "center",
    gap: 12, marginBottom: 12, flexWrap: "wrap",
  },
  title: {
    margin: 0, fontSize: 17, fontWeight: 600, color: "var(--text)",
    letterSpacing: -0.2,
  },
  helpBox: {
    padding: "8px 12px", background: "var(--bg-elevated,#fafafa)",
    border: "1px dashed var(--border)", borderRadius: 6,
    fontSize: 12, color: "var(--muted)", marginBottom: 12,
  },
  ownSelector: {
    display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap",
    marginBottom: 12,
  },
  empty: {
    background: "var(--bg-elevated,#fafafa)",
    border: "1px solid var(--border)", borderRadius: 8,
    padding: 24, color: "var(--muted)", textAlign: "center",
  },
  tableWrap: {
    overflowX: "auto",
    background: "var(--card)", border: "1px solid var(--border)",
    borderRadius: 8, padding: 4,
  },
  table: { width: "100%", borderCollapse: "collapse", fontSize: 13 },
  th: {
    padding: "6px 4px", fontSize: 11, fontWeight: 600,
    color: "var(--muted)", borderBottom: "2px solid var(--border)",
    textAlign: "center", whiteSpace: "nowrap",
  },
  tdName: {
    padding: "8px 10px", fontSize: 13, color: "var(--text)",
    borderBottom: "1px solid var(--border)",
    position: "sticky", left: 0, background: "var(--card)", zIndex: 1,
  },
  tdCell: {
    padding: "6px 4px", textAlign: "center",
    borderBottom: "1px solid var(--border)",
  },
};
