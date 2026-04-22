/**
 * Tipuri pentru "Bonusări" — calcul bonus lunar per agent.
 * Oglindeste contractul /api/bonusari (camelCase via APISchema).
 */

export type BonScope = "adp" | "sika" | "sikadp";

export interface BonTier {
  thresholdPct: string;     // ex. "15"
  amount: string;           // ex. "5500"
}

export interface BonRules {
  tiers: BonTier[];
  recoveryAmount: string;
  recoveryThresholdPct: string;
}

export interface BonMonthCell {
  month: number;            // 1..12
  monthName: string;
  prevSales: string;
  currSales: string;
  growthPct: string;
  bonus: string;
  recovery: string;
  total: string;
  isFuture: boolean;
}

export interface BonAgentRow {
  agentId: string | null;
  agentName: string;
  months: BonMonthCell[];   // 12 items
  totalBonus: string;
}

export interface BonMonthTotal {
  month: number;
  monthName: string;
  bonus: string;
  recovery: string;
  total: string;
}

export interface BonResponse {
  scope: BonScope;
  yearCurr: number;
  yearPrev: number;
  currentMonthLimit: number;
  rules: BonRules;
  lastUpdate: string | null;
  agents: BonAgentRow[];
  monthTotals: BonMonthTotal[];
  grandTotal: string;
}
