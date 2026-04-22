export interface AuditLog {
  id: string;
  tenantId: string | null;
  userId: string | null;
  eventType: string;
  targetType: string | null;
  targetId: string | null;
  eventMetadata: Record<string, unknown> | null;
  ipAddress: string | null;
  userAgent: string | null;
  createdAt: string;
}

export interface AuditLogListResponse {
  items: AuditLog[];
  total: number;
  page: number;
  pageSize: number;
}
