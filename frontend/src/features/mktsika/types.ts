/**
 * Tipuri pentru /api/marketing/sika — Acțiuni SIKA.
 * DB schema TODO; `items` va fi gol până la implementare.
 */

export interface MktSikaItem {
  id: string;
  title: string;
  luna: string | null; // "YYYY-MM"
  notes: string | null;
}

export interface MktSikaResponse {
  items: MktSikaItem[];
  notice: string | null;
}
