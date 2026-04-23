/**
 * Tipuri pentru /prices/pret3net — Preț 3 Net Comp KA.
 *
 * Per produs, per client KA: preț mediu de facturare (sales/qty).
 * Discount-urile contractuale sunt configurate per KA și aplicate CLIENT-SIDE
 * (nu sunt persistate în backend pentru MVP — stocate în localStorage).
 *
 * Utilizare: `netPrice = price * product(1 - disc/100)` pentru fiecare discount
 * definit la acel KA.
 */

/** Date per client KA pentru un produs. */
export interface Pret3NetClient {
  sales: string;
  qty: string;
  price: string | null;
}

/** Un produs în pagina Pret 3 Net. */
export interface Pret3NetProduct {
  description: string;
  /** Key = KA client key. Nu toți KA apar — doar cei unde produsul s-a vândut. */
  clients: Record<string, Pret3NetClient>;
  totalSales: string;
  totalQty: string;
  isPrivateLabel?: boolean;
}

export interface Pret3NetResponse {
  year: number | null;
  kaClients: string[];
  /** Key = category_code (ex: "ADEZIVI", "EPS"). Valoare = listă produse. */
  categories: Record<string, Pret3NetProduct[]>;
}

export interface Pret3NetFilters {
  year?: number;
  months?: number[];
  company?: string; // "adeplast" | "sika" | "sikadp"
}

/** Un discount contractual, aplicat compus. */
export interface Discount {
  name: string;
  /** Procent 0..100. Aplicat ca factor (1 - pct/100). */
  pct: number;
}

/** Configurația discount-urilor per KA, persistată în localStorage. */
export type DiscountConfig = Record<string, Discount[]>;
