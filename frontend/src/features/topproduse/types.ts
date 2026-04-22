/**
 * Tipuri pentru "Top Produse" — top-N produse KA dintr-o grupa, sortat
 * dupa vanzarile anului curent. Oglindeste contractul /api/top-produse.
 *
 * Decimale vin ca string-uri (convention comuna /api/vz-la-zi etc.).
 */

export type TopProduseScope = "adp" | "sika" | "sikadp";

export interface TopProduseMonthCell {
  month: number;        // 1..12
  monthName: string;
  salesY1: string;
  salesY2: string;
}

export interface TopProduseProductRow {
  rank: number;
  productId: string;
  productCode: string;
  productName: string;
  salesY1: string;
  salesY2: string;
  qtyY1: string;
  qtyY2: string;
  diff: string;
  pct: string | null;
  priceY1: string | null;
  priceY2: string | null;
  /** 12 celule lunare (Ian..Dec) — populat pentru toate produsele din top. */
  monthly: TopProduseMonthCell[];
}

export interface TopProduseTotals {
  salesY1: string;
  salesY2: string;
  qtyY1: string;
  qtyY2: string;
  diff: string;
  pct: string | null;
}

export interface TopProduseCategoryInfo {
  id: string;
  code: string;
  label: string;
}

export interface TopProduseResponse {
  scope: TopProduseScope;
  yearCurr: number;
  yearPrev: number;
  group: string;
  groupLabel: string;
  limit: number;
  lastUpdate: string | null;
  products: TopProduseProductRow[];
  totals: TopProduseTotals;
  availableCategories: TopProduseCategoryInfo[];
  ytdMonths: number[];
}
