from datetime import date, timedelta
from decimal import Decimal

from app.core.timeutils import today_local
from tests.conftest import API


def _weekdays_from(start: date, n: int) -> list[date]:
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def _future_window(n: int) -> list[date]:
    start = today_local() + timedelta(days=7)
    days = _weekdays_from(start, n)
    if days[0].year != days[-1].year:
        days = _weekdays_from(date(days[-1].year, 1, 5), n)
    return days


def _role_id(client, headers, name):
    return next(r["id"] for r in client.get(f"{API}/roles", headers=headers).json() if r["name"] == name)


# ---------------------------------------------------------------- RBAC
def test_role_based_access(client, admin_headers, make_employee):
    _, emp_h = make_employee()
    _, hr_h = make_employee(role_id=_role_id(client, admin_headers, "HR"))

    assert client.get(f"{API}/employees", headers=emp_h).status_code == 403
    assert client.get(f"{API}/payroll/runs", headers=emp_h).status_code == 403
    assert client.get(f"{API}/audit-logs", headers=emp_h).status_code == 403
    assert client.get(f"{API}/dashboard/admin", headers=emp_h).status_code == 403
    assert client.get(f"{API}/dashboard/employee", headers=emp_h).status_code == 200

    assert client.get(f"{API}/employees", headers=hr_h).status_code == 200
    assert client.get(f"{API}/audit-logs", headers=hr_h).status_code == 403
    assert client.post(f"{API}/roles", headers=hr_h, json={"name": "X", "permissions": []}).status_code == 403
    assert client.get(f"{API}/audit-logs", headers=admin_headers).status_code == 200


def test_custom_role_permissions_take_effect_immediately(client, admin_headers, make_employee):
    emp, emp_h = make_employee()
    assert client.get(f"{API}/reports/leave", headers=emp_h).status_code == 403
    r = client.post(f"{API}/roles", headers=admin_headers, json={
        "name": "Report Viewer", "description": "Employee + reports",
        "permissions": ["attendance:self", "leave:apply", "payslip:self", "reports:view"],
    })
    assert r.status_code == 201
    assert client.put(f"{API}/users/{emp['user_id']}/role", headers=admin_headers, json={"role_id": r.json()["id"]}).status_code == 200
    assert client.get(f"{API}/reports/leave", headers=emp_h).status_code == 200


def test_admin_role_cannot_be_reduced(client, admin_headers):
    admin_role = _role_id(client, admin_headers, "Admin")
    r = client.put(f"{API}/roles/{admin_role}", headers=admin_headers, json={"name": "Admin", "permissions": ["audit:view"]})
    assert r.status_code == 422


# ---------------------------------------------------------------- employees
def test_employee_validation_and_duplicates(client, admin_headers, make_employee):
    emp, _ = make_employee()
    dup = client.post(f"{API}/employees", headers=admin_headers, json={
        "first_name": "Dup", "last_name": "User", "email": emp["email"], "date_of_joining": "2024-01-01",
        "salary": {"basic": 1000},
    })
    assert dup.status_code == 409
    bad = client.post(f"{API}/employees", headers=admin_headers, json={
        "first_name": "", "last_name": "User", "email": "not-an-email", "date_of_joining": "2024-01-01",
        "pan_number": "123", "salary": {"basic": -5},
    })
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "validation_error"


def test_employee_search_filter_and_update_is_audited(client, admin_headers, make_employee):
    emp, _ = make_employee()
    res = client.get(f"{API}/employees", headers=admin_headers, params={"search": emp["last_name"]}).json()
    assert res["total"] == 1 and res["items"][0]["id"] == emp["id"]
    upd = {k: emp[k] for k in ["first_name", "last_name", "email", "date_of_joining"]} | {"phone": "+91 9876543210"}
    assert client.put(f"{API}/employees/{emp['id']}", headers=admin_headers, json=upd).status_code == 200
    logs = client.get(f"{API}/audit-logs", headers=admin_headers, params={"action": "employee.update", "entity_id": emp["id"]}).json()
    assert logs["total"] == 1 and "phone" in logs["items"][0]["changes"]


