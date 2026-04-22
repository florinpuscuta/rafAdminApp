/**
 * Tipuri pentru "Grupe Produse" — defalcare per PRODUS a vanzarilor KA
 * dintr-o categorie (grupa), comparativ Y1 vs Y2.
 *
 * Shape-ul backend e camelCase (strings pentru Decimal). Oglindeste contractul
 * /api/grupe-produse.
 */

export type GrupeProduseScope = "adp" | "sika" | "sikadp";

export interface GrupeProduseProductRow {
  productId: string;
  productCode: string;
  productName: string;
  salesY1: string;
  salesY2: string;
  qtyY1: string;
  qtyY2: string;
  diff: string;
  /** Procentul Y2/Y1 * 100. `null` cand Y1 = 0. */
  pct: string | null;
  /** Pret mediu Y1 = salesY1 / qtyY1. `null` cand qty = 0. */
  priceY1: string | null;
  priceY2: string | null;
}

export interface GrupeProduseTotals {
  salesY1: string;
  salesY2: string;
  qtyY1: string;
  qtyY2: string;
  diff: string;
  pct: string | null;
}

export interface GrupeProduseCategoryInfo {
  id: string;
  code: string;
  label: string;
}

export interface GrupeProduseResponse {
  scope: GrupeProduseScope;
  yearCurr: number;
  yearPrev: number;
  /** Codul categoriei curente, ex "EPS". */
  group: string;
  /** Label-ul human-readable, ex "Polistiren Expandat". */
  groupLabel: string;
  lastUpdate: string | null;
  products: GrupeProduseProductRow[];
  totals: GrupeProduseTotals;
  /** Lista tuturor categoriilor disponibile — pentru selectorul din UI. */
  availableCategories: GrupeProduseCategoryInfo[];
}
