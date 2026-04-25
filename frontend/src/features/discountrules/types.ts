export type DRScope = "adp" | "sika";

export interface DRGroup {
  kind: "category" | "private_label" | "tm";
  key: string;
  label: string;
}

export interface DRClient {
  canonical: string;
  label: string;
}

export interface DRMatrixCell {
  clientCanonical: string;
  groupKind: string;
  groupKey: string;
  applies: boolean;
}

export interface DRMatrixResponse {
  scope: DRScope;
  clients: DRClient[];
  groups: DRGroup[];
  cells: DRMatrixCell[];
}

export interface DRRuleIn {
  clientCanonical: string;
  groupKind: string;
  groupKey: string;
  applies: boolean;
}

export interface DRBulkUpsertResponse {
  upserted: number;
  deleted: number;
}
