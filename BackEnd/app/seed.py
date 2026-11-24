"""Seed reference data and a realistic demo dataset.

    python -m app.seed            # base data + demo data (only if the database is empty)
    python -m app.seed --base     # roles, permissions, settings, templates, leave types, admin only
    python -m app.seed --reset    # downgrade + re-run migrations first (DESTROYS DATA)

Demo credentials are printed at the end (and listed in README.md).
"""

import argparse
import random
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import select

import app.models  # noqa: F401
from app.core.config import BASE_DIR, settings
from app.core.database import SessionLocal
from app.core.deps import RequestContext
from app.core.permissions import DEFAULT_ROLE_PERMISSIONS, PERMISSION_CATALOG, ROLE_ADMIN, ROLE_DESCRIPTIONS, ROLE_HR
from app.core.security import hash_password
from app.core.timeutils import daterange, now_local, today_local
from app.models import (
    Attendance,
    Department,
    Designation,
    EmailTemplate,
    Employee,
    Holiday,
    LeaveRequest,
    LeaveType,
    Permission,
    Role,
    SystemSetting,
    User,
)
from app.models.enums import AdjustmentKind, AttendanceStatus
from app.services import (
    attendance_service,
    employee_service,
    leave_service,
    payroll_service,
    settings_service,
)
from app.services.calendar_service import WorkCalendar
from app.utils.email_templates import DEFAULT_TEMPLATES

ADMIN_EMAIL, ADMIN_PASSWORD = "admin@example.com", "Admin@123"
HR_EMAIL, HR_PASSWORD = "hr@example.com", "Hr@12345"
EMPLOYEE_PASSWORD = "Employee@123"


# ------------------------------------------------------------------------- base data
def seed_base(db) -> User:
    perms = {p.code: p for p in db.scalars(select(Permission))}
    for code, module, desc in PERMISSION_CATALOG:
        if code not in perms:
            perms[code] = Permission(code=code, module=module, description=desc)
            db.add(perms[code])
    db.flush()
    for name, codes in DEFAULT_ROLE_PERMISSIONS.items():
        role = db.scalar(select(Role).where(Role.name == name))
        if role is None:
            db.add(Role(name=name, description=ROLE_DESCRIPTIONS[name], is_system=True, permissions=[perms[c] for c in codes]))
        elif name == ROLE_ADMIN:
            role.permissions = list(perms.values())  # keep Admin complete when new permissions are added
    for key, (default, _, desc) in settings_service.DEFAULTS.items():
        if db.get(SystemSetting, key) is None:
            db.add(SystemSetting(key=key, value=default, description=desc))
    for tpl in DEFAULT_TEMPLATES:
        if not db.scalar(select(EmailTemplate).where(EmailTemplate.code == tpl["code"])):
            db.add(EmailTemplate(**tpl))
    for lt in [
        dict(name="Casual Leave", code="CL", annual_quota=12, is_paid=True, color="#6366f1", description="Personal errands and short breaks"),
        dict(name="Sick Leave", code="SL", annual_quota=10, is_paid=True, color="#f59e0b", description="Illness or medical appointments"),
        dict(name="Earned Leave", code="EL", annual_quota=15, is_paid=True, carry_forward=True, max_carry_forward=10, color="#10b981", description="Planned vacation; up to 10 days carry forward"),
        dict(name="Loss of Pay", code="LOP", annual_quota=0, is_paid=False, color="#ef4444", description="Unpaid leave, deducted from salary"),
    ]:
        if not db.scalar(select(LeaveType).where(LeaveType.code == lt["code"])):
            db.add(LeaveType(**lt))
    db.flush()
    admin = db.scalar(select(User).where(User.email == ADMIN_EMAIL))
    if admin is None:
        admin = User(
            email=ADMIN_EMAIL, full_name="System Administrator", password_hash=hash_password(ADMIN_PASSWORD),
            role_id=db.scalar(select(Role.id).where(Role.name == ROLE_ADMIN)),
        )
        db.add(admin)
    db.commit()
    return admin


