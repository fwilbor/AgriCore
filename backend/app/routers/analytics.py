"""Analytics endpoints - one per key business question.

Each query is built with SQLAlchemy Core expressions that compile to a single
SQL statement with JOIN / GROUP BY / COUNT(...) FILTER / HAVING, so PostgreSQL
does the aggregation instead of Python looping over rows. The equivalent raw
SQL for every query is in docs/analytics.sql - run it in psql to compare.

Access: Farm Operations Admin and Auditor (Farm Hands get 403).
"""
from fastapi import APIRouter, Query
from sqlalchemy import and_, distinct, func, select
from sqlalchemy.orm import Session, aliased

from ..deps import AdminOrAuditor, DbSession
from ..enums import (
    ACTIVE_EQUIPMENT_STATUSES,
    ACTIVE_JOB_STATUSES,
    EquipmentStatus,
    JobStatus,
    Role,
)
from ..models import Equipment, Farm, FieldJob, User
from ..schemas import (
    CoLocationItem,
    CoLocationOut,
    DashboardSummary,
    LowFuelItem,
    LowFuelOut,
    MaintenanceFlagItem,
    MaintenanceFlagOut,
    ReliabilityItem,
    SupervisorActivityItem,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


# ------------------------------------------------------------ Q1 Low fuel
def query_low_fuel(db: Session, threshold: float) -> list[LowFuelItem]:
    stmt = (
        select(
            Equipment.id,
            Equipment.serial_number,
            Equipment.model,
            Equipment.status,
            Equipment.fuel_level,
            Farm.name.label("farm_name"),
        )
        .join(Farm, Equipment.facility_id == Farm.id)
        .where(Equipment.status.in_(ACTIVE_EQUIPMENT_STATUSES), Equipment.fuel_level < threshold)
        .order_by(Equipment.fuel_level)
    )
    return [LowFuelItem(**row._mapping) for row in db.execute(stmt)]


@router.get("/low-fuel", response_model=LowFuelOut)
def low_fuel(db: DbSession, _: AdminOrAuditor, threshold: float = Query(20, ge=0, le=100)):
    """Which active (Idle / In-Use) units are below `threshold` % fuel?"""
    items = query_low_fuel(db, threshold)
    return LowFuelOut(threshold=threshold, count=len(items), items=items)


# ------------------------------------------------------ Q2 Co-location
def query_colocation(db: Session) -> list[CoLocationItem]:
    # The same tables appear twice in different roles, so we alias them.
    hand = aliased(User, name="hand")
    equipment_farm = aliased(Farm, name="equipment_farm")
    hand_farm = aliased(Farm, name="hand_farm")
    stmt = (
        select(
            Equipment.id.label("equipment_id"),
            Equipment.serial_number,
            Equipment.model,
            equipment_farm.name.label("equipment_farm"),
            hand.full_name.label("farmhand"),
            hand_farm.name.label("farmhand_farm"),
        )
        .join(equipment_farm, Equipment.facility_id == equipment_farm.id)
        .join(hand, Equipment.assigned_to_id == hand.id)
        .outerjoin(hand_farm, hand.farm_id == hand_farm.id)
        # IS DISTINCT FROM treats NULL safely (a hand with no farm counts as a mismatch)
        .where(hand.role == Role.FARM_HAND, hand.farm_id.is_distinct_from(Equipment.facility_id))
        .order_by(equipment_farm.name, Equipment.serial_number)
    )
    return [CoLocationItem(**row._mapping) for row in db.execute(stmt)]


@router.get("/co-location", response_model=CoLocationOut)
def co_location(db: DbSession, _: AdminOrAuditor):
    """Equipment assigned to a farmhand whose home farm differs from the unit's farm."""
    items = query_colocation(db)
    return CoLocationOut(count=len(items), items=items)


# ---------------------------------------------------- Q3 Reliability
@router.get("/reliability", response_model=list[ReliabilityItem])
def reliability(db: DbSession, _: AdminOrAuditor):
    """Completed vs Failed field jobs per equipment model."""
    completed = func.count().filter(FieldJob.status == JobStatus.COMPLETED)
    failed = func.count().filter(FieldJob.status == JobStatus.FAILED)
    stmt = (
        select(Equipment.model, completed.label("completed"), failed.label("failed"))
        .join(FieldJob, FieldJob.equipment_id == Equipment.id)
        .where(FieldJob.status.in_([JobStatus.COMPLETED, JobStatus.FAILED]))
        .group_by(Equipment.model)
    )
    items = []
    for model, done, bad in db.execute(stmt):
        total = done + bad
        items.append(
            ReliabilityItem(
                model=model,
                completed=done,
                failed=bad,
                total_finished=total,
                completion_rate=round(done / total, 4),
                failure_rate=round(bad / total, 4),
            )
        )
    return sorted(items, key=lambda i: i.failure_rate, reverse=True)


# ------------------------------------------------ Q4 Maintenance flags
def query_maintenance(db: Session, threshold: float, only_flagged: bool) -> list[MaintenanceFlagItem]:
    total = func.count(Equipment.id)
    in_maint = func.count(Equipment.id).filter(Equipment.status == EquipmentStatus.MAINTENANCE)
    pct = in_maint * 1.0 / func.nullif(total, 0)  # NULLIF avoids divide-by-zero
    stmt = (
        select(Farm.id, Farm.name, total.label("total"), in_maint.label("in_maint"))
        # Retired units are excluded from the fleet size; outer join keeps empty farms.
        .outerjoin(
            Equipment,
            and_(Equipment.facility_id == Farm.id, Equipment.status != EquipmentStatus.RETIRED),
        )
        .group_by(Farm.id, Farm.name)
        .order_by(pct.desc().nulls_last(), Farm.name)
    )
    if only_flagged:
        stmt = stmt.having(pct > threshold)  # HAVING filters *after* grouping
    items = []
    for farm_id, name, tot, maint in db.execute(stmt):
        share = maint / tot if tot else 0.0
        items.append(
            MaintenanceFlagItem(
                farm_id=farm_id,
                farm_name=name,
                total_equipment=tot,
                in_maintenance=maint,
                maintenance_pct=round(share, 4),
                flagged=share > threshold,
            )
        )
    return items


@router.get("/maintenance-flags", response_model=MaintenanceFlagOut)
def maintenance_flags(
    db: DbSession,
    _: AdminOrAuditor,
    threshold: float = Query(0.30, ge=0, le=1),
    only_flagged: bool = False,
):
    """Farms with more than `threshold` (default 30%) of their fleet in Maintenance."""
    items = query_maintenance(db, threshold, only_flagged)
    return MaintenanceFlagOut(
        threshold=threshold, flagged_count=sum(i.flagged for i in items), items=items
    )


# --------------------------------------------- Q5 Supervisor reporting lines
@router.get("/supervisor-activity", response_model=list[SupervisorActivityItem])
def supervisor_activity(db: DbSession, _: AdminOrAuditor, supervisor_id: int | None = None):
    """For each Regional Agronomy Supervisor: how many of their farmhands have
    active (Pending / In-Progress) field jobs?"""
    sup = aliased(User, name="sup")
    hand = aliased(User, name="hand")
    stmt = (
        select(
            sup.id,
            sup.full_name,
            func.count(distinct(hand.id)).label("direct_reports"),
            func.count(distinct(hand.id)).filter(FieldJob.id.is_not(None)).label("with_active"),
            func.count(distinct(FieldJob.id)).label("active_jobs"),
        )
        .join(hand, hand.supervisor_id == sup.id)
        .outerjoin(
            FieldJob,
            and_(FieldJob.operator_id == hand.id, FieldJob.status.in_(ACTIVE_JOB_STATUSES)),
        )
        .where(hand.role == Role.FARM_HAND, hand.is_active.is_(True))
        .group_by(sup.id, sup.full_name)
        .order_by(sup.full_name)
    )
    if supervisor_id is not None:
        stmt = stmt.where(sup.id == supervisor_id)
    return [
        SupervisorActivityItem(
            supervisor_id=sid,
            supervisor_name=name,
            direct_reports=reports,
            reports_with_active_jobs=with_active,
            active_jobs=jobs,
        )
        for sid, name, reports, with_active, jobs in db.execute(stmt)
    ]


# ------------------------------------------------------------- Summary
@router.get("/summary", response_model=DashboardSummary)
def summary(db: DbSession, _: AdminOrAuditor):
    """Headline numbers for the dashboard metric cards."""
    equipment_by_status = dict(
        db.execute(select(Equipment.status, func.count()).group_by(Equipment.status)).all()
    )
    jobs_by_status = dict(
        db.execute(select(FieldJob.status, func.count()).group_by(FieldJob.status)).all()
    )
    done = jobs_by_status.get(JobStatus.COMPLETED, 0)
    finished = done + jobs_by_status.get(JobStatus.FAILED, 0)
    return DashboardSummary(
        total_farms=db.scalar(select(func.count(Farm.id))),
        total_equipment=sum(equipment_by_status.values()),
        equipment_by_status={s.value: equipment_by_status.get(s, 0) for s in EquipmentStatus},
        jobs_by_status={s.value: jobs_by_status.get(s, 0) for s in JobStatus},
        low_fuel_count=len(query_low_fuel(db, 20)),
        maintenance_flagged_farms=len(query_maintenance(db, 0.30, only_flagged=True)),
        colocation_discrepancies=len(query_colocation(db)),
        overall_completion_rate=round(done / finished, 4) if finished else 0.0,
    )
