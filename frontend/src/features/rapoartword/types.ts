/**
 * Tipuri pentru "Raport Word" — export dashboard într-un `.docx`.
 *
 * Frontend-ul nu mânuiește structura raportului; trimite doar filtre
 * (an/lună/scope) și primește back un Blob docx.
 */

export interface RapoartWordRequest {
  year?: number;
  month?: number;
  compareYear?: number;
  chain?: string;
  storeId?: string;
  agentId?: string;
  productId?: string;
}
