/**
 * Tipuri pentru "Targhet" — target vs realizat pe 12 luni, per agent.
 * Oglindeste contractul /api/targhet (camelCase via APISchema).
 *
 * Decimal fields vin ca string-uri pentru a evita pierderi de precizie.
 */

export type TgtScope = "adp" | "sika" | "sikadp";

export interface TgtMonthCell {
  month: number;        // 1..12
  monthName: string;
  prevSales: string;
  currSales: string;
  target: string;
  targetPct: string;
  gap: string;
  achievementPct: string | null;
}

export interface TgtTotals {
  prevSales: string;
  currSales: string;
  target: string;
  gap: string;
  achievementPct: string | null;
}

export interface TgtAgentRow {
  agentId: string | null;
  agentName: string;
  months: TgtMonthCell[];    // 12 items
  totals: TgtTotals;
}

export interface TgtMonthTotal {
  month: number;
  monthName: string;
  prevSales: string;
  currSales: string;
  target: string;
  targetPct: string;
  gap: string;
  achievementPct: string | null;
}

export interface TgtGrowthItem {
  year: number;
  month: number;
  pct: string;
}

export interface TgtGrowthList {
  year: number;
  items: TgtGrowthItem[];
}

export interface TgtResponse {
  scope: TgtScope;
  yearCurr: number;
  yearPrev: number;
  lastUpdate: string | null;
  agents: TgtAgentRow[];
  monthTotals: TgtMonthTotal[];
  grandTotals: TgtTotals;
  growthPct: TgtGrowthItem[];
}
