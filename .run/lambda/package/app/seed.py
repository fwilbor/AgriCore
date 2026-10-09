"""Seed the database with realistic, *deterministic* mock data.

    python -m app.seed               # wipe + recreate tables, insert data, upload files to S3
    python -m app.seed --files-only  # only re-upload service-report files (after an S3 emulator restart)

A fixed random seed means every run produces the same numbers, so the
dashboard you rehearse with is the dashboard you demo with.
"""
import argparse
import random
from datetime import date, datetime, time, timedelta, timezone
from io import BytesIO

from sqlalchemy import func, select
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from . import storage
from .database import Base, SessionLocal, engine
from .enums import EquipmentStatus, EquipmentType, JobPriority, JobStatus, Role
from .models import AuditLog, Equipment, Farm, FieldJob, ServiceReport, User
from .security import hash_password

DEMO_PASSWORD = "AgriCore2026!"
TODAY = date.today()

# (name, region, capacity, supervisor email, units, in_maintenance, retired)
FARMS = [
    ("Prairie Crest North", "Northern Plains", 16, "maria.gonzalez", 12, 2, 1),
    ("Willow Creek Elevator", "Northern Plains", 10, "maria.gonzalez", 8, 3, 0),   # 37.5% -> flagged
    ("Cedar Bend Farm", "River Valley", 14, "darnell.brooks", 10, 2, 0),
    ("Red Clay Acres", "Eastern Uplands", 12, "darnell.brooks", 9, 1, 1),
    ("Golden Hollow Ranch", "Southern Plains", 12, "priya.patel", 10, 4, 0),       # 40% -> flagged
    ("Bluestem Grain Site", "Southern Plains", 10, "priya.patel", 7, 2, 0),        # 28.6% -> just under
]

SUPERVISORS = [
    ("maria.gonzalez", "Maria Gonzalez"),
    ("darnell.brooks", "Darnell Brooks"),
    ("priya.patel", "Priya Patel"),
]

# Two farm hands per farm, in FARMS order. The first is the demo login.
FARM_HANDS = [
    ("farmhand", "Tyler Hansen"), ("grace.lindqvist", "Grace Lindqvist"),
    ("owen.mercer", "Owen Mercer"), ("hannah.ruiz", "Hannah Ruiz"),
    ("marcus.bell", "Marcus Bell"), ("lena.ortiz", "Lena Ortiz"),
    ("caleb.novak", "Caleb Novak"), ("aisha.grant", "Aisha Grant"),
    ("diego.ramos", "Diego Ramos"), ("emma.clarke", "Emma Clarke"),
    ("noah.whitaker", "Noah Whitaker"), ("zoe.kim", "Zoe Kim"),
]
# These hands get no active jobs, so "farmhands with active jobs" < "direct reports".
IDLE_HANDS = {"owen.mercer", "aisha.grant", "zoe.kim"}

# model -> (type, serial prefix, probability a finished job failed)
MODELS = {
    "John Deere 8R 410": (EquipmentType.TRACTOR, "JD8R", 0.08),
    "Case IH Magnum 340": (EquipmentType.TRACTOR, "CIHM", 0.12),
    "New Holland T7.315": (EquipmentType.TRACTOR, "NHT7", 0.18),
    "John Deere S790": (EquipmentType.COMBINE, "JDS7", 0.10),
    "Case IH Axial-Flow 8250": (EquipmentType.COMBINE, "CIAF", 0.22),
    "Claas Lexion 8800": (EquipmentType.COMBINE, "CLLX", 0.32),
    "John Deere R4045": (EquipmentType.SPRAYER, "JDR4", 0.10),
    "Hagie STS16": (EquipmentType.SPRAYER, "HGST", 0.26),
    "Cornell 6RB": (EquipmentType.IRRIGATION_PUMP, "CN6R", 0.05),
    "Valley VP-50 Pivot Pump": (EquipmentType.IRRIGATION_PUMP, "VLVP", 0.15),
}

FIELDS = ["North 40", "Creek Bottom", "East Quarter", "Section 12", "Home Place",
          "West Pivot", "River Flats", "South 80"]
