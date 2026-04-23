/**
 * Tipuri pentru "Evaluare Agenți" — SIKADP-only.
 *
 * Valorile bănești sunt string (Decimal) ca să nu pierdem precizie —
 * aceeași convenție ca restul feature-urilor.
 */

// ─────────── Sal Fix (constantă per agent) ───────────

export interface AgentCompRow {
  agentId: string;
  agentName: string;
  salariuFix: string;
  note: string | null;
  updatedAt: string | null;
}

export interface AgentCompList {
  rows: AgentCompRow[];
}

export interface AgentCompUpsert {
  agentId: string;
  salariuFix: string;
  note: string | null;
}

// ─────────── Input Lunar (matrix costuri directe) ───────────

export interface MonthInputRow {
  agentId: string;
  agentName: string;
  year: number;
  month: number;
  // readonly (pachet + /bonusari + /raion-bonus)
  vanzari: string;
  salariuFix: string;
  bonusAgent: string;
  bonusRaion: string;
  // editabile (direct RON)
  costCombustibil: string;
  costRevizii: string;
  alteCosturi: string;
  // computed
  totalCost: string;
  note: string | null;
}

export interface MonthInputList {
  year: number;
  month: number;
  rows: MonthInputRow[];
}

export interface MonthInputUpsert {
  agentId: string;
  year: number;
  month: number;
  costCombustibil: string;
  costRevizii: string;
  alteCosturi: string;
  note: string | null;
}

// ─────────── Zona Agent ───────────

export interface ZonaStoreRow {
  storeId: string;
  storeName: string;
  target: string;
  realizat: string;
  achievementPct: string | null;
  bonus: string;
  note: string | null;
}

export interface ZonaAgentSummary {
  agentId: string;
  agentName: string;
  storeCount: number;
  totalTarget: string;
  totalRealizat: string;
  totalBonus: string;
}

export interface ZonaAgentsResponse {
  year: number;
  month: number;
  agents: ZonaAgentSummary[];
}

export interface ZonaAgentDetail {
  agentId: string;
  agentName: string;
  year: number;
  month: number;
  stores: ZonaStoreRow[];
  totalTarget: string;
  totalRealizat: string;
  totalBonus: string;
}

export interface ZonaBonusUpsert {
  agentId: string;
  storeId: string;
  year: number;
  month: number;
  bonus: string;
  note: string | null;
}

// ─────────── Bonusări Oameni Raion (legacy) ───────────

export interface RaionBonusRow {
  id: string;
  storeId: string;
  storeName: string;
  agentId: string | null;
  agentName: string | null;
  year: number;
  month: number;
  contactName: string;
  suma: string;
  note: string | null;
}

export interface RaionBonusList {
  year: number;
  month: number;
  rows: RaionBonusRow[];
  total: string;
}

export interface RaionBonusCreate {
  storeId: string;
  year: number;
  month: number;
  contactName: string;
  suma: string;
  note: string | null;
}

export interface RaionBonusUpdate {
  contactName: string;
  suma: string;
  note: string | null;
}

// ─────────── Matricea ───────────

export interface MatrixRow {
  agentId: string;
  agentName: string;
  vanzari: string;
  salariuFix: string;
  bonusAgent: string;
  salariuTotal: string;
  costCombustibil: string;
  costRevizii: string;
  alteCosturi: string;
  bonusRaion: string;
  totalCost: string;
  costPer100k: string | null;
}

export interface MatrixResponse {
  year: number;
  month: number;
  rows: MatrixRow[];
  grandVanzari: string;
  grandCost: string;
}
