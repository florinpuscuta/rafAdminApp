/**
 * Tipuri pentru "Raport Lunar Management" — consolidat KA pentru (year, month).
 *
 * Sumele sunt string-uri (Decimal) — aceeași convenție ca vz-la-zi /
 * analiza-pe-luni pentru precizie.
 */

export interface RLKpis {
  totalAmount: string;
  totalRows: number;
  distinctStores: number;
  distinctAgents: number;
  compareAmount: string | null;
  compareRows: number | null;
  pctYoy: string | null;
}

export interface RLTopClient {
  storeId: string | null;
  storeName: string;
  chain: string | null;
  totalAmount: string;
}

export interface RLTopAgent {
  agentId: string | null;
  agentName: string;
  totalAmount: string;
}

export interface RLChainRow {
  chain: string;
  storeCount: number;
  totalAmount: string;
}

export interface RaportLunarResponse {
  year: number;
  month: number;
  hasData: boolean;
  kpis: RLKpis;
  topClients: RLTopClient[];
  topAgents: RLTopAgent[];
  chains: RLChainRow[];
}
