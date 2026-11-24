"""Generate a Postman v2.1 collection from the FastAPI OpenAPI schema.

    python scripts/generate_postman.py   ->  ../docs/HRMS.postman_collection.json
                                            ../docs/HRMS.postman_environment.json

Folders follow API tags. The "Login" requests store the access token in {{accessToken}}; every other
request inherits Bearer auth from the collection. Run "Auth > Login (Admin)" first.
"""

import json
import sys
import uuid
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.main import app  # noqa: E402

OUT = ROOT.parent / "docs"
today = date.today()
nxt = today + timedelta(days=14)
while nxt.weekday() >= 5:
    nxt += timedelta(days=1)
prev_month = (today.replace(day=1) - timedelta(days=1))

# Hand-written example bodies for the important endpoints (method, path) -> body
EXAMPLES = {
    ("POST", "/api/v1/auth/login"): {"email": "{{adminEmail}}", "password": "{{adminPassword}}"},
    ("POST", "/api/v1/auth/change-password"): {"current_password": "Employee@123", "new_password": "NewSecret@456"},
    ("POST", "/api/v1/auth/forgot-password"): {"email": "rahul.verma@example.com"},
    ("POST", "/api/v1/auth/reset-password"): {"token": "<token from the emailed link>", "new_password": "NewSecret@456"},
    ("POST", "/api/v1/employees"): {
        "first_name": "Kiran", "last_name": "Rao", "email": "kiran.rao@example.com", "phone": "+91 9876543210",
        "date_of_birth": "1997-05-14", "gender": "male", "address": "12, Jubilee Hills, Hyderabad",
        "department_id": 1, "designation_id": 3, "manager_id": 2, "date_of_joining": today.isoformat(),
        "employment_type": "full_time", "work_location": "Hyderabad", "bank_name": "HDFC Bank",
        "bank_account_number": "501002345678", "ifsc_code": "HDFC0001234", "pan_number": "ABCPR1234K",
        "password": "Welcome@123",
        "salary": {"basic": 35000, "hra": 14000, "conveyance_allowance": 1600, "medical_allowance": 1250,
                   "special_allowance": 8000, "pf_applicable": True, "professional_tax_applicable": True, "tds_monthly": 0},
    },
    ("PUT", "/api/v1/employees/{employee_id}"): {
        "first_name": "Rahul", "last_name": "Verma", "email": "rahul.verma@example.com", "phone": "+91 9000000001",
        "date_of_joining": "2022-07-01", "department_id": 1, "designation_id": 2, "manager_id": 2,
        "employment_type": "full_time", "work_location": "Hyderabad",
    },
    ("POST", "/api/v1/employees/{employee_id}/deactivate"): {"exit_date": today.isoformat(), "reason": "Resigned"},
    ("POST", "/api/v1/employees/{employee_id}/salary"): {"effective_from": today.isoformat(), "basic": 65000, "hra": 26000, "conveyance_allowance": 1600, "medical_allowance": 1250, "special_allowance": 19500, "tds_monthly": 3250, "remarks": "Annual appraisal"},
    ("PUT", "/api/v1/me/profile"): {"phone": "+91 9000000002", "address": "Flat 4B, Madhapur, Hyderabad"},
    ("POST", "/api/v1/attendance/override"): {
        "employee_id": 3, "work_date": (today - timedelta(days=1)).isoformat(),
        "check_in": f"{today - timedelta(days=1)}T09:15:00", "check_out": f"{today - timedelta(days=1)}T18:05:00",
        "reason": "Biometric device offline",
    },
    ("POST", "/api/v1/leaves/preview"): {"leave_type_id": 1, "start_date": nxt.isoformat(), "end_date": nxt.isoformat(), "is_half_day": False},
    ("POST", "/api/v1/leaves"): {"leave_type_id": 1, "start_date": nxt.isoformat(), "end_date": nxt.isoformat(), "is_half_day": False, "reason": "Personal work"},
    ("POST", "/api/v1/leaves/{request_id}/approve"): {"comment": "Approved"},
    ("POST", "/api/v1/leaves/{request_id}/reject"): {"comment": "Critical release this week"},
    ("POST", "/api/v1/leaves/balances/adjust"): {"employee_id": 3, "leave_type_id": 1, "year": today.year, "allocated": 14, "reason": "Compensatory days for weekend support"},
    ("POST", "/api/v1/leaves/types"): {"name": "Paternity Leave", "code": "PTL", "annual_quota": 5, "is_paid": True, "carry_forward": False, "max_carry_forward": 0, "color": "#0ea5e9", "is_active": True},
    ("POST", "/api/v1/payroll/runs"): {"year": prev_month.year, "month": prev_month.month, "notes": "Monthly payroll"},
    ("POST", "/api/v1/payroll/payslips/{payslip_id}/adjustments"): {"kind": "earning", "label": "Performance Bonus", "amount": 5000, "reason": "Quarterly award"},
    ("POST", "/api/v1/departments"): {"name": "Legal", "code": "LEGAL", "description": "Contracts and compliance", "is_active": True},
    ("POST", "/api/v1/designations"): {"title": "Legal Counsel", "department_id": 1, "is_active": True},
    ("POST", "/api/v1/holidays"): {"holiday_date": f"{today.year}-12-31", "name": "Year End", "is_optional": True},
    ("PUT", "/api/v1/settings"): {"values": {"full_day_hours": "8", "half_day_hours": "4"}},
    ("POST", "/api/v1/roles"): {"name": "Payroll Officer", "description": "Runs payroll only", "permissions": ["payroll:view", "payroll:process", "payroll:adjust", "reports:view", "attendance:self", "leave:apply", "payslip:self"]},
    ("PUT", "/api/v1/users/{user_id}/role"): {"role_id": 2},
}

