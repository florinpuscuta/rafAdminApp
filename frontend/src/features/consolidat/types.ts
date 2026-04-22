export interface ConsolidatTotals {
  salesY1: string;
  salesY2: string;
  diff: string;
  pct: number;
}

export interface ConsolidatAgentRow {
  agentId: string | null;
  name: string;
  storesCount: number;
  salesY1: string;
  salesY2: string;
  diff: string;
  pct: number;
}

export interface ConsolidatStoreRow {
  storeId: string | null;
  name: string;
  chain: string | null;
  city: string | null;
  salesY1: string;
  salesY2: string;
  diff: string;
  pct: number;
}

export interface ConsolidatAgentStoresResponse {
  agentId: string | null;
  company: "adeplast" | "sika" | "sikadp";
  y1: number;
  y2: number;
  months: number[];
  stores: ConsolidatStoreRow[];
}

export interface ConsolidatKaResponse {
  company: "adeplast" | "sika" | "sikadp";
  companyLabel: string;
  y1: number;
  y2: number;
  months: number[];
  periodLabel: string;
  includeCurrentMonth: boolean;
  totals: ConsolidatTotals;
  byAgent: ConsolidatAgentRow[];
}
