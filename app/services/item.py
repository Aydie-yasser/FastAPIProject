from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.item import Item
from app.models.membership import Membership, MembershipRole
from app.models.organization import Organization
from app.models.user import User
from app.schemas import ItemRead
from app.services.organization import OrganizationNotFoundError


class NotOrgMemberError(Exception):
    pass


def _require_organization_member(
    db: Session,
    org_id: int,
    actor: User,
) -> Organization:
    org = db.get(Organization, org_id)
    if org is None:
        raise OrganizationNotFoundError
    row = db.execute(
        select(Membership).where(
            Membership.org_id == org_id,
            Membership.user_id == actor.id,
        )
    ).scalar_one_or_none()
    if row is None:
        raise NotOrgMemberError
    return org


def create_item(
    db: Session,
    org_id: int,
    actor: User,
    item_details: dict[str, Any],
) -> Item:
    _require_organization_member(db, org_id, actor)

    item = Item(
        org_id=org_id,
        user_id=actor.id,
        item_details=item_details,
    )
    db.add(item)
    db.flush()

    db.add(
        AuditLog(
            org_id=org_id,
            user_id=actor.id,
            action="item.create",
            resource_type="item",
            resource_id=item.item_id,
            details={"item_details": item_details},
        )
    )
    db.commit()
    db.refresh(item)
    return item


def list_organization_items(
    db: Session,
    org_id: int,
    actor: User,
    limit: int,
    offset: int,
) -> tuple[list[ItemRead], int]:
    """Members: own items only. Admins: all org items. Writes audit_log per request."""
    _require_organization_member(db, org_id, actor)

    m_row = db.execute(
        select(Membership).where(
            Membership.org_id == org_id,
            Membership.user_id == actor.id,
        )
    ).scalar_one()
    is_admin = m_row.role == MembershipRole.admin.value

    filters = [Item.org_id == org_id]
    if not is_admin:
        filters.append(Item.user_id == actor.id)
    where_clause = and_(*filters)

    total = db.scalar(select(func.count()).select_from(Item).where(where_clause))
    if total is None:
        total = 0

    stmt = (
        select(Item)
        .where(where_clause)
        .order_by(Item.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = list(db.scalars(stmt).all())
    item_reads = [ItemRead.model_validate(r) for r in rows]

    db.add(
        AuditLog(
            org_id=org_id,
            user_id=actor.id,
            action="item.list",
            resource_type="item",
            resource_id=None,
            details={
                "limit": limit,
                "offset": offset,
                "total_matching": total,
                "returned_count": len(item_reads),
                "scope": "all" if is_admin else "own",
            },
        )
    )
    db.commit()
    return item_reads, total
