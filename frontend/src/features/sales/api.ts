import { apiFetch, ApiError, getActiveOrgId, getToken } from "../../shared/api";

function authHeaders(): Record<string, string> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  const org = getActiveOrgId();
  if (org) headers["X-Active-Org-Id"] = org;
  return headers;
}
import type {
  ImportBatch,
  ImportJobAccepted,
  ImportJobStatus,
  ImportResponse,
  SalesListResponse,
} from "./types";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export interface SalesFilters {
  storeId?: string;
  agentId?: string;
  productId?: string;
  year?: number;
}

export function listSales(
  page = 1,
  pageSize = 50,
  filters: SalesFilters = {},
): Promise<SalesListResponse> {
  const p = new URLSearchParams({ page: String(page), pageSize: String(pageSize) });
  if (filters.storeId) p.set("storeId", filters.storeId);
  if (filters.agentId) p.set("agentId", filters.agentId);
  if (filters.productId) p.set("productId", filters.productId);
  if (filters.year != null) p.set("year", String(filters.year));
  return apiFetch<SalesListResponse>(`/api/sales?${p.toString()}`);
}

export async function importSales(
  file: File,
  opts: { fullReload?: boolean } = {},
): Promise<ImportResponse> {
  // apiFetch nu suportă FormData; facem manual pentru multipart.
  const form = new FormData();
  form.append("file", file);

  const qs = opts.fullReload ? "?fullReload=true" : "";
  const resp = await fetch(`${API_URL}/api/sales/import${qs}`, {
    method: "POST",
    body: form,
    headers: authHeaders(),
  });

  if (!resp.ok) {
    let code: string | undefined;
    let message = resp.statusText;
    try {
      const data = await resp.json();
      const detail = (data as { detail?: unknown }).detail;
      if (typeof detail === "string") message = detail;
      else if (detail && typeof detail === "object") {
        const d = detail as { code?: string; message?: string };
        code = d.code;
        message = d.message ?? message;
      }
    } catch {
      /* non-json */
    }
    throw new ApiError(resp.status, message, code);
  }
  return (await resp.json()) as ImportResponse;
}

export async function importSalesAsync(
  file: File,
  opts: { fullReload?: boolean } = {},
): Promise<ImportJobAccepted> {
  const form = new FormData();
  form.append("file", file);
  const qs = opts.fullReload ? "?fullReload=true" : "";
  const resp = await fetch(`${API_URL}/api/sales/import/async${qs}`, {
    method: "POST",
    body: form,
    headers: authHeaders(),
  });
  if (!resp.ok) {
    let code: string | undefined;
    let message = resp.statusText;
    try {
      const data = await resp.json();
      const detail = (data as { detail?: unknown }).detail;
      if (typeof detail === "string") message = detail;
      else if (detail && typeof detail === "object") {
        const d = detail as { code?: string; message?: string };
        code = d.code;
        message = d.message ?? message;
      }
    } catch {
      /* non-json */
    }
    throw new ApiError(resp.status, message, code);
  }
  return (await resp.json()) as ImportJobAccepted;
}

export function getImportJob(jobId: string): Promise<ImportJobStatus> {
  return apiFetch<ImportJobStatus>(`/api/sales/import/jobs/${jobId}`);
}

export function listBatches(): Promise<ImportBatch[]> {
  return apiFetch<ImportBatch[]>("/api/sales/batches");
}

export function deleteBatch(id: string): Promise<void> {
  return apiFetch<void>(`/api/sales/batches/${id}`, { method: "DELETE" });
}

export async function downloadSalesExport(
  year?: number | null,
  month?: number | null,
): Promise<void> {
  const params = new URLSearchParams();
  if (year != null) params.set("year", String(year));
  if (month != null) params.set("month", String(month));
  const qs = params.toString();
  const resp = await fetch(
    `${API_URL}/api/sales/export${qs ? "?" + qs : ""}`,
    { headers: authHeaders() },
  );
  if (!resp.ok) throw new ApiError(resp.status, "Export a eșuat");
  const blob = await resp.blob();
  const cd = resp.headers.get("content-disposition") ?? "";
  const m = cd.match(/filename="([^"]+)"/);
  const filename = m?.[1] ?? "sales.xlsx";
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
