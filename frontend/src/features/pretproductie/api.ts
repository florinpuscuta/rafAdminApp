import { apiFetch, ApiError, getToken } from "../../shared/api";
import type {
  PPListResponse,
  PPMonthlyListResponse,
  PPMonthlySummaryResponse,
  PPMonthlyUploadResponse,
  PPScopeKey,
  PPSummaryResponse,
  PPUploadResponse,
} from "./types";

const BASE = "/api/pret-productie";
const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export function getSummary(): Promise<PPSummaryResponse> {
  return apiFetch<PPSummaryResponse>(`${BASE}/summary`);
}

export function listPrices(scope: PPScopeKey): Promise<PPListResponse> {
  const p = new URLSearchParams({ scope });
  return apiFetch<PPListResponse>(`${BASE}?${p.toString()}`);
}

export function resetScope(scope: PPScopeKey): Promise<void> {
  const p = new URLSearchParams({ scope });
  return apiFetch<void>(`${BASE}?${p.toString()}`, { method: "DELETE" });
}

export function uploadPrices(
  scope: PPScopeKey,
  file: File,
): Promise<PPUploadResponse> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const url = `${API_URL}${BASE}/upload?scope=${encodeURIComponent(scope)}`;
    xhr.open("POST", url);
    const token = getToken();
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.responseType = "json";
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(xhr.response as PPUploadResponse);
      } else {
        let msg = xhr.statusText || "Eroare upload";
        const body = xhr.response as { detail?: unknown } | null;
        const detail = body?.detail;
        if (typeof detail === "string") msg = detail;
        else if (detail && typeof detail === "object") {
          const d = detail as { message?: string };
          if (d.message) msg = d.message;
        }
        reject(new ApiError(xhr.status, msg));
      }
    };
    xhr.onerror = () => reject(new ApiError(0, "Eroare de retea"));
    const form = new FormData();
    form.append("file", file);
    xhr.send(form);
  });
}


// ─── Snapshot lunar ────────────────────────────────────────────


export function getMonthlySummary(): Promise<PPMonthlySummaryResponse> {
  return apiFetch<PPMonthlySummaryResponse>(`${BASE}/monthly-summary`);
}

export function listMonthly(
  scope: PPScopeKey, year: number, month: number,
): Promise<PPMonthlyListResponse> {
  const p = new URLSearchParams({
    scope, year: String(year), month: String(month),
  });
  return apiFetch<PPMonthlyListResponse>(`${BASE}/monthly?${p.toString()}`);
}

export function resetMonthly(
  scope: PPScopeKey, year: number, month: number,
): Promise<void> {
  const p = new URLSearchParams({
    scope, year: String(year), month: String(month),
  });
  return apiFetch<void>(`${BASE}/monthly?${p.toString()}`, { method: "DELETE" });
}

export function uploadMonthly(
  scope: PPScopeKey, year: number, month: number, file: File,
): Promise<PPMonthlyUploadResponse> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const url = `${API_URL}${BASE}/upload-monthly?scope=${encodeURIComponent(scope)}&year=${year}&month=${month}`;
    xhr.open("POST", url);
    const token = getToken();
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.responseType = "json";
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(xhr.response as PPMonthlyUploadResponse);
      } else {
        let msg = xhr.statusText || "Eroare upload";
        const body = xhr.response as { detail?: unknown } | null;
        const detail = body?.detail;
        if (typeof detail === "string") msg = detail;
        else if (detail && typeof detail === "object") {
          const d = detail as { message?: string };
          if (d.message) msg = d.message;
        }
        reject(new ApiError(xhr.status, msg));
      }
    };
    xhr.onerror = () => reject(new ApiError(0, "Eroare de retea"));
    const form = new FormData();
    form.append("file", file);
    xhr.send(form);
  });
}