JOB_TITLES = {
    EquipmentType.TRACTOR: ["Spring planting - {f}", "Tillage pass - {f}", "Grain cart hauling - {f}"],
    EquipmentType.COMBINE: ["Corn harvest - {f}", "Soybean harvest - {f}", "Wheat harvest - {f}"],
    EquipmentType.SPRAYER: ["Herbicide application - {f}", "Fungicide spray - {f}"],
    EquipmentType.IRRIGATION_PUMP: ["Pivot irrigation cycle - {f}", "Pump flow test - {f}"],
}
FAILURE_NOTES = [
    "Hydraulic pressure dropped mid-pass; hose replaced, job aborted.",
    "Engine overheat warning - radiator clogged with chaff.",
    "GPS guidance lost signal repeatedly; operator halted work.",
    "Header drive belt snapped. Parts on order.",
    "Nozzle clogging across boom section 3; uneven coverage.",
    "Pump cavitation detected; suction line air leak.",
]
SUCCESS_NOTES = [
    "Routine post-job inspection. Fluids topped off, no issues.",
    "Greased all fittings; tire pressure adjusted to spec.",
    "Air filter cleaned; minor wear on bearings noted for next service.",
    "Calibration check passed. Yield monitor data exported.",
]


# ------------------------------------------------------------------ files
def make_pdf(lines: list[str]) -> bytes:
    """Build a tiny, valid one-page PDF by hand (no extra library needed)."""
    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    stream = "BT /F1 12 Tf 50 750 Td 16 TL " + " ".join(f"({esc(l)}) '" for l in lines) + " ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        "/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream",
    ]
    out, offsets = b"%PDF-1.4\n", []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{body}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{o:010d} 00000 n \n" for o in offsets).encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return out


def report_body(report: ServiceReport, job: FieldJob) -> bytes:
    """Regenerable file content, so --files-only can rebuild identical files."""
    eq = job.equipment
    lines = [
        "PRAIRIE CREST AGRICULTURAL COOPERATIVE",
        f"Service Report #{report.id}  -  Field Job #{job.id}",
        f"Job: {job.title}",
        f"Equipment: {eq.serial_number} ({eq.model})",
        f"Farm: {eq.farm.name}",
        f"Outcome: {job.status.value}",
        f"Operator: {job.operator.full_name if job.operator else 'n/a'}",
        f"Notes: {report.notes}",
    ]
    if report.content_type == "application/pdf":
        return make_pdf(lines)
    return ("\n".join(lines) + "\n").encode()


def upload_report_file(report: ServiceReport, job: FieldJob) -> None:
    body = report_body(report, job)
    storage.upload_file(BytesIO(body), report.file_key, report.content_type)
    report.file_size = len(body)


# --------------------------------------------------------------- builders
def email(handle: str) -> str:
    return f"{handle}@prairiecrest.coop"


