import { useEffect, useMemo, useState, type CSSProperties } from "react";
import { useParams, useNavigate } from "react-router-dom";

import { Skeleton } from "../../shared/ui/Skeleton";
import { useCompanyScope, type CompanyScope } from "../../shared/ui/CompanyScopeProvider";
import { getProbleme, saveProbleme } from "./api";
import type { ProblemeResponse, ProblemeScope } from "./types";

/**
 * /probleme/:period — "Probleme în Activitate" pentru o lună.
 *
 * period = "YYYY-MM". Dacă lipsește, se folosește luna curentă.
 */

function scopeFromCompany(c: CompanyScope): ProblemeScope {
  return c === "adeplast" ? "adp" : (c as ProblemeScope);
}

function parsePeriod(period: string | undefined): { year: number; month: number } {
  if (period) {
    const m = period.match(/^(\d{4})-(\d{1,2})$/);
    if (m) {
      const y = Number(m[1]);
      const mm = Number(m[2]);
      if (mm >= 1 && mm <= 12) return { year: y, month: mm };
    }
  }
  const n = new Date();
  return { year: n.getFullYear(), month: n.getMonth() + 1 };
}

function toPeriodStr(year: number, month: number): string {
  return `${year}-${String(month).padStart(2, "0")}`;
}

