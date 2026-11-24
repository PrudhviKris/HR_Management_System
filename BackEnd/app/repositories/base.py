import math
from typing import Any, TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.database import Base
from app.exceptions import NotFoundError

M = TypeVar("M", bound=Base)


def get_or_404(db: Session, model: type[M], obj_id: Any, label: str | None = None) -> M:
    obj = db.get(model, obj_id)
    if obj is None:
        raise NotFoundError(f"{label or model.__name__} not found")
    return obj


def paginate(db: Session, stmt: Select, page: int, page_size: int) -> dict:
    """Runs a COUNT over the filtered statement then fetches one page. Returns the Page dict shape."""
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    items = db.scalars(stmt.limit(page_size).offset((page - 1) * page_size)).unique().all()
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": math.ceil(total / page_size) if page_size else 0,
    }


def escape_like(term: str) -> str:
    return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
