/**
 * Tipuri pentru /prices/propuneri — Propuneri Listare KA.
 *
 * Pentru fiecare KA, produsele vândute la alte rețele KA dar NU la acesta,
 * cu prețul minim dintre celelalte rețele ca referință de listare.
 */

export interface PropunereRow {
  category: string;
  description: string;
  totalSales: string;
  totalQty: string;
  /** Prețul minim găsit la celelalte KA. */
  minPrice: string;
  /** KA-ul la care s-a găsit prețul minim. */
  minPriceKa: string;
  /** Prețuri la celelalte KA (exclusiv cel curent). */
  prices: Record<string, string>;
  /** Număr de KA (altele) unde produsul e listat. */
  numKas: number;
}

export interface PropuneriResponse {
  year: number | null;
  kaClients: string[];
  /** Key = KA pentru care facem propuneri. Valoare = listă produse nelistate. */
  suggestions: Record<string, PropunereRow[]>;
}

export interface PropuneriFilters {
  year?: number;
  months?: number[];
  company?: string; // "adeplast" | "sika" | "sikadp"
}
