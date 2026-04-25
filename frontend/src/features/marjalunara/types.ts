export type MLScope = "adp" | "sika" | "sikadp";

export interface MLGroupRow {
  label: string;
  kind: "category" | "tm" | "private_label";
  key: string;
  revenue: string;
  quantity: string;
  costTotal: string;
  profit: string;
  marginPct: string;
  discountAllocated: string;
  profitNet: string;
  marginPctNet: string;
}

export interface MLMonthRow {
  year: number;
  month: number;
  revenuePeriod: string;
  revenueCovered: string;
  costTotal: string;
  profitTotal: string;
  marginPct: string;
  discountTotal: string;
  discountAllocatedTotal: string;
  profitNetTotal: string;
  marginPctNet: string;
  hasMonthlySnapshot: boolean;
  fallbackRevenuePct: string;
  productsWithCost: number;
  productsMissingCost: number;
  groups: MLGroupRow[];
}

export interface MarjaLunaraResponse {
  scope: MLScope;
  fromYear: number;
  fromMonth: number;
  toYear: number;
  toMonth: number;
  months: MLMonthRow[];
}