def test_salary_revision_history(client, admin_headers, make_employee):
    emp, _ = make_employee(basic=20000)
    r = client.post(f"{API}/employees/{emp['id']}/salary", headers=admin_headers, json={"basic": 25000, "hra": 10000})
    assert r.status_code == 201 and r.json()["gross_monthly"] == 35000
    hist = client.get(f"{API}/employees/{emp['id']}/salary", headers=admin_headers).json()
    assert len(hist) == 2 and hist[0]["basic"] == 25000


# ---------------------------------------------------------------- documents
def test_secure_document_upload(client, admin_headers, make_employee):
    emp, emp_h = make_employee()
    url = f"{API}/employees/{emp['id']}/documents"
    pdf = b"%PDF-1.4\n%test document\n"
    ok = client.post(url, headers=admin_headers, data={"document_type": "ID Proof"}, files={"file": ("../../evil name.pdf", pdf, "application/pdf")})
    assert ok.status_code == 201, ok.text
    assert ok.json()["original_filename"] == "evil name.pdf"  # path components stripped

    exe = client.post(url, headers=admin_headers, data={"document_type": "Other"}, files={"file": ("run.exe", b"MZ....", "application/octet-stream")})
    assert exe.status_code == 422 and exe.json()["error"]["code"] == "invalid_file_type"
    spoof = client.post(url, headers=admin_headers, data={"document_type": "Other"}, files={"file": ("fake.pdf", b"\x89PNG\r\n\x1a\nxxxx", "application/pdf")})
    assert spoof.status_code == 422 and spoof.json()["error"]["code"] == "invalid_file_content"

    dl = client.get(f"{url}/{ok.json()['id']}/download", headers=admin_headers)
    assert dl.status_code == 200 and dl.content == pdf
    # employees reach documents only through /me
    assert client.get(f"{url}/{ok.json()['id']}/download", headers=emp_h).status_code == 403
    assert client.get(f"{API}/me/documents/{ok.json()['id']}/download", headers=emp_h).status_code == 200


# ---------------------------------------------------------------- attendance
def test_check_in_out_and_duplicate_prevention(client, make_employee):
    _, h = make_employee()
    r = client.post(f"{API}/attendance/check-in", headers=h)
    assert r.status_code == 201
    dup = client.post(f"{API}/attendance/check-in", headers=h)
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "duplicate_check_in"
    out = client.post(f"{API}/attendance/check-out", headers=h)
    assert out.status_code == 200 and out.json()["check_out"] is not None
    assert client.post(f"{API}/attendance/check-out", headers=h).status_code == 409
    cal = client.get(f"{API}/attendance/me", headers=h).json()
    assert any(d["attendance_id"] == r.json()["id"] for d in cal["days"])


def test_check_out_without_check_in(client, make_employee):
    _, h = make_employee()
    r = client.post(f"{API}/attendance/check-out", headers=h)
    assert r.status_code == 422 and r.json()["error"]["code"] == "not_checked_in"


def test_admin_override_computes_hours_and_requires_reason(client, admin_headers, make_employee):
    emp, _ = make_employee()
    day = today_local() - timedelta(days=1)
    body = {"employee_id": emp["id"], "work_date": day.isoformat(), "check_in": f"{day}T09:00:00", "check_out": f"{day}T13:30:00"}
    assert client.post(f"{API}/attendance/override", headers=admin_headers, json=body).status_code == 422  # no reason
    r = client.post(f"{API}/attendance/override", headers=admin_headers, json=body | {"reason": "Forgot to check in"})
    assert r.status_code == 200
    assert r.json()["work_minutes"] == 270 and r.json()["status"] == "half_day" and r.json()["is_overridden"]


