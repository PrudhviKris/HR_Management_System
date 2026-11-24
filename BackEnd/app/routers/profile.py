"""Self-service endpoints for the signed-in employee."""

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import RequestContext, get_current_employee, get_request_context
from app.models import Employee
from app.routers.employees import document_response
from app.schemas.employee import DocumentOut, EmployeeDetail, EmployeeSelfUpdate, SalaryOut
from app.services import employee_service as svc

router = APIRouter(prefix="/me", tags=["My Profile"])


@router.get("/profile", response_model=EmployeeDetail)
def my_profile(emp: Employee = Depends(get_current_employee)):
    return svc.to_detail(emp)


@router.put("/profile", response_model=EmployeeDetail)
def update_my_profile(
    body: EmployeeSelfUpdate,
    emp: Employee = Depends(get_current_employee),
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    """Employees may update contact details only; job, bank and salary data are HR-managed."""
    return svc.to_detail(svc.update_self(db, ctx, emp, body.model_dump(exclude_unset=True)))


@router.get("/salary", response_model=SalaryOut | None)
def my_salary(emp: Employee = Depends(get_current_employee), db: Session = Depends(get_db)):
    history = svc.salary_history(db, emp.id)
    return history[0] if history else None


@router.get("/documents", response_model=list[DocumentOut])
def my_documents(emp: Employee = Depends(get_current_employee), db: Session = Depends(get_db)):
    return svc.list_documents(db, emp.id)


@router.post("/documents", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_my_document(
    document_type: str = Form(..., min_length=2, max_length=50),
    file: UploadFile = File(...),
    emp: Employee = Depends(get_current_employee),
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    doc = await svc.upload_document(db, ctx, emp.id, document_type, file)
    return next(d for d in svc.list_documents(db, emp.id) if d["id"] == doc.id)


@router.get("/documents/{document_id}/download")
def download_my_document(document_id: int, emp: Employee = Depends(get_current_employee), db: Session = Depends(get_db)):
    return document_response(svc.get_document(db, emp.id, document_id))
