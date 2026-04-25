"""Service pentru Taskuri — CRUD cu scope tenant_id.

Design:
  - Fiecare read/write filtrează explicit pe `tenant_id` (vezi auth/deps.py).
  - Asignările sunt gestionate ca set: la update `assignee_agent_ids`, șterg
    mai întâi toate asignările existente ale task-ului, apoi inserez lista
    nouă. Mai simplu decât diff; pentru un task volumul e mic (≤zeci de
    agenți). Idempotent.
  - UNIQUE (task_id, agent_id) pe DB previne duplicate accidentale chiar și
    sub paralelism ridicat.
"""
from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.agents.models import Agent
from app.modules.taskuri.models import Task, TaskAssignment


async def list_tasks(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    status: str | None = None,
    agent_id: UUID | None = None,
    due_from: date | None = None,
    due_to: date | None = None,
) -> list[dict]:
    """Wrapper single-tenant; foloseste list_tasks_by_tenants."""
    return await list_tasks_by_tenants(
        session, [tenant_id],
        status=status, agent_id=agent_id,
        due_from=due_from, due_to=due_to,
    )


async def list_tasks_by_tenants(
    session: AsyncSession,
    tenant_ids: list[UUID],
    *,
    status: str | None = None,
    agent_id: UUID | None = None,
    due_from: date | None = None,
    due_to: date | None = None,
) -> list[dict]:
    """Returnează lista de task-uri cu assignees denormalizați.

    Filtre opționale:
      - status: exact match (TODO/IN_PROGRESS/DONE)
      - agent_id: task-uri unde agent-ul apare ca asignat
      - due_from / due_to: interval pe due_date (inclusiv)
    """
    if not tenant_ids:
        return []
    q = select(Task).where(Task.tenant_id.in_(tenant_ids))
    if status:
        q = q.where(Task.status == status.upper())
    if due_from is not None:
        q = q.where(Task.due_date >= due_from)
    if due_to is not None:
        q = q.where(Task.due_date <= due_to)

    if agent_id is not None:
        # Semi-join prin subselect (nu JOIN cu DISTINCT — mai curat).
        q = q.where(
            Task.id.in_(
                select(TaskAssignment.task_id).where(
                    TaskAssignment.agent_id == agent_id
                )
            )
        )

    # Sortare: task-urile cu due_date cel mai apropiat prima data, NULL la final.
    q = q.order_by(Task.due_date.asc().nulls_last(), Task.created_at.desc())

    tasks = list((await session.execute(q)).scalars().all())
    if not tasks:
        return []

    # Încărcăm în bulk asignările + agenții (evităm N+1).
    task_ids = [t.id for t in tasks]
    rows = (await session.execute(
        select(TaskAssignment, Agent)
        .join(Agent, Agent.id == TaskAssignment.agent_id)
        .where(TaskAssignment.task_id.in_(task_ids))
    )).all()
    assignees_by_task: dict[UUID, list[dict]] = {tid: [] for tid in task_ids}
    for ta, ag in rows:
        assignees_by_task[ta.task_id].append(
            {"agent_id": ag.id, "agent_name": ag.full_name}
        )

    return [
        {
            "id": t.id,
            "title": t.title,
            "description": t.description,
            "status": t.status,
            "priority": t.priority,
            "due_date": t.due_date,
            "created_by_user_id": t.created_by_user_id,
            "created_at": t.created_at,
            "updated_at": t.updated_at,
            "assignees": assignees_by_task.get(t.id, []),
        }
        for t in tasks
    ]


async def get_task(
    session: AsyncSession, tenant_id: UUID, task_id: UUID,
) -> Task | None:
    return (await session.execute(
        select(Task).where(Task.tenant_id == tenant_id, Task.id == task_id)
    )).scalar_one_or_none()


async def get_task_with_assignees(
    session: AsyncSession, tenant_id: UUID, task_id: UUID,
) -> dict | None:
    t = await get_task(session, tenant_id, task_id)
    if t is None:
        return None
    rows = (await session.execute(
        select(TaskAssignment, Agent)
        .join(Agent, Agent.id == TaskAssignment.agent_id)
        .where(TaskAssignment.task_id == t.id)
    )).all()
    return {
        "id": t.id,
        "title": t.title,
        "description": t.description,
        "status": t.status,
        "priority": t.priority,
        "due_date": t.due_date,
        "created_by_user_id": t.created_by_user_id,
        "created_at": t.created_at,
        "updated_at": t.updated_at,
        "assignees": [
            {"agent_id": ag.id, "agent_name": ag.full_name}
            for _, ag in rows
        ],
    }


async def _validate_agents(
    session: AsyncSession, tenant_id: UUID, agent_ids: list[UUID],
) -> list[UUID]:
    """Verifică că toți agenții aparțin tenant-ului curent. Întoarce lista
    deduplicated. Raise ValueError dacă vreunul nu aparține/nu există."""
    if not agent_ids:
        return []
    unique = list(dict.fromkeys(agent_ids))  # păstrează ordinea, dedupe
    found = (await session.execute(
        select(Agent.id).where(
            and_(Agent.tenant_id == tenant_id, Agent.id.in_(unique))
        )
    )).scalars().all()
    found_set = set(found)
    missing = [a for a in unique if a not in found_set]
    if missing:
        raise ValueError(f"Agenți invalizi pentru tenant: {missing}")
    return unique


async def create_task(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    title: str,
    description: str = "",
    status: str = "TODO",
    priority: str = "medium",
    due_date: date | None = None,
    assignee_agent_ids: list[UUID] | None = None,
    created_by_user_id: UUID | None = None,
) -> Task:
    agent_ids = await _validate_agents(
        session, tenant_id, assignee_agent_ids or [],
    )

    t = Task(
        tenant_id=tenant_id,
        title=title.strip(),
        description=(description or "").strip(),
        status=status,
        priority=priority,
        due_date=due_date,
        created_by_user_id=created_by_user_id,
    )
    session.add(t)
    await session.flush()

    for aid in agent_ids:
        session.add(TaskAssignment(task_id=t.id, agent_id=aid))
    await session.flush()
    return t


async def update_task(
    session: AsyncSession,
    tenant_id: UUID,
    task_id: UUID,
    *,
    title: str | None = None,
    description: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    due_date: date | None = None,
    due_date_set: bool = False,  # distinge "None = nu atinge" de "None = clear"
    assignee_agent_ids: list[UUID] | None = None,
) -> Task | None:
    t = await get_task(session, tenant_id, task_id)
    if t is None:
        return None

    if title is not None:
        t.title = title.strip()
    if description is not None:
        t.description = description.strip()
    if status is not None:
        t.status = status
    if priority is not None:
        t.priority = priority
    if due_date_set:
        t.due_date = due_date

    if assignee_agent_ids is not None:
        agent_ids = await _validate_agents(
            session, tenant_id, assignee_agent_ids,
        )
        # Reset asignări: șterg tot, reinsert setul nou.
        await session.execute(
            delete(TaskAssignment).where(TaskAssignment.task_id == t.id)
        )
        for aid in agent_ids:
            session.add(TaskAssignment(task_id=t.id, agent_id=aid))

    await session.flush()
    return t


async def delete_task(
    session: AsyncSession, tenant_id: UUID, task_id: UUID,
) -> bool:
    t = await get_task(session, tenant_id, task_id)
    if t is None:
        return False
    await session.delete(t)  # CASCADE șterge și asignările (ondelete=CASCADE)
    await session.flush()
    return True
