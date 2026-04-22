export interface VzKpis {
  prevSales: string;
  currSales: string;
  nelivrate: string;
  nefacturate: string;
  ordersTotal: string;
  exercitiu: string;
  gap: string;
}

export interface VzStoreRow {
  storeId: string | null;
  storeName: string;
  prevSales: string;
  currSales: string;
  nelivrate: string;
  nefacturate: string;
  ordersTotal: string;
  exercitiu: string;
}

export interface VzAgentRow {
  agentId: string | null;
  agentName: string;
  storesCount: number;
  prevSales: string;
  currSales: string;
  nelivrate: string;
  nefacturate: string;
  ordersTotal: string;
  exercitiu: string;
  stores: VzStoreRow[];
}

export interface VzScopeBlock {
  kpis: VzKpis;
  reportDate: string | null;
  indProcessed: number | null;
  indMissing: number | null;
  indProcessedAmount: string | null;
  indMissingAmount: string | null;
}

export interface VzCombinedBlock {
  kpis: VzKpis;
  agents: VzAgentRow[];
}

export interface VzResponse {
  scope: "adp" | "sika" | "sikadp";
  yearCurr: number;
  yearPrev: number;
  month: number;
  monthName: string;
  lastUpdate: string | null;
  reportDate: string | null;
  kpis: VzKpis | null;
  agents: VzAgentRow[];
  indProcessed: number | null;
  indMissing: number | null;
  indProcessedAmount: string | null;
  indMissingAmount: string | null;
  combined: VzCombinedBlock | null;
  adeplast: VzScopeBlock | null;
  sika: VzScopeBlock | null;
}
