import { ApiError, apiFetch, getToken } from "../../shared/api";
import type { AuditLogListResponse } from "./types";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export interface AuditFilters {
  eventType?: string;
  eventPrefix?: string;
  userId?: string;
  since?: string;
  until?: string;
}

function buildQuery(filters: AuditFilters): URLSearchParams {
  const q = new URLSearchParams();
  if (filters.eventType) q.set("eventType", filters.eventType);
  if (filters.eventPrefix) q.set("eventPrefix", filters.eventPrefix);
  if (filters.userId) q.set("userId", filters.userId);
  if (filters.since) q.set("since", filters.since);
  if (filters.until) q.set("until", filters.until);
  return q;
}

export function listAuditLogs(
  page = 1,
  pageSize = 50,
  filters: AuditFilters = {},
): Promise<AuditLogListResponse> {
  const q = buildQuery(filters);
  q.set("page", String(page));
  q.set("pageSize", String(pageSize));
  return apiFetch<AuditLogListResponse>(`/api/audit-logs?${q.toString()}`);
}

export function listAuditEventTypes(): Promise<string[]> {
  return apiFetch<string[]>("/api/audit-logs/event-types");
}

export async function downloadAuditCsv(filters: AuditFilters = {}): Promise<void> {
  const token = getToken();
  const q = buildQuery(filters);
  const resp = await fetch(
    `${API_URL}/api/audit-logs/export${q.toString() ? "?" + q.toString() : ""}`,
    { headers: token ? { Authorization: `Bearer ${token}` } : undefined },
  );
  if (!resp.ok) throw new ApiError(resp.status, "Export audit log a eșuat");
  const blob = await resp.blob();
  const cd = resp.headers.get("content-disposition") ?? "";
  const m = cd.match(/filename="([^"]+)"/);
  const filename = m?.[1] ?? "audit-log.csv";
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
