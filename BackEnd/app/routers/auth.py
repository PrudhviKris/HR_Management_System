from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import RequestContext, client_ip, get_current_user, get_request_context
from app.models import User
from app.schemas.auth import (
    ChangePasswordRequest,
    CurrentUser,
    ForgotPasswordRequest,
    LoginRequest,
    ResetPasswordRequest,
    TokenResponse,
)
from app.schemas.common import Message
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Auth"])

COOKIE_PATH = f"{settings.API_PREFIX}/auth"


def _set_refresh_cookie(response: Response, tokens: auth_service.IssuedTokens) -> None:
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=tokens.refresh_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        httponly=True,  # not readable from JS -> safe from XSS token theft
        secure=settings.COOKIE_SECURE,
        samesite="strict",
        path=COOKIE_PATH,
    )


def _token_response(user: User, tokens: auth_service.IssuedTokens) -> TokenResponse:
    return TokenResponse(
        access_token=tokens.access_token, expires_at=tokens.access_expires_at, user=CurrentUser.from_user(user)
    )


def _ua(request: Request) -> str:
    return (request.headers.get("user-agent") or "")[:255]


@router.post("/login", response_model=TokenResponse, summary="Sign in with email and password")
def login(body: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    """Returns a short-lived access token (send as `Authorization: Bearer <token>`) and sets a
    rotating refresh token in an HttpOnly cookie."""
    user, tokens = auth_service.login(db, body.email, body.password, client_ip(request), _ua(request))
    _set_refresh_cookie(response, tokens)
    return _token_response(user, tokens)


@router.post("/refresh", response_model=TokenResponse, summary="Exchange the refresh cookie for a new access token")
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    raw = request.cookies.get(settings.REFRESH_COOKIE_NAME)
    try:
        user, tokens = auth_service.refresh(db, raw, client_ip(request), _ua(request))
    except Exception:
        response.delete_cookie(settings.REFRESH_COOKIE_NAME, path=COOKIE_PATH)
        raise
    _set_refresh_cookie(response, tokens)
    return _token_response(user, tokens)


@router.post("/logout", response_model=Message)
def logout(
    request: Request,
    response: Response,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    auth_service.logout(db, ctx, request.cookies.get(settings.REFRESH_COOKIE_NAME))
    response.delete_cookie(settings.REFRESH_COOKIE_NAME, path=COOKIE_PATH)
    return Message(message="Signed out")


@router.get("/me", response_model=CurrentUser)
def me(user: User = Depends(get_current_user)):
    return CurrentUser.from_user(user)


@router.post("/change-password", response_model=TokenResponse)
def change_password(
    body: ChangePasswordRequest,
    response: Response,
    ctx: RequestContext = Depends(get_request_context),
    db: Session = Depends(get_db),
):
    tokens = auth_service.change_password(db, ctx, body.current_password, body.new_password)
    _set_refresh_cookie(response, tokens)
    return _token_response(ctx.user, tokens)


@router.post("/forgot-password", response_model=Message)
def forgot_password(body: ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)):
    auth_service.forgot_password(db, body.email, client_ip(request), _ua(request))
    return Message(message="If an account exists for that email, a reset link has been sent.")


@router.post("/reset-password", response_model=Message, summary="Set a new password using an emailed link token")
def reset_password(body: ResetPasswordRequest, request: Request, db: Session = Depends(get_db)):
    auth_service.reset_password(db, body.token, body.new_password, client_ip(request), _ua(request))
    return Message(message="Password updated. You can now sign in.")
