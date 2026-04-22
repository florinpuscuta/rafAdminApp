import { apiFetch } from "../../shared/api";
import type { DiscountConfig, Pret3NetFilters, Pret3NetResponse } from "./types";

const DISCOUNT_STORAGE_KEY = "adeplast_pret3net_discounts";

function buildQuery(f: Pret3NetFilters): string {
  const q = new URLSearchParams();
  if (f.year != null) q.set("year", String(f.year));
  if (f.months && f.months.length > 0) q.set("months", f.months.join(","));
  if (f.company) q.set("company", f.company);
  const qs = q.toString();
  return qs ? `?${qs}` : "";
}

/**
 * GET /api/prices/pret3net?year=YYYY&months=1,2
 *
 * Preț mediu per produs × KA, grupat pe categorie. Nu aplică discount —
 * asta se face în frontend (vezi `loadDiscounts` / `computeNetPrice`).
 */
export function getPret3Net(filters: Pret3NetFilters = {}): Promise<Pret3NetResponse> {
  return apiFetch<Pret3NetResponse>(`/api/prices/pret3net${buildQuery(filters)}`);
}

/** Încarcă configurația de discounturi din localStorage per tenant curent. */
export function loadDiscounts(): DiscountConfig {
  try {
    const raw = localStorage.getItem(DISCOUNT_STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return typeof parsed === "object" && parsed !== null ? parsed : {};
  } catch {
    return {};
  }
}

/** Salvează configurația de discounturi în localStorage. */
export function saveDiscounts(cfg: DiscountConfig): void {
  localStorage.setItem(DISCOUNT_STORAGE_KEY, JSON.stringify(cfg));
}

/**
 * Calculează factor-ul net compus pentru un KA: product(1 - pct/100).
 * Ex: 10% + 5% → 0.9 × 0.95 = 0.855 → discount total 14.5%.
 */
export function netFactor(discounts: { pct: number }[] | undefined): number {
  if (!discounts || discounts.length === 0) return 1;
  let f = 1;
  for (const d of discounts) {
    const p = Number(d.pct) || 0;
    f *= 1 - p / 100;
  }
  return f;
}
