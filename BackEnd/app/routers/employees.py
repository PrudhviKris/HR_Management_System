from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import RequestContext, get_request_context, require_permissions
from app.core.permissions import P
from app.models.enums import EmployeeStatus, EmploymentType
from app.schemas.common import Message, Page
from app.schemas.employee import (
    DeactivateIn,
    DocumentOut,
    EmployeeCreate,
    EmployeeDetail,
    EmployeeListItem,
    EmployeeUpdate,
    SalaryIn,
    SalaryOut,
)
from app.services import employee_service as svc
from app.utils import files

router = APIRouter(prefix="/employees", tags=["Employees"])


def document_response(doc) -> FileResponse:
    return FileResponse(
        files.document_path(doc.stored_filename),
        media_type=doc.content_type,
        filename=doc.original_filename,
        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"},
    )


@router.get("", response_model=Page[EmployeeListItem], dependencies=[Depends(require_permissions(P.EMPLOYEE_VIEW))])
def list_employees(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=100),
    department_id: int | None = None,
    designation_id: int | None = None,
    status: EmployeeStatus | None = None,
    employment_type: EmploymentType | None = None,
    sort: str = Query("employee_code", pattern="^(employee_code|name|date_of_joining|created_at)$"),
    order: str = Query("asc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
):
    return svc.list_employees(
        db, page=page, page_size=page_size, search=search, department_id=department_id,
        designation_id=designation_id, status=status, employment_type=employment_type, sort=sort, order=order,
    )


@router.post("", response_model=EmployeeDetail, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_permissions(P.EMPLOYEE_CREATE, P.SALARY_MANAGE))])
def create_employee(body: EmployeeCreate, ctx: RequestContext = Depends(get_request_context), db: Session = Depends(get_db)):
    """Creates the login account, employee profile, initial salary structure and leave balances, then
    sends the onboarding email (with a set-password link unless an initial password is given)."""
    return svc.to_detail(svc.create_employee(db, ctx, body.model_dump()))


@router.get("/{employee_id}", response_model=EmployeeDetail, dependencies=[Depends(require_permissions(P.EMPLOYEE_VIEW))])
def get_employee(employee_id: int, db: Session = Depends(get_db)):
    return svc.to_detail(svc.get_employee(db, employee_id))


@router.put("/{employee_id}", response_model=EmployeeDetail, dependencies=[Depends(require_permissions(P.EMPLOYEE_UPDATE))])
def update_employee(employee_id: int, body: EmployeeUpdate, ctx: RequestContext = Depends(get_request_context), db: Session = Depends(get_db)):
    return svc.to_detail(svc.update_employee(db, ctx, employee_id, body.model_dump()))


@router.post("/{employee_id}/deactivate", response_model=EmployeeDetail, dependencies=[Depends(require_permissions(P.EMPLOYEE_DEACTIVATE))])
def deactivate_employee(employee_id: int, body: DeactivateIn, ctx: RequestContext = Depends(get_request_context), db: Session = Depends(get_db)):
    """Soft delete: blocks login, revokes sessions, cancels pending leave. History is retained."""
    return svc.to_detail(svc.deactivate(db, ctx, employee_id, body.exit_date, body.reason))


@router.post("/{employee_id}/activate", response_model=EmployeeDetail, dependencies=[Depends(require_permissions(P.EMPLOYEE_DEACTIVATE))])
def activate_employee(employee_id: int, ctx: RequestContext = Depends(get_request_context), db: Session = Depends(get_db)):
    return svc.to_detail(svc.activate(db, ctx, employee_id))


@router.post("/{employee_id}/send-password-reset", response_model=Message, dependencies=[Depends(require_permissions(P.EMPLOYEE_UPDATE))])
def send_password_reset(employee_id: int, ctx: RequestContext = Depends(get_request_context), db: Session = Depends(get_db)):
    svc.reset_credentials(db, ctx, employee_id)
    return Message(message="Password reset link sent")


# salary ---------------------------------------------------------------------
@router.get("/{employee_id}/salary", response_model=list[SalaryOut], dependencies=[Depends(require_permissions(P.SALARY_VIEW))])
def salary_history(employee_id: int, db: Session = Depends(get_db)):
    return svc.salary_history(db, employee_id)


@router.post("/{employee_id}/salary", response_model=SalaryOut, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_permissions(P.SALARY_MANAGE))])
def revise_salary(employee_id: int, body: SalaryIn, ctx: RequestContext = Depends(get_request_context), db: Session = Depends(get_db)):
    return svc.add_salary(db, ctx, employee_id, body.model_dump())


# documents ------------------------------------------------------------------
@router.get("/{employee_id}/documents", response_model=list[DocumentOut], dependencies=[Depends(require_permissions(P.EMPLOYEE_VIEW))])
def list_documents(employee_id: int, db: Session = Depends(get_db)):
    svc.get_employee(db, employee_id)
    return svc.list_documents(db, employee_id)


@router.post("/{employee_id}/documents", response_model=DocumentOut, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_permissions(P.DOCUMENT_MANAGE))])
async def upload_document(
    employee_id: int,
    document_type: str = Form(..., min_length=2, max_length=50),
    file: UploadFile = File(..., description="PDF, PNG, JPG or DOCX, max 5 MB"),
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    doc = await svc.upload_document(db, ctx, employee_id, document_type, file)
    return next(d for d in svc.list_documents(db, employee_id) if d["id"] == doc.id)


@router.get("/{employee_id}/documents/{document_id}/download", dependencies=[Depends(require_permissions(P.EMPLOYEE_VIEW))])
def download_document(employee_id: int, document_id: int, db: Session = Depends(get_db)):
    return document_response(svc.get_document(db, employee_id, document_id))


@router.delete("/{employee_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(require_permissions(P.DOCUMENT_MANAGE))])
def delete_document(employee_id: int, document_id: int, ctx: RequestContext = Depends(get_request_context), db: Session = Depends(get_db)):
    svc.delete_document(db, ctx, employee_id, document_id)
