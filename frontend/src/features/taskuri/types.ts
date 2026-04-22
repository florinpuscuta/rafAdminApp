/**
 * Tipuri pentru feature-ul Taskuri.
 * Oglindesc schemele Pydantic din `backend/app/modules/taskuri/schemas.py`.
 */

export type TaskStatus = "TODO" | "IN_PROGRESS" | "DONE";
export type TaskPriority = "low" | "medium" | "high";

export interface TaskAssignee {
  agentId: string;
  agentName: string;
}

export interface TaskItem {
  id: string;
  title: string;
  description: string;
  status: TaskStatus;
  priority: TaskPriority;
  dueDate: string | null;
  createdByUserId: string | null;
  createdAt: string;
  updatedAt: string;
  assignees: TaskAssignee[];
}

export interface TaskuriListResponse {
  items: TaskItem[];
  total: number;
}

export interface TaskCreatePayload {
  title: string;
  description?: string;
  status?: TaskStatus;
  priority?: TaskPriority;
  dueDate?: string | null;
  assigneeAgentIds?: string[];
}

export interface TaskUpdatePayload {
  title?: string;
  description?: string;
  status?: TaskStatus;
  priority?: TaskPriority;
  dueDate?: string | null;
  assigneeAgentIds?: string[];
}

export interface TaskListFilters {
  status?: TaskStatus;
  agentId?: string;
  dueFrom?: string;
  dueTo?: string;
}
