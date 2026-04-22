from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.core.schemas import APISchema


class AgentOut(APISchema):
    id: UUID
    full_name: str
    email: str | None
    phone: str | None
    active: bool
    created_at: datetime


class CreateAgentRequest(APISchema):
    full_name: str = Field(min_length=1, max_length=255)
    email: str | None = None
    phone: str | None = None


class AgentAliasOut(APISchema):
    id: UUID
    raw_agent: str
    agent_id: UUID
    resolved_by_user_id: UUID | None
    resolved_at: datetime


class CreateAgentAliasRequest(APISchema):
    raw_agent: str = Field(min_length=1, max_length=255)
    agent_id: UUID


class UpdateAgentAliasRequest(APISchema):
    agent_id: UUID  # reasignează la alt agent canonic


class UnmappedAgentRow(APISchema):
    raw_agent: str
    row_count: int
    total_amount: Decimal


class AssignmentOut(APISchema):
    id: UUID
    agent_id: UUID
    store_id: UUID
    created_at: datetime


class AssignRequest(APISchema):
    agent_id: UUID
    store_id: UUID


class BulkImportResponse(APISchema):
    created_agents: int
    created_aliases: int
    skipped: int
    errors: list[str]


class MergeAgentsRequest(APISchema):
    primary_id: UUID
    duplicate_ids: list[UUID] = Field(min_length=1)


class MergeAgentsResponse(APISchema):
    primary_id: UUID
    merged_count: int
    aliases_reassigned: int
    sales_reassigned: int
    assignments_reassigned: int
    assignments_deduped: int


class BulkSetActiveRequest(APISchema):
    ids: list[UUID] = Field(min_length=1, max_length=500)
    active: bool


class BulkSetActiveResponse(APISchema):
    updated: int
