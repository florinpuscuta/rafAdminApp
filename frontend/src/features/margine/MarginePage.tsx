import { useEffect, useMemo, useState, type CSSProperties } from "react";

import { ApiError } from "../../shared/api";
import { useCompanyScope, type CompanyScope } from "../../shared/ui/CompanyScopeProvider";
import { getMargine } from "./api";
import type { MargineResponse, MargineScope } from "./types";


const MONTH_NAMES = [
  "", "Ian", "Feb", "Mar", "Apr", "Mai", "Iun",
  "Iul", "Aug", "Sep", "Oct", "Noi", "Dec",
];


function scopeFromCompany(c: CompanyScope): MargineScope {
  if (c === "sika") return "sika";
  if (c === "sikadp") return "sikadp";
  return "adp";
}


function scopeLabel(s: MargineScope): string {
  if (s === "sika") return "Sika";
  if (s === "sikadp") return "Combinat";
  return "Adeplast";
}


function toNum(v: string | number | null | undefined): number {
  if (v == null) return 0;
  if (typeof v === "number") return v;
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}


function fmtRo(n: number, maxFrac = 0): string {
  return new Intl.NumberFormat("ro-RO", {
    maximumFractionDigits: maxFrac,
    minimumFractionDigits: maxFrac,
  }).format(n);
}


function fmtPct(n: number, frac = 1): string {
  return `${n >= 0 ? "" : "−"}${Math.abs(n).toLocaleString("ro-RO", {
    minimumFractionDigits: frac, maximumFractionDigits: frac,
  })}%`;
}


function shiftMonths(year: number, month: number, delta: number): { y: number; m: number } {
  const total = year * 12 + (month - 1) + delta;
  return { y: Math.floor(total / 12), m: (total % 12) + 1 };
}


function defaultPeriod(): { fromYear: number; fromMonth: number; toYear: number; toMonth: number } {
  // YTD pana la luna curenta inclusiv — paritate cu Consolidat
  // (consolidat/router.py::_parse_months default_to_ytd=True).
  const now = new Date();
  const year = now.getFullYear();
  const month = now.getMonth() + 1;
  return { fromYear: year, fromMonth: 1, toYear: year, toMonth: month };
}


export default function MarginePage() {
  const { scope: companyScope } = useCompanyScope();
  const [scope, setScope] = useState<MargineScope>(scopeFromCompany(companyScope));
  const init = defaultPeriod();
  const [fromYear, setFromYear] = useState(init.fromYear);
  const [fromMonth, setFromMonth] = useState(init.fromMonth);
  const [toYear, setToYear] = useState(init.toYear);
  const [toMonth, setToMonth] = useState(init.toMonth);

  const [data, setData] = useState<MargineResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refreshTick, setRefreshTick] = useState(0);

  function applyPreset(from: { y: number; m: number }, to?: { y: number; m: number }) {
    setFromYear(from.y);
    setFromMonth(from.m);
    if (to) {
      setToYear(to.y);
      setToMonth(to.m);
    }
    // Force re-fetch chiar daca starea ramane identica (preset = no-op).
    setRefreshTick((n) => n + 1);
  }

  useEffect(() => {
    setScope(scopeFromCompany(companyScope));
  }, [companyScope]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getMargine(scope, fromYear, fromMonth, toYear, toMonth)
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        if (e instanceof ApiError) setError(e.message);
        else if (e instanceof Error) setError(e.message);
        else setError("Eroare la incarcare");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [scope, fromYear, fromMonth, toYear, toMonth, refreshTick]);

  const yearsOptions = useMemo(() => {
    const cy = new Date().getFullYear();
    return [cy - 3, cy - 2, cy - 1, cy];
  }, []);

  const scopeOptions: MargineScope[] = companyScope === "sikadp"
    ? ["adp", "sika", "sikadp"]
    : companyScope === "sika"
      ? ["sika"]
      : ["adp"];

  return (
    <div style={styles.page}>
      <div style={styles.sectionTitle}>Marja pe Perioada — {scopeLabel(scope)}</div>
      <div style={styles.sectionSubtitle}>
        Calculul marjei: revenue (din raw_sales) - cost (qty × pret_productie).
        Produsele fara pret de productie sunt listate separat si NU intra in
        totaluri.
      </div>

      <div style={styles.controls}>
        {scopeOptions.length > 1 && (
          <div style={styles.tabs}>
            {scopeOptions.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => setScope(s)}
                style={{ ...styles.tabBtn, ...(scope === s ? styles.tabBtnActive : {}) }}
              >
                {scopeLabel(s)}
              </button>
            ))}
          </div>
        )}

        <div style={styles.periodGroup}>
          <span style={styles.periodLabel}>De la</span>
          <PeriodSelect
            year={fromYear} month={fromMonth} years={yearsOptions}
            onChange={(y, m) => { setFromYear(y); setFromMonth(m); }}
          />
          <span style={styles.periodLabel}>pana la</span>
          <PeriodSelect
            year={toYear} month={toMonth} years={yearsOptions}
            onChange={(y, m) => { setToYear(y); setToMonth(m); }}
          />
        </div>

        <div style={styles.presets}>
          <PresetBtn
            label="YTD"
            title="Year-to-Date — de la ianuarie pana la luna curenta"
            onClick={() => {
              const now = new Date();
              const y = now.getFullYear();
              const m = now.getMonth() + 1;
              applyPreset({ y, m: 1 }, { y, m });
            }}
          />
          <PresetBtn
            label="3 luni"
            onClick={() => applyPreset(shiftMonths(toYear, toMonth, -2))}
          />
          <PresetBtn
            label="6 luni"
            onClick={() => applyPreset(shiftMonths(toYear, toMonth, -5))}
          />
          <PresetBtn
            label="12 luni"
            onClick={() => applyPreset(shiftMonths(toYear, toMonth, -11))}
          />
          <PresetBtn
            label={`An ${toYear - 1}`}
            title="Anul anterior complet"
            onClick={() =>
              applyPreset({ y: toYear - 1, m: 1 }, { y: toYear - 1, m: 12 })
            }
          />
        </div>
      </div>

      {loading && <div style={styles.muted}>Se calculeaza...</div>}

      {error && (
        <div style={styles.errorBox}>
          <strong>Eroare:</strong> {error}
        </div>
      )}

      {!loading && data && <MargineKpis data={data} />}
      {!loading && data && <GroupsSection data={data} />}
      {!loading && data && data.missingCost.length > 0 && (
        <MissingSection rows={data.missingCost} />
      )}
    </div>
  );
}


