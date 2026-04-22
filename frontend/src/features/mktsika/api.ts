import { apiFetch } from "../../shared/api";
import type { MktSikaResponse } from "./types";

/**
 * GET /api/marketing/sika — Acțiuni SIKA.
 * Placeholder până la modelul DB.
 */
export function getMktSika(): Promise<MktSikaResponse> {
  return apiFetch<MktSikaResponse>("/api/marketing/sika");
}