# ------------------------------------------------------------------------- demo data
DEPARTMENTS = [
    ("Engineering", "ENG", "Product development and QA"),
    ("Human Resources", "HR", "People operations"),
    ("Finance", "FIN", "Accounts and payroll"),
    ("Sales & Marketing", "SALES", "Revenue and brand"),
    ("Operations", "OPS", "Customer support and facilities"),
]
DESIGNATIONS = [
    ("Engineering Manager", "ENG"), ("Senior Software Engineer", "ENG"), ("Software Engineer", "ENG"),
    ("QA Engineer", "ENG"), ("HR Manager", "HR"), ("Finance Manager", "FIN"), ("Sales Executive", "SALES"),
    ("Marketing Executive", "SALES"), ("Operations Executive", "OPS"), ("Support Engineer", "OPS"),
    ("Business Analyst", "ENG"),
]
HOLIDAYS = [
    ("2026-01-01", "New Year's Day", True), ("2026-01-26", "Republic Day", False), ("2026-03-04", "Holi", False),
    ("2026-03-19", "Ugadi", False), ("2026-04-03", "Good Friday", False), ("2026-05-01", "May Day", False),
    ("2026-08-15", "Independence Day", False), ("2026-08-28", "Raksha Bandhan", True),
    ("2026-09-14", "Ganesh Chaturthi", False), ("2026-10-02", "Gandhi Jayanti", False), ("2026-10-20", "Dussehra", False),
    ("2026-11-09", "Diwali", False), ("2026-12-25", "Christmas", False), ("2027-01-01", "New Year's Day", True),
    ("2027-01-26", "Republic Day", False),
]

# first, last, email local part, dept, designation, joining, gender, dob, basic, role, manager key
PEOPLE = [
    ("Priya", "Sharma", "hr", "HR", "HR Manager", "2023-04-10", "female", "1988-06-21", 55000, ROLE_HR, None),
    ("Karthik", "Reddy", "karthik.reddy", "ENG", "Engineering Manager", "2021-03-01", "male", "1985-11-02", 85000, None, None),
    ("Rahul", "Verma", "rahul.verma", "ENG", "Senior Software Engineer", "2022-07-01", "male", "1993-03-14", 60000, None, "karthik.reddy"),
    ("Ananya", "Iyer", "ananya.iyer", "ENG", "Software Engineer", "2024-01-15", "female", "1998-08-30", 38000, None, "karthik.reddy"),
    ("Sneha", "Patil", "sneha.patil", "ENG", "QA Engineer", "2026-08-17", "female", "2000-01-12", 30000, None, "karthik.reddy"),
    ("Vikram", "Singh", "vikram.singh", "FIN", "Finance Manager", "2023-09-01", "male", "1987-04-25", 70000, None, None),
    ("Meera", "Nair", "meera.nair", "SALES", "Marketing Executive", "2025-02-03", "female", "1996-12-05", 32000, None, None),
    ("Arjun", "Mehta", "arjun.mehta", "SALES", "Sales Executive", "2024-06-10", "male", "1995-09-18", 34000, None, None),
    ("Divya", "Krishnan", "divya.krishnan", "OPS", "Operations Executive", "2025-11-20", "female", "1997-02-27", 28000, None, None),
    ("Rohan", "Gupta", "rohan.gupta", "OPS", "Support Engineer", "2024-05-01", "male", "1996-07-07", 26000, None, None),
    ("Neha", "Kapoor", "neha.kapoor", "ENG", "Business Analyst", "2026-10-01", "female", "1999-10-10", 40000, None, "karthik.reddy"),
]
ROHAN_EXIT = date(2026, 9, 15)


def d(s: str) -> date:
    return date.fromisoformat(s)