function PresetBtn({
  label, onClick, title,
}: { label: string; onClick: () => void; title?: string }) {
  return (
    <button type="button" onClick={onClick} title={title} style={styles.presetBtn}>
      {label}
    </button>
  );
}


function PeriodSelect({
  year, month, years, onChange,
}: {
  year: number; month: number; years: number[];
  onChange: (y: number, m: number) => void;
}) {
  return (
    <span style={{ display: "inline-flex", gap: 6 }}>
      <select
        value={month}
        onChange={(e) => onChange(year, Number(e.target.value))}
        style={styles.select}
      >
        {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
          <option key={m} value={m}>{MONTH_NAMES[m]}</option>
        ))}
      </select>
      <select
        value={year}
        onChange={(e) => onChange(Number(e.target.value), month)}
        style={styles.select}
      >
        {years.map((y) => (
          <option key={y} value={y}>{y}</option>
        ))}
      </select>
    </span>
  );
}


function MargineKpis({ data }: { data: MargineResponse }) {
  const revenue = toNum(data.revenuePeriod);
  const covered = toNum(data.revenueCovered);
  const cost = toNum(data.costTotal);
  const profit = toNum(data.profitTotal);
  const margin = toNum(data.marginPct);
  const coverage = toNum(data.coveragePct);
  const discountTotal = toNum(data.discountTotal);
  const discountAllocated = toNum(data.discountAllocatedTotal);
  const profitNet = toNum(data.profitNetTotal);
  const marginNet = toNum(data.marginPctNet);

  return (
    <>
      <div style={styles.kpiRow}>
        <Kpi label="Revenue (= Consolidat)" value={fmtRo(revenue, 0)} unit="RON" tone="neutral" />
        <Kpi label="Revenue cu cost" value={fmtRo(covered, 0)} unit="RON" tone="neutral" />
        <Kpi label="Cost productie" value={fmtRo(cost, 0)} unit="RON" tone="warn" />
        <Kpi label="Profit brut" value={fmtRo(profit, 0)} unit="RON" tone={profit >= 0 ? "good" : "bad"} />
        <Kpi label="Marja bruta" value={fmtPct(margin, 1)} tone={margin >= 30 ? "good" : margin >= 15 ? "warn" : "bad"} />
        <Kpi label="Acoperire cost" value={fmtPct(coverage, 1)} tone={coverage >= 80 ? "good" : coverage >= 50 ? "warn" : "bad"} />
      </div>
      <div style={styles.kpiRow}>
        <Kpi
          label="Discount KA total"
          value={fmtRo(discountTotal, 0)}
          unit="RON"
          tone={discountTotal < 0 ? "bad" : "neutral"}
        />
        <Kpi
          label="Discount alocat"
          value={fmtRo(discountAllocated, 0)}
          unit="RON"
          tone={discountAllocated < 0 ? "bad" : "neutral"}
        />
        <Kpi
          label="Profit net (dupa discount)"
          value={fmtRo(profitNet, 0)}
          unit="RON"
          tone={profitNet >= 0 ? "good" : "bad"}
        />
        <Kpi
          label="Marja neta"
          value={fmtPct(marginNet, 1)}
          tone={marginNet >= 30 ? "good" : marginNet >= 15 ? "warn" : "bad"}
        />
      </div>
    </>
  );
}


