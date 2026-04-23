import { apiFetch } from "../../shared/api";
import type {
  AgentCompList,
  AgentCompRow,
  AgentCompUpsert,
  MatrixResponse,
  MonthInputList,
  MonthInputRow,
  MonthInputUpsert,
  RaionBonusCreate,
  RaionBonusList,
  RaionBonusRow,
  RaionBonusUpdate,
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

// ─────────── Matricea ───────────

export function getMatrix(
  year: number, month: number,
): Promise<MatrixResponse> {
  const p = new URLSearchParams({ year: String(year), month: String(month) });
  return apiFetch<MatrixResponse>(`/api/evaluare-agenti/matrix?${p.toString()}`);
}
