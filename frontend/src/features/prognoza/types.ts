/**
 * Tipuri pentru "Prognoză Vânzări" — forecast KA pe orizont 1..12 luni,
 * cu 3 scope-uri (adp|sika|sikadp). Oglindeste contractul /api/prognoza.
 *
 * Shape-ul backend e camelCase (strings pentru Decimal, pentru a evita pierderi
 * de precizie — aceeasi conventie ca /api/analiza-pe-luni).
 */

export type PrognozaScope = "adp" | "sika" | "sikadp";

/** Un punct din istoric (lună completă cu vânzări). */
export interface HistoryPoint {
  year: number;
  /** 1..12 */
  month: number;
  /** "Ianuarie"..."Decembrie" */
  monthName: string;
  /** "Ian 2025" — pentru axa chart. */
  label: string;
  /** Vânzări reale (RON). */
  sales: string;
}

/** Un punct din viitor (predicție). */
export interface ForecastPoint {
  year: number;
  month: number;
  monthName: string;
  label: string;
  /** Valoarea prognozată (RON). */
  forecastSales: string;
  /** Media mobilă ultimele 3 luni — componenta de baza a forecast-ului. */
  movingAvg: string;
  /** Factor sezonal (raport vs same-month PY), null daca date insuficiente. */
  seasonalFactor: string | null;
  /** Trend linear regression 12 luni, % per luna. Null daca date insuficiente. */
  trendPct: string | null;
}

/** Un rând per agent: total istoric 12 luni + forecast pe orizont. */
export interface AgentRow {
  agentId: string | null;
  agentName: string;
  historyTotal: string;
  forecastTotal: string;
  /** Lungime = horizon_months, în aceeași ordine ca `forecast`. */
  forecastMonths: string[];
}

/** Răspunsul complet al endpoint-ului /api/prognoza. */
export interface PrognozaResponse {
  scope: PrognozaScope;
  horizonMonths: number;
  /** "moving_avg_3m" | "moving_avg_3m_with_seasonal" — pt transparență în UI. */
  method: string;
  lastUpdate: string | null;
  /** Ex. "Aprilie 2026". */
  lastCompleteMonth: string | null;
  /** Ultimele 12 luni cu vânzări reale, cronologic. */
  history: HistoryPoint[];
  /** `horizonMonths` luni viitoare, cronologic. */
  forecast: ForecastPoint[];
  /** Agenți sortați — mapati primii (descrescător după historyTotal). */
  agents: AgentRow[];
}
