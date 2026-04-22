"""Scheme Pydantic pentru /api/taskuri."""
from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.core.schemas import APISchema


TaskStatus = Literal["TODO", "IN_PROGRESS", "DONE"]
TaskPriority = Literal["low", "medium", "high"]


class AssigneeOut(APISchema):
    """Agent asignat — expunem id + nume ca să UI-ul nu mai facă un al
    doilea round-trip pentru resolve."""

    agent_id: UUID
    agent_name: str


class TaskOut(APISchema):
    id: UUID
    title: str
    description: str = ""
    status: TaskStatus
    priority: TaskPriority
    due_date: date | None = None
    created_by_user_id: UUID | None = None
    created_at: datetime
    updated_at: datetime
    assignees: list[AssigneeOut] = Field(default_factory=list)


class TaskListResponse(APISchema):
    items: list[TaskOut] = Field(default_factory=list)
    total: int = 0


class TaskCreate(APISchema):
    title: str
    description: str = ""
    status: TaskStatus = "TODO"
    priority: TaskPriority = "medium"
    due_date: date | None = None
    assignee_agent_ids: list[UUID] = Field(default_factory=list)


class TaskUpdate(APISchema):
    title: str | None = None
    description: str | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    due_date: date | None = None
    # None = nu atinge asignările; lista goală = șterge toate asignările.
    assignee_agent_ids: list[UUID] | None = None
