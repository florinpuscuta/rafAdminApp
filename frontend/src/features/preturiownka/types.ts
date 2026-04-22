/**
 * Tipuri pentru /prices/own — Prețuri cross-KA (brand propriu).
 *
 * Per produs vândut la cel puțin 2 KA, afișează prețul mediu la fiecare rețea
 * + min/max/spread%. Util pentru a identifica produse cu preț discrepant între
 * magazine — target pentru analiză comercială.
 *
 * Numerele vin ca string din backend (JSON Decimal) pentru a evita pierderi
 * de precizie; conversia spre number se face doar la afișare/sort.
 */

/** Prețul pentru un produs la un KA specific. */
export interface CrossKaPrice {
  /** Preț mediu = sales/qty. Null dacă qty=0. */
  price: string | null;
  /** Cantitate totală vândută la acest KA (unitatea raw_sales.quantity). */
  qty: string;
  /** Vânzări totale (RON) la acest KA în perioada filtrată. */
  sales: string;
}

/** Un rând = un produs cu prețuri la toate KA unde a fost vândut. */
export interface CrossKaRow {
  description: string;
  productCode: string | null;
  category: string | null;
  /** Key = KA client key (DEDEMAN, LEROY, HORNBACH, ALTEX, BRICO). */
  prices: Record<string, CrossKaPrice>;
  minPrice: string | null;
  maxPrice: string | null;
  /** Spread procentual = (max-min)/min * 100. */
  spreadPct: string | null;
  /** Câte KA vând acest produs (minim 2 pentru a apărea în listă). */
  nStores: number;
}

export interface CrossKaResponse {
  kaClients: string[];
  rows: CrossKaRow[];
}

export interface CrossKaFilters {
  year?: number;
  /** Luni selectate 1..12, trimise ca CSV la backend. */
  months?: number[];
  category?: string;
}