PATH_DEFAULTS = {"employee_id": "3", "payslip_id": "1", "run_id": "1", "request_id": "1", "attendance_id": "1",
                 "dept_id": "1", "desig_id": "1", "holiday_id": "1", "type_id": "1", "role_id": "4", "user_id": "3",
                 "document_id": "1", "adjustment_id": "1", "notification_id": "1", "template_id": "1", "log_id": "1"}

LOGIN_TEST = [
    "const body = pm.response.json();",
    "if (pm.response.code === 200) {",
    "  pm.collectionVariables.set('accessToken', body.access_token);",
    "  pm.test('Logged in as ' + body.user.role, () => pm.expect(body.access_token).to.be.a('string'));",
    "}",
]


def sample(schema: dict, components: dict, depth: int = 0):
    if "$ref" in schema:
        return sample(components[schema["$ref"].split("/")[-1]], components, depth)
    if "anyOf" in schema:
        non_null = [s for s in schema["anyOf"] if s.get("type") != "null"]
        return sample(non_null[0], components, depth) if non_null else None
    if "default" in schema:
        return schema["default"]
    if "enum" in schema:
        return schema["enum"][0]
    t = schema.get("type")
    if t == "object" and depth < 3:
        return {k: sample(v, components, depth + 1) for k, v in schema.get("properties", {}).items()}
    if t == "array":
        return []
    fmt = schema.get("format")
    return {"string": {"date": today.isoformat(), "date-time": f"{today}T09:00:00", "email": "user@example.com"}.get(fmt, "string"),
            "integer": 1, "number": 0, "boolean": False}.get(t)