function Kpi({
  label, value, unit, tone,
}: {
  label: string; value: string; unit?: string;
  tone: "good" | "bad" | "warn" | "neutral";
}) {
  const color =
    tone === "good" ? "var(--green)"
      : tone === "bad" ? "var(--red)"
        : tone === "warn" ? "var(--orange)"
          : "var(--text)";
  return (
    <div style={styles.kpiCard}>
      <div style={styles.kpiLabel}>{label}</div>
      <div style={{ ...styles.kpiValue, color }}>
        {value}
        {unit && <span style={styles.kpiUnit}> {unit}</span>}
      </div>
    </div>
  );
}


function GroupsSection({ data }: { data: MargineResponse }) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const toggle = (key: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  };

  const groupNoun = data.scope === "sika" ? "Target Market"
    : data.scope === "sikadp" ? "Categorie / TM"
      : "Categorie de produs";

  if (data.groups.length === 0) {
    return (
      <div style={styles.card}>
        <div style={styles.muted}>
          Nu exista vanzari mapate la produse cu pret de productie in perioada selectata.
        </div>
      </div>
    );
  }

  const regularGroups = data.groups.filter((g) => g.kind !== "private_label");
  const plGroups = data.groups.filter((g) => g.kind === "private_label");

  function sumGroups(arr: typeof data.groups) {
    return arr.reduce(
      (acc, g) => {
        acc.revenue += toNum(g.revenue);
        acc.cost += toNum(g.costTotal);
        acc.profit += toNum(g.profit);
        acc.discount += toNum(g.discountAllocated);
        acc.profitNet += toNum(g.profitNet);
        acc.products += g.products.length;
        return acc;
      },
      { revenue: 0, cost: 0, profit: 0, discount: 0, profitNet: 0, products: 0 },
    );
  }
  function marginsOf(t: ReturnType<typeof sumGroups>) {
    const m = t.revenue ? (t.profit / t.revenue) * 100 : 0;
    const mn = t.revenue ? (t.profitNet / t.revenue) * 100 : 0;
    return { m, mn };
  }

  const plTotals = sumGroups(plGroups);
  const grandTotals = sumGroups(data.groups);
  const grandMargins = marginsOf(grandTotals);
  const plMargins = marginsOf(plTotals);

  return (
    <div style={styles.card}>
      <div style={styles.cardTitle}>Pe {groupNoun}</div>
      <table style={styles.table}>
        <thead>
          <tr>
            <th style={styles.th} />
            <th style={styles.th}>Grupa</th>
            <th style={{ ...styles.th, textAlign: "right" }}>Revenue</th>
            <th style={{ ...styles.th, textAlign: "right" }}>Cost</th>
            <th style={{ ...styles.th, textAlign: "right" }}>Profit</th>
            <th style={{ ...styles.th, textAlign: "right" }}>Marja</th>
            <th style={{ ...styles.th, textAlign: "right" }} title="Cota din storno KA alocata acestei grupe (negativ).">
              Discount
            </th>
            <th style={{ ...styles.th, textAlign: "right" }} title="Marja dupa scaderea discount-ului alocat.">
              Marja neta
            </th>
            <th style={{ ...styles.th, textAlign: "right" }}>Produse</th>
          </tr>
        </thead>
        <tbody>
          {[...regularGroups, ...plGroups].map((g, i) => {
            const key = `${g.kind}::${g.label}::${i}`;
            const open = expanded.has(key);
            const margin = toNum(g.marginPct);
            const tone = margin >= 30 ? "var(--green)" : margin >= 15 ? "var(--orange)" : "var(--red)";
            const isFirstPL = g.kind === "private_label" && i === regularGroups.length;
            return (
              <>
                {isFirstPL && (
                  <SubHeaderRow
                    label="Marca Privata"
                    totals={plTotals}
                    marginPct={plMargins.m}
                    marginPctNet={plMargins.mn}
                  />
                )}
                <tr key={key} style={{ cursor: "pointer" }} onClick={() => toggle(key)}>
                  <td style={styles.td}>{open ? "▾" : "▸"}</td>
                  <td style={{ ...styles.td, fontWeight: 600 }}>{g.label}</td>
                  <td style={styles.tdNum}>{fmtRo(toNum(g.revenue), 0)}</td>
                  <td style={styles.tdNum}>{fmtRo(toNum(g.costTotal), 0)}</td>
                  <td style={{ ...styles.tdNum, color: toNum(g.profit) >= 0 ? "var(--green)" : "var(--red)" }}>
                    {fmtRo(toNum(g.profit), 0)}
                  </td>
                  <td style={{ ...styles.tdNum, color: tone, fontWeight: 700 }}>
                    {fmtPct(margin, 1)}
                  </td>
                  <td style={{ ...styles.tdNum, color: toNum(g.discountAllocated) < 0 ? "var(--red)" : "var(--muted)" }}>
                    {toNum(g.discountAllocated) === 0 ? "—" : fmtRo(toNum(g.discountAllocated), 0)}
                  </td>
                  <td style={{
                    ...styles.tdNum,
                    color: toNum(g.marginPctNet) >= 30 ? "var(--green)"
                      : toNum(g.marginPctNet) >= 15 ? "var(--orange)"
                        : "var(--red)",
                    fontWeight: 700,
                  }}>
                    {fmtPct(toNum(g.marginPctNet), 1)}
                  </td>
                  <td style={styles.tdNum}>{g.products.length}</td>
                </tr>
                {open && g.products.map((p) => (
                  <tr key={p.productId} style={{ background: "rgba(255,255,255,0.02)" }}>
                    <td style={styles.td} />
                    <td style={{ ...styles.td, paddingLeft: 24, color: "var(--muted)" }}>
                      <div style={{ fontWeight: 500, color: "var(--text)" }}>{p.productName}</div>
                      <div style={{ fontSize: 11, color: "var(--muted)" }}>{p.productCode}</div>
                    </td>
                    <td style={styles.tdNum}>{fmtRo(toNum(p.revenue), 0)}</td>
                    <td style={styles.tdNum}>{fmtRo(toNum(p.cost) * toNum(p.quantity), 0)}</td>
                    <td style={{ ...styles.tdNum, color: toNum(p.profit) >= 0 ? "var(--green)" : "var(--red)" }}>
                      {fmtRo(toNum(p.profit), 0)}
                    </td>
                    <td style={{ ...styles.tdNum, color: toNum(p.marginPct) >= 30 ? "var(--green)" : toNum(p.marginPct) >= 15 ? "var(--orange)" : "var(--red)" }}>
                      {fmtPct(toNum(p.marginPct), 1)}
                    </td>
                    <td style={{ ...styles.tdNum, color: "var(--muted)", fontSize: 11 }}>—</td>
                    <td style={{ ...styles.tdNum, color: "var(--muted)", fontSize: 11 }}>—</td>
                    <td style={{ ...styles.tdNum, fontSize: 11, color: "var(--muted)" }}>
                      {fmtRo(toNum(p.quantity), 1)} buc
                    </td>
                  </tr>
                ))}
              </>
            );
          })}
          {data.groups.length > 0 && (
            <TotalGeneralRow totals={grandTotals} marginPct={grandMargins.m} marginPctNet={grandMargins.mn} />
          )}
        </tbody>
      </table>
    </div>
  );
}


