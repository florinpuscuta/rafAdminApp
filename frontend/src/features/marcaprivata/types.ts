/**
 * Tipuri pentru "Marca Privată" — vânzări private label pe canal KA, breakdown
 * lunar (Y1 vs Y2) + listă clienți. Oglindește contractul /api/marca-privata.
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

export interface MPClientRow {
  client: string;
  salesY1: string;
  salesY2: string;
  qtyY1: string;
  qtyY2: string;
  diff: string;
  pct: string | null;
}

export interface MarcaPrivataResponse {
  scope: MarcaPrivataScope;
  yearCurr: number;
  yearPrev: number;
  /** 12 celule, ordonate Ian..Dec. */
  months: MPMonthCell[];
  /** Clienți KA care cumpără private label, sortat desc. după Y1. */
  clients: MPClientRow[];
  grandTotals: MPYearTotals;
  lastUpdate: string | null;
}
