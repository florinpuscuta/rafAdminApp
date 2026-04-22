export interface Sale {
  id: string;
  year: number;
  month: number;
  client: string;
  channel: string | null;
  productCode: string | null;
  productName: string | null;
  categoryCode: string | null;
  amount: string;
  quantity: string | null;
  agent: string | null;
  createdAt: string;
}

export interface SalesListResponse {
  items: Sale[];
  total: number;
  page: number;
  pageSize: number;
}

export interface AlocareSummary {
  rowsProcessed: number;
  agentsCreated: number;
  storesCreated: number;
  storeAliasesCreated: number;
  agentAliasesCreated: number;
  assignmentsCreated: number;
}

export interface JobStage {
  key: string;
  label: string;
  progress: number;
  done: boolean;
}

export interface ImportJobStatus {
  id: string;
  status: "pending" | "running" | "done" | "error";
  stages: JobStage[];
  currentStage: string | null;
  overallProgress: number;
  result: ImportResponse | null;
  error: string | null;
  errorCode: string | null;
}

export interface ImportJobAccepted {
  jobId: string;
}

export interface ImportResponse {
  inserted: number;
  skipped: number;
  deletedBeforeInsert: number;
  monthsAffected: string[];
  unmappedClients: number;
  unmappedAgents: number;
  unmappedProducts: number;
  alocare: AlocareSummary;
  errors: string[];
}

export interface ImportBatch {
  id: string;
  filename: string;
  source: string;
  insertedRows: number;
  skippedRows: number;
  uploadedByUserId: string | null;
  createdAt: string;
}
