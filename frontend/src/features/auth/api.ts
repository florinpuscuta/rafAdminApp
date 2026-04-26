import { apiFetch } from "../../shared/api";
import type {
  AuthResponse,
  Capabilities,
  LoginPayload,
  SignupPayload,
  User,
} from "./types";

export function signup(payload: SignupPayload): Promise<AuthResponse> {
  return apiFetch<AuthResponse>("/api/auth/signup", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function login(payload: LoginPayload): Promise<AuthResponse> {
  return apiFetch<AuthResponse>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function me(): Promise<User> {
  return apiFetch<User>("/api/auth/me");
}

export function capabilities(): Promise<Capabilities> {
  return apiFetch<Capabilities>("/api/auth/me/capabilities");
}

export interface ChangePasswordPayload {
  oldPassword: string;
  newPassword: string;
}

export function changePassword(payload: ChangePasswordPayload): Promise<void> {
  return apiFetch<void>("/api/auth/change-password", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function requestPasswordReset(email: string): Promise<void> {
  return apiFetch<void>("/api/auth/password-reset/request", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export function confirmPasswordReset(
  token: string,
  newPassword: string,
): Promise<void> {
  return apiFetch<void>("/api/auth/password-reset/confirm", {
    method: "POST",
    body: JSON.stringify({ token, newPassword }),
  });
}

export function confirmEmailVerify(token: string): Promise<void> {
  return apiFetch<void>("/api/auth/email-verify/confirm", {
    method: "POST",
    body: JSON.stringify({ token }),
  });
}

export function resendEmailVerify(): Promise<void> {
  return apiFetch<void>("/api/auth/email-verify/resend", {
    method: "POST",
  });
}

export function logout(refreshToken: string): Promise<void> {
  return apiFetch<void>("/api/auth/logout", {
    method: "POST",
    body: JSON.stringify({ refreshToken }),
  });
}
