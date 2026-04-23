/**
 * Tipuri pentru "Marca Privată" — vânzări private label pe canal KA, breakdown
 * lunar (Y1 vs Y2) + listă rețele (chain) × categorie (MU/EPS/UMEDE).
 * Oglindește contractul /api/marca-privata.
 *
 * Shape-ul backend e camelCase (strings pentru Decimal — aceeași convenție
 * ca /api/analiza-pe-luni și /api/vz-la-zi, pentru a evita pierderi de
 * precizie pe valori bănești).
 */

export type MarcaPrivataScope = "adp";

export interface MPYearTotals {
  salesY1: string;
  salesY2: string;
  diff: string;
  pct: string | null;
}

export interface MPMonthCell {
  /** 1..12 */
  month: number;
  /** Numele lunii ("Ianuarie", ...). */
  monthName: string;
  salesY1: string;
  salesY2: string;
  diff: string;
  pct: string | null;
}

/** Categorie (MU / EPS / UMEDE) în interiorul unei rețele. */
export interface MPCategoryCell {
  code: string;
  label: string;
  salesY1: string;
  salesY2: string;
  diff: string;
  pct: string | null;
}

/** Rețea canonică (Dedeman / Altex / Leroy Merlin / Hornbach / Alte). */
export interface MPChainRow {
  chain: string;
  salesY1: string;
  salesY2: string;
  diff: string;
  pct: string | null;
  /** Mereu 3 elemente, în ordinea MU / EPS / UMEDE. */
  categories: MPCategoryCell[];
}

export interface MarcaPrivataResponse {
  scope: MarcaPrivataScope;
  yearCurr: number;
  yearPrev: number;
  /** 12 celule, ordonate Ian..Dec. */
  months: MPMonthCell[];
  /** Rețele KA care cumpără private label, ordonate după un ordin canonic. */
  chains: MPChainRow[];
  grandTotals: MPYearTotals;
  lastUpdate: string | null;
}
