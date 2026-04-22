/**
 * Tipuri pentru "Analiza Magazin" — gap de sortimentație pentru un magazin
 * KA vs. produsele listate pe ansamblul rețelei (Dedeman/Altex/Leroy/Hornbach)
 * în ultimele 3 luni.
 *
 * Shape-ul backend e camelCase; valorile bănești/cantitățile sunt string-uri
 * (Decimal) ca să nu pierdem precizie — aceeași convenție ca restul feature-urilor.
 */

export type AMScope = "adp" | "sika";

export interface AMStoreOption {
  key: string;       // RawSale.client
  label: string;     // identic cu key deocamdată
  chain: string;     // "Dedeman" | "Altex" | "Leroy Merlin" | "Hornbach"
  agent: string | null;  // agent dominant
}

export interface AMStoresResponse {
  scope: AMScope;
  monthsWindow: number;
  stores: AMStoreOption[];
}

export interface AMGapProduct {
  productId: string;
  productCode: string;
  productName: string;
  /** Cod categorie (MU/EPS/UMEDE/...) pentru ADP sau label TM pentru Sika. */
  category: string | null;
  chainQty: string;
  chainValue: string;
  storesSellingCount: number;
}

export interface AMCategoryBreakdown {
  /** null = produse fără categorie/TM. */
  category: string | null;
  chainSkuCount: number;
  ownSkuCount: number;
  gapCount: number;
}

export interface AMResponse {
  scope: AMScope;
  store: string;
  chain: string;
  monthsWindow: number;
  chainSkuCount: number;
  ownSkuCount: number;
  gapCount: number;
  gap: AMGapProduct[];
  breakdown: AMCategoryBreakdown[];
}
