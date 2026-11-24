from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import RequestContext
from app.core.permissions import ALL_PERMISSIONS, ROLE_ADMIN
from app.exceptions import ConflictError, ValidationError
from app.models import Permission, Role, User
from app.repositories.base import escape_like, get_or_404, paginate
from app.services import audit_service


def to_out(role: Role, user_count: int = 0) -> dict:
    return {
        "id": role.id, "name": role.name, "description": role.description, "is_system": role.is_system,
        "permissions": role.permission_codes, "user_count": user_count,
    }


def list_roles(db: Session) -> list[dict]:
    counts = dict(db.execute(select(User.role_id, func.count(User.id)).group_by(User.role_id)).all())
    return [to_out(r, counts.get(r.id, 0)) for r in db.scalars(select(Role).order_by(Role.id))]


def list_permissions(db: Session) -> list[Permission]:
    return list(db.scalars(select(Permission).order_by(Permission.module, Permission.code)))


def _resolve(db: Session, codes: list[str]) -> list[Permission]:
    unknown = set(codes) - set(ALL_PERMISSIONS)
    if unknown:
        raise ValidationError(f"Unknown permission(s): {', '.join(sorted(unknown))}")
    return list(db.scalars(select(Permission).where(Permission.code.in_(codes))))


def create_role(db: Session, ctx: RequestContext, name: str, description: str, codes: list[str]) -> dict:
    if db.scalar(select(Role).where(func.lower(Role.name) == name.lower())):
        raise ConflictError("A role with this name already exists")
    role = Role(name=name, description=description, is_system=False, permissions=_resolve(db, codes))
    db.add(role)
    db.flush()
    audit_service.record(
        db, ctx, "role.create", f"Created role {name}", entity_type="role", entity_id=role.id, changes={"permissions": sorted(codes)}
    )
    db.commit()
    return to_out(role)


def update_role(db: Session, ctx: RequestContext, role_id: int, name: str, description: str, codes: list[str]) -> dict:
    role = get_or_404(db, Role, role_id, "Role")
    if role.name == ROLE_ADMIN and set(codes) != set(ALL_PERMISSIONS):
        raise ValidationError("The Admin role always has every permission")
    if role.is_system and name != role.name:
        raise ValidationError("System roles cannot be renamed")
    if db.scalar(select(Role).where(func.lower(Role.name) == name.lower(), Role.id != role_id)):
        raise ConflictError("A role with this name already exists")
    before = set(role.permission_codes)
    role.name, role.description = name, description
    role.permissions = _resolve(db, codes)
    audit_service.record(
        db, ctx, "role.update", f"Updated role {role.name}", entity_type="role", entity_id=role.id,
        changes={"added": sorted(set(codes) - before), "removed": sorted(before - set(codes))},
    )
    db.commit()
    count = db.scalar(select(func.count(User.id)).where(User.role_id == role.id)) or 0
    return to_out(role, count)


def delete_role(db: Session, ctx: RequestContext, role_id: int) -> None:
    role = get_or_404(db, Role, role_id, "Role")
    if role.is_system:
        raise ValidationError("System roles cannot be deleted")
    if db.scalar(select(func.count(User.id)).where(User.role_id == role_id)):
        raise ConflictError("Role is assigned to users; reassign them first")
    audit_service.record(db, ctx, "role.delete", f"Deleted role {role.name}", entity_type="role", entity_id=role.id)
    db.delete(role)
    db.commit()


def list_users(db: Session, page: int, page_size: int, search: str | None, role_id: int | None) -> dict:
    stmt = select(User).order_by(User.full_name)
    if search:
        term = f"%{escape_like(search)}%"
        stmt = stmt.where(User.full_name.ilike(term, escape="\\") | User.email.ilike(term, escape="\\"))
    if role_id:
        stmt = stmt.where(User.role_id == role_id)
    res = paginate(db, stmt, page, page_size)
    res["items"] = [
        {
            "id": u.id, "email": u.email, "full_name": u.full_name, "role_id": u.role_id, "role": u.role.name,
            "is_active": u.is_active, "last_login_at": u.last_login_at,
            "employee_code": u.employee.employee_code if u.employee else None,
            "employee_id": u.employee.id if u.employee else None,
        }
        for u in res["items"]
    ]
    return res


def change_user_role(db: Session, ctx: RequestContext, user_id: int, role_id: int) -> User:
    user = get_or_404(db, User, user_id, "User")
    role = get_or_404(db, Role, role_id, "Role")
    if user.id == ctx.user_id:
        raise ValidationError("You cannot change your own role")
    if user.role.name == ROLE_ADMIN and role.name != ROLE_ADMIN:
        admins = db.scalar(
            select(func.count(User.id)).join(Role).where(Role.name == ROLE_ADMIN, User.is_active.is_(True))
        )
        if admins <= 1:
            raise ValidationError("At least one active administrator is required")
    old = user.role.name
    user.role_id = role.id
    audit_service.record(
        db, ctx, "user.role_change", f"Changed role of {user.full_name} from {old} to {role.name}",
        entity_type="user", entity_id=user.id, changes={"role": {"from": old, "to": role.name}},
    )
    db.commit()
    db.refresh(user)
    return user
