import { useEffect, useMemo, useState, type CSSProperties } from "react";

import { Skeleton } from "../../shared/ui/Skeleton";
import { useCompanyScope, type CompanyScope } from "../../shared/ui/CompanyScopeProvider";
import { createVisit, getActivitate, type ActivitateScope } from "./api";
import type { ActivitateAgentRow, ActivitateResponse } from "./types";

/**
 * /activitate — Activitate Agenți (vizite teren).
 *
 * Legacy: /api/agent_activity?date=... sau ?from=&to=. În SaaS avem
 * /api/activitate care întoarce același shape.
 *
 * DB: tabelul dedicat (agent_visits) nu există încă — vezi `response.todo`.
 */

function scopeFromCompany(c: CompanyScope): ActivitateScope {
  return c === "adeplast" ? "adp" : (c as ActivitateScope);
}

function todayIso(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function yearStartIso(): string {
  return `${new Date().getFullYear()}-01-01`;
}

function fmtDateRo(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("ro-RO", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

function toNum(v: string | number | null | undefined): number {
  if (v == null) return 0;
  const n = typeof v === "number" ? v : parseFloat(v);
  return Number.isFinite(n) ? n : 0;
}

type Preset = "today" | "ytd" | "custom";

export default function ActivitatePage() {
  const { scope: companyScope } = useCompanyScope();
  const apiScope = scopeFromCompany(companyScope);

  const [preset, setPreset] = useState<Preset>("today");
  const [dateFrom, setDateFrom] = useState(() => todayIso());
  const [dateTo, setDateTo] = useState(() => todayIso());
  const [data, setData] = useState<ActivitateResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [showAdd, setShowAdd] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    const isSingle = dateFrom === dateTo;
    const query = isSingle
      ? { scope: apiScope, date: dateFrom }
      : { scope: apiScope, dateFrom, dateTo };
    getActivitate(query)
      .then((resp) => {
        if (!cancelled) setData(resp);
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
  }, [apiScope, dateFrom, dateTo, reloadKey]);

  function applyPreset(p: Preset) {
    setPreset(p);
    if (p === "today") {
      const t = todayIso();
      setDateFrom(t);
      setDateTo(t);
    } else if (p === "ytd") {
      setDateFrom(yearStartIso());
      setDateTo(todayIso());
    }
  }

  function toggle(id: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  const companyTitle =
    companyScope === "adeplast" ? "Adeplast" : companyScope === "sika" ? "SIKA" : "Consolidat SIKADP";

  return (
    <div style={styles.page}>
      <div style={styles.headerRow}>
        <span style={styles.titleIcon}>👥</span>
        <h1 style={styles.title}>Activitate Agenți — {companyTitle}</h1>
        <span style={styles.periodLabel}>
          {dateFrom === dateTo
            ? fmtDateRo(dateFrom)
            : `${fmtDateRo(dateFrom)} → ${fmtDateRo(dateTo)}`}
        </span>
      </div>

      {/* Filters */}
      <div style={styles.filterBar}>
        <button
          style={preset === "today" ? styles.btnActive : styles.btn}
          onClick={() => applyPreset("today")}
        >
          Azi
        </button>
        <button
          style={preset === "ytd" ? styles.btnActive : styles.btn}
          onClick={() => applyPreset("ytd")}
        >
          YTD
        </button>
        <span style={styles.divider} />
        <label style={styles.label}>De la:</label>
        <input
          type="date"
          value={dateFrom}
          onChange={(e) => {
            setPreset("custom");
            setDateFrom(e.target.value);
          }}
          style={styles.dateInput}
        />
        <label style={styles.label}>Până la:</label>
        <input
          type="date"
          value={dateTo}
          onChange={(e) => {
            setPreset("custom");
            setDateTo(e.target.value);
          }}
          style={styles.dateInput}
        />
      </div>

      {data?.todo && <div style={styles.todoBanner}>⚠ {data.todo}</div>}

      <div style={{ display: "flex", justifyContent: "flex-end" }}>
        <button
          style={styles.btnActive}
          onClick={() => setShowAdd((v) => !v)}
        >
          {showAdd ? "× Anulează" : "+ Adaugă vizită"}
        </button>
      </div>

      {showAdd && data && (
        <AddVisitForm
          scope={apiScope}
          agents={data.agents}
          onSaved={() => {
            setShowAdd(false);
            setReloadKey((k) => k + 1);
          }}
        />
      )}

      {loading && (
        <>
          <Skeleton height={70} />
          <Skeleton height={200} />
        </>
      )}
      {error && <div style={styles.errorBox}>Eroare: {error}</div>}
      {!loading && !error && data && (
        <>
          <KpiStrip data={data} />
          <AgentsList data={data} expanded={expanded} onToggle={toggle} />
        </>
      )}
    </div>
  );
}

function AddVisitForm({
  scope,
  agents,
  onSaved,
}: {
  scope: ActivitateScope;
  agents: ActivitateAgentRow[];
  onSaved: () => void;
}) {
  const [visitDate, setVisitDate] = useState(todayIso());
  const [agentId, setAgentId] = useState<string>("");
  const [storeName, setStoreName] = useState("");
  const [checkIn, setCheckIn] = useState("");
  const [checkOut, setCheckOut] = useState("");
  const [durationMin, setDurationMin] = useState<string>("");
  const [km, setKm] = useState<string>("");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setErr(null);
    try {
      await createVisit({
        scope,
        visitDate,
        agentId: agentId || null,
        storeId: null,
        client: storeName || null,
        checkIn: checkIn || null,
        checkOut: checkOut || null,
        durationMin: durationMin ? Number(durationMin) : null,
        km: km ? Number(km) : null,
        notes: notes || null,
      });
      onSaved();
    } catch (e) {
      setErr((e as Error).message || "Eroare la salvare");
    } finally {
      setSaving(false);
    }
  }

  const formStyle: CSSProperties = {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
    gap: 10,
    padding: 14,
    background: "var(--card)",
    border: "1px solid var(--border)",
    borderRadius: 10,
  };
  const inp: CSSProperties = {
    padding: "7px 10px",
    border: "1px solid var(--border)",
    borderRadius: 6,
    background: "var(--card)",
    color: "var(--text)",
    fontSize: 13,
  };
  const lbl: CSSProperties = {
    fontSize: 11,
    color: "var(--muted)",
    textTransform: "uppercase",
    letterSpacing: "0.04em",
    fontWeight: 600,
    marginBottom: 4,
    display: "block",
  };

  return (
    <form onSubmit={submit} style={formStyle}>
      <div>
        <label style={lbl}>Data</label>
        <input type="date" style={inp} value={visitDate} onChange={(e) => setVisitDate(e.target.value)} required />
      </div>
      <div>
        <label style={lbl}>Agent</label>
        <select style={inp} value={agentId} onChange={(e) => setAgentId(e.target.value)}>
          <option value="">— fără —</option>
          {agents.filter((a) => a.agentId).map((a) => (
            <option key={a.agentId!} value={a.agentId!}>{a.agentName}</option>
          ))}
        </select>
      </div>
      <div style={{ gridColumn: "span 2" }}>
        <label style={lbl}>Magazin / Client</label>
        <input type="text" style={inp} value={storeName} onChange={(e) => setStoreName(e.target.value)} placeholder="Ex: DEDEMAN CLUJ" />
      </div>
      <div>
        <label style={lbl}>Check-in</label>
        <input type="text" style={inp} value={checkIn} onChange={(e) => setCheckIn(e.target.value)} placeholder="09:30" />
      </div>
      <div>
        <label style={lbl}>Check-out</label>
        <input type="text" style={inp} value={checkOut} onChange={(e) => setCheckOut(e.target.value)} placeholder="10:45" />
      </div>
      <div>
        <label style={lbl}>Durată (min)</label>
        <input type="number" style={inp} value={durationMin} onChange={(e) => setDurationMin(e.target.value)} />
      </div>
      <div>
        <label style={lbl}>Km</label>
        <input type="number" style={inp} value={km} onChange={(e) => setKm(e.target.value)} />
      </div>
      <div style={{ gridColumn: "1 / -1" }}>
        <label style={lbl}>Notițe</label>
        <textarea style={{ ...inp, minHeight: 48 }} value={notes} onChange={(e) => setNotes(e.target.value)} />
      </div>
      {err && (
        <div style={{ gridColumn: "1 / -1", color: "var(--red)", fontSize: 12 }}>{err}</div>
      )}
      <div style={{ gridColumn: "1 / -1", textAlign: "right" }}>
        <button type="submit" style={styles.btnActive} disabled={saving}>
          {saving ? "Se salvează..." : "Salvează vizita"}
        </button>
      </div>
    </form>
  );
}

function KpiStrip({ data }: { data: ActivitateResponse }) {
  const km = toNum(data.totalKm);
  return (
    <div style={styles.kpiRow}>
      <KpiCard label="AGENȚI" value={String(data.agentsCount)} sub="total" />
      <KpiCard
        label="VIZITE"
        value={String(data.totalVisits)}
        sub="check-ins"
        valueColor="var(--cyan)"
      />
      <KpiCard
        label="MAGAZINE"
        value={String(data.totalStores)}
        sub="distincte"
      />
      <KpiCard
        label="KM"
        value={new Intl.NumberFormat("ro-RO", { maximumFractionDigits: 0 }).format(km)}
        sub="parcurși"
        valueColor="var(--orange)"
      />
    </div>
  );
}

function KpiCard({
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

function AgentsList({
  data,
  expanded,
  onToggle,
}: {
  data: ActivitateResponse;
  expanded: Set<string>;
  onToggle: (id: string) => void;
}) {
  const agents = useMemo(
    () => [...data.agents].sort((a, b) => b.visitsCount - a.visitsCount),
    [data.agents],
  );

  if (agents.length === 0) {
    return (
      <div style={styles.emptyBox}>
        <p style={{ color: "var(--muted)", margin: 0 }}>
          Nu există agenți canonici pentru această companie.
        </p>
      </div>
    );
  }

  return (
    <div style={styles.tableCard}>
      <div style={styles.agentHeaderRow}>
        <div>AGENT</div>
        <div style={styles.thRight}>Vizite</div>
        <div style={styles.thRight}>Magazine</div>
        <div style={styles.thRight}>Km</div>
        <div style={styles.thRight}>Durată (min)</div>
      </div>
      {agents.map((a, idx) => {
        const id = a.agentId ?? `nomap-${idx}`;
        const isOpen = expanded.has(id);
        const empty = a.visitsCount === 0;
        return (
          <div key={id} className="agent-section">
            <div
              style={{
                ...styles.agentRow,
                opacity: empty ? 0.65 : 1,
              }}
              onClick={() => !empty && onToggle(id)}
              role="button"
              tabIndex={0}
            >
              <div style={styles.tdAgent}>
                <span
                  style={{
                    ...styles.expandArrow,
                    visibility: empty ? "hidden" : "visible",
                    transform: isOpen ? "rotate(90deg)" : "rotate(0deg)",
                  }}
                >
                  ▶
                </span>
                <span style={styles.agentName}>{a.agentName}</span>
              </div>
              <div style={styles.tdNumRight}>{a.visitsCount}</div>
              <div style={styles.tdNumRight}>{a.storesCount}</div>
              <div style={styles.tdNumRight}>
                {new Intl.NumberFormat("ro-RO", { maximumFractionDigits: 0 }).format(
                  toNum(a.totalKm),
                )}
              </div>
              <div style={styles.tdNumRight}>{a.totalDurationMin}</div>
            </div>
            {isOpen && <VisitsDrilldown agent={a} />}
          </div>
        );
      })}
    </div>
  );
}

function VisitsDrilldown({ agent }: { agent: ActivitateAgentRow }) {
  if (agent.visits.length === 0) {
    return (
      <div style={styles.agentDetails}>
        <span style={{ color: "var(--muted)", fontSize: 12 }}>
          Nicio vizită înregistrată pentru acest agent în intervalul selectat.
        </span>
      </div>
    );
  }
  return (
    <div style={styles.storesDetails}>
      <div style={styles.storeHeaderRow}>
        <div>Data</div>
        <div>Magazin</div>
        <div style={styles.thRight}>Check-in</div>
        <div style={styles.thRight}>Check-out</div>
        <div style={styles.thRight}>Durată</div>
        <div style={styles.thRight}>Km</div>
      </div>
      {agent.visits.map((v, i) => (
        <div key={i} style={styles.storeRow}>
          <div>{fmtDateRo(v.visitDate)}</div>
          <div style={styles.storeName} title={v.storeName}>
            {v.storeName}
          </div>
          <div style={styles.tdNumRight}>{v.checkIn ?? "—"}</div>
          <div style={styles.tdNumRight}>{v.checkOut ?? "—"}</div>
          <div style={styles.tdNumRight}>{v.durationMin ?? "—"}</div>
          <div style={styles.tdNumRight}>{v.km ?? "—"}</div>
        </div>
      ))}
    </div>
  );
}

const styles: Record<string, CSSProperties> = {
  page: { display: "flex", flexDirection: "column", gap: 12 },
  headerRow: { display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" },
  titleIcon: { fontSize: 18 },
  title: { fontSize: 20, fontWeight: 700, color: "var(--cyan)", margin: 0 },
  periodLabel: { fontSize: 13, color: "var(--muted)" },
  filterBar: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    flexWrap: "wrap",
    padding: "8px 12px",
    background: "var(--card)",
    border: "1px solid var(--border)",
    borderRadius: 10,
  },
  btn: {
    padding: "6px 14px",
    borderRadius: 6,
    border: "1px solid var(--border)",
    background: "var(--card)",
    color: "var(--muted)",
    fontSize: 13,
    cursor: "pointer",
  },
  btnActive: {
    padding: "6px 14px",
    borderRadius: 6,
    border: "1px solid var(--cyan)",
    background: "var(--cyan)",
    color: "#0f172a",
    fontWeight: 600,
    fontSize: 13,
    cursor: "pointer",
  },
  divider: {
    width: 1,
    height: 22,
    background: "var(--border)",
    margin: "0 4px",
  },
  label: { fontSize: 12, color: "var(--muted)" },
  dateInput: {
    padding: "6px 10px",
    border: "1px solid var(--border)",
    borderRadius: 6,
    background: "var(--card)",
    color: "var(--text)",
    fontSize: 13,
  },
  todoBanner: {
    padding: "8px 14px",
    background: "rgba(251,146,60,0.08)",
    border: "1px solid rgba(251,146,60,0.35)",
    borderRadius: 8,
    fontSize: 12,
    color: "var(--text)",
  },
  kpiRow: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
    gap: 12,
  },
  kpiCard: {
    background: "var(--card)",
    border: "1px solid var(--border)",
    borderRadius: 12,
    padding: "8px 10px",
    display: "flex",
    flexDirection: "column",
    justifyContent: "center",
    minHeight: 58,
  },
  kpiLabel: {
    fontSize: 10,
    color: "var(--muted)",
    textTransform: "uppercase",
    letterSpacing: "0.06em",
    fontWeight: 600,
    marginBottom: 2,
    lineHeight: 1.2,
  },
  kpiValue: { fontSize: 18, fontWeight: 800, lineHeight: 1.15 },
  kpiSub: { fontSize: 10.5, marginTop: 2, color: "var(--muted)", lineHeight: 1.2 },
  tableCard: {
    background: "var(--card)",
    border: "1px solid var(--border)",
    borderRadius: 10,
    overflow: "hidden",
  },
  agentHeaderRow: {
    display: "grid",
    gridTemplateColumns: "2fr 0.7fr 0.7fr 0.7fr 0.9fr",
    gap: 14,
    padding: "6px 16px",
    borderBottom: "1px solid var(--border)",
    fontSize: 10,
    textTransform: "uppercase",
    letterSpacing: "0.04em",
    color: "var(--muted)",
    fontWeight: 600,
  },
  agentRow: {
    display: "grid",
    gridTemplateColumns: "2fr 0.7fr 0.7fr 0.7fr 0.9fr",
    gap: 14,
    padding: "5px 16px",
    alignItems: "center",
    borderBottom: "1px solid rgba(30,41,59,0.5)",
    cursor: "pointer",
  },
  tdAgent: { display: "flex", alignItems: "center", gap: 10 },
  expandArrow: {
    fontSize: 10,
    color: "var(--muted)",
    transition: "transform 0.12s ease",
    width: 10,
  },
  agentName: { fontSize: 13, color: "var(--text)", lineHeight: 1.2 },
  thRight: { textAlign: "right" },
  tdNumRight: { fontSize: 13, textAlign: "right", color: "var(--text)" },
  agentDetails: {
    padding: "6px 40px 8px",
    background: "rgba(0,0,0,0.06)",
    borderBottom: "1px solid rgba(30,41,59,0.3)",
  },
  storesDetails: {
    padding: "4px 16px 6px 40px",
    background: "rgba(0,0,0,0.06)",
    borderBottom: "1px solid rgba(30,41,59,0.3)",
  },
  storeHeaderRow: {
    display: "grid",
    gridTemplateColumns: "1fr 2.4fr 0.9fr 0.9fr 0.7fr 0.7fr",
    gap: 14,
    padding: "4px 0",
    fontSize: 10,
    textTransform: "uppercase",
    letterSpacing: "0.04em",
    color: "var(--muted)",
    fontWeight: 600,
    borderBottom: "1px solid rgba(30,41,59,0.25)",
  },
  storeRow: {
    display: "grid",
    gridTemplateColumns: "1fr 2.4fr 0.9fr 0.9fr 0.7fr 0.7fr",
    gap: 14,
    padding: "3px 0",
    alignItems: "center",
    fontSize: 12,
  },
  storeName: {
    color: "var(--text)",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
  emptyBox: {
    background: "var(--card)",
    border: "1px solid var(--border)",
    borderRadius: 10,
    padding: "32px 20px",
    textAlign: "center",
  },
  errorBox: {
    background: "rgba(239,68,68,0.1)",
    border: "1px solid var(--red)",
    color: "var(--red)",
    padding: 16,
    borderRadius: 8,
  },
};
