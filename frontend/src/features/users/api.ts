import { apiFetch } from "../../shared/api";
import type { User } from "../auth/types";

export interface CreateUserPayload {
  email: string;
  password: string;
  role: "admin" | "manager" | "member" | "viewer";
}

export function listUsers(): Promise<User[]> {
  return apiFetch<User[]>("/api/users");
}

export function createUser(payload: CreateUserPayload): Promise<User> {
  return apiFetch<User>("/api/users", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export interface UpdateUserPayload {
  role?: CreateUserPayload["role"];
  active?: boolean;
}

export function updateUser(id: string, payload: UpdateUserPayload): Promise<User> {
  return apiFetch<User>(`/api/users/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteUser(id: string): Promise<void> {
  return apiFetch<void>(`/api/users/${id}`, { method: "DELETE" });
}

export function impersonateUser(id: string): Promise<{ accessToken: string; impersonating: string }> {
  return apiFetch(`/api/users/${id}/impersonate`, { method: "POST" });
}