function fmtDateTimeRo(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("ro-RO", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

const MONTH_NAMES = [
  "", "Ianuarie", "Februarie", "Martie", "Aprilie", "Mai", "Iunie",
  "Iulie", "August", "Septembrie", "Octombrie", "Noiembrie", "Decembrie",
];

export default function ProblemePage() {
  const { period } = useParams<{ period?: string }>();
  const navigate = useNavigate();
  const { scope: companyScope } = useCompanyScope();
  const apiScope = scopeFromCompany(companyScope);

  const initial = useMemo(() => parsePeriod(period), [period]);
  const [year, setYear] = useState(initial.year);
  const [month, setMonth] = useState(initial.month);

  const [data, setData] = useState<ProblemeResponse | null>(null);
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<string | null>(null);

  useEffect(() => {
    setYear(initial.year);
    setMonth(initial.month);
  }, [initial.year, initial.month]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getProbleme({ scope: apiScope, period: toPeriodStr(year, month) })
      .then((resp) => {
        if (!cancelled) {
          setData(resp);
          setContent(resp.content);
        }
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message || "Eroare la încărcare");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [apiScope, year, month]);

  function changeMonth(delta: number) {
    let newM = month + delta;
    let newY = year;
    if (newM < 1) {
      newM = 12;
      newY -= 1;
    } else if (newM > 12) {
      newM = 1;
      newY += 1;
    }
    navigate(`/probleme/${toPeriodStr(newY, newM)}`);
  }

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      const resp = await saveProbleme({
        scope: apiScope,
        year,
        month,
        content,
      });
      setData(resp);
      setSavedAt(new Date().toISOString());
    } catch (e) {
      setError((e as Error).message || "Eroare la salvare");
    } finally {
      setSaving(false);
    }
  }

  const companyTitle =
    companyScope === "adeplast" ? "Adeplast" : companyScope === "sika" ? "SIKA" : "SIKADP";

  return (
    <div style={styles.page}>
      <div style={styles.headerRow}>
        <span style={styles.titleIcon}>⚠️</span>
        <h1 style={styles.title}>
          Probleme în Activitate — {companyTitle}
        </h1>
      </div>

      {/* Month navigator */}
      <div style={styles.monthBar}>
        <button style={styles.btn} onClick={() => changeMonth(-1)}>
          ← Lună anterioară
        </button>
        <span style={styles.monthLabel}>
          {MONTH_NAMES[month]} {year}
        </span>
        <button style={styles.btn} onClick={() => changeMonth(1)}>
          Lună următoare →
        </button>
        <span style={{ flex: 1 }} />
        {data?.updatedAt && (
          <span style={styles.lastUpdate}>
            ultima modificare: {fmtDateTimeRo(data.updatedAt)}
            {data.updatedBy && ` (${data.updatedBy})`}
          </span>
        )}
      </div>

      {data?.todo && <div style={styles.todoBanner}>⚠ {data.todo}</div>}

      {loading && <Skeleton height={320} />}
      {error && <div style={styles.errorBox}>{error}</div>}

      {!loading && (
        <>
          <div style={styles.editorCard}>
            <textarea
              style={styles.textarea}
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder={`Descrieți problemele întâmpinate în activitate în ${MONTH_NAMES[month]} ${year}...\n\nExemplu:\n- Întârzieri livrări zonă X\n- Reclamații calitate produs Y\n- Probleme stoc depozit Z`}
            />
            <div style={styles.editorFooter}>
              <span style={styles.footerStatus}>
                {savedAt
                  ? `✓ salvat ${fmtDateTimeRo(savedAt)}`
                  : data?.updatedAt
                  ? "—"
                  : "Nesalvat"}
              </span>
              <button
                style={styles.btnPrimary}
                onClick={handleSave}
                disabled={saving}
              >
                {saving ? "Se salvează..." : "💾 Salvează"}
              </button>
            </div>
          </div>

          <div style={styles.photosCard}>
            <div style={styles.photosTitle}>📷 Poze atașate</div>
            {data && data.photos.length > 0 ? (
              <div style={styles.photosGrid}>
                {data.photos.map((p) => (
                  <div key={p.id} style={styles.photoItem}>
                    <img src={p.url} alt="" style={styles.photoImg} />
                  </div>
                ))}
              </div>
            ) : (
              <div style={styles.emptyPhotos}>
                Nicio poză atașată pentru această lună.
                {" "}
                <span style={{ color: "var(--muted)", fontSize: 11 }}>
                  (upload: TODO — se portează modulul gallery pentru probleme)
                </span>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

const styles: Record<string, CSSProperties> = {
  page: { display: "flex", flexDirection: "column", gap: 12, maxWidth: 960 },
  headerRow: { display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" },
  titleIcon: { fontSize: 20 },
  title: {
    fontSize: 20,
    fontWeight: 700,
    color: "var(--orange, #f59e0b)",
    margin: 0,
  },
  monthBar: {
    display: "flex",
    alignItems: "center",
    gap: 10,
    flexWrap: "wrap",
    padding: "8px 12px",
    background: "var(--card)",
    border: "1px solid var(--border)",
    borderRadius: 10,
  },
  btn: {
    padding: "6px 12px",
    borderRadius: 6,
    border: "1px solid var(--border)",
    background: "var(--card)",
    color: "var(--text)",
    fontSize: 13,
    cursor: "pointer",
  },
  btnPrimary: {
    padding: "8px 22px",
    borderRadius: 6,
    background: "var(--orange, #f59e0b)",
    color: "#0f172a",
    border: "none",
    fontWeight: 700,
    fontSize: 13,
    cursor: "pointer",
  },
  monthLabel: { fontSize: 14, fontWeight: 700, color: "var(--text)" },
  lastUpdate: { fontSize: 11, color: "var(--muted)", fontStyle: "italic" },
  todoBanner: {
    padding: "8px 14px",
    background: "rgba(251,146,60,0.08)",
    border: "1px solid rgba(251,146,60,0.35)",
    borderRadius: 8,
    fontSize: 12,
    color: "var(--text)",
  },
  editorCard: {
    background: "var(--card)",
    border: "1px solid var(--border)",
    borderRadius: 12,
    padding: 14,
    display: "flex",
    flexDirection: "column",
    gap: 10,
  },
  textarea: {
    width: "100%",
    minHeight: 360,
    background: "var(--card)",
    color: "var(--text)",
    border: "1px solid var(--border)",
    borderRadius: 6,
    padding: 12,
    fontSize: 14,
    lineHeight: 1.7,
    resize: "vertical",
    fontFamily: "Calibri, sans-serif",
  },
  editorFooter: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 10,
    flexWrap: "wrap",
  },
  footerStatus: { fontSize: 12, color: "var(--muted)" },
  photosCard: {
    background: "var(--card)",
    border: "1px solid var(--border)",
    borderRadius: 12,
    padding: 14,
  },
  photosTitle: {
    fontSize: 14,
    fontWeight: 600,
    color: "var(--orange, #f59e0b)",
    marginBottom: 10,
  },
  photosGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fill, minmax(110px, 1fr))",
    gap: 6,
  },
  photoItem: {
    aspectRatio: "1 / 1",
    overflow: "hidden",
    borderRadius: 6,
    border: "1px solid var(--border)",
  },
  photoImg: {
    width: "100%",
    height: "100%",
    objectFit: "cover",
    display: "block",
  },
  emptyPhotos: {
    padding: "16px 8px",
    color: "var(--muted)",
    fontSize: 13,
    textAlign: "center",
  },
  errorBox: {
    background: "rgba(239,68,68,0.1)",
    border: "1px solid var(--red)",
    color: "var(--red)",
    padding: 12,
    borderRadius: 8,
    fontSize: 13,
  },
};
