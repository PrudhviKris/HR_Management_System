import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import settings
from app.core.database import engine
from app.exceptions import register_exception_handlers
from app.routers import (
    admin,
    attendance,
    auth,
    dashboard,
    employees,
    leaves,
    notifications,
    organization,
    payroll,
    profile,
    reports,
)
from app.services import notification_service
from app.utils import files

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    files.ensure_dirs()
    notification_service.start_worker()
    yield


app = FastAPI(
    title=f"{settings.APP_NAME} API",
    version="1.0.0",
    description=(
        "Human Resource Management System: employees, attendance, leave, payroll, payslips, notifications, "
        "reports and audit logs.\n\nAuthenticate with `POST /api/v1/auth/login`, then send "
        "`Authorization: Bearer <access_token>`. The refresh token lives in an HttpOnly cookie."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["Content-Disposition"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if request.url.path.startswith(settings.API_PREFIX):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


register_exception_handlers(app)

for r in (auth, dashboard, profile, employees, attendance, leaves, payroll, reports, organization, admin, notifications):
    app.include_router(r.router, prefix=settings.API_PREFIX)


@app.get("/health", tags=["Health"])
def health():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok", "database": engine.dialect.name}
