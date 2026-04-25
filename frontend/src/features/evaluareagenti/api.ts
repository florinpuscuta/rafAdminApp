import { apiFetch } from "../../shared/api";
import type {
  AgentAnnualResponse,
  AgentCompList,
  AgentCompRow,
  AgentCompUpsert,
  AnnualCostResponse,
  BonusMagazinAnnualResponse,
  DashboardResponse,
  FacturaBonusAcceptResponse,
  FacturaBonusList,
  FacturaBonusPendingCount,
  FacturaBonusUnassignResponse,
  MonthInputList,
  MonthInputRow,
  MonthInputUpsert,
  RaionBonusCreate,
  RaionBonusList,
  RaionBonusRow,
  RaionBonusUpdate,
  SalariuBonusAnnualResponse,
  ZonaAgentDetail,
  ZonaAgentsResponse,
  ZonaBonusUpsert,
  ZonaStoreRow,
} from "./types";

// ─────────── Pachet Salarial ───────────

export function getCompensation(): Promise<AgentCompList> {
  return apiFetch<AgentCompList>("/api/evaluare-agenti/compensation");
}

export function upsertCompensation(
  payload: AgentCompUpsert,
): Promise<AgentCompRow> {
  return apiFetch<AgentCompRow>("/api/evaluare-agenti/compensation", {
    method: "PUT",
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json" },
  });
}

// ─────────── Input Lunar ───────────

export function getMonthInputs(
  year: number, month: number,
): Promise<MonthInputList> {
  const p = new URLSearchParams({ year: String(year), month: String(month) });
  return apiFetch<MonthInputList>(`/api/evaluare-agenti/month-inputs?${p.toString()}`);
}

export function upsertMonthInput(
  payload: MonthInputUpsert,
): Promise<MonthInputRow> {
  return apiFetch<MonthInputRow>("/api/evaluare-agenti/month-inputs", {
    method: "PUT",
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json" },
  });
}

// ─────────── Bonusări Raion ───────────

export function getRaionBonus(
  year: number, month: number,
): Promise<RaionBonusList> {
  const p = new URLSearchParams({ year: String(year), month: String(month) });
  return apiFetch<RaionBonusList>(`/api/evaluare-agenti/raion-bonus?${p.toString()}`);
}

export function createRaionBonus(
  payload: RaionBonusCreate,
): Promise<RaionBonusRow> {
  return apiFetch<RaionBonusRow>("/api/evaluare-agenti/raion-bonus", {
    method: "POST",
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json" },
  });
}

export function updateRaionBonus(
  id: string, payload: RaionBonusUpdate,
): Promise<RaionBonusRow> {
  return apiFetch<RaionBonusRow>(`/api/evaluare-agenti/raion-bonus/${id}`, {
    method: "PUT",
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json" },
  });
}

export function deleteRaionBonus(id: string): Promise<void> {
  return apiFetch<void>(`/api/evaluare-agenti/raion-bonus/${id}`, {
    method: "DELETE",
  });
}

// ─────────── Zona Agent ───────────

export function getZonaAgents(
  year: number, month: number,
): Promise<ZonaAgentsResponse> {
  const p = new URLSearchParams({ year: String(year), month: String(month) });
  return apiFetch<ZonaAgentsResponse>(`/api/evaluare-agenti/zona-agent?${p.toString()}`);
}

export function getZonaAgentDetail(
  agentId: string, year: number, month: number,
): Promise<ZonaAgentDetail> {
  const p = new URLSearchParams({ year: String(year), month: String(month) });
  return apiFetch<ZonaAgentDetail>(
    `/api/evaluare-agenti/zona-agent/${agentId}?${p.toString()}`,
  );
}

export function upsertZonaBonus(
  payload: ZonaBonusUpsert,
): Promise<ZonaStoreRow> {
  return apiFetch<ZonaStoreRow>("/api/evaluare-agenti/zona-agent/bonus", {
    method: "PUT",
    body: JSON.stringify(payload),
    headers: { "Content-Type": "application/json" },
  });
}

// ─────────── Analiza costuri anuală ───────────

export function getCostAnnual(year: number): Promise<AnnualCostResponse> {
  const p = new URLSearchParams({ year: String(year) });
  return apiFetch<AnnualCostResponse>(`/api/evaluare-agenti/cost-annual?${p.toString()}`);
}

export function getAgentAnnual(
  agentId: string, year: number,
): Promise<AgentAnnualResponse> {
  const p = new URLSearchParams({ agent_id: agentId, year: String(year) });
  return apiFetch<AgentAnnualResponse>(`/api/evaluare-agenti/agent-annual?${p.toString()}`);
}

// ─────────── Dashboard ───────────

export function getDashboard(
  year: number, months?: number[] | null,
): Promise<DashboardResponse> {
  const p = new URLSearchParams({ year: String(year) });
  if (months && months.length > 0) {
    for (const m of months) p.append("months", String(m));
  }
  return apiFetch<DashboardResponse>(`/api/evaluare-agenti/dashboard?${p.toString()}`);
}

export function getBonusMagazinAnnual(
  year: number,
): Promise<BonusMagazinAnnualResponse> {
  const p = new URLSearchParams({ year: String(year) });
  return apiFetch<BonusMagazinAnnualResponse>(
    `/api/evaluare-agenti/bonus-magazin-annual?${p.toString()}`,
  );
}

export function getSalariuBonusAnnual(
  year: number,
): Promise<SalariuBonusAnnualResponse> {
  const p = new URLSearchParams({ year: String(year) });
  return apiFetch<SalariuBonusAnnualResponse>(
    `/api/evaluare-agenti/salariu-bonus-annual?${p.toString()}`,
  );
}

// ─────────── Facturi Bonus de Asignat ───────────

export function getFacturiBonus(): Promise<FacturaBonusList> {
  return apiFetch<FacturaBonusList>("/api/evaluare-agenti/facturi-bonus");
}

export function getFacturiBonusPendingCount(): Promise<FacturaBonusPendingCount> {
  return apiFetch<FacturaBonusPendingCount>(
    "/api/evaluare-agenti/facturi-bonus/pending-count",
  );
}

export function acceptFacturiBonus(
  ids: string[],
): Promise<FacturaBonusAcceptResponse> {
  return apiFetch<FacturaBonusAcceptResponse>(
    "/api/evaluare-agenti/facturi-bonus/accept",
    {
      method: "POST",
      body: JSON.stringify({ ids }),
      headers: { "Content-Type": "application/json" },
    },
  );
}

export function unassignFacturiBonus(
  ids: string[],
): Promise<FacturaBonusUnassignResponse> {
  return apiFetch<FacturaBonusUnassignResponse>(
    "/api/evaluare-agenti/facturi-bonus/unassign",
    {
      method: "POST",
      body: JSON.stringify({ ids }),
      headers: { "Content-Type": "application/json" },
    },
  );
}