def salary_for(basic: int) -> dict:
    b = Decimal(basic)
    return {
        "basic": b, "hra": (b * Decimal("0.4")).quantize(Decimal("1")), "conveyance_allowance": Decimal(1600),
        "medical_allowance": Decimal(1250), "special_allowance": (b * Decimal("0.3")).quantize(Decimal("1")),
        "pf_applicable": True, "professional_tax_applicable": True,
        "tds_monthly": Decimal(round(basic * 0.05)) if basic >= 50000 else Decimal(0),
    }


def seed_demo(db, admin: User) -> dict[str, Employee]:
    rnd = random.Random(42)
    actx = RequestContext(user=admin, ip="127.0.0.1", user_agent="seed-script")

    depts = {}
    for name, code, desc in DEPARTMENTS:
        depts[code] = Department(name=name, code=code, description=desc)
        db.add(depts[code])
    db.flush()
    desigs = {}
    for title, dc in DESIGNATIONS:
        desigs[title] = Designation(title=title, department_id=depts[dc].id)
        db.add(desigs[title])
    for ds, name, opt in HOLIDAYS:
        db.add(Holiday(holiday_date=d(ds), name=name, is_optional=opt))
    db.commit()

    emps: dict[str, Employee] = {}
    roles = {r.name: r for r in db.scalars(select(Role))}
    for i, (first, last, key, dc, title, doj, gender, dob, basic, role, mgr) in enumerate(PEOPLE):
        email = f"{key}@example.com"
        data = {
            "first_name": first, "last_name": last, "email": email, "phone": f"+91 98{rnd.randint(10000000, 99999999)}",
            "date_of_birth": d(dob), "gender": gender, "address": f"{rnd.randint(1, 400)}, {rnd.choice(['MG Road', 'Banjara Hills', 'Madhapur', 'Kondapur', 'Gachibowli'])}, Hyderabad",
            "emergency_contact_name": f"{rnd.choice(['Suresh', 'Lakshmi', 'Ramesh', 'Kavita'])} {last}",
            "emergency_contact_phone": f"+91 97{rnd.randint(10000000, 99999999)}",
            "department_id": depts[dc].id, "designation_id": desigs[title].id,
            "manager_id": emps[mgr].id if mgr else None, "date_of_joining": d(doj), "employment_type": "full_time",
            "work_location": "Hyderabad", "bank_name": rnd.choice(["HDFC Bank", "ICICI Bank", "State Bank of India", "Axis Bank"]),
            "bank_account_number": f"{rnd.randint(10**11, 10**12 - 1)}", "ifsc_code": f"HDFC0{rnd.randint(100000, 999999)}",
            "pan_number": f"{''.join(rnd.choice('ABCDEFGHJKLMNPRSTUVWXYZ') for _ in range(3))}P{last[0]}{rnd.randint(1000, 9999)}{rnd.choice('ABCDEFGHJK')}",
            "salary": salary_for(basic), "role_id": roles[role].id if role else None,
            "password": HR_PASSWORD if key == "hr" else EMPLOYEE_PASSWORD,
        }
        emp = employee_service.create_employee(db, actx, data)
        emp.user.must_change_password = False  # demo accounts are ready to use
        emps[key] = emp
    db.commit()

    hr = emps["hr"]
    hctx = RequestContext(user=hr.user, ip="127.0.0.1", user_agent="seed-script")

    # ---- approved / past leave (inserted as pending, then approved through the service)
    def past_leave(key, code, start, end, reason, half=False, approver=hctx):
        emp = emps[key]
        lt = db.scalar(select(LeaveType).where(LeaveType.code == code))
        pv = leave_service.preview(db, emp, lt, d(start), d(end), half)
        req = LeaveRequest(employee_id=emp.id, leave_type_id=lt.id, start_date=d(start), end_date=d(end), is_half_day=half,
                           total_days=pv["total_days"], paid_days=pv["paid_days"], lop_days=pv["lop_days"], reason=reason,
                           applied_at=datetime.combine(d(start) - timedelta(days=5), time(10, 15)))
        db.add(req)
        db.commit()
        return leave_service.approve(db, approver, req.id, "Approved")

    past_leave("karthik.reddy", "EL", "2026-07-06", "2026-07-10", "Family vacation to Kerala")
    past_leave("rahul.verma", "CL", "2026-07-16", "2026-07-17", "Sister's wedding preparations")
    past_leave("vikram.singh", "CL", "2026-07-31", "2026-07-31", "Personal work at bank")
    past_leave("hr", "CL", "2026-08-14", "2026-08-14", "Long weekend travel", approver=actx)
    past_leave("ananya.iyer", "SL", "2026-08-11", "2026-08-12", "Viral fever")
    past_leave("arjun.mehta", "CL", "2026-08-24", "2026-08-28", "Visiting hometown")
    past_leave("rahul.verma", "SL", "2026-09-08", "2026-09-08", "Dental appointment", half=True)
    past_leave("meera.nair", "EL", "2026-09-15", "2026-09-18", "Trip to Goa")
    past_leave("ananya.iyer", "LOP", "2026-09-21", "2026-09-23", "Extended personal leave (unpaid)")
    past_leave("sneha.patil", "SL", "2026-09-24", "2026-09-30", "Hospitalised - typhoid")  # exceeds balance -> partial LOP

    # ---- attendance history (bulk insert, skipping full-day leave)
    cfg = settings_service.get_many(db)
    start, yesterday = date(2026, 7, 1), today_local() - timedelta(days=1)
    cal = WorkCalendar(db, start, today_local())
    ids = [e.id for e in emps.values()]
    leave_map = leave_service.leave_day_map(db, ids, start, today_local())
    absences = {("arjun.mehta", "2026-07-21"), ("divya.krishnan", "2026-08-05"), ("meera.nair", "2026-09-29"), ("rohan.gupta", "2026-08-19")}
    rows = []
    for key, emp in emps.items():
        last_day = min(yesterday, ROHAN_EXIT) if key == "rohan.gupta" else yesterday
        for day in daterange(max(start, emp.date_of_joining), last_day):
            if not cal.is_working_day(day) or (key, day.isoformat()) in absences:
                continue
            paid, lop = leave_map.get((emp.id, day), (Decimal(0), Decimal(0)))
            if paid + lop >= 1:
                continue
            r = rnd.random()
            cin = datetime.combine(day, time(9, 0)) + timedelta(minutes=rnd.randint(0, 50))
            if paid + lop > 0 or r < 0.03:  # half day
                cout = cin + timedelta(hours=4, minutes=rnd.randint(30, 50))
            elif r < 0.04 and key != "rahul.verma":  # forgot to check out
                cout = None
            else:
                cout = cin + timedelta(hours=8, minutes=rnd.randint(5, 100))
            minutes = int((cout - cin).total_seconds() // 60) if cout else 0
            rows.append(Attendance(
                employee_id=emp.id, work_date=day, check_in=cin, check_out=cout, work_minutes=minutes,
                status=attendance_service.classify(db, minutes, cfg) if cout else AttendanceStatus.HALF_DAY,
                is_late=attendance_service._is_late(cin, cfg), check_in_ip="10.0.0.%d" % rnd.randint(2, 250),
            ))
    # today: most people have checked in already (the Rahul demo account is left for you to try)
    now = now_local()
    if cal.is_working_day(today_local()) and now.time() > time(9, 30):
        for key, emp in emps.items():
            if key in ("rahul.verma", "rohan.gupta", "meera.nair") or emp.date_of_joining > today_local():
                continue
            cin = datetime.combine(today_local(), time(9, 0)) + timedelta(minutes=rnd.randint(0, 40))
            rows.append(Attendance(employee_id=emp.id, work_date=today_local(), check_in=min(cin, now),
                                   status=AttendanceStatus.HALF_DAY, is_late=attendance_service._is_late(cin, cfg)))
    db.add_all(rows)
    db.commit()

    # one HR correction so the override trail is visible
    attendance_service.override(db, hctx, {
        "employee_id": emps["arjun.mehta"].id, "work_date": date(2026, 9, 10),
        "check_in": datetime(2026, 9, 10, 9, 20), "check_out": datetime(2026, 9, 10, 18, 5),
        "reason": "Biometric device was offline; confirmed with team lead",
    })

    # ---- exit
    employee_service.deactivate(db, hctx, emps["rohan.gupta"].id, ROHAN_EXIT, "Resigned - relocating to Pune")

    # ---- payroll: July & August paid, September left as an editable draft
    for month in (7, 8):
        run = payroll_service.generate(db, actx, 2026, month)["run"]
        payroll_service.lock(db, actx, run.id)
        payroll_service.credit(db, actx, run.id)
    sep = payroll_service.generate(db, actx, 2026, 9, notes="Includes Q3 performance bonus for selected employees")["run"]
    rahul_slip = next(s for s in sep.payslips if s.employee_id == emps["rahul.verma"].id)
    payroll_service.add_adjustment(db, actx, rahul_slip.id, {
        "kind": AdjustmentKind.EARNING, "label": "Performance Bonus", "amount": Decimal(5000),
        "reason": "Q3 performance award approved by Engineering Manager",
    })

    # ---- open requests for the approval queue (applied through the normal validated flow)
    def apply(key, code, start, end, reason, half=False):
        emp = emps[key]
        ctx = RequestContext(user=emp.user, ip="127.0.0.1", user_agent="seed-script")
        lt = db.scalar(select(LeaveType).where(LeaveType.code == code))
        return leave_service.apply(db, ctx, emp, {"leave_type_id": lt.id, "start_date": d(start), "end_date": d(end), "is_half_day": half, "reason": reason})

    t = today_local()
    nxt = lambda n: (t + timedelta(days=n)).isoformat()  # noqa: E731
    apply("rahul.verma", "EL", nxt(21), nxt(25), "Diwali vacation with family")
    apply("vikram.singh", "SL", nxt(2), nxt(2), "Medical check-up")
    rej = apply("arjun.mehta", "CL", nxt(4), nxt(4), "Personal errand")
    leave_service.reject(db, hctx, rej.id, "Quarter-end client meetings scheduled; please pick another date")
    apply("divya.krishnan", "CL", nxt(9), nxt(10), "Attending a friend's wedding")
    return emps


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the HRMS database")
    parser.add_argument("--reset", action="store_true", help="drop and recreate all tables first")
    parser.add_argument("--base", action="store_true", help="only reference data + admin account")
    args = parser.parse_args()

    settings.SMTP_HOST = ""  # never send real emails while seeding; they are only logged
    alembic_cfg = AlembicConfig(str(BASE_DIR / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(BASE_DIR / "migrations"))
    if args.reset:
        command.downgrade(alembic_cfg, "base")
    command.upgrade(alembic_cfg, "head")  # idempotent: creates/updates the schema

    with SessionLocal() as db:
        has_people = db.scalar(select(Employee.id).limit(1)) is not None
        admin = seed_base(db)
        if args.base:
            print("Base data seeded.")
        elif has_people:
            print("Employees already exist - demo data skipped (use --reset to rebuild).")
        else:
            seed_demo(db, admin)
            print("Demo data seeded.")
    print(f"\n  Admin    : {ADMIN_EMAIL} / {ADMIN_PASSWORD}")
    if not args.base:
        print(f"  HR       : {HR_EMAIL} / {HR_PASSWORD}")
        print(f"  Employee : rahul.verma@example.com / {EMPLOYEE_PASSWORD}  (all other employees use the same password)\n")


if __name__ == "__main__":
    main()