# ---------------------------------------------------------------- leave
def test_leave_apply_approve_deducts_balance_and_handles_lop(client, admin_headers, make_employee):
    emp, h = make_employee()
    types = {t["code"]: t["id"] for t in client.get(f"{API}/leaves/types", headers=h).json()}
    days = _future_window(13)

    cl = client.post(f"{API}/leaves", headers=h, json={"leave_type_id": types["CL"], "start_date": days[0].isoformat(), "end_date": days[1].isoformat(), "reason": "Family function"})
    assert cl.status_code == 201 and cl.json()["total_days"] == 2
    overlap = client.post(f"{API}/leaves", headers=h, json={"leave_type_id": types["SL"], "start_date": days[1].isoformat(), "end_date": days[1].isoformat(), "reason": "Overlap check"})
    assert overlap.status_code == 409

    assert client.post(f"{API}/leaves/{cl.json()['id']}/approve", headers=admin_headers).json()["status"] == "approved"
    year = days[0].year
    bal = {b["code"]: b for b in client.get(f"{API}/leaves/balances/me?year={year}", headers=h).json()}
    assert bal["CL"]["used"] == 2 and bal["CL"]["available"] == 10

    # Sick leave quota is 10 -> 11 days requested => 10 paid + 1 LOP
    sl = client.post(f"{API}/leaves", headers=h, json={"leave_type_id": types["SL"], "start_date": days[2].isoformat(), "end_date": days[12].isoformat(), "reason": "Surgery and recovery"})
    assert sl.status_code == 201 and sl.json()["lop_days"] == 1
    approved = client.post(f"{API}/leaves/{sl.json()['id']}/approve", headers=admin_headers).json()
    assert approved["paid_days"] == 10 and approved["lop_days"] == 1

    # cancelling restores the balance
    assert client.post(f"{API}/leaves/{sl.json()['id']}/cancel", headers=h).json()["status"] == "cancelled"
    bal = {b["code"]: b for b in client.get(f"{API}/leaves/balances/me?year={year}", headers=h).json()}
    assert bal["SL"]["used"] == 0


def test_reject_requires_comment_and_no_self_approval(client, admin_headers, make_employee):
    hr, hr_h = make_employee(role_id=_role_id(client, admin_headers, "HR"))
    types = {t["code"]: t["id"] for t in client.get(f"{API}/leaves/types", headers=hr_h).json()}
    d = _future_window(1)[0].isoformat()
    req = client.post(f"{API}/leaves", headers=hr_h, json={"leave_type_id": types["CL"], "start_date": d, "end_date": d, "reason": "Personal work"}).json()
    assert client.post(f"{API}/leaves/{req['id']}/approve", headers=hr_h).status_code == 403
    assert client.post(f"{API}/leaves/{req['id']}/reject", headers=admin_headers, json={}).status_code == 422
    r = client.post(f"{API}/leaves/{req['id']}/reject", headers=admin_headers, json={"comment": "Team offsite"})
    assert r.json()["status"] == "rejected"