def build() -> dict:
    spec = app.openapi()
    components = spec.get("components", {}).get("schemas", {})
    folders: dict[str, list] = {}
    for path, methods in spec["paths"].items():
        for method, op in methods.items():
            if method not in ("get", "post", "put", "delete"):
                continue
            tag = (op.get("tags") or ["Misc"])[0]
            raw = path
            for p in [p for p in op.get("parameters", []) if p["in"] == "path"]:
                raw = raw.replace("{" + p["name"] + "}", PATH_DEFAULTS.get(p["name"], "1"))
            query = [
                {"key": p["name"], "value": "", "disabled": True, "description": (p.get("description") or "")}
                for p in op.get("parameters", []) if p["in"] == "query"
            ]
            url_path = raw.lstrip("/").split("/")
            req = {
                "method": method.upper(),
                "header": [],
                "url": {"raw": "{{baseUrl}}" + raw, "host": ["{{baseUrl}}"], "path": url_path, **({"query": query} if query else {})},
                "description": op.get("description") or op.get("summary", ""),
            }
            body_schema = op.get("requestBody", {}).get("content", {})
            if "application/json" in body_schema:
                body = EXAMPLES.get((method.upper(), path)) or sample(body_schema["application/json"]["schema"], components)
                req["header"].append({"key": "Content-Type", "value": "application/json"})
                req["body"] = {"mode": "raw", "raw": json.dumps(body, indent=2), "options": {"raw": {"language": "json"}}}
            elif "multipart/form-data" in body_schema:
                req["body"] = {"mode": "formdata", "formdata": [
                    {"key": "document_type", "value": "ID Proof", "type": "text"},
                    {"key": "file", "type": "file", "src": []},
                ]}
            if path == "/api/v1/auth/login":
                req["auth"] = {"type": "noauth"}
            item = {"name": op.get("summary") or f"{method.upper()} {path}", "request": req}
            if path == "/api/v1/auth/login":
                item["name"] = "Login (Admin)"
                item["event"] = [{"listen": "test", "script": {"type": "text/javascript", "exec": LOGIN_TEST}}]
            folders.setdefault(tag, []).append(item)

    # extra logins for the other demo roles
    for role, email_var, pwd_var in (("HR", "hrEmail", "hrPassword"), ("Employee", "employeeEmail", "employeePassword")):
        folders["Auth"].insert(1, {
            "name": f"Login ({role})",
            "event": [{"listen": "test", "script": {"type": "text/javascript", "exec": LOGIN_TEST}}],
            "request": {
                "method": "POST", "auth": {"type": "noauth"},
                "header": [{"key": "Content-Type", "value": "application/json"}],
                "url": {"raw": "{{baseUrl}}/api/v1/auth/login", "host": ["{{baseUrl}}"], "path": ["api", "v1", "auth", "login"]},
                "body": {"mode": "raw", "raw": json.dumps({"email": "{{%s}}" % email_var, "password": "{{%s}}" % pwd_var}, indent=2), "options": {"raw": {"language": "json"}}},
            },
        })

    order = ["Auth", "Dashboard", "My Profile", "Employees", "Attendance", "Leave", "Payroll", "Reports", "Organization", "Administration", "Notifications", "Health"]
    items = [{"name": t, "item": folders[t]} for t in order if t in folders] + [{"name": t, "item": v} for t, v in folders.items() if t not in order]
    variables = {
        "baseUrl": "http://localhost:8000", "accessToken": "",
        "adminEmail": "admin@example.com", "adminPassword": "Admin@123",
        "hrEmail": "hr@example.com", "hrPassword": "Hr@12345",
        "employeeEmail": "rahul.verma@example.com", "employeePassword": "Employee@123",
    }
    return {
        "info": {
            "_postman_id": str(uuid.uuid5(uuid.NAMESPACE_URL, "hrms-api")),
            "name": "HRMS API",
            "description": (
                "Human Resource Management System API.\n\n1. Run **Auth > Login (Admin)** (or HR / Employee). The test script stores "
                "the JWT in `{{accessToken}}`.\n2. All other requests use Bearer auth from the collection.\n3. The refresh token is an "
                "HttpOnly cookie; Postman keeps it automatically so **Auth > Refresh** works.\n\nDemo credentials are in the collection variables."
            ),
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "auth": {"type": "bearer", "bearer": [{"key": "token", "value": "{{accessToken}}", "type": "string"}]},
        "variable": [{"key": k, "value": v} for k, v in variables.items()],
        "item": items,
    }, variables


def main() -> None:
    OUT.mkdir(exist_ok=True)
    collection, variables = build()
    (OUT / "HRMS.postman_collection.json").write_text(json.dumps(collection, indent=2), encoding="utf-8")
    env = {
        "id": str(uuid.uuid5(uuid.NAMESPACE_URL, "hrms-env")), "name": "HRMS Local",
        "values": [{"key": k, "value": v, "enabled": True} for k, v in variables.items()],
        "_postman_variable_scope": "environment",
    }
    (OUT / "HRMS.postman_environment.json").write_text(json.dumps(env, indent=2), encoding="utf-8")
    n = sum(len(f["item"]) for f in collection["item"])
    print(f"wrote {OUT / 'HRMS.postman_collection.json'} ({n} requests)")


if __name__ == "__main__":
    main()
