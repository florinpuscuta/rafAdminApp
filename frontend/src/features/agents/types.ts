export interface Agent {
  id: string;
  fullName: string;
  email: string | null;
  phone: string | null;
  active: boolean;
  createdAt: string;
}

export interface AgentAlias {
  id: string;
  rawAgent: string;
  agentId: string;
  resolvedByUserId: string | null;
  resolvedAt: string;
}

export interface UnmappedAgentRow {
  rawAgent: string;
  rowCount: number;
  totalAmount: string;
}

export interface CreateAgentPayload {
  fullName: string;
  email?: string | null;
  phone?: string | null;
}

export interface CreateAgentAliasPayload {
  rawAgent: string;
  agentId: string;
}
