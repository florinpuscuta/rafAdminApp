/**
 * Tipuri pentru "Analiza Magazine — Dashboard pe magazin".
 * Selectoare: client KA → magazin canonic → fereastra (3/6/9/12 luni).
 * Răspunsul include KPI curent, YoY, MoM, serie lunară, breakdown pe categorie
 * și split brand vs marcă privată.
 *
 * Decimal-urile vin string din backend (Pydantic Decimal serializat ca string).
 */

export type AMDScope = "adp" | "sika";

export interface AMDClientsResponse {
  clients: string[];
}

export interface AMDStoreOption {
  storeId: string;
  name: string;
}

export interface AMDStoresResponse {
  client: string;
  stores: AMDStoreOption[];
}

export interface AMDMetrics {
  sales: string;
  quantity: string;
  skuCount: number;
}

export interface AMDMonthSeries {
  year: number;
  month: number;
  salesCurr: string;
  salesPrevYear: string;
  skuCurr: number;
  skuPrevYear: number;
}

export interface AMDCategoryRow {
  code: string;
  label: string;
  curr: AMDMetrics;
  yoy: AMDMetrics;
}

export interface AMDBrandSplit {
  brand: AMDMetrics;
  privateLabel: AMDMetrics;
  brandYoy: AMDMetrics;
  privateLabelYoy: AMDMetrics;
}

export interface AMDPair {
  year: number;
  month: number;
}

export interface AMDDashboardResponse {
  scope: AMDScope;
  storeId: string;
  storeName: string;
  monthsWindow: number;
  windowCurr: AMDPair[];
  windowYoy: AMDPair[];
  windowPrev: AMDPair[];
  kpiCurr: AMDMetrics;
  kpiYoy: AMDMetrics;
  kpiPrev: AMDMetrics;
  monthly: AMDMonthSeries[];
  categories: AMDCategoryRow[];
  brandSplit: AMDBrandSplit;
}
