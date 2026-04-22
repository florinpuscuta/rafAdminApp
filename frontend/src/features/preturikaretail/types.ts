/**
 * Tipuri pentru /prices/ka-retail — Top produse KA vs Retail.
 *
 * Distinct de /prices/ka-vs-tt (KaVsTtPage) — aici tratăm STRICT channel='RETAIL'
 * ca retail, nu "orice non-KA". Util când tenantul are și channel='TT' separat
 * și vrem doar comparația KA-Retail.
 */

export interface KaRetailRow {
  description: string;
  productCode: string | null;
  category: string | null;
  kaSales: string;
  kaQty: string;
  kaPrice: string | null;
  retailSales: string;
  retailQty: string;
  retailPrice: string | null;
  /** (kaPrice - retailPrice) / retailPrice * 100. */
  diffPct: string | null;
  totalSales: string;
}

export interface KaRetailResponse {
  rows: KaRetailRow[];
}

export interface KaRetailFilters {
  year?: number;
  months?: number[];
  category?: string;
  limit?: number;
}
