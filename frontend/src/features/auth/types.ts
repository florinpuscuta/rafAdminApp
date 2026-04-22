export interface Tenant {
  id: string;
  name: string;
  slug: string;
  active: boolean;
  createdAt: string;
}

export interface User {
  id: string;
  tenantId: string;
  email: string;
  role: string;
  active: boolean;
  createdAt: string;
  lastLoginAt: string | null;
  emailVerified: boolean;
  emailVerifiedAt: string | null;
  totpEnabled: boolean;
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
