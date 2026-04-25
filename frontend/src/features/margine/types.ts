export type MargineScope = "adp" | "sika" | "sikadp";

export interface MargineProductRow {
  productId: string;
  productCode: string;
  productName: string;
  revenue: string;
  quantity: string;
  avgSale: string;
  cost: string;
  profit: string;
  marginPct: string;
}

export interface MargineGroupRow {
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
  products: MargineProductRow[];
}

export interface MargineMissingRow {
  productId: string;
  productCode: string;
  productName: string;
  revenue: string;
  quantity: string;
}

export interface MargineResponse {
  scope: MargineScope;
  fromYear: number;
  fromMonth: number;
  toYear: number;
  toMonth: number;
  revenuePeriod: string;
  revenueCovered: string;
  costTotal: string;
  profitTotal: string;
  marginPct: string;
  coveragePct: string;
  discountTotal: string;
  discountAllocatedTotal: string;
  profitNetTotal: string;
  marginPctNet: string;
  productsWithCost: number;
  productsMissingCost: number;
  groups: MargineGroupRow[];
  missingCost: MargineMissingRow[];
}
