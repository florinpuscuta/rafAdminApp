"""Taskuri — sistem de to-do-uri pentru agenți.

Modele DB:
  - `Task` (tenant-scoped): id, title, description, status (TODO/IN_PROGRESS/DONE),
    priority (low/medium/high), due_date, created_by_user_id, created_at, updated_at.
  - `TaskAssignment`: task_id FK, agent_id FK, assigned_at. UNIQUE(task_id, agent_id).

API: CRUD complet pe `/api/taskuri` (GET cu filtre status/agent/due range,
POST create, PATCH update/reassign, DELETE).
"""
