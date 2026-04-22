import { useEffect, useMemo, useState, type CSSProperties } from "react";

import { Skeleton } from "../../shared/ui/Skeleton";
import { useCompanyScope, type CompanyScope } from "../../shared/ui/CompanyScopeProvider";
import { generateParcurs, getParcursAgents } from "./api";
import type {
  ParcursAgentOption,
  ParcursResponse,
  ParcursScope,
} from "./types";

/**
 * /parcurs — Foaie de Parcurs.
 *
 * Form de generare + preview entries. În SaaS logica AI de generare nu e
 * portată încă: backend-ul întoarce un schelet gol cu metadate.
 */

function scopeFromCompany(c: CompanyScope): ParcursScope {
  return c === "adeplast" ? "adp" : (c as ParcursScope);
}

function fmtNum(n: number): string {
  return new Intl.NumberFormat("ro-RO", { maximumFractionDigits: 0 }).format(n);
}

const MONTH_NAMES = [
  "", "Ianuarie", "Februarie", "Martie", "Aprilie", "Mai", "Iunie",
  "Iulie", "August", "Septembrie", "Octombrie", "Noiembrie", "Decembrie",
];

export default function ParcursPage() {
  const { scope: companyScope } = useCompanyScope();
  const apiScope = scopeFromCompany(companyScope);

  const now = new Date();
  const [agents, setAgents] = useState<ParcursAgentOption[]>([]);
  const [loadingAgents, setLoadingAgents] = useState(true);
  const [selectedAgent, setSelectedAgent] = useState("");
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [kmStart, setKmStart] = useState<number>(0);
  const [kmEnd, setKmEnd] = useState<number>(0);
  const [carNumber, setCarNumber] = useState("");
  const [sediu, setSediu] = useState("Oradea");

  const [result, setResult] = useState<ParcursResponse | null>(null);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoadingAgents(true);
    getParcursAgents(apiScope)
      .then((resp) => {
        if (!cancelled) {
          setAgents(resp.agents);
          if (resp.agents.length && !selectedAgent) {
            setSelectedAgent(resp.agents[0].agentName);
          }
        }
      })
      .catch((e: Error) => {
        if (!cancelled) setError(e.message || "Eroare la încărcare agenți");
      })
      .finally(() => {
        if (!cancelled) setLoadingAgents(false);
      });
    return () => {
      cancelled = true;
    };
    // selectedAgent intentionally not in deps — nu vrem reload la schimbarea lui
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiScope]);

  async function handleGenerate() {
    if (!selectedAgent) {
      setError("Selectează un agent.");
      return;
    }
    if (kmEnd <= kmStart) {
      setError("Km sfârșit trebuie > km început.");
      return;
    }
    setGenerating(true);
    setError(null);
    try {
      const resp = await generateParcurs({
        scope: apiScope,
        agent: selectedAgent,
        year,
        month,
        kmStart,
        kmEnd,
        carNumber: carNumber || undefined,
        sediu,
      });
      setResult(resp);
    } catch (e) {
      setError((e as Error).message || "Eroare la generare");
    } finally {
      setGenerating(false);
    }
  }

  const companyTitle =
    companyScope === "adeplast" ? "Adeplast" : companyScope === "sika" ? "SIKA" : "SIKADP";

  return (
    <div style={styles.page}>
      <div style={styles.headerRow}>
        <span style={styles.titleIcon}>🚗</span>
        <h1 style={styles.title}>Foaie de Parcurs — {companyTitle}</h1>
      </div>

      {/* ── Form ───────────────────────────────────────── */}
      <div style={styles.formCard}>
        <div style={styles.formGrid}>
          <Field label="Agent">
            {loadingAgents ? (
              <Skeleton height={34} />
            ) : (
              <select
                style={styles.input}
                value={selectedAgent}
                onChange={(e) => setSelectedAgent(e.target.value)}
              >
                <option value="">— selectează —</option>
                {agents.map((a) => (
                  <option key={a.agentId ?? a.agentName} value={a.agentName}>
                    {a.agentName} ({a.storesCount} mag.)
                  </option>
                ))}
              </select>
            )}
          </Field>
          <Field label="Lună">
            <select
              style={styles.input}
              value={month}
              onChange={(e) => setMonth(Number(e.target.value))}
            >
              {MONTH_NAMES.slice(1).map((n, i) => (
                <option key={i + 1} value={i + 1}>
                  {n}
                </option>
              ))}
            </select>
          </Field>
          <Field label="An">
            <input
              type="number"
              style={styles.input}
              value={year}
              min={2020}
              max={2100}
              onChange={(e) => setYear(Number(e.target.value))}
            />
          </Field>
          <Field label="Sediu">
            <input
              type="text"
              style={styles.input}
              value={sediu}
              onChange={(e) => setSediu(e.target.value)}
              placeholder="Oradea"
            />
          </Field>
          <Field label="Număr mașină">
            <input
              type="text"
              style={styles.input}
              value={carNumber}
              onChange={(e) => setCarNumber(e.target.value)}
              placeholder="BH 12 ABC"
            />
          </Field>
          <Field label="Km început">
            <input
              type="number"
              style={styles.input}
              value={kmStart}
              onChange={(e) => setKmStart(Number(e.target.value))}
            />
          </Field>
          <Field label="Km sfârșit">
            <input
              type="number"
              style={styles.input}
              value={kmEnd}
              onChange={(e) => setKmEnd(Number(e.target.value))}
            />
          </Field>
          <Field label=" ">
            <button
              style={styles.btnPrimary}
              disabled={generating || !selectedAgent}
              onClick={handleGenerate}
            >
              {generating ? "Generez..." : "🧭 Generează"}
            </button>
          </Field>
        </div>
      </div>

      {error && <div style={styles.errorBox}>{error}</div>}

      {/* ── Result ─────────────────────────────────────── */}
      {result && <ParcursResult result={result} />}
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div style={styles.field}>
      <label style={styles.formLabel}>{label}</label>
      {children}
    </div>
  );
}

