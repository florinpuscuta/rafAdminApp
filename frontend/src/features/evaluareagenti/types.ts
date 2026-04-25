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
  bonusVanzariEligibil: boolean;
  note: string | null;
  updatedAt: string | null;
}

export interface AgentCompList {
  rows: AgentCompRow[];
}

export interface AgentCompUpsert {
  agentId: string;
  salariuFix: string;
  bonusVanzariEligibil: boolean;
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
  merchandiserZona: string;
  cheltuieliAuto: string;
  alteCheltuieli: string;
  alteCheltuieliLabel: string | null;
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
  merchandiserZona: string;
  cheltuieliAuto: string;
  alteCheltuieli: string;
  alteCheltuieliLabel: string | null;
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

// ─────────── Analiza costuri anuală ───────────

export interface AnnualCostRow {
  agentId: string;
  agentName: string;
  monthly: string[]; // 12 valori
  total: string;
}

export interface AnnualCostResponse {
  year: number;
  rows: AnnualCostRow[];
  monthTotals: string[]; // 12 valori
  grandTotal: string;
}

export interface AgentAnnualMonthRow {
  month: number;
  salariuFix: string;
  bonusAgent: string;
  merchandiserZona: string;
  cheltuieliAuto: string;
  alteCheltuieli: string;
  bonusRaion: string;
  total: string;
}

export interface AgentAnnualResponse {
  agentId: string;
  agentName: string;
  year: number;
  rows: AgentAnnualMonthRow[];
  columnTotals: AgentAnnualMonthRow;
}

// ─────────── Dashboard agenți ───────────

export interface DashboardAgentRow {
  agentId: string;
  agentName: string;
  storeCount: number;
  vanzari: string;
  vanzariPrev: string;
  cheltuieli: string;
  costPct: string | null;
  costPer100k: string | null;
  yoyPct: string | null;
  bonusAgent: string;
}

export interface DashboardResponse {
  year: number;
  month: number | null;
  rows: DashboardAgentRow[];
  grandVanzari: string;
  grandCheltuieli: string;
  grandBonusAgent: string;
  grandStoreCount: number;
  grandCostPct: string | null;
}

export interface BonusMagazinAnnualRow {
  agentId: string;
  agentName: string;
  monthly: string[]; // 12 valori
  total: string;
}

export interface BonusMagazinAnnualResponse {
  year: number;
  rows: BonusMagazinAnnualRow[];
  monthTotals: string[];
  grandTotal: string;
}

export interface SalariuBonusAnnualRow {
  agentId: string;
  agentName: string;
  monthly: string[]; // 12 valori
  total: string;
}

export interface SalariuBonusAnnualResponse {
  year: number;
  rows: SalariuBonusAnnualRow[];
  monthTotals: string[];
  grandTotal: string;
}

// ─────────── Facturi Bonus de Asignat ───────────

export interface FacturaBonusRow {
  id: string;
  year: number;
  month: number;
  amount: string;
  client: string;
  chain: string | null;
  agentId: string | null;
  agentName: string | null;
  storeId: string | null;
  storeName: string | null;
  suggestedStoreId: string | null;
  suggestedStoreName: string | null;
  suggestedAgentId: string | null;
  suggestedAgentName: string | null;
  status: "pending" | "assigned";
  decidedAt: string | null;
  decisionSource: "auto" | "manual" | null;
}

export interface FacturaBonusPendingCount {
  pendingCount: number;
  pendingAmount: string;
}

export interface FacturaBonusList {
  rows: FacturaBonusRow[];
  pendingCount: number;
  pendingAmount: string;
  assignedCount: number;
  assignedAmount: string;
  threshold: string;
}

export interface FacturaBonusAcceptResponse {
  accepted: number;
  skipped: number;
}

export interface FacturaBonusUnassignResponse {
  unassigned: number;
  skipped: number;
}
