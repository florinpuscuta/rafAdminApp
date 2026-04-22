import { apiFetch } from "../../shared/api";
import type { DashboardOverview } from "./types";

export interface DashboardQuery {
  year?: number | null;
  month?: number | null;
  chain?: string | null;
  category?: string | null;
  storeId?: string | null;
  agentId?: string | null;
  productId?: string | null;
}

export function getOverview(q: DashboardQuery = {}): Promise<DashboardOverview> {
  const params = new URLSearchParams();
  if (q.year != null) params.set("year", String(q.year));
  if (q.month != null) params.set("month", String(q.month));
  if (q.chain) params.set("chain", q.chain);
  if (q.category) params.set("category", q.category);
  if (q.storeId) params.set("storeId", q.storeId);
  if (q.agentId) params.set("agentId", q.agentId);
  if (q.productId) params.set("productId", q.productId);
  const s = params.toString();
  return apiFetch<DashboardOverview>(
    `/api/dashboard/overview${s ? "?" + s : ""}`,
  );
}

export function listChains(): Promise<string[]> {
  return apiFetch<string[]>("/api/stores/chains");
}

export function listCategories(): Promise<string[]> {
  return apiFetch<string[]>("/api/products/categories");
}

export async function downloadDashboardReport(q: DashboardQuery = {}): Promise<void> {
  const { getToken, ApiError } = await import("../../shared/api");
  const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
  const token = getToken();
  const params = new URLSearchParams();
  if (q.year != null) params.set("year", String(q.year));
  if (q.month != null) params.set("month", String(q.month));
  if (q.chain) params.set("chain", q.chain);
  if (q.category) params.set("category", q.category);
  if (q.storeId) params.set("storeId", q.storeId);
  if (q.agentId) params.set("agentId", q.agentId);
  if (q.productId) params.set("productId", q.productId);
  const url = `${API_URL}/api/reports/dashboard.docx?${params.toString()}`;
  const resp = await fetch(url, {
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
  if (!resp.ok) throw new ApiError(resp.status, "Export a eșuat");
  const blob = await resp.blob();
  const cd = resp.headers.get("content-disposition") ?? "";
  const m = cd.match(/filename="([^"]+)"/);
  const filename = m?.[1] ?? "raport.docx";
  const obj = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = obj;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(obj);
}
