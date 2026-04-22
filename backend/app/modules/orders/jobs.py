"""
Registry in-memory pentru job-uri de import orders — design identic cu
`sales.jobs`, dar cu alte etape (fără Alocare).
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4


@dataclass
class JobStage:
    key: str
    label: str
    progress: float = 0.0
    done: bool = False


@dataclass
class Job:
    id: UUID
    tenant_id: UUID
    status: str = "pending"
    stages: list[JobStage] = field(default_factory=list)
    current_stage: str | None = None
    overall_progress: float = 0.0
    result: dict[str, Any] | None = None
    error: str | None = None
    error_code: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


_STAGES_TEMPLATE = [
    ("parse_main", "Parsare Excel comenzi"),
    ("delete_old", "Ștergere snapshot existent (aceeași dată)"),
    ("insert", "Inserare raw_orders"),
    ("finalize", "Finalizare & audit"),
]


_jobs: dict[UUID, Job] = {}
_lock = asyncio.Lock()


async def create_job(tenant_id: UUID) -> Job:
    async with _lock:
        job = Job(
            id=uuid4(),
            tenant_id=tenant_id,
            stages=[JobStage(key=k, label=l) for k, l in _STAGES_TEMPLATE],
        )
        _jobs[job.id] = job
        _prune_old_locked()
        return job


def get_job(job_id: UUID) -> Job | None:
    return _jobs.get(job_id)


def has_active_job(tenant_id: UUID) -> Job | None:
    for j in _jobs.values():
        if j.tenant_id == tenant_id and j.status in ("pending", "running"):
            return j
    return None


async def set_status(job_id: UUID, status: str) -> None:
    async with _lock:
        job = _jobs.get(job_id)
        if job is None:
            return
        job.status = status
        job.updated_at = datetime.now(timezone.utc)


async def update_stage(
    job_id: UUID, stage_key: str, progress: float, *, done: bool = False,
) -> None:
    async with _lock:
        job = _jobs.get(job_id)
        if job is None:
            return
        clamped = max(0.0, min(100.0, progress))
        for s in job.stages:
            if s.key == stage_key:
                s.progress = clamped
                if done:
                    s.progress = 100.0
                    s.done = True
                break
        job.current_stage = stage_key
        job.overall_progress = sum(s.progress for s in job.stages) / max(len(job.stages), 1)
        job.updated_at = datetime.now(timezone.utc)


async def finish_stage(job_id: UUID, stage_key: str) -> None:
    await update_stage(job_id, stage_key, 100.0, done=True)


async def set_done(job_id: UUID, result: dict[str, Any]) -> None:
    async with _lock:
        job = _jobs.get(job_id)
        if job is None:
            return
        job.status = "done"
        job.result = result
        for s in job.stages:
            s.progress = 100.0
            s.done = True
        job.overall_progress = 100.0
        job.updated_at = datetime.now(timezone.utc)


async def set_error(job_id: UUID, *, message: str, code: str = "error") -> None:
    async with _lock:
        job = _jobs.get(job_id)
        if job is None:
            return
        job.status = "error"
        job.error = message
        job.error_code = code
        job.updated_at = datetime.now(timezone.utc)


def _prune_old_locked() -> None:
    now = datetime.now(timezone.utc)
    to_drop = [
        jid for jid, j in _jobs.items()
        if j.status in ("done", "error")
        and (now - j.updated_at).total_seconds() > 30 * 60
    ]
    for jid in to_drop:
        _jobs.pop(jid, None)
