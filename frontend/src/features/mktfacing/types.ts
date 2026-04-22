/**
 * Tipuri Facing Tracker — oglindă a `adeplast-dashboard/services/facing_service.py`
 * cu adaptare UUID (în loc de INTEGER).
 */

export type UUID = string;

export interface Raion {
  id: UUID;
  name: string;
  sortOrder: number;
  active: boolean;
  parentId: UUID | null;
}

export interface RaionTreeNode extends Raion {
  children: RaionTreeNode[];
}

export interface Brand {
  id: UUID;
  name: string;
  color: string;
  isOwn: boolean;
  sortOrder: number;
  active: boolean;
}

export interface ConfigResponse {
  ok: boolean;
  raioane: Raion[];
  raioaneTree: RaionTreeNode[];
  brands: Brand[];
  chainBrands: Record<string, UUID[]>;
  chains: string[];
}

export interface OkResponse {
  ok: boolean;
  error?: string;
}

export interface TreeResponse {
  ok: boolean;
  tree: RaionTreeNode[];
}

export interface SaveEntry {
  storeName: string;
  raionId: UUID;
  brandId: UUID;
  luna: string;
  nrFete: number;
}

export interface SaveResponse {
  ok: boolean;
  saved: number;
}

export interface Snapshot {
  id: UUID;
  storeName: string;
  raionId: UUID;
  raionName: string;
  brandId: UUID;
  brandName: string;
  brandColor: string;
  luna: string;
  nrFete: number;
  updatedAt: string | null;
  updatedBy: string | null;
}

export interface SnapshotsResponse {
  ok: boolean;
  data: Snapshot[];
}

export interface EvolutionRow {
  luna: string;
  storeName: string;
  raionName: string;
  raionId: UUID;
  brandName: string;
  brandColor: string;
  brandId: UUID;
  nrFete: number;
}

export interface EvolutionResponse {
  ok: boolean;
  data: EvolutionRow[];
}

export interface BrandSummary {
  brandId: UUID;
  brandName: string;
  brandColor: string;
  totalFete: number;
  avgFete: number;
  prevAvgFete: number;
  deltaAvg: number;
  pct: number;
}

export interface ChainSummary {
  chain: string;
  nrMagazine: number;
  prevNrMagazine: number;
  totalFeteAll: number;
  avgFeteAll: number;
  ownPctWeighted: number;
  prevOwnPctWeighted: number;
  ownPctDelta: number;
  ownTotalFete: number;
  ownStoresCounted: number;
  brandsSummary: BrandSummary[];
  stores: Record<string, {
    storeName: string;
    raioane: Record<string, Array<{ brandName: string; brandColor: string; nrFete: number }>>;
  }>;
}

export interface CompetitorGlobal {
  brandId: UUID;
  brandName: string;
  brandColor: string;
  totalFete: number;
  pct: number;
  pctArith: number;
  prevPct: number;
  prevPctArith: number;
  deltaPp: number;
  deltaPpArith: number;
}

export interface DashboardResponse {
  ok: boolean;
  luna: string;
  prevLuna: string;
  chains: ChainSummary[];
  totalChains: number;
  globalTotalFete: number;
  globalOwnTotalFete: number;
  globalOwnPctWeighted: number;
  globalPrevOwnPctWeighted: number;
  globalOwnPctDelta: number;
  globalOwnPctArith: number;
  globalPrevOwnPctArith: number;
  globalOwnPctArithDelta: number;
  globalStoresCountedArith: number;
  globalCompetitors: CompetitorGlobal[];
  totalMagazine: number;
}

export interface StoresResponse {
  ok: boolean;
  stores: string[];
}

export interface MonthsResponse {
  ok: boolean;
  months: string[];
}
