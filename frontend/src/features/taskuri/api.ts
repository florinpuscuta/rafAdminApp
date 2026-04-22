import { apiFetch } from "../../shared/api";
import type {
  TaskCreatePayload,
  TaskItem,
  TaskListFilters,
  TaskUpdatePayload,
  TaskuriListResponse,
} from "./types";

function buildQS(filters?: TaskListFilters): string {
  if (!filters) return "";
  const params = new URLSearchParams();
  if (filters.status) params.set("status", filters.status);
  if (filters.agentId) params.set("agentId", filters.agentId);
  if (filters.dueFrom) params.set("dueFrom", filters.dueFrom);
  if (filters.dueTo) params.set("dueTo", filters.dueTo);
  const s = params.toString();
  return s ? `?${s}` : "";
}

export function listTaskuri(
  filters?: TaskListFilters,
): Promise<TaskuriListResponse> {
  return apiFetch<TaskuriListResponse>(`/api/taskuri${buildQS(filters)}`);
}

export function createTask(payload: TaskCreatePayload): Promise<TaskItem> {
  return apiFetch<TaskItem>("/api/taskuri", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function updateTask(
  id: string,
  payload: TaskUpdatePayload,
): Promise<TaskItem> {
  return apiFetch<TaskItem>(`/api/taskuri/${id}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export function deleteTask(id: string): Promise<void> {
  return apiFetch<void>(`/api/taskuri/${id}`, { method: "DELETE" });
}
