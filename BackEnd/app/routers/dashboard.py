from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_employee, require_permissions
from app.core.permissions import P
from app.models import Employee
from app.services import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/admin", dependencies=[Depends(require_permissions(P.DASHBOARD_ADMIN))])
def admin_dashboard(db: Session = Depends(get_db)):
    """Headcount, today's attendance, leave and payroll summaries, recent activity."""
    return dashboard_service.admin_dashboard(db)


@router.get("/employee")
def employee_dashboard(emp: Employee = Depends(get_current_employee), db: Session = Depends(get_db)):
    """Today's check-in state, month summary, leave balances, latest payslip."""
    return dashboard_service.employee_dashboard(db, emp)
