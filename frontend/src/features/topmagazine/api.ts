import { apiFetch } from "../../shared/api";

export interface StoreRankRow {
  storeId: string | null;
  storeName: string;
  chain: string | null;
  totalAmount: string;
  rowCount: number;
  distinctProducts: number;
  rankValue: number;
  rankSku: number;
  scoreCombined: number;
}

export interface TopStoresByChainResponse {
  chain: string;
  year: number | null;
  availableChains: string[];
  rows: StoreRankRow[];
}

export function getTopStoresByChain(
  chain: string | null,
  scope?: "adp" | "sika" | "sikadp" | null,
  year?: number | null,
): Promise<TopStoresByChainResponse> {
  const params = new URLSearchParams();
  if (chain) params.set("chain", chain);
  if (year != null) params.set("year", String(year));
  if (scope) params.set("scope", scope);
  const s = params.toString();
  return apiFetch<TopStoresByChainResponse>(
    `/api/dashboard/top-stores-by-chain${s ? "?" + s : ""}`,
  );
}
