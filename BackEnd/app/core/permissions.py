"""Permission catalogue and default role grants.

Every protected endpoint declares the permission it needs (see app.core.deps.require_permissions).
Roles are stored in the DB and editable from the admin panel; these are only the seed defaults.
"""


class P:
    # employees
    EMPLOYEE_VIEW = "employee:view"
    EMPLOYEE_CREATE = "employee:create"
    EMPLOYEE_UPDATE = "employee:update"
    EMPLOYEE_DEACTIVATE = "employee:deactivate"
    SALARY_VIEW = "salary:view"
    SALARY_MANAGE = "salary:manage"
    DOCUMENT_MANAGE = "document:manage"
    # attendance
    ATTENDANCE_SELF = "attendance:self"
    ATTENDANCE_VIEW = "attendance:view"
    ATTENDANCE_OVERRIDE = "attendance:override"
    # leave
    LEAVE_APPLY = "leave:apply"
    LEAVE_VIEW = "leave:view"
    LEAVE_APPROVE = "leave:approve"
    LEAVE_CONFIGURE = "leave:configure"
    # payroll
    PAYROLL_VIEW = "payroll:view"
    PAYROLL_PROCESS = "payroll:process"
    PAYROLL_ADJUST = "payroll:adjust"
    PAYSLIP_SELF = "payslip:self"
    # org & admin
    ORG_MANAGE = "org:manage"
    REPORTS_VIEW = "reports:view"
    AUDIT_VIEW = "audit:view"
    ROLE_MANAGE = "role:manage"
    SETTINGS_MANAGE = "settings:manage"
    NOTIFICATION_MANAGE = "notification:manage"
    DASHBOARD_ADMIN = "dashboard:admin"


PERMISSION_CATALOG: list[tuple[str, str, str]] = [
    (P.EMPLOYEE_VIEW, "employees", "View employee directory and profiles"),
    (P.EMPLOYEE_CREATE, "employees", "Onboard new employees"),
    (P.EMPLOYEE_UPDATE, "employees", "Edit employee profiles"),
    (P.EMPLOYEE_DEACTIVATE, "employees", "Deactivate / reactivate employees"),
    (P.SALARY_VIEW, "employees", "View salary structures"),
    (P.SALARY_MANAGE, "employees", "Create or revise salary structures"),
    (P.DOCUMENT_MANAGE, "employees", "Upload / delete documents for any employee"),
    (P.ATTENDANCE_SELF, "attendance", "Check in / out and view own attendance"),
    (P.ATTENDANCE_VIEW, "attendance", "View attendance of all employees"),
    (P.ATTENDANCE_OVERRIDE, "attendance", "Correct / override attendance records"),
    (P.LEAVE_APPLY, "leave", "Apply for leave and view own leave"),
    (P.LEAVE_VIEW, "leave", "View leave requests of all employees"),
    (P.LEAVE_APPROVE, "leave", "Approve or reject leave requests"),
    (P.LEAVE_CONFIGURE, "leave", "Manage leave types and balances"),
    (P.PAYROLL_VIEW, "payroll", "View payroll runs and all payslips"),
    (P.PAYROLL_PROCESS, "payroll", "Generate, lock and credit payroll"),
    (P.PAYROLL_ADJUST, "payroll", "Add manual payroll adjustments"),
    (P.PAYSLIP_SELF, "payroll", "View and download own payslips"),
    (P.ORG_MANAGE, "organization", "Manage departments, designations and holidays"),
    (P.REPORTS_VIEW, "reports", "View and export reports"),
    (P.AUDIT_VIEW, "audit", "View audit logs (read-only)"),
    (P.ROLE_MANAGE, "administration", "Manage roles, permissions and user roles"),
    (P.SETTINGS_MANAGE, "administration", "Change system settings"),
    (P.NOTIFICATION_MANAGE, "administration", "Edit email templates and view email logs"),
    (P.DASHBOARD_ADMIN, "dashboard", "View organisation-wide dashboard"),
]

ALL_PERMISSIONS = [code for code, _, _ in PERMISSION_CATALOG]

ROLE_ADMIN = "Admin"
ROLE_HR = "HR"
ROLE_EMPLOYEE = "Employee"

EMPLOYEE_SELF_SERVICE = [P.ATTENDANCE_SELF, P.LEAVE_APPLY, P.PAYSLIP_SELF]

DEFAULT_ROLE_PERMISSIONS: dict[str, list[str]] = {
    ROLE_ADMIN: ALL_PERMISSIONS,
    ROLE_HR: [
        P.EMPLOYEE_VIEW,
        P.EMPLOYEE_CREATE,
        P.EMPLOYEE_UPDATE,
        P.EMPLOYEE_DEACTIVATE,
        P.SALARY_VIEW,
        P.SALARY_MANAGE,
        P.DOCUMENT_MANAGE,
        P.ATTENDANCE_VIEW,
        P.ATTENDANCE_OVERRIDE,
        P.LEAVE_VIEW,
        P.LEAVE_APPROVE,
        P.LEAVE_CONFIGURE,
        P.PAYROLL_VIEW,
        P.PAYROLL_PROCESS,
        P.PAYROLL_ADJUST,
        P.ORG_MANAGE,
        P.REPORTS_VIEW,
        P.DASHBOARD_ADMIN,
        *EMPLOYEE_SELF_SERVICE,
    ],
    ROLE_EMPLOYEE: EMPLOYEE_SELF_SERVICE,
}

ROLE_DESCRIPTIONS = {
    ROLE_ADMIN: "Full system access. Permissions of this role cannot be reduced.",
    ROLE_HR: "Human resources: people, attendance, leave and payroll operations.",
    ROLE_EMPLOYEE: "Self-service: attendance, leave and payslips.",
}
