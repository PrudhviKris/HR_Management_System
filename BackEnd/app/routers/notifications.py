from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.exceptions import NotFoundError
from app.models import Notification, User
from app.repositories.base import paginate
from app.schemas.admin import NotificationOut
from app.schemas.common import Message, Page

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=Page[NotificationOut])
def my_notifications(
    page: int = Query(1, ge=1), page_size: int = Query(10, ge=1, le=50), unread_only: bool = False,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    stmt = select(Notification).where(Notification.user_id == user.id).order_by(Notification.id.desc())
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))
    return paginate(db, stmt, page, page_size)


@router.get("/unread-count")
def unread_count(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    n = db.scalar(select(func.count(Notification.id)).where(Notification.user_id == user.id, Notification.is_read.is_(False)))
    return {"count": n or 0}


@router.post("/{notification_id}/read", response_model=NotificationOut)
def mark_read(notification_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    n = db.get(Notification, notification_id)
    if n is None or n.user_id != user.id:
        raise NotFoundError("Notification not found")
    n.is_read = True
    db.commit()
    return n


@router.post("/read-all", response_model=Message)
def mark_all_read(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.execute(update(Notification).where(Notification.user_id == user.id, Notification.is_read.is_(False)).values(is_read=True))
    db.commit()
    return Message(message="All notifications marked as read")
