"""
Modele pentru Facing Tracker — port 1:1 al feature-ului din
`adeplast-dashboard/services/facing_service.py`.

Oglindim fidel schema legacy (pentru paritate completă cu UI-ul și logica veche),
cu adaptările necesare pentru SaaS:
  - UUID în loc de INTEGER AUTOINCREMENT pentru PK-uri
  - `tenant_id` pe fiecare tabelă (izolare multi-tenant)
  - `store_name` rămâne TEXT liber (legacy folosea cheia `cheie_finala` din
    unified_store_agent_map ca identificator opac — NU avem FK la `stores`).

Cinci tabele — una pentru una cu legacy:
  facing_raioane        — nomenclator de raioane; arbore self-referential via parent_id
  facing_brands         — branduri (proprii + concurenți)
  facing_snapshots      — date lunare (store_name × raion × brand × luna → nr_fete)
  facing_history        — log audit al tuturor modificărilor
  facing_chain_brands   — matrice rețea → [branduri urmărite]
"""
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class FacingRaion(Base):
    """Raion urmărit (grup sau sub-raion). Arbore via `parent_id`.

    Semantică identică cu legacy:
      - parent_id NULL → grup părinte (ex: Constructii)
      - parent_id SET  → sub-raion (ex: Paleti, parent=Constructii)
    """

    __tablename__ = "facing_raioane"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_facing_raioane_tenant_name"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    parent_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("facing_raioane.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    # Pastrez INT-ul vechi pentru import din users.db legacy — nu e folosit in runtime.
    legacy_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class FacingBrand(Base):
    """Brand urmărit (propriu sau concurență)."""

    __tablename__ = "facing_brands"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_facing_brands_tenant_name"),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    color: Mapped[str] = mapped_column(String(20), nullable=False, default="#888888")
    is_own: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    legacy_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class FacingSnapshot(Base):
    """Nr. fețe pentru (store_name × raion × brand × luna).

    `store_name` e TEXT (cheia `cheie_finala` din mapping-ul Noemi — păstrăm
    legacy semantic: nu e FK la `stores`). `luna` păstrează formatul "YYYY-MM".
    """

    __tablename__ = "facing_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "store_name",
            "raion_id",
            "brand_id",
            "luna",
            name="uq_facing_snap_tenant_store_raion_brand_luna",
        ),
    )

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    store_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    raion_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("facing_raioane.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    brand_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("facing_brands.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    luna: Mapped[str] = mapped_column(String(7), nullable=False, index=True)  # YYYY-MM
    nr_fete: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    updated_by: Mapped[str | None] = mapped_column(String(255), nullable=True)


class FacingHistory(Base):
    """Audit-log pentru toate modificările de snapshots.

    Legacy folosea raion_id=0 / brand_id=0 ca markers pentru ștergeri la nivel
    de magazin. În SaaS lăsăm raion_id/brand_id NULLABLE și nu punem FK (audit
    log trebuie să supraviețuiască ștergerii entităților referențiate).
    """

    __tablename__ = "facing_history"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    store_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    raion_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True, index=True)
    brand_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True, index=True)
    luna: Mapped[str] = mapped_column(String(7), nullable=False)
    nr_fete: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    action: Mapped[str] = mapped_column(String(64), nullable=False, default="update")
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    changed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Optional legacy_raion_id / legacy_brand_id pentru randuri importate unde
    # raionul/brandul original nu mai exista in canonical (0 = marker special).
    legacy_raion_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    legacy_brand_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class FacingChainBrand(Base):
    """Matrice rețea → branduri urmărite. Cheie compusă (tenant, chain, brand)."""

    __tablename__ = "facing_chain_brands"
    __table_args__ = (
        PrimaryKeyConstraint("tenant_id", "chain", "brand_id", name="pk_facing_chain_brands"),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    chain: Mapped[str] = mapped_column(String(100), nullable=False)
    brand_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("facing_brands.id", ondelete="CASCADE"),
        nullable=False,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class FacingRaionCompetitor(Base):
    """Matrice (own_brand × competitor × sub_raion) pentru Dash Face Tracker.

    Pentru fiecare sub-raion + brand propriu, stochează lista brandurilor cu
    care concurează la acel sub-raion. Înlocuiește configul hardcodat per
    scope cu decizii configurabile din UI.
    """

    __tablename__ = "facing_raion_competitors"
    __table_args__ = (
        PrimaryKeyConstraint(
            "tenant_id", "raion_id", "own_brand_id", "competitor_brand_id",
            name="pk_facing_raion_competitors",
        ),
    )

    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    raion_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("facing_raioane.id", ondelete="CASCADE"),
        nullable=False,
    )
    own_brand_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("facing_brands.id", ondelete="CASCADE"),
        nullable=False,
    )
    competitor_brand_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("facing_brands.id", ondelete="CASCADE"),
        nullable=False,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
