import { useEffect, useMemo, useRef, useState, type ChangeEvent } from "react";

import { ApiError } from "../../shared/api";
import {
  getMonthlySummary,
  getSummary,
  listMonthly,
  listPrices,
  resetMonthly,
  resetScope,
  uploadMonthly,
  uploadPrices,
} from "./api";
import type {
  PPListResponse,
  PPMonthlyListResponse,
  PPMonthlySummaryResponse,
  PPMonthlyUploadResponse,
  PPRow,
  PPScopeKey,
  PPSummaryResponse,
  PPUploadResponse,
} from "./types";


const SCOPE_LABEL: Record<PPScopeKey, string> = {
  adp: "Adeplast",
  sika: "Sika",
};

type Mode = "medie" | "lunar";

const MONTH_NAMES = [
  "", "Ian", "Feb", "Mar", "Apr", "Mai", "Iun",
  "Iul", "Aug", "Sep", "Oct", "Noi", "Dec",
];


export default function PretProductiePage() {
  const [scope, setScope] = useState<PPScopeKey>("adp");
  const [mode, setMode] = useState<Mode>("medie");
  const [summary, setSummary] = useState<PPSummaryResponse | null>(null);
  const [list, setList] = useState<PPListResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("");

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const [s, l] = await Promise.all([getSummary(), listPrices(scope)]);
      setSummary(s);
      setList(l);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Eroare la incarcare");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (mode === "medie") refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scope, mode]);

  return (
    <div style={styles.page}>
      <div style={styles.sectionTitle}>Pret Productie</div>
      <div style={styles.sectionSubtitle}>
        Incarca lista preturilor de productie per produs (Excel). Modul "Mediu"
        e o singura lista activa per scope (folosit pentru "Marja pe Perioada"
        si fallback). Modul "Pe luna" stocheaza snapshot-uri lunare (folosit
        pentru "Analiza Marja Lunara" — variatie instantanee).
      </div>

      <div style={styles.controlsRow}>
        <div style={styles.tabs}>
          {(Object.keys(SCOPE_LABEL) as PPScopeKey[]).map((k) => (
            <button
              key={k}
              type="button"
              onClick={() => setScope(k)}
              style={{
                ...styles.tabBtn,
                ...(scope === k ? styles.tabBtnActive : {}),
              }}
            >
              {SCOPE_LABEL[k]}
            </button>
          ))}
        </div>
        <div style={styles.modeTabs}>
          {(["medie", "lunar"] as Mode[]).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setMode(m)}
              style={{
                ...styles.modeTabBtn,
                ...(mode === m ? styles.modeTabBtnActive : {}),
              }}
            >
              {m === "medie" ? "Pret Mediu" : "Pe Luna"}
            </button>
          ))}
        </div>
      </div>

      {mode === "lunar" ? (
        <MonthlyMode scope={scope} />
      ) : (
        <>
      {summary && (
        <div style={styles.summaryGrid}>
          <SummaryCard
            title={`Adeplast`}
            count={summary.adp.count}
            ts={summary.adp.lastImportedAt}
            file={summary.adp.lastImportedFilename}
            active={scope === "adp"}
          />
          <SummaryCard
            title={`Sika`}
            count={summary.sika.count}
            ts={summary.sika.lastImportedAt}
            file={summary.sika.lastImportedFilename}
            active={scope === "sika"}
          />
        </div>
      )}

      <UploadCard scope={scope} onDone={refresh} />

      {error && (
        <div style={styles.errorBox}>
          <strong>Eroare:</strong> {error}
        </div>
      )}

      <PricesTable
        list={list}
        loading={loading}
        filter={filter}
        onFilter={setFilter}
        scope={scope}
        onReset={async () => {
          if (!confirm(`Sigur stergi toate preturile pentru ${SCOPE_LABEL[scope]}?`)) return;
          try {
            await resetScope(scope);
            await refresh();
          } catch (e) {
            setError(e instanceof Error ? e.message : "Eroare la reset");
          }
        }}
      />
        </>
      )}
    </div>
  );
}


