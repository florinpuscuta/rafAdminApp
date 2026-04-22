/**
 * Tipuri pentru Dash Face Tracker — cota-parte fețe per sub-raion.
 * Oglindeste /api/marketing/facing/raion-share.
 *
 * Pentru scope=sikadp, response.analyses conține 2 intrări (Adeplast + Sika),
 * fiecare cu "Alții" excluzând brandurile celuilalt scope.
 */

export type RaionShareScope = "adp" | "sika" | "sikadp";

export interface RaionBrandShare {
  brandId: string | null;  // null pentru "Alții"
  brandName: string;
  brandColor: string;
  totalFete: number;
  pct: number;
  category: "own" | "competitor" | "other";
}

export interface SubRaionShare {
  raionId: string;
  raionName: string;
  totalFete: number;
  ownFete: number;
  ownPct: number;
  brands: RaionBrandShare[];
}

export interface ParentRaionShare {
  parentId: string;
  parentName: string;
  totalFete: number;
  ownFete: number;
  ownPct: number;
  subRaioane: SubRaionShare[];
}

export interface RaionShareAnalysis {
  scope: "adp" | "sika";
  ownBrandName: string;
  competitorNames: string[];
  parents: ParentRaionShare[];
  globalTotalFete: number;
  globalOwnFete: number;
  globalOwnPct: number;
}

export interface RaionShareResponse {
  ok: boolean;
  luna: string;
  requestedScope: RaionShareScope;
  analyses: RaionShareAnalysis[];
}
