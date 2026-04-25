export type PPScopeKey = "adp" | "sika";

export interface PPScope {
  scope: string;
  count: number;
  lastImportedAt: string | null;
  lastImportedFilename: string | null;
}

export interface PPSummaryResponse {
  adp: PPScope;
  sika: PPScope;
}

export interface PPRow {
  productId: string;
  productCode: string;
  productName: string;
  categoryLabel: string | null;
  price: string;
}

export interface PPListResponse {
  scope: string;
  items: PPRow[];
}

export interface PPUploadResponse {
  scope: string;
  filename: string;
  rowsTotal: number;
  rowsMatched: number;
  rowsUnmatched: number;
  rowsInvalid: number;
  unmatchedCodes: string[];
  inserted: number;
  deletedBefore: number;
}


export interface PPMonthlySlot {
  year: number;
  month: number;
  count: number;
  lastImportedAt: string | null;
}

export interface PPMonthlySummaryResponse {
  adp: PPMonthlySlot[];
  sika: PPMonthlySlot[];
}

export interface PPMonthlyListResponse {
  scope: string;
  year: number;
  month: number;
  items: PPRow[];
}

export interface PPMonthlyUploadResponse {
  scope: string;
  year: number;
  month: number;
  filename: string;
  rowsTotal: number;
  rowsMatched: number;
  rowsUnmatched: number;
  rowsInvalid: number;
  unmatchedCodes: string[];
  inserted: number;
  deletedBefore: number;
}