function MonthlyMode({ scope }: { scope: PPScopeKey }) {
  const today = new Date();
  const [year, setYear] = useState(today.getFullYear());
  const [month, setMonth] = useState(today.getMonth() + 1);
  const [summary, setSummary] = useState<PPMonthlySummaryResponse | null>(null);
  const [list, setList] = useState<PPMonthlyListResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("");

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const [s, l] = await Promise.all([
        getMonthlySummary(),
        listMonthly(scope, year, month),
      ]);
      setSummary(s);
      setList(l);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Eroare la incarcare");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scope, year, month]);

  const yearsOptions = useMemo(() => {
    const cy = new Date().getFullYear();
    return [cy - 2, cy - 1, cy, cy + 1];
  }, []);

  const slotsForScope = (summary?.[scope] ?? []) as PPMonthlySummaryResponse["adp"];
  const hasCurrentSlot = slotsForScope.some((s) => s.year === year && s.month === month);

  return (
    <>
      <div style={styles.controlsRow}>
        <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
          <span style={{ fontSize: 12, color: "var(--muted)" }}>Luna:</span>
          <select value={month} onChange={(e) => setMonth(Number(e.target.value))} style={styles.select}>
            {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
              <option key={m} value={m}>{MONTH_NAMES[m]}</option>
            ))}
          </select>
          <select value={year} onChange={(e) => setYear(Number(e.target.value))} style={styles.select}>
            {yearsOptions.map((y) => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
        </div>
        <div style={{ flex: 1 }} />
        <div style={{ fontSize: 12, color: hasCurrentSlot ? "var(--green)" : "var(--orange)" }}>
          {hasCurrentSlot
            ? `✓ Snapshot incarcat pentru ${MONTH_NAMES[month]} ${year}`
            : `⚠ Niciun snapshot pentru ${MONTH_NAMES[month]} ${year} (foloseste pret mediu)`}
        </div>
      </div>

      {summary && (
        <MonthlyHeatmap slots={slotsForScope} year={year} month={month} onPick={(y, m) => { setYear(y); setMonth(m); }} />
      )}

      <MonthlyUploadCard scope={scope} year={year} month={month} onDone={refresh} />

      {error && (
        <div style={styles.errorBox}>
          <strong>Eroare:</strong> {error}
        </div>
      )}

      <MonthlyPricesTable
        list={list}
        loading={loading}
        filter={filter}
        onFilter={setFilter}
        scope={scope}
        year={year}
        month={month}
        onReset={async () => {
          if (!confirm(`Sigur stergi snapshot-ul pentru ${SCOPE_LABEL[scope]} ${MONTH_NAMES[month]} ${year}?`)) return;
          try {
            await resetMonthly(scope, year, month);
            await refresh();
          } catch (e) {
            setError(e instanceof Error ? e.message : "Eroare la reset");
          }
        }}
      />
    </>
  );
}


