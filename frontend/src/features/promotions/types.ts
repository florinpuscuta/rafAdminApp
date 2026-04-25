export type PromoScope = "adp" | "sika";
export type PromoStatus = "draft" | "active" | "archived";
export type PromoDiscountType = "pct" | "override_price" | "fixed_per_unit";
export type PromoTargetKind = "product" | "category" | "tm" | "private_label" | "all";
export type BaselineKind = "yoy" | "mom";

export interface PromotionTargetIn {
  kind: PromoTargetKind;
  key: string;
}

export interface PromotionTargetOut extends PromotionTargetIn {
  id: string;
}

export interface PromotionIn {
  scope: PromoScope;
  name: string;
  status: PromoStatus;
  discountType: PromoDiscountType;
  value: string;
  validFrom: string;  // YYYY-MM-DD
  validTo: string;
  clientFilter: string[] | null;
  notes: string | null;
  targets: PromotionTargetIn[];
}

export interface PromotionOut {
  id: string;
  scope: PromoScope;
  name: string;
  status: PromoStatus;
  discountType: PromoDiscountType;
  value: string;
  validFrom: string;
  validTo: string;
  clientFilter: string[] | null;
  notes: string | null;
  targets: PromotionTargetOut[];
  createdAt: string;
  updatedAt: string;
}

export interface PromotionListResponse {
  items: PromotionOut[];
}

export interface PromoSimGroupRow {
  label: string;
  kind: string;
  key: string;
  baselineRevenue: string;
  baselineCost: string;
  baselineProfit: string;
  baselineMarginPct: string;
  scenarioRevenue: string;
  scenarioCost: string;
  scenarioProfit: string;
  scenarioMarginPct: string;
  deltaRevenue: string;
  deltaProfit: string;
  deltaMarginPp: string;
  productsAffected: number;
}

export interface ProductSearchItem {
  code: string;
  name: string;
  categoryCode: string | null;
  categoryLabel: string | null;
}

export interface ProductSearchResponse {
  items: ProductSearchItem[];
}

export interface GroupOption {
  kind: string;
  key: string;
  label: string;
}

export interface GroupsResponse {
  items: GroupOption[];
}


export interface PromoSimResponse {
  promotionId: string;
  baselineKind: BaselineKind;
  baselineLabel: string;
  promoLabel: string;
  productsInScope: number;
  baselineRevenue: string;
  baselineCost: string;
  baselineProfit: string;
  baselineMarginPct: string;
  scenarioRevenue: string;
  scenarioCost: string;
  scenarioProfit: string;
  scenarioMarginPct: string;
  deltaRevenue: string;
  deltaProfit: string;
  deltaMarginPp: string;
  groups: PromoSimGroupRow[];
}