function SubHeaderRow({
  label, totals, marginPct, marginPctNet,
}: {
  label: string;
  totals: { revenue: number; cost: number; profit: number; discount: number; profitNet: number; products: number };
  marginPct: number;
  marginPctNet: number;
}) {
  const tone = marginPct >= 30 ? "var(--green)" : marginPct >= 15 ? "var(--orange)" : "var(--red)";
  const toneNet = marginPctNet >= 30 ? "var(--green)" : marginPctNet >= 15 ? "var(--orange)" : "var(--red)";
  return (
    <tr style={styles.subHeaderRow}>
      <td style={styles.subHeaderTd} />
      <td style={{ ...styles.subHeaderTd, fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.04em" }}>
        {label}
      </td>
      <td style={styles.subHeaderTdNum}>{fmtRo(totals.revenue, 0)}</td>
      <td style={styles.subHeaderTdNum}>{fmtRo(totals.cost, 0)}</td>
      <td style={{ ...styles.subHeaderTdNum, color: totals.profit >= 0 ? "var(--green)" : "var(--red)" }}>
        {fmtRo(totals.profit, 0)}
      </td>
      <td style={{ ...styles.subHeaderTdNum, color: tone, fontWeight: 800 }}>{fmtPct(marginPct, 1)}</td>
      <td style={{ ...styles.subHeaderTdNum, color: totals.discount < 0 ? "var(--red)" : "var(--muted)" }}>
        {totals.discount === 0 ? "—" : fmtRo(totals.discount, 0)}
      </td>
      <td style={{ ...styles.subHeaderTdNum, color: toneNet, fontWeight: 800 }}>{fmtPct(marginPctNet, 1)}</td>
      <td style={styles.subHeaderTdNum}>{totals.products}</td>
    </tr>
  );
}


function TotalGeneralRow({
  totals, marginPct, marginPctNet,
}: {
  totals: { revenue: number; cost: number; profit: number; discount: number; profitNet: number; products: number };
  marginPct: number;
  marginPctNet: number;
}) {
  const tone = marginPct >= 30 ? "var(--green)" : marginPct >= 15 ? "var(--orange)" : "var(--red)";
  const toneNet = marginPctNet >= 30 ? "var(--green)" : marginPctNet >= 15 ? "var(--orange)" : "var(--red)";
  return (
    <tr style={styles.totalRow}>
      <td style={styles.totalTd} />
      <td style={{ ...styles.totalTd, fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.04em" }}>
        Total General
      </td>
      <td style={styles.totalTdNum}>{fmtRo(totals.revenue, 0)}</td>
      <td style={styles.totalTdNum}>{fmtRo(totals.cost, 0)}</td>
      <td style={{ ...styles.totalTdNum, color: totals.profit >= 0 ? "var(--green)" : "var(--red)" }}>
        {fmtRo(totals.profit, 0)}
      </td>
      <td style={{ ...styles.totalTdNum, color: tone, fontWeight: 800 }}>{fmtPct(marginPct, 1)}</td>
      <td style={{ ...styles.totalTdNum, color: totals.discount < 0 ? "var(--red)" : "var(--muted)" }}>
        {totals.discount === 0 ? "—" : fmtRo(totals.discount, 0)}
      </td>
      <td style={{ ...styles.totalTdNum, color: toneNet, fontWeight: 800 }}>{fmtPct(marginPctNet, 1)}</td>
      <td style={styles.totalTdNum}>{totals.products}</td>
    </tr>
  );
}


function MissingSection({ rows }: { rows: MargineResponse["missingCost"] }) {
  const totalRev = rows.reduce((a, r) => a + toNum(r.revenue), 0);
  return (
    <div style={{ ...styles.card, borderColor: "var(--orange)" }}>
      <div style={{ ...styles.cardTitle, color: "var(--orange)" }}>
        Produse fara pret de productie ({rows.length}) — Revenue total: {fmtRo(totalRev, 0)} RON
      </div>
      <div style={{ fontSize: 12, color: "var(--muted)", marginBottom: 8 }}>
        Aceste produse au vanzari in perioada selectata dar nu au cost incarcat,
        deci NU sunt incluse in marja totala. Adauga preturi pe meniu Settings → Pret Productie.
      </div>
      <table style={styles.table}>
        <thead>
          <tr>
            <th style={styles.th}>Cod</th>
            <th style={styles.th}>Denumire</th>
            <th style={{ ...styles.th, textAlign: "right" }}>Revenue</th>
            <th style={{ ...styles.th, textAlign: "right" }}>Cantitate</th>
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, 50).map((r) => (
            <tr key={r.productId}>
              <td style={{ ...styles.td, fontSize: 11, fontFamily: "monospace" }}>{r.productCode}</td>
              <td style={styles.td}>{r.productName}</td>
              <td style={styles.tdNum}>{fmtRo(toNum(r.revenue), 0)}</td>
              <td style={styles.tdNum}>{fmtRo(toNum(r.quantity), 1)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length > 50 && (
        <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 6 }}>
          Sunt afisate primele 50 din {rows.length}.
        </div>
      )}
    </div>
  );
}


const styles: Record<string, CSSProperties> = {
  page: { display: "flex", flexDirection: "column", gap: 16 },
  sectionTitle: { fontSize: 20, fontWeight: 700 },
  sectionSubtitle: { fontSize: 12, color: "var(--muted)", marginTop: -8, lineHeight: 1.5 },
  controls: { display: "flex", gap: 14, alignItems: "center", flexWrap: "wrap" },
  tabs: { display: "flex", gap: 6 },
  tabBtn: {
    background: "transparent",
    color: "var(--text)",
    border: "1px solid var(--border)",
    padding: "6px 14px",
    borderRadius: 6,
    fontSize: 13,
    fontWeight: 600,
    cursor: "pointer",
  },
  tabBtnActive: {
    background: "linear-gradient(135deg, #22d3ee, #06b6d4)",
    color: "#0a0e17",
    border: "none",
  },
  periodGroup: { display: "flex", gap: 6, alignItems: "center" },
  periodLabel: { fontSize: 12, color: "var(--muted)" },
  presets: { display: "flex", gap: 4 },
  presetBtn: {
    background: "transparent",
    color: "var(--muted)",
    border: "1px solid var(--border)",
    padding: "5px 10px",
    borderRadius: 6,
    fontSize: 11,
    fontWeight: 600,
    cursor: "pointer",
  },
  select: {
    background: "var(--bg)",
    color: "var(--text)",
    border: "1px solid var(--border)",
    padding: "5px 10px",
    borderRadius: 6,
    fontSize: 13,
  },
  card: {
    background: "var(--card)",
    border: "1px solid var(--border)",
    borderRadius: 10,
    padding: 18,
    display: "flex",
    flexDirection: "column",
    gap: 10,
  },
  cardTitle: { fontSize: 14, fontWeight: 700 },
  errorBox: {
    background: "rgba(239,68,68,0.1)",
    border: "1px solid var(--red)",
    color: "var(--red)",
    padding: 12,
    borderRadius: 8,
    fontSize: 13,
  },
  muted: { color: "var(--muted)", fontSize: 13 },
  kpiRow: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
    gap: 10,
  },
  kpiCard: {
    background: "var(--card)",
    border: "1px solid var(--border)",
    borderRadius: 10,
    padding: "10px 14px",
    minHeight: 64,
  },
  kpiLabel: {
    fontSize: 10,
    textTransform: "uppercase",
    letterSpacing: "0.06em",
    color: "var(--muted)",
    fontWeight: 600,
    marginBottom: 4,
  },
  kpiValue: { fontSize: 20, fontWeight: 800, lineHeight: 1.15 },
  kpiUnit: { fontSize: 11, fontWeight: 500, color: "var(--muted)", marginLeft: 4 },
  table: { width: "100%", borderCollapse: "collapse", fontSize: 12 },
  th: {
    borderBottom: "1px solid var(--border)",
    padding: "8px 10px",
    textAlign: "left",
    fontSize: 11,
    fontWeight: 700,
    color: "var(--muted)",
    textTransform: "uppercase",
    letterSpacing: "0.04em",
  },
  td: {
    borderBottom: "1px solid rgba(255,255,255,0.04)",
    padding: "8px 10px",
    color: "var(--text)",
  },
  tdNum: {
    borderBottom: "1px solid rgba(255,255,255,0.04)",
    padding: "8px 10px",
    textAlign: "right",
    fontVariantNumeric: "tabular-nums",
    color: "var(--text)",
  },
  totalRow: {
    background: "rgba(34,211,238,0.06)",
    borderTop: "2px solid var(--cyan)",
    borderBottom: "2px solid var(--cyan)",
  },
  totalTd: {
    padding: "10px",
    color: "var(--cyan)",
    fontSize: 13,
  },
  totalTdNum: {
    padding: "10px",
    textAlign: "right",
    fontVariantNumeric: "tabular-nums",
    color: "var(--cyan)",
    fontWeight: 700,
    fontSize: 13,
  },
  subHeaderRow: {
    background: "rgba(251,146,60,0.08)",
    borderTop: "1px solid var(--orange)",
  },
  subHeaderTd: {
    padding: "8px 10px",
    color: "var(--orange)",
    fontSize: 12,
  },
  subHeaderTdNum: {
    padding: "8px 10px",
    textAlign: "right",
    fontVariantNumeric: "tabular-nums",
    color: "var(--orange)",
    fontWeight: 700,
    fontSize: 12,
  },
};