function MonthlyHeatmap({
  slots, year, month, onPick,
}: {
  slots: PPMonthlySummaryResponse["adp"];
  year: number; month: number;
  onPick: (y: number, m: number) => void;
}) {
  if (slots.length === 0) {
    return (
      <div style={{ ...styles.muted, padding: 8 }}>
        Niciun snapshot lunar incarcat inca pentru acest scope.
      </div>
    );
  }
  const years = Array.from(new Set(slots.map((s) => s.year))).sort((a, b) => b - a);
  return (
    <div style={styles.heatmapCard}>
      <div style={styles.cardTitle}>Snapshot-uri incarcate</div>
      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
        {years.map((y) => (
          <div key={y} style={{ display: "flex", gap: 4, alignItems: "center" }}>
            <div style={{ width: 50, fontSize: 12, color: "var(--muted)" }}>{y}</div>
            {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => {
              const slot = slots.find((s) => s.year === y && s.month === m);
              const isSelected = y === year && m === month;
              return (
                <button
                  key={m}
                  type="button"
                  onClick={() => onPick(y, m)}
                  title={slot ? `${slot.count} produse` : "Fara snapshot"}
                  style={{
                    width: 36, height: 28,
                    border: isSelected ? "2px solid var(--cyan)" : "1px solid var(--border)",
                    borderRadius: 4,
                    fontSize: 10,
                    cursor: "pointer",
                    background: slot ? "rgba(34,197,94,0.18)" : "transparent",
                    color: slot ? "var(--green)" : "var(--muted)",
                    fontWeight: 600,
                  }}
                >
                  {MONTH_NAMES[m]}
                </button>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}


function MonthlyUploadCard({
  scope, year, month, onDone,
}: { scope: PPScopeKey; year: number; month: number; onDone: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<PPMonthlyUploadResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  function reset() {
    setFile(null); setResult(null); setErr(null);
    if (inputRef.current) inputRef.current.value = "";
  }

  async function onSubmit() {
    if (!file) return;
    setBusy(true); setErr(null); setResult(null);
    try {
      const r = await uploadMonthly(scope, year, month, file);
      setResult(r);
      onDone();
    } catch (e) {
      if (e instanceof ApiError) setErr(e.message);
      else if (e instanceof Error) setErr(e.message);
      else setErr("Eroare la upload");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={styles.card}>
      <div style={styles.cardTitle}>
        Incarca snapshot — {SCOPE_LABEL[scope]} · {MONTH_NAMES[month]} {year}
      </div>
      <label style={styles.fileDrop}>
        <input
          ref={inputRef}
          type="file"
          accept=".xlsx"
          onChange={(e: ChangeEvent<HTMLInputElement>) => {
            setFile(e.target.files?.[0] ?? null);
            setResult(null); setErr(null);
          }}
          style={{ display: "none" }}
          disabled={busy}
        />
        {file ? (
          <>
            <div style={styles.fileName}>{file.name}</div>
            <div style={styles.fileSize}>{(file.size / 1024).toFixed(0)} KB</div>
          </>
        ) : (
          <>
            <div style={{ fontSize: 24, marginBottom: 6 }}>📅</div>
            <div style={{ fontWeight: 600 }}>
              Click pentru a selecta fisierul de cost pentru {MONTH_NAMES[month]} {year}
            </div>
            <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 4 }}>
              Header asteptat: "Cod produs" + "Pret productie"
            </div>
          </>
        )}
      </label>
      <div style={styles.actions}>
        <button
          type="button" onClick={onSubmit} disabled={!file || busy}
          style={styles.primaryBtn}
        >
          {busy ? "Se incarca..." : "Incarca"}
        </button>
        {(file || result || err) && (
          <button type="button" onClick={reset} disabled={busy} style={styles.secondaryBtn}>
            Reseteaza
          </button>
        )}
      </div>
      {err && <div style={styles.errorBox}><strong>Eroare:</strong> {err}</div>}
      {result && (
        <div style={styles.resultBox}>
          <div style={styles.resultTitle}>✓ Import {MONTH_NAMES[month]} {year}</div>
          <div style={styles.kpiGrid}>
            <Kpi label="Total" value={result.rowsTotal} variant="muted" />
            <Kpi label="Mapate" value={result.rowsMatched} variant="success" />
            <Kpi label="Inserate" value={result.inserted} variant="muted" />
            <Kpi label="Sterse anterior" value={result.deletedBefore} variant="muted" />
            <Kpi label="Nemapate" value={result.rowsUnmatched} variant={result.rowsUnmatched > 0 ? "warning" : "muted"} />
            <Kpi label="Invalide" value={result.rowsInvalid} variant={result.rowsInvalid > 0 ? "warning" : "muted"} />
          </div>
        </div>
      )}
    </div>
  );
}


function MonthlyPricesTable({
  list, loading, filter, onFilter, scope, year, month, onReset,
}: {
  list: PPMonthlyListResponse | null;
  loading: boolean;
  filter: string;
  onFilter: (s: string) => void;
  scope: PPScopeKey;
  year: number;
  month: number;
  onReset: () => void | Promise<void>;
}) {
  const grouped = useMemo(() => {
    if (!list) return new Map<string, PPRow[]>();
    const f = filter.trim().toLowerCase();
    const items = f
      ? list.items.filter((it) =>
          it.productCode.toLowerCase().includes(f) ||
          it.productName.toLowerCase().includes(f) ||
          (it.categoryLabel ?? "").toLowerCase().includes(f)
        )
      : list.items;
    const m = new Map<string, PPRow[]>();
    for (const it of items) {
      const key = it.categoryLabel ?? "Fara categorie";
      const arr = m.get(key) ?? [];
      arr.push(it);
      m.set(key, arr);
    }
    return m;
  }, [list, filter]);

  return (
    <div style={styles.card}>
      <div style={styles.tableHeader}>
        <div style={styles.cardTitle}>
          Snapshot {SCOPE_LABEL[scope]} · {MONTH_NAMES[month]} {year}
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <input
            type="search"
            placeholder="Cauta cod / denumire / grupa..."
            value={filter}
            onChange={(e) => onFilter(e.target.value)}
            style={styles.searchInput}
          />
          <button type="button" onClick={onReset} style={styles.dangerBtn}>
            Sterge luna
          </button>
        </div>
      </div>
      {loading && <div style={styles.muted}>Se incarca...</div>}
      {!loading && list && list.items.length === 0 && (
        <div style={styles.muted}>
          Niciun snapshot pentru {SCOPE_LABEL[scope]} pe {MONTH_NAMES[month]} {year}.
          Incarca un fisier deasupra ca sa il creezi.
        </div>
      )}
      {!loading && grouped.size > 0 && (
        <div style={{ maxHeight: 520, overflowY: "auto" }}>
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={styles.th}>Cod</th>
                <th style={styles.th}>Denumire</th>
                <th style={{ ...styles.th, textAlign: "right" }}>Pret productie</th>
              </tr>
            </thead>
            <tbody>
              {Array.from(grouped.entries()).map(([grp, items]) => (
                <ScopeGroup key={grp} label={grp} items={items} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}


function SummaryCard({
  title, count, ts, file, active,
}: {
  title: string;
  count: number;
  ts: string | null;
  file: string | null;
  active: boolean;
}) {
  const tsLabel = ts ? new Date(ts).toLocaleString("ro-RO") : "—";
  return (
    <div style={{ ...styles.summaryCard, ...(active ? styles.summaryCardActive : {}) }}>
      <div style={styles.summaryTitle}>{title}</div>
      <div style={styles.summaryValue}>{count.toLocaleString("ro-RO")}</div>
      <div style={styles.summaryMeta}>produse cu pret de productie</div>
      <div style={styles.summaryMeta}>Ultima incarcare: {tsLabel}</div>
      {file && <div style={styles.summaryMeta}>Fisier: {file}</div>}
    </div>
  );
}


function UploadCard({ scope, onDone }: { scope: PPScopeKey; onDone: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<PPUploadResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  function onFileChange(e: ChangeEvent<HTMLInputElement>) {
    setFile(e.target.files?.[0] ?? null);
    setResult(null);
    setErr(null);
  }

  function reset() {
    setFile(null);
    setResult(null);
    setErr(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  async function onSubmit() {
    if (!file) return;
    setBusy(true);
    setErr(null);
    setResult(null);
    try {
      const r = await uploadPrices(scope, file);
      setResult(r);
      onDone();
    } catch (e) {
      if (e instanceof ApiError) setErr(e.message);
      else if (e instanceof Error) setErr(e.message);
      else setErr("Eroare la upload");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={styles.card}>
      <div style={styles.cardTitle}>
        Incarca fisier — {SCOPE_LABEL[scope]}
      </div>
      <label style={styles.fileDrop}>
        <input
          ref={fileInputRef}
          type="file"
          accept=".xlsx"
          onChange={onFileChange}
          style={{ display: "none" }}
          disabled={busy}
        />
        {file ? (
          <>
            <div style={styles.fileName}>{file.name}</div>
            <div style={styles.fileSize}>
              {(file.size / 1024).toFixed(0)} KB
            </div>
          </>
        ) : (
          <>
            <div style={{ fontSize: 24, marginBottom: 6 }}>📊</div>
            <div style={{ fontWeight: 600 }}>
              Click pentru a selecta Pret_Productie_{SCOPE_LABEL[scope]}.xlsx
            </div>
            <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 4 }}>
              Header asteptat: "Cod produs" + "Pret productie"
            </div>
          </>
        )}
      </label>

      <div style={styles.actions}>
        <button
          type="button"
          onClick={onSubmit}
          disabled={!file || busy}
          style={styles.primaryBtn}
        >
          {busy ? "Se incarca..." : "Incarca"}
        </button>
        {(file || result || err) && (
          <button
            type="button"
            onClick={reset}
            disabled={busy}
            style={styles.secondaryBtn}
          >
            Reseteaza
          </button>
        )}
      </div>

      {err && (
        <div style={styles.errorBox}>
          <strong>Eroare:</strong> {err}
        </div>
      )}

      {result && <UploadResult res={result} />}
    </div>
  );
}


function UploadResult({ res }: { res: PPUploadResponse }) {
  return (
    <div style={styles.resultBox}>
      <div style={styles.resultTitle}>✓ Import finalizat</div>
      <div style={styles.kpiGrid}>
        <Kpi label="Total randuri" value={res.rowsTotal} variant="muted" />
        <Kpi label="Mapate" value={res.rowsMatched} variant="success" />
        <Kpi label="Inserate" value={res.inserted} variant="muted" />
        <Kpi label="Sterse anterior" value={res.deletedBefore} variant="muted" />
        <Kpi label="Nemapate" value={res.rowsUnmatched} variant={res.rowsUnmatched > 0 ? "warning" : "muted"} />
        <Kpi label="Invalide" value={res.rowsInvalid} variant={res.rowsInvalid > 0 ? "warning" : "muted"} />
      </div>
      {res.unmatchedCodes.length > 0 && (
        <div style={styles.subSection}>
          <div style={styles.subTitle}>Coduri produse nemapate (primele 50)</div>
          <div style={styles.unmatchedList}>
            {res.unmatchedCodes.map((c, i) => (
              <span key={i} style={styles.codeBadge}>{c}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}


function Kpi({
  label, value, variant,
}: {
  label: string; value: number; variant: "success" | "warning" | "muted";
}) {
  const color =
    variant === "success" ? "var(--green)"
      : variant === "warning" ? "var(--orange)"
        : "var(--text)";
  return (
    <div style={styles.kpi}>
      <div style={styles.kpiLabel}>{label}</div>
      <div style={{ ...styles.kpiValue, color }}>
        {value.toLocaleString("ro-RO")}
      </div>
    </div>
  );
}


function PricesTable({
  list, loading, filter, onFilter, scope, onReset,
}: {
  list: PPListResponse | null;
  loading: boolean;
  filter: string;
  onFilter: (s: string) => void;
  scope: PPScopeKey;
  onReset: () => void | Promise<void>;
}) {
  const grouped = useMemo(() => {
    if (!list) return new Map<string, PPRow[]>();
    const f = filter.trim().toLowerCase();
    const items = f
      ? list.items.filter((it) =>
          it.productCode.toLowerCase().includes(f) ||
          it.productName.toLowerCase().includes(f) ||
          (it.categoryLabel ?? "").toLowerCase().includes(f)
        )
      : list.items;
    const m = new Map<string, PPRow[]>();
    for (const it of items) {
      const key = it.categoryLabel ?? "Fara categorie";
      const arr = m.get(key) ?? [];
      arr.push(it);
      m.set(key, arr);
    }
    return m;
  }, [list, filter]);

  return (
    <div style={styles.card}>
      <div style={styles.tableHeader}>
        <div style={styles.cardTitle}>
          Preturi salvate — {SCOPE_LABEL[scope]}
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <input
            type="search"
            placeholder="Cauta cod / denumire / grupa..."
            value={filter}
            onChange={(e) => onFilter(e.target.value)}
            style={styles.searchInput}
          />
          <button
            type="button"
            onClick={onReset}
            style={styles.dangerBtn}
            title="Sterge toate preturile pentru acest scope"
          >
            Sterge tot
          </button>
        </div>
      </div>

      {loading && <div style={styles.muted}>Se incarca...</div>}

      {!loading && list && list.items.length === 0 && (
        <div style={styles.muted}>
          Nu exista preturi de productie incarcate pentru {SCOPE_LABEL[scope]}.
        </div>
      )}

      {!loading && grouped.size > 0 && (
        <div style={{ maxHeight: 520, overflowY: "auto" }}>
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={styles.th}>Cod</th>
                <th style={styles.th}>Denumire</th>
                <th style={{ ...styles.th, textAlign: "right" }}>Pret productie</th>
              </tr>
            </thead>
            <tbody>
              {Array.from(grouped.entries()).map(([grp, items]) => (
                <ScopeGroup key={grp} label={grp} items={items} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}


function ScopeGroup({ label, items }: { label: string; items: PPRow[] }) {
  return (
    <>
      <tr>
        <td colSpan={3} style={styles.groupRow}>
          {label} <span style={{ color: "var(--muted)", fontWeight: 400 }}>({items.length})</span>
        </td>
      </tr>
      {items.map((it) => (
        <tr key={it.productId}>
          <td style={styles.td}>{it.productCode}</td>
          <td style={styles.td}>{it.productName}</td>
          <td style={{ ...styles.td, textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
            {Number(it.price).toLocaleString("ro-RO", {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2,
            })}
          </td>
        </tr>
      ))}
    </>
  );
}


const styles: Record<string, React.CSSProperties> = {
  page: { display: "flex", flexDirection: "column", gap: 16, maxWidth: 1100 },
  sectionTitle: { fontSize: 20, fontWeight: 700, color: "var(--text)" },
  sectionSubtitle: {
    fontSize: 13, color: "var(--muted)", lineHeight: 1.5, marginTop: -8,
  },
  tabs: { display: "flex", gap: 6 },
  controlsRow: { display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" },
  modeTabs: { display: "flex", gap: 4, padding: 3, background: "rgba(0,0,0,0.2)", borderRadius: 8 },
  modeTabBtn: {
    background: "transparent",
    color: "var(--muted)",
    border: "none",
    padding: "5px 14px",
    borderRadius: 6,
    fontSize: 12,
    fontWeight: 600,
    cursor: "pointer",
  },
  modeTabBtnActive: {
    background: "var(--card)",
    color: "var(--cyan)",
    boxShadow: "0 0 0 1px var(--border)",
  },
  select: {
    background: "var(--bg)",
    color: "var(--text)",
    border: "1px solid var(--border)",
    padding: "5px 10px",
    borderRadius: 6,
    fontSize: 13,
  },
  heatmapCard: {
    background: "var(--card)",
    border: "1px solid var(--border)",
    borderRadius: 10,
    padding: 12,
    display: "flex",
    flexDirection: "column",
    gap: 8,
    overflow: "auto",
  },
  tabBtn: {
    background: "transparent",
    color: "var(--text)",
    border: "1px solid var(--border)",
    padding: "8px 18px",
    borderRadius: 8,
    fontSize: 13,
    fontWeight: 600,
    cursor: "pointer",
  },
  tabBtnActive: {
    background: "linear-gradient(135deg, #22d3ee, #06b6d4)",
    color: "#0a0e17",
    border: "none",
  },
  summaryGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
    gap: 12,
  },
  summaryCard: {
    background: "var(--card)",
    border: "1px solid var(--border)",
    borderRadius: 10,
    padding: 14,
    display: "flex",
    flexDirection: "column",
    gap: 4,
  },
  summaryCardActive: {
    borderColor: "var(--cyan)",
    boxShadow: "0 0 0 1px var(--cyan)",
  },
  summaryTitle: { fontSize: 12, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.06em", fontWeight: 600 },
  summaryValue: { fontSize: 24, fontWeight: 800, color: "var(--text)" },
  summaryMeta: { fontSize: 11, color: "var(--muted)" },
  card: {
    background: "var(--card)",
    border: "1px solid var(--border)",
    borderRadius: 10,
    padding: 18,
    display: "flex",
    flexDirection: "column",
    gap: 12,
  },
  cardTitle: { fontSize: 14, fontWeight: 700, color: "var(--text)" },
  fileDrop: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    padding: "26px 20px",
    border: "2px dashed var(--border)",
    borderRadius: 10,
    cursor: "pointer",
    background: "rgba(34,211,238,0.03)",
    minHeight: 110,
  },
  fileName: {
    fontSize: 14, fontWeight: 600, color: "var(--cyan)",
    wordBreak: "break-all", textAlign: "center",
  },
  fileSize: { fontSize: 12, color: "var(--muted)", marginTop: 4 },
  actions: { display: "flex", gap: 10 },
  primaryBtn: {
    background: "linear-gradient(135deg, #22d3ee, #06b6d4)",
    color: "#0a0e17",
    border: "none",
    padding: "10px 24px",
    borderRadius: 8,
    fontSize: 14,
    fontWeight: 700,
    cursor: "pointer",
  },
  secondaryBtn: {
    background: "transparent",
    color: "var(--text)",
    border: "1px solid var(--border)",
    padding: "10px 20px",
    borderRadius: 8,
    fontSize: 13,
    cursor: "pointer",
  },
  dangerBtn: {
    background: "transparent",
    color: "var(--red)",
    border: "1px solid var(--red)",
    padding: "6px 14px",
    borderRadius: 6,
    fontSize: 12,
    cursor: "pointer",
  },
  errorBox: {
    background: "rgba(239,68,68,0.1)",
    border: "1px solid var(--red)",
    color: "var(--red)",
    padding: 12,
    borderRadius: 8,
    fontSize: 13,
  },
  resultBox: {
    background: "rgba(0,0,0,0.15)",
    border: "1px solid var(--border)",
    borderRadius: 10,
    padding: 14,
    display: "flex",
    flexDirection: "column",
    gap: 14,
  },
  resultTitle: { fontSize: 14, fontWeight: 700, color: "var(--green)" },
  subSection: { display: "flex", flexDirection: "column", gap: 8 },
  subTitle: {
    fontSize: 11, textTransform: "uppercase", letterSpacing: "0.06em",
    color: "var(--muted)", fontWeight: 600,
  },
  kpiGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))",
    gap: 10,
  },
  kpi: {
    background: "rgba(0,0,0,0.18)",
    border: "1px solid var(--border)",
    borderRadius: 8,
    padding: "8px 10px",
    minHeight: 54,
  },
  kpiLabel: {
    fontSize: 10, color: "var(--muted)", textTransform: "uppercase",
    letterSpacing: "0.04em", marginBottom: 2,
  },
  kpiValue: { fontSize: 18, fontWeight: 800, lineHeight: 1.15 },
  unmatchedList: { display: "flex", flexWrap: "wrap", gap: 6 },
  codeBadge: {
    background: "rgba(251,146,60,0.12)",
    color: "var(--orange)",
    padding: "3px 10px",
    borderRadius: 12,
    fontSize: 11,
    fontFamily: "monospace",
  },
  tableHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 10,
    flexWrap: "wrap",
  },
  searchInput: {
    background: "var(--bg)",
    color: "var(--text)",
    border: "1px solid var(--border)",
    padding: "6px 10px",
    borderRadius: 6,
    fontSize: 13,
    minWidth: 240,
  },
  table: {
    width: "100%",
    borderCollapse: "collapse",
    fontSize: 12,
  },
  th: {
    position: "sticky",
    top: 0,
    background: "var(--card)",
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
    padding: "6px 10px",
    color: "var(--text)",
  },
  groupRow: {
    background: "rgba(34,211,238,0.06)",
    color: "var(--cyan)",
    padding: "6px 10px",
    fontWeight: 700,
    fontSize: 12,
    borderBottom: "1px solid var(--border)",
  },
  muted: { color: "var(--muted)", fontSize: 13 },
};