def seed(db: Session) -> None:
    rng = random.Random(17)
    pw = hash_password(DEMO_PASSWORD)  # hash once - bcrypt is slow on purpose

    # --- people without a farm yet
    admin = User(email=email("admin"), full_name="Jordan Reyes", role=Role.ADMIN,
                 job_title="Farm Operations Admin", hashed_password=pw)
    auditor = User(email=email("auditor"), full_name="Sam Whitfield", role=Role.AUDITOR,
                   job_title="Compliance Auditor", hashed_password=pw)
    supervisors = {
        handle: User(email=email(handle), full_name=name, role=Role.ADMIN,
                     job_title="Regional Agronomy Supervisor", hashed_password=pw)
        for handle, name in SUPERVISORS
    }
    db.add_all([admin, auditor, *supervisors.values()])
    db.flush()

    # --- farms
    farms = []
    for name, region, cap, sup, *_ in FARMS:
        farm = Farm(name=name, location_region=region, capacity=cap, supervisor_id=supervisors[sup].id)
        farms.append(farm)
    db.add_all(farms)
    db.flush()
    supervisors["maria.gonzalez"].farm_id = farms[0].id  # supervisors' home farms
    supervisors["darnell.brooks"].farm_id = farms[2].id
    supervisors["priya.patel"].farm_id = farms[4].id

    # --- farm hands, two per farm, reporting to their farm's supervisor
    hands_by_farm: dict[int, list[User]] = {}
    hand_handles: dict[int, str] = {}
    for i, (handle, name) in enumerate(FARM_HANDS):
        farm = farms[i // 2]
        sup_handle = FARMS[i // 2][3]
        hand = User(email=email(handle), full_name=name, role=Role.FARM_HAND, job_title="Farm Hand",
                    hashed_password=pw, farm_id=farm.id, supervisor_id=supervisors[sup_handle].id)
        db.add(hand)
        db.flush()
        hands_by_farm.setdefault(farm.id, []).append(hand)
        hand_handles[hand.id] = handle

    # --- equipment
    model_names = list(MODELS)
    serial_counter = 1
    all_equipment: list[Equipment] = []
    for farm, (_, _, _, _, units, maint, retired) in zip(farms, FARMS):
        statuses = (
            [EquipmentStatus.MAINTENANCE] * maint
            + [EquipmentStatus.RETIRED] * retired
            + [EquipmentStatus.IN_USE if k % 5 in (0, 2) else EquipmentStatus.IDLE
               for k in range(units - maint - retired)]
        )
        rng.shuffle(statuses)
        hands = hands_by_farm[farm.id]
        for k, status in enumerate(statuses):
            model = model_names[(serial_counter * 3 + k) % len(model_names)]
            etype, prefix, _ = MODELS[model]
            active = status in (EquipmentStatus.IDLE, EquipmentStatus.IN_USE)
            low = active and serial_counter % 6 == 0
            fuel = round(rng.uniform(4, 19) if low else rng.uniform(24, 98), 1)
            assigned = None
            if status != EquipmentStatus.RETIRED and k % 4 != 3:  # ~75% assigned
                assigned = hands[k % 2].id
            eq = Equipment(
                serial_number=f"{prefix}-{2018 + serial_counter % 7}-{serial_counter:04d}",
                model=model,
                equipment_type=etype,
                status=status,
                fuel_level=fuel,
                facility_id=farm.id,
                assigned_to_id=assigned,
                last_service_date=TODAY - timedelta(days=rng.randint(10, 300)),
            )
            all_equipment.append(eq)
            serial_counter += 1
    db.add_all(all_equipment)
    db.flush()

    # --- co-location discrepancies: units "borrowed" by hands at another farm
    def first_hand(farm_idx: int, which: int = 0) -> User:
        return hands_by_farm[farms[farm_idx].id][which]

    borrowed = [(1, first_hand(0, 0)), (2, first_hand(3, 0)), (4, first_hand(5, 0)),
                (4, first_hand(2, 1)), (5, first_hand(4, 1))]
    reassigned: set[int] = set()
    for farm_idx, hand in borrowed:
        unit = next(e for e in all_equipment
                    if e.facility_id == farms[farm_idx].id and e.status == EquipmentStatus.IDLE
                    and e.id not in reassigned)
        unit.assigned_to_id = hand.id
        reassigned.add(unit.id)

    # --- field jobs
    def operator_for(eq: Equipment, active: bool) -> User:
        hands = hands_by_farm[eq.facility_id]
        if eq.assigned_to_id and not (active and hand_handles[eq.assigned_to_id] in IDLE_HANDS):
            return db.get(User, eq.assigned_to_id)
        usable = [h for h in hands if not (active and hand_handles[h.id] in IDLE_HANDS)]
        return usable[0] if usable else hands[0]

    def title_for(eq: Equipment) -> str:
        return rng.choice(JOB_TITLES[eq.equipment_type]).format(f=rng.choice(FIELDS))

    def priority() -> JobPriority:
        return rng.choices(list(JobPriority), weights=[30, 50, 20])[0]

    jobs: list[FieldJob] = []
    for eq in all_equipment:
        fail_p = MODELS[eq.model][2]
        for _ in range(rng.randint(2, 5)):  # history
            failed = rng.random() < fail_p
            jobs.append(FieldJob(
                title=title_for(eq), priority=priority(),
                status=JobStatus.FAILED if failed else JobStatus.COMPLETED,
                equipment_id=eq.id, operator_id=operator_for(eq, False).id,
                scheduled_date=TODAY - timedelta(days=rng.randint(5, 150)),
            ))
        if eq.status == EquipmentStatus.IN_USE:
            jobs.append(FieldJob(
                title=title_for(eq), priority=priority(), status=JobStatus.IN_PROGRESS,
                equipment_id=eq.id, operator_id=operator_for(eq, True).id,
                scheduled_date=TODAY - timedelta(days=rng.randint(0, 2)),
            ))
        if eq.status in (EquipmentStatus.IDLE, EquipmentStatus.IN_USE) and rng.random() < 0.45:
            jobs.append(FieldJob(
                title=title_for(eq), priority=priority(), status=JobStatus.PENDING,
                equipment_id=eq.id, operator_id=operator_for(eq, True).id,
                scheduled_date=TODAY + timedelta(days=rng.randint(1, 21)),
            ))
    db.add_all(jobs)
    db.flush()

    # --- service reports: every failed job + ~1 in 5 completed jobs
    reports: list[tuple[ServiceReport, FieldJob]] = []
    for job in jobs:
        if job.status == JobStatus.FAILED:
            notes, ctype, ext, kind = rng.choice(FAILURE_NOTES), "application/pdf", "pdf", "diagnostic"
        elif job.status == JobStatus.COMPLETED and rng.random() < 0.2:
            notes, ctype, ext, kind = rng.choice(SUCCESS_NOTES), "text/plain", "txt", "service-log"
        else:
            continue
        filename = f"{kind}-job-{job.id}.{ext}"
        key = storage.build_key(job.id, filename)
        report = ServiceReport(
            field_job_id=job.id, file_key=key, file_url=f"s3://{storage.get_settings().s3_bucket}/{key}",
            file_name=filename, content_type=ctype, file_size=0, notes=notes,
            uploaded_by_id=job.operator_id,
            created_at=datetime.combine(job.scheduled_date + timedelta(days=1), time(16, 30),
                                        tzinfo=timezone.utc),
        )
        db.add(report)
        reports.append((report, job))
    db.flush()

    db.add(AuditLog(action="SEED", entity_type="system",
                    detail=f"Database seeded: {len(farms)} farms, {serial_counter - 1} equipment, "
                           f"{len(jobs)} jobs, {len(reports)} service reports"))

    # --- upload report files to S3 (boto3)
    storage.ensure_bucket()
    for report, job in reports:
        db.refresh(job)
        upload_report_file(report, job)
    db.commit()

    print(f"Seeded {len(farms)} farms, {serial_counter - 1} equipment units, {len(jobs)} field jobs, "
          f"{len(reports)} service reports, {db.scalar(select(func.count(User.id)))} users.")


def reupload_files(db: Session) -> None:
    storage.ensure_bucket()
    reports = db.scalars(select(ServiceReport)).all()
    for report in reports:
        upload_report_file(report, report.field_job)
    db.commit()
    print(f"Re-uploaded {len(reports)} service report files to S3.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--files-only", action="store_true", help="only re-upload report files to S3")
    args = parser.parse_args()

    if args.files_only:
        with SessionLocal() as db:
            try:
                reupload_files(db)
            except ProgrammingError:
                raise SystemExit("Tables don't exist yet - run bin/seed.sh first.")
        return

    print("Dropping and recreating all tables...")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed(db)
    print(f"\nDemo logins (password for all: {DEMO_PASSWORD})")
    print("  Farm Operations Admin : admin@prairiecrest.coop")
    print("  Farm Hand             : farmhand@prairiecrest.coop  (Tyler Hansen)")
    print("  Auditor (read-only)   : auditor@prairiecrest.coop")


if __name__ == "__main__":
    main()
