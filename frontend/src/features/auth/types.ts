export interface Tenant {
  id: string;
  name: string;
  slug: string;
  active: boolean;
  createdAt: string;
}

export type UserRoleV2 =
  | "admin"
  | "director"
  | "finance_manager"
  | "regional_manager"
  | "sales_agent"
  | "viewer";

export interface User {
  id: string;
  tenantId: string;
  email: string;
  role: string;
  // `roleV2` e canonic. Pentru user-i pre-migration poate fi null;
  // în acest caz frontend-ul cade pe `role` legacy.
  roleV2: UserRoleV2 | null;
  active: boolean;
  createdAt: string;
  lastLoginAt: string | null;
  emailVerified: boolean;
  emailVerifiedAt: string | null;
  totpEnabled: boolean;
}

export interface Capabilities {
  roleV2: UserRoleV2;
  modules: string[]; // `["*"]` pentru admin
}

export interface AuthResponse {
  accessToken: string;
  refreshToken: string;
  tokenType: string;
  user: User;
  tenant: Tenant;
}

export interface SignupPayload {
  tenantName: string;
  email: string;
  password: string;
}

export interface LoginPayload {
  email: string;
  password: string;
  totpCode?: string;
}
