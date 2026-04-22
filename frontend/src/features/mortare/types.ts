/**
 * Tipuri pentru "Mortare Silozuri (Vrac)" — vânzări mortare vrac (categoria
 * canonică VARSACI), breakdown lunar (Y1 vs Y2) + listă produse.
 *
 * Shape backend camelCase; valorile bănești/cantitative sunt strings
 * (Decimal) pentru a evita pierderi de precizie — aceeași convenție ca în
 * celelalte module de vânzări.
 */

export type MortareScope = "adp";

export interface MortareYearTotals {
  salesY1: string;
  salesY2: string;
  qtyY1: string;
  qtyY2: string;
  diff: string;
  pct: string | null;
}

export interface MortareMonthCell {
  month: number;       // 1..12
  monthName: string;
  salesY1: string;
  salesY2: string;
  qtyY1: string;
  qtyY2: string;
  diff: string;
  pct: string | null;
}

export interface MortareProductRow {
  productId: string | null;
  productCode: string | null;
  productName: string;
  salesY1: string;
  salesY2: string;
  qtyY1: string;
  qtyY2: string;
  diff: string;
  pct: string | null;
}

export interface MortareResponse {
  scope: MortareScope;
  yearCurr: number;
  yearPrev: number;
  months: MortareMonthCell[];     // 12 items
  products: MortareProductRow[];
  grandTotals: MortareYearTotals;
  lastUpdate: string | null;
}
