export interface ActivitateVisitRow {
  visitDate: string;        // "YYYY-MM-DD"
  storeId: string | null;
  storeName: string;
  client: string | null;
  checkIn: string | null;
  checkOut: string | null;
  durationMin: number | null;
  km: string | null;
  notes: string | null;
  photosCount: number;
}

export interface ActivitateAgentRow {
  agentId: string | null;
  agentName: string;
  visitsCount: number;
  storesCount: number;
  totalKm: string;
  totalDurationMin: number;
  visits: ActivitateVisitRow[];
}

export interface ActivitateResponse {
  scope: "adp" | "sika" | "sikadp";
  dateFrom: string;
  dateTo: string;
  agentsCount: number;
  totalVisits: number;
  totalStores: number;
  totalKm: string;
  agents: ActivitateAgentRow[];
  todo: string | null;
}
