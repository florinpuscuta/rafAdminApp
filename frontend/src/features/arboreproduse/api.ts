import { apiFetch } from "../../shared/api";
import type { ArboreProduseResponse } from "./types";

/**
 * `months`:
 *   - undefined → YTD auto (default)
 *   - "all" → tot anul (1..12)
 *   - [] → niciuna (rezultat gol)
 *   - [1,2,3] → luni specifice
 */
export function getArboreProduse(
  scope: string,
  year?: number,
  months?: number[] | "all",
): Promise<ArboreProduseResponse> {
  const q = new URLSearchParams({ scope });
  if (year != null) q.set("year", String(year));
  if (months === "all") {
    q.set("months", "all");
  } else if (Array.isArray(months)) {
    q.set("months", months.join(","));
  }
  return apiFetch<ArboreProduseResponse>(`/api/grupe-produse/tree?${q.toString()}`);
}
