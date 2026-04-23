import { useCallback, useEffect, useState, type CSSProperties } from "react";

export const MONTHS_RO: string[] = [
  "Ianuarie", "Februarie", "Martie", "Aprilie", "Mai", "Iunie",
  "Iulie", "August", "Septembrie", "Octombrie", "Noiembrie", "Decembrie",
];

export function defaultYearMonth(): { year: number; month: number } {
  const now = new Date();
  return { year: now.getFullYear(), month: now.getMonth() + 1 };
}

// ─────────── Shared year/month selection across all Evaluare pages ───────────

const EVALUARE_YM_KEY = "evaluare.ym";
const EVALUARE_YM_EVENT = "evaluare-ym-change";

type YM = { year: number; month: number };

function readEvaluareYM(): YM {
  try {
    const raw = typeof window !== "undefined" ? localStorage.getItem(EVALUARE_YM_KEY) : null;
    if (raw) {
      const parsed = JSON.parse(raw);
      if (
        Number.isInteger(parsed?.year) &&
        Number.isInteger(parsed?.month) &&
        parsed.month >= 1 && parsed.month <= 12
      ) {
        return { year: parsed.year, month: parsed.month };
      }
    }
  } catch { /* fallthrough */ }
  return defaultYearMonth();
}

export function useEvaluareYearMonth(): {
  year: number;
  month: number;
  setYearMonth: (y: number, m: number) => void;
} {
  const [ym, setYM] = useState<YM>(readEvaluareYM);

  useEffect(() => {
    const onCustom = (e: Event) => {
      const detail = (e as CustomEvent<YM>).detail;
      if (detail) setYM(detail);
    };
    const onStorage = (e: StorageEvent) => {
      if (e.key === EVALUARE_YM_KEY) setYM(readEvaluareYM());
    };
    window.addEventListener(EVALUARE_YM_EVENT, onCustom);
    window.addEventListener("storage", onStorage);
    return () => {
      window.removeEventListener(EVALUARE_YM_EVENT, onCustom);
      window.removeEventListener("storage", onStorage);
    };
  }, []);

  const setYearMonth = useCallback((y: number, m: number) => {
    const next: YM = { year: y, month: m };
    try { localStorage.setItem(EVALUARE_YM_KEY, JSON.stringify(next)); } catch { /* ignore */ }
    window.dispatchEvent(new CustomEvent<YM>(EVALUARE_YM_EVENT, { detail: next }));
    setYM(next);
  }, []);

  return { year: ym.year, month: ym.month, setYearMonth };
}

export function toNum(v: string | number | null | undefined): number {
  if (v == null) return 0;
  if (typeof v === "number") return v;
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}

export function fmtRo(n: number, maxFrac = 0): string {
  return new Intl.NumberFormat("ro-RO", {
    maximumFractionDigits: maxFrac,
    minimumFractionDigits: maxFrac,
  }).format(n);
}

export function MonthYearPicker({
  year, month, onChange,
}: {
  year: number;
  month: number;
  onChange: (y: number, m: number) => void;
}) {
  const years: number[] = [];
  const curr = new Date().getFullYear();
  for (let y = curr - 3; y <= curr + 1; y++) years.push(y);
  return (
    <div style={pickerStyles.wrap}>
      <label style={pickerStyles.label}>Luna</label>
      <select
        data-wide="true"
        value={month}
        onChange={(e) => onChange(year, Number(e.target.value))}
        style={pickerStyles.select}
      >
        {MONTHS_RO.map((name, idx) => (
          <option key={idx + 1} value={idx + 1}>{name}</option>
        ))}
      </select>
      <label style={pickerStyles.label}>An</label>
      <select
        data-wide="true"
        value={year}
        onChange={(e) => onChange(Number(e.target.value), month)}
        style={pickerStyles.selectYear}
      >
        {years.map((y) => <option key={y} value={y}>{y}</option>)}
      </select>
    </div>
  );
}

const pickerStyles: Record<string, CSSProperties> = {
  wrap: {
    display: "inline-flex",
    alignItems: "center",
    gap: 8,
    padding: "6px 10px",
    background: "var(--bg-panel)",
    border: "1px solid var(--border)",
    borderRadius: 6,
  },
  label: { fontSize: 11, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.05em" },
  select: {
    minWidth: 140,
    padding: "5px 8px",
    fontSize: 13,
    background: "var(--bg)",
    color: "var(--text)",
    border: "1px solid var(--border)",
    borderRadius: 4,
  },
  selectYear: {
    minWidth: 90,
    padding: "5px 8px",
    fontSize: 13,
    background: "var(--bg)",
    color: "var(--text)",
    border: "1px solid var(--border)",
    borderRadius: 4,
  },
};
