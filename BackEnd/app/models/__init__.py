"""Import every model so SQLAlchemy metadata (and Alembic autogenerate) sees all tables."""

from app.models.attendance import Attendance
from app.models.audit import AuditLog
from app.models.employee import Employee, EmployeeDocument, SalaryStructure
from app.models.leave import LeaveBalance, LeaveRequest, LeaveType
from app.models.notification import EmailLog, EmailTemplate, Notification
from app.models.organization import Department, Designation, Holiday, SystemSetting
from app.models.payroll import PayrollAdjustment, PayrollRun, Payslip
from app.models.user import PasswordResetToken, Permission, RefreshToken, Role, User, role_permissions

__all__ = [
    "Attendance",
    "AuditLog",
    "Department",
    "Designation",
    "EmailLog",
    "EmailTemplate",
    "Employee",
    "EmployeeDocument",
    "Holiday",
    "LeaveBalance",
    "LeaveRequest",
    "LeaveType",
    "Notification",
    "PasswordResetToken",
    "PayrollAdjustment",
    "PayrollRun",
    "Payslip",
    "Permission",
    "RefreshToken",
    "Role",
    "SalaryStructure",
    "SystemSetting",
    "User",
    "role_permissions",
]