function ParcursResult({ result }: { result: ParcursResponse }) {
  const totalDriven = useMemo(
    () => result.entries.reduce((acc, e) => acc + e.kmDriven, 0),
    [result.entries],
  );
  return (
    <>
      {result.todo && <div style={styles.todoBanner}>⚠ {result.todo}</div>}

      <div style={styles.summaryRow}>
        <SummaryCard
          label={`${result.monthName} ${result.year}`}
          value={`${fmtNum(result.totalKm)} km`}
          sub={`${result.workingDays} zile lucrătoare`}
          valueColor="var(--cyan)"
        />
        <SummaryCard
          label="AGENT"
          value={result.agent}
          sub={`Sediu: ${result.sediu}`}
        />
        <SummaryCard
          label="KM BORD"
          value={`${fmtNum(result.kmStart)} → ${fmtNum(result.kmEnd)}`}
          sub={`medie ${result.avgKmPerDay.toFixed(1)} km/zi`}
        />
        <SummaryCard
          label="COMBUSTIBIL"
          value={`${result.totalFuelLiters.toFixed(1)} L`}
          sub={`${fmtNum(result.totalFuelCost)} RON`}
          valueColor="var(--orange)"
        />
        <SummaryCard
          label="GENERARE"
          value={result.aiGenerated ? "AI" : "fallback"}
          sub={result.aiGenerated ? "inteligentă" : "locală"}
        />
      </div>

      <div style={styles.tableCard}>
        <div style={styles.entryHeader}>
          <div>DATĂ</div>
          <div>ZI</div>
          <div>RUTĂ</div>
          <div style={styles.thRight}>Km bord start</div>
          <div style={styles.thRight}>Km bord end</div>
          <div style={styles.thRight}>Km parc.</div>
          <div style={styles.thRight}>Comb. (L)</div>
        </div>
        {result.entries.length === 0 ? (
          <div style={styles.emptyBox}>
            <p style={{ color: "var(--muted)", margin: 0, fontSize: 13 }}>
              Fără entries — generatorul AI/fallback nu e portat încă în SaaS.
            </p>
          </div>
        ) : (
          result.entries.map((e, i) => (
            <div key={i} style={styles.entryRow}>
              <div>{e.date}</div>
              <div>{e.dayName}</div>
              <div style={styles.routeCell} title={e.route}>
                {e.route}
              </div>
              <div style={styles.tdNumRight}>{fmtNum(e.kmStart)}</div>
              <div style={styles.tdNumRight}>{fmtNum(e.kmEnd)}</div>
              <div style={{ ...styles.tdNumRight, color: "var(--cyan)", fontWeight: 600 }}>
                {fmtNum(e.kmDriven)}
              </div>
              <div style={styles.tdNumRight}>
                {e.fuelLiters != null ? e.fuelLiters.toFixed(1) : "—"}
              </div>
            </div>
          ))
        )}
        {result.entries.length > 0 && (
          <div style={styles.entryTotalRow}>
            <div style={{ gridColumn: "1 / 6", textAlign: "right", fontWeight: 700 }}>
              TOTAL
            </div>
            <div style={{ ...styles.tdNumRight, fontWeight: 800, color: "var(--cyan)" }}>
              {fmtNum(totalDriven)}
            </div>
            <div style={{ ...styles.tdNumRight, fontWeight: 700 }}>
              {result.totalFuelLiters.toFixed(1)}
            </div>
          </div>
        )}
      </div>
    </>
  );
}

