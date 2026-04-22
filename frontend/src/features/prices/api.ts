import { apiFetch, ApiError, getToken } from "../../shared/api";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export interface KaVsTtRow {
  productId: string | null;
  description: string;
  productCode: string | null;
  category: string | null;
  kaPrice: string | null;
  kaQty: string;
  kaSales: string;
  ttPrice: string | null;
  ttQty: string;
  ttSales: string;
  deltaAbs: string | null;
  deltaPct: string | null;
}

export interface KaVsTtSummary {
  kaAvgPrice: string | null;
  ttAvgPrice: string | null;
  deltaPct: string | null;
  kaTotalSales: string;
  ttTotalSales: string;
}

export interface KaVsTtResponse {
  summary: KaVsTtSummary;
  rows: KaVsTtRow[];
}

export interface KaVsTtFilters {
  year?: number;
  month?: number;
  category?: string;
  productId?: string;
  minQty?: number;
}

function buildQuery(filters: KaVsTtFilters): URLSearchParams {
  const q = new URLSearchParams();
  if (filters.year != null) q.set("year", String(filters.year));
  if (filters.month != null) q.set("month", String(filters.month));
  if (filters.category) q.set("category", filters.category);
  if (filters.productId) q.set("productId", filters.productId);
  if (filters.minQty != null) q.set("minQty", String(filters.minQty));
  return q;
}

export function getKaVsTt(filters: KaVsTtFilters = {}): Promise<KaVsTtResponse> {
  const q = buildQuery(filters);
  const qs = q.toString();
  return apiFetch<KaVsTtResponse>(`/api/prices/ka-vs-tt${qs ? "?" + qs : ""}`);
}

export async function downloadKaVsTtCsv(filters: KaVsTtFilters = {}): Promise<void> {
  const token = getToken();
  const q = buildQuery(filters);
  const url = `${API_URL}/api/prices/ka-vs-tt/export${q.toString() ? "?" + q.toString() : ""}`;
  const resp = await fetch(url, {
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
  if (!resp.ok) throw new ApiError(resp.status, "Export a eșuat");
  const blob = await resp.blob();
  const cd = resp.headers.get("content-disposition") ?? "";
  const m = cd.match(/filename="([^"]+)"/);
  const filename = m?.[1] ?? "ka-vs-tt.csv";
  const a = document.createElement("a");
  const objUrl = URL.createObjectURL(blob);
  a.href = objUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(objUrl);
}
