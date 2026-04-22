export type ParcursScope = "adp" | "sika" | "sikadp";

export interface ParcursAgentOption {
  agentId: string | null;
  agentName: string;
  storesCount: number;
}

export interface ParcursStoreOption {
  storeId: string | null;
  storeName: string;
  city: string | null;
}

export interface ParcursFuelFill {
  date: string;   // "YYYY-MM-DD"
  liters: number;
  cost: number;
}

export interface ParcursEntry {
  date: string;       // "DD.MM.YYYY"
  dayName: string;
  route: string;
  storesVisited: string[];
  kmStart: number;
  kmEnd: number;
  kmDriven: number;
  purpose: string;
  fuelLiters: number | null;
  fuelCost: number | null;
}

export interface ParcursResponse {
  agent: string;
  month: number;
  monthName: string;
  year: number;
  carNumber: string | null;
  sediu: string;
  kmStart: number;
  kmEnd: number;
  totalKm: number;
  workingDays: number;
  avgKmPerDay: number;
  totalFuelLiters: number;
  totalFuelCost: number;
  aiGenerated: boolean;
  entries: ParcursEntry[];
  fuelFills: ParcursFuelFill[];
  todo: string | null;
}

export interface ParcursGenerateRequest {
  scope: ParcursScope;
  agent: string;
  year: number;
  month: number;
  kmStart: number;
  kmEnd: number;
  carNumber?: string;
  sediu?: string;
  fuelFills?: ParcursFuelFill[];
  aiProvider?: string;
  aiKey?: string;
}

export interface ParcursAgentsResponse {
  scope: ParcursScope;
  agents: ParcursAgentOption[];
}

export interface ParcursStoresResponse {
  scope: ParcursScope;
  agent: string;
  stores: ParcursStoreOption[];
}