function SummaryCard({
  label,
  value,
  sub,
  valueColor,
}: {
  label: string;
  value: string;
  sub: string;
  valueColor?: string;
}) {
  return (
    <div style={styles.kpiCard}>
      <div style={styles.kpiLabel}>{label}</div>
      <div style={{ ...styles.kpiValue, color: valueColor ?? "var(--text)" }}>{value}</div>
      <div style={styles.kpiSub}>{sub}</div>
    </div>
  );
}

const styles: Record<string, CSSProperties> = {
  page: { display: "flex", flexDirection: "column", gap: 12 },
  headerRow: { display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" },
  titleIcon: { fontSize: 18 },
  title: { fontSize: 20, fontWeight: 700, color: "var(--cyan)", margin: 0 },
  formCard: {
    background: "var(--card)",
    border: "1px solid var(--border)",
    borderRadius: 12,
    padding: 16,
  },
  formGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))",
    gap: 12,
  },
  field: { display: "flex", flexDirection: "column", gap: 4 },
  formLabel: {
    fontSize: 11,
    color: "var(--muted)",
    textTransform: "uppercase",
    letterSpacing: "0.04em",
    fontWeight: 600,
  },
  input: {
    padding: "7px 10px",
    border: "1px solid var(--border)",
    borderRadius: 6,
    background: "var(--card)",
    color: "var(--text)",
    fontSize: 13,
  },
  btnPrimary: {
    padding: "8px 16px",
    borderRadius: 6,
    background: "var(--cyan)",
    color: "#0f172a",
    border: "none",
    fontWeight: 700,
    fontSize: 13,
    cursor: "pointer",
  },
  todoBanner: {
    padding: "8px 14px",
    background: "rgba(251,146,60,0.08)",
    border: "1px solid rgba(251,146,60,0.35)",
    borderRadius: 8,
    fontSize: 12,
    color: "var(--text)",
  },
  summaryRow: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
    gap: 12,
  },
  kpiCard: {
    background: "var(--card)",
    border: "1px solid var(--border)",
    borderRadius: 12,
    padding: "10px 14px 8px",
  },
  kpiLabel: {
    fontSize: 10,
    color: "var(--muted)",
    textTransform: "uppercase",
    letterSpacing: "0.06em",
    fontWeight: 600,
    marginBottom: 4,
  },
  kpiValue: { fontSize: 20, fontWeight: 800, lineHeight: 1.15 },
  kpiSub: { fontSize: 11, marginTop: 3, color: "var(--muted)" },
  tableCard: {
    background: "var(--card)",
    border: "1px solid var(--border)",
    borderRadius: 10,
    overflow: "hidden",
  },
  entryHeader: {
    display: "grid",
    gridTemplateColumns: "0.9fr 0.8fr 2.2fr 1fr 1fr 0.8fr 0.8fr",
    gap: 12,
    padding: "6px 16px",
    borderBottom: "1px solid var(--border)",
    fontSize: 10,
    textTransform: "uppercase",
    letterSpacing: "0.04em",
    color: "var(--muted)",
    fontWeight: 600,
  },
  entryRow: {
    display: "grid",
    gridTemplateColumns: "0.9fr 0.8fr 2.2fr 1fr 1fr 0.8fr 0.8fr",
    gap: 12,
    padding: "4px 16px",
    alignItems: "center",
    borderBottom: "1px solid rgba(30,41,59,0.25)",
    fontSize: 12.5,
  },
  entryTotalRow: {
    display: "grid",
    gridTemplateColumns: "0.9fr 0.8fr 2.2fr 1fr 1fr 0.8fr 0.8fr",
    gap: 12,
    padding: "6px 16px",
    alignItems: "center",
    background: "rgba(34,211,238,0.06)",
    borderTop: "2px solid var(--cyan)",
    fontSize: 13,
  },
  routeCell: {
    color: "var(--text)",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
  thRight: { textAlign: "right" },
  tdNumRight: { fontSize: 12.5, textAlign: "right", color: "var(--text)" },
  emptyBox: {
    padding: "24px 20px",
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
