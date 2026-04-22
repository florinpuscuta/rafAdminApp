"""Router pentru /api/taskuri.

Endpoint-uri:
  - GET    /api/taskuri              — listă cu filtre status/agent/due range
  - POST   /api/taskuri              — crează task
  - GET    /api/taskuri/{id}         — detaliu task
  - PATCH  /api/taskuri/{id}         — update parțial (status, priority, etc)
  - DELETE /api/taskuri/{id}         — șterge (cascade pe asignări)
"""
from datetime import date
from uuid import UUID

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api import APIRouter
from app.core.db import get_session
from app.modules.auth.deps import get_current_user
from app.modules.taskuri import service
from app.modules.taskuri.schemas import (
    TaskCreate,
    TaskListResponse,
    TaskOut,
    TaskUpdate,
)
from app.modules.users.models import User

router = APIRouter(prefix="/api/taskuri", tags=["taskuri"])


@router.get("", response_model=TaskListResponse)
async def list_taskuri(
    status_filter: str | None = Query(None, alias="status"),
    agent_id: UUID | None = Query(None, alias="agentId"),
    due_from: date | None = Query(None, alias="dueFrom"),
    due_to: date | None = Query(None, alias="dueTo"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> TaskListResponse:
    items = await service.list_tasks(
        session,
        current_user.tenant_id,
        status=status_filter,
        agent_id=agent_id,
        due_from=due_from,
        due_to=due_to,
    )
    return TaskListResponse(
        items=[TaskOut.model_validate(i) for i in items],
        total=len(items),
    )


@router.post("", response_model=TaskOut, status_code=201)
async def create_task(
    payload: TaskCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> TaskOut:
    try:
        t = await service.create_task(
            session,
            current_user.tenant_id,
            title=payload.title,
            description=payload.description,
            status=payload.status,
            priority=payload.priority,
            due_date=payload.due_date,
            assignee_agent_ids=payload.assignee_agent_ids,
            created_by_user_id=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))
    await session.commit()

    result = await service.get_task_with_assignees(
        session, current_user.tenant_id, t.id,
    )
    return TaskOut.model_validate(result)


@router.get("/{task_id}", response_model=TaskOut)
async def get_task(
    task_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> TaskOut:
    result = await service.get_task_with_assignees(
        session, current_user.tenant_id, task_id,
    )
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task inexistent")
    return TaskOut.model_validate(result)


@router.patch("/{task_id}", response_model=TaskOut)
async def update_task(
    task_id: UUID,
    payload: TaskUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> TaskOut:
    # Separă "nu atinge due_date" de "șterge due_date" — ambele ajung None în
    # model_dump(exclude_unset=True) dacă câmpul e explicit None.
    data = payload.model_dump(exclude_unset=True)
    try:
        t = await service.update_task(
            session,
            current_user.tenant_id,
            task_id,
            title=data.get("title"),
            description=data.get("description"),
            status=data.get("status"),
            priority=data.get("priority"),
            due_date=data.get("due_date"),
            due_date_set=("due_date" in data),
            assignee_agent_ids=data.get("assignee_agent_ids"),
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))
    if t is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task inexistent")
    await session.commit()

    result = await service.get_task_with_assignees(
        session, current_user.tenant_id, t.id,
    )
    return TaskOut.model_validate(result)


@router.delete("/{task_id}", status_code=204)
async def delete_task(
    task_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    ok = await service.delete_task(
        session, current_user.tenant_id, task_id,
    )
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Task inexistent")
    await session.commit()
