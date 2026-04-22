export interface OverviewKPIs {
  totalRows: number;
  totalAmount: string;
  distinctMappedStores: number;
  distinctMappedAgents: number;
  unmappedStoreRows: number;
  unmappedAgentRows: number;
}

export interface TopStoreRow {
  storeId: string | null;
  storeName: string;
  chain: string | null;
  totalAmount: string;
  rowCount: number;
}

export interface TopAgentRow {
  agentId: string | null;
  agentName: string;
  totalAmount: string;
  rowCount: number;
}

export interface MonthTotalRow {
  month: number;
  totalAmount: string;
  rowCount: number;
}

export interface TopChainRow {
  chain: string;
  totalAmount: string;
  rowCount: number;
  storeCount: number;
}

export interface TopProductRow {
  productId: string | null;
  productCode: string;
  productName: string;
  category: string | null;
  totalAmount: string;
  totalQuantity: string;
  rowCount: number;
}

export interface ScopeInfo {
  storeId: string | null;
  storeName: string | null;
  agentId: string | null;
  agentName: string | null;
  productId: string | null;
  productCode: string | null;
  productName: string | null;
}

export interface DashboardOverview {
  year: number | null;
  month: number | null;
  chain: string | null;
  category: string | null;
  scope: ScopeInfo | null;
  availableYears: number[];
  kpis: OverviewKPIs;
  topStores: TopStoreRow[];
  topAgents: TopAgentRow[];
  topChains: TopChainRow[];
  topProducts: TopProductRow[];
  monthlyTotals: MonthTotalRow[];
  compareYear: number | null;
  compareKpis: OverviewKPIs | null;
  monthlyTotalsCompare: MonthTotalRow[];
}
