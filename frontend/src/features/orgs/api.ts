import { apiFetch } from "../../shared/api";

export interface OrganizationMembership {
  organizationId: string;
  name: string;
  slug: string;
  kind: "production" | "demo" | "test";
  roleV2: string;
  isDefault: boolean;
}

export interface MembershipsResponse {
  items: OrganizationMembership[];
}

export function getMyOrganizations(): Promise<MembershipsResponse> {
  return apiFetch<MembershipsResponse>("/api/auth/me/organizations");
}