# ---------------------------------------------------------------- payroll
def test_payroll_calculation_lock_and_payslip_access(client, admin_headers, make_employee):
    emp, emp_h = make_employee(basic=30000, doj="2024-01-01")
    _, other_h = make_employee()
    first = today_local().replace(day=1)
    last_month_end = first - timedelta(days=1)
    y, m = last_month_end.year, last_month_end.month
    working = [d for d in (date(y, m, i) for i in range(1, last_month_end.day + 1)) if d.weekday() < 5]
    for d in working[:-2]:  # two absent days -> 2 LOP
        r = client.post(f"{API}/attendance/override", headers=admin_headers, json={
            "employee_id": emp["id"], "work_date": d.isoformat(), "check_in": f"{d}T09:00:00",
            "check_out": f"{d}T18:00:00", "reason": "Back-filled for payroll test"})
        assert r.status_code == 200, r.text

    gen = client.post(f"{API}/payroll/runs", headers=admin_headers, json={"year": y, "month": m})
    assert gen.status_code == 201, gen.text
    run = gen.json()["run"]
    slip = next(s for s in run["payslips"] if s["employee_id"] == emp["id"])
    W = len(working)
    gross = Decimal(30000 + 12000 + 1000)
    assert slip["working_days"] == W and slip["lop_days"] == 2 and slip["paid_days"] == W - 2
    assert Decimal(str(slip["lop_deduction"])) == (gross / W * 2).quantize(Decimal("0.01"))
    assert Decimal(str(slip["provident_fund"])) == (Decimal(30000) * (W - 2) / W * Decimal("0.12")).quantize(Decimal("0.01"))

    # employees can't see draft payslips; admins can adjust drafts
    assert client.get(f"{API}/payroll/payslips/{slip['id']}", headers=emp_h).status_code == 404
    adj = client.post(f"{API}/payroll/payslips/{slip['id']}/adjustments", headers=admin_headers,
                      json={"kind": "earning", "label": "Bonus", "amount": 1000, "reason": "Spot award"})
    assert adj.status_code == 201 and adj.json()["net_salary"] == slip["net_salary"] + 1000

    assert client.post(f"{API}/payroll/runs/{run['id']}/lock", headers=admin_headers).json()["status"] == "locked"

    # month is now frozen
    blocked = client.post(f"{API}/attendance/override", headers=admin_headers, json={
        "employee_id": emp["id"], "work_date": working[-1].isoformat(), "check_in": f"{working[-1]}T09:00:00",
        "check_out": f"{working[-1]}T18:00:00", "reason": "Too late to change"})
    assert blocked.status_code == 423
    assert client.post(f"{API}/payroll/payslips/{slip['id']}/adjustments", headers=admin_headers,
                       json={"kind": "earning", "label": "Late", "amount": 1, "reason": "Should fail"}).status_code == 423
    assert client.post(f"{API}/payroll/runs", headers=admin_headers, json={"year": y, "month": m}).status_code == 423

    pdf = client.get(f"{API}/payroll/payslips/{slip['id']}/pdf", headers=emp_h)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert client.get(f"{API}/payroll/payslips/{slip['id']}/pdf", headers=other_h).status_code == 404
    mine = client.get(f"{API}/payroll/payslips/me", headers=emp_h).json()
    assert mine["total"] == 1

    credit = client.post(f"{API}/payroll/runs/{run['id']}/credit", headers=admin_headers).json()
    assert credit["credited"] >= 1
    paid = client.get(f"{API}/payroll/payslips/{slip['id']}", headers=emp_h).json()
    assert paid["payment_status"] == "credited" and paid["transaction_ref"].startswith("SIM")


def test_cannot_generate_payroll_for_running_month(client, admin_headers):
    t = today_local()
    r = client.post(f"{API}/payroll/runs", headers=admin_headers, json={"year": t.year, "month": t.month})
    assert r.status_code == 422


# ---------------------------------------------------------------- reports & audit
def test_report_exports(client, admin_headers):
    csv = client.get(f"{API}/reports/attendance", headers=admin_headers, params={"format": "csv"})
    assert csv.status_code == 200 and csv.headers["content-type"].startswith("text/csv")
    pdf = client.get(f"{API}/reports/leave", headers=admin_headers, params={"format": "pdf"})
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    js = client.get(f"{API}/reports/attendance", headers=admin_headers).json()
    assert {"title", "columns", "rows"} <= js.keys()


def test_audit_logs_are_read_only(client, admin_headers):
    assert client.delete(f"{API}/audit-logs", headers=admin_headers).status_code == 405
    assert client.put(f"{API}/audit-logs", headers=admin_headers, json={}).status_code == 405
    logs = client.get(f"{API}/audit-logs", headers=admin_headers).json()
    assert logs["total"] > 0 and {"action", "created_at", "actor_email"} <= logs["items"][0].keys()


def test_onboarding_email_logged_from_template(client, admin_headers, make_employee):
    emp, _ = make_employee()
    logs = client.get(f"{API}/email-logs", headers=admin_headers, params={"recipient": emp["email"]}).json()["items"]
    assert any(log["template_code"] == "employee_onboarding" and log["status"] == "logged" for log in logs)
