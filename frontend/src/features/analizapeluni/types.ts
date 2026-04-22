/**
 * Tipuri pentru "Analiza pe luni" — vanzari comparative pe 12 luni (Y1 vs Y2),
 * cu defalcare per agent. Oglindeste contractul /api/analiza-pe-luni.
 *
 * Shape-ul backend e camelCase (strings pentru Decimal, pentru a evita pierderi
 * de precizie — aceeasi conventie ca /api/vz-la-zi).
 */

export type AnalizaScope = "adp" | "sika" | "sikadp";

/** O celula lunara (Ian..Dec) — vanzari pe cei doi ani comparati. */
export interface MonthCell {
  /** 1..12 */
  month: number;
  /** Numele lunii, RO ("Ianuarie", "Februarie", ...). */
  monthName: string;
  /** Vanzari an referinta (Y1 = yearPrev). */
  salesY1: string;
  /** Vanzari an curent (Y2 = yearCurr). */
  salesY2: string;
  /** Diferenta Y2 - Y1 (poate fi negativa). */
  diff: string;
  /** Procentul Y2/Y1 * 100 (poate fi negativ; 0 cand Y1 = 0). */
  pct: string;
}

/** Totaluri pe an pentru un rand (agent sau sectiune). */
export interface YearTotals {
  salesY1: string;
  salesY2: string;
  diff: string;
  pct: string;
}

/** Un rand de agent — 12 celule lunare + totaluri pe an. */
export interface AgentRow {
  agentId: string | null;
  agentName: string;
  months: MonthCell[];
  totals: YearTotals;
}

/** Un rand "total pe luna" = sumarul tuturor agentilor pe acea luna. */
export interface MonthTotalRow {
  month: number;
  monthName: string;
  salesY1: string;
  salesY2: string;
  diff: string;
  pct: string;
}

/** Raspunsul complet al endpoint-ului /api/analiza-pe-luni. */
export interface AnalizaResponse {
  scope: AnalizaScope;
  yearCurr: number;
  yearPrev: number;
  /** Agenti, fiecare cu 12 celule. */
  agents: AgentRow[];
  /** Totaluri pe coloana (per luna, toti agentii la un loc). */
  monthTotals: MonthTotalRow[];
  /** Totaluri pe ansamblu (intregul an, toti agentii). */
  grandTotals: YearTotals;
  /** Ultima actualizare a datelor (ISO), optional. */
  lastUpdate: string | null;
}
