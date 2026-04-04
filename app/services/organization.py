from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.membership import Membership, MembershipRole
from app.models.organization import Organization
from app.models.user import User
from app.schemas import AuditLogRead


class OrganizationNotFoundError(Exception):
    pass


class NotOrgAdminError(Exception):
    pass


class MemberUserNotFoundError(Exception):
    pass


class AlreadyMemberError(Exception):
    pass


def _require_organization_admin(
    db: Session,
    org_id: int,
    actor: User,
) -> Organization:
    org = db.get(Organization, org_id)
    if org is None:
        raise OrganizationNotFoundError
    actor_row = db.execute(
        select(Membership).where(
            Membership.org_id == org_id,
            Membership.user_id == actor.id,
        )
    ).scalar_one_or_none()
    if actor_row is None or actor_row.role != MembershipRole.admin.value:
        raise NotOrgAdminError
    return org


def create_organization(db: Session, user: User, org_name: str) -> Organization:
    org = Organization(org_name=org_name)
    db.add(org)
    db.flush()
    db.add(
        Membership(
            org_id=org.org_id,
            user_id=user.id,
            role=MembershipRole.admin.value,
        )
    )
    db.add(
        AuditLog(
            org_id=org.org_id,
            user_id=user.id,
            action="organization.create",
            resource_type="organization",
            resource_id=org.org_id,
            details={"org_name": org_name},
        )
    )
    db.commit()
    db.refresh(org)
    return org


def add_member_by_email(
    db: Session,
    org_id: int,
    actor: User,
    email: str,
    role: MembershipRole,
) -> tuple[Membership, User]:
    _require_organization_admin(db, org_id, actor)

    normalized = email.lower()
    target = db.execute(select(User).where(User.email == normalized)).scalar_one_or_none()
    if target is None:
        raise MemberUserNotFoundError

    existing = db.execute(
        select(Membership).where(
            Membership.org_id == org_id,
            Membership.user_id == target.id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        raise AlreadyMemberError

    membership = Membership(
        org_id=org_id,
        user_id=target.id,
        role=role.value,
    )
    db.add(membership)
    db.commit()
    db.refresh(membership)
    return membership, target


def list_organization_members(
    db: Session,
    org_id: int,
    actor: User,
    limit: int,
    offset: int,
) -> tuple[list[tuple[Membership, User]], int]:
    _require_organization_admin(db, org_id, actor)

    total = db.scalar(
        select(func.count()).select_from(Membership).where(Membership.org_id == org_id)
    )
    if total is None:
        total = 0

    stmt = (
        select(Membership, User)
        .join(User, Membership.user_id == User.id)
        .where(Membership.org_id == org_id)
        .order_by(User.email)
        .limit(limit)
        .offset(offset)
    )
    rows = db.execute(stmt).all()
    return rows, total


def search_organization_members(
    db: Session,
    org_id: int,
    actor: User,
    q: str,
    limit: int,
    offset: int,
) -> tuple[list[tuple[Membership, User]], int]:
    """Filter org members with PostgreSQL FTS: search_vector @@ plainto_tsquery."""
    _require_organization_admin(db, org_id, actor)

    tsq = func.plainto_tsquery("english", q)
    fts_match = User.search_vector.op("@@")(tsq)

    count_stmt = (
        select(func.count())
        .select_from(Membership)
        .join(User, Membership.user_id == User.id)
        .where(Membership.org_id == org_id, fts_match)
    )
    total = db.scalar(count_stmt)
    if total is None:
        total = 0

    rank = func.ts_rank_cd(User.search_vector, tsq)
    stmt = (
        select(Membership, User)
        .join(User, Membership.user_id == User.id)
        .where(Membership.org_id == org_id, fts_match)
        .order_by(rank.desc(), User.email)
        .limit(limit)
        .offset(offset)
    )
    rows = db.execute(stmt).all()
    return rows, total


def list_organization_audit_logs(
    db: Session,
    org_id: int,
    actor: User,
    limit: int,
    offset: int,
) -> tuple[list[AuditLogRead], int]:
    _require_organization_admin(db, org_id, actor)

    total = db.scalar(
        select(func.count()).select_from(AuditLog).where(AuditLog.org_id == org_id)
    )
    if total is None:
        total = 0

    stmt = (
        select(AuditLog)
        .where(AuditLog.org_id == org_id)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = list(db.scalars(stmt).all())
    return [AuditLogRead.model_validate(r) for r in rows], total
