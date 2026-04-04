from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import get_current_user
from app.models.membership import MembershipRole
from app.models.user import User
from app.schemas import (
    AddOrganizationMember,
    AuditLogRead,
    ItemCreate,
    ItemCreated,
    ItemRead,
    OrganizationCreate,
    OrganizationMemberListItem,
    OrganizationMemberRead,
    OrganizationRead,
    Page,
)
from app.services.item import NotOrgMemberError, create_item, list_organization_items
from app.services.organization import (
    AlreadyMemberError,
    MemberUserNotFoundError,
    NotOrgAdminError,
    OrganizationNotFoundError,
    add_member_by_email,
    create_organization,
    list_organization_audit_logs,
    list_organization_members,
    search_organization_members,
)

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.post(
    "/",
    response_model=OrganizationRead,
    status_code=status.HTTP_201_CREATED,
)
def create_org(
    body: OrganizationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return create_organization(db, current_user, body.org_name)


@router.get("/{org_id}/users/search", response_model=Page[OrganizationMemberListItem])
def search_organization_users(
    org_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    q: str = Query(..., min_length=1, max_length=200, description="Full-text search on name and email"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """Org admins only. Uses PostgreSQL `tsvector` / `tsquery` (see `users.search_vector` + GIN index)."""
    try:
        rows, total = search_organization_members(
            db, org_id, current_user, q=q, limit=limit, offset=offset
        )
    except OrganizationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    except NotOrgAdminError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only organization admins can search members",
        )
    items = [
        OrganizationMemberListItem(
            user_id=user.id,
            full_name=user.full_name,
            email=user.email,
            role=m.role,
        )
        for m, user in rows
    ]
    return Page(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{org_id}/users", response_model=Page[OrganizationMemberListItem])
def list_organization_users(
    org_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """Return paginated org members. Caller must be an admin of this org.
    `total` is how many members exist in the org; `items` is only the current page."""
    try:
        rows, total = list_organization_members(
            db, org_id, current_user, limit=limit, offset=offset
        )
    except OrganizationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    except NotOrgAdminError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only organization admins can list members",
        )
    # Map join rows to API models: m = membership (role), user = profile fields (no password).
    items = [
        OrganizationMemberListItem(
            user_id=user.id,
            full_name=user.full_name,
            email=user.email,
            role=m.role,
        )
        for m, user in rows
    ]
    return Page(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{org_id}/audit-logs", response_model=Page[AuditLogRead])
def list_organization_audit_logs_endpoint(
    org_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    try:
        items, total = list_organization_audit_logs(
            db, org_id, current_user, limit=limit, offset=offset
        )
    except OrganizationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    except NotOrgAdminError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only organization admins can view audit logs",
        )
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.get("/{org_id}/item", response_model=Page[ItemRead])
def list_organization_items_endpoint(
    org_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """Members see only their items; admins see all. Each request appends `audit_log` (`item.list`)."""
    try:
        items, total = list_organization_items(
            db, org_id, current_user, limit=limit, offset=offset
        )
    except OrganizationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    except NotOrgMemberError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must be a member of this organization to list items",
        )
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.post(
    "/{org_id}/item",
    response_model=ItemCreated,
    status_code=status.HTTP_201_CREATED,
)
def create_organization_item(
    org_id: int,
    body: ItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Any org member (admin or member) may create items; writes an audit_log row."""
    try:
        item = create_item(db, org_id, current_user, body.item_details)
        return ItemCreated(item_id=item.item_id)
    except OrganizationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    except NotOrgMemberError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must be a member of this organization to create items",
        )


@router.post(
    "/{org_id}/user",
    response_model=OrganizationMemberRead,
    status_code=status.HTTP_201_CREATED,
)
def add_organization_user(
    org_id: int,
    body: AddOrganizationMember,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        membership, target_user = add_member_by_email(
            db,
            org_id,
            current_user,
            str(body.email),
            MembershipRole(body.role),
        )
    except OrganizationNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    except NotOrgAdminError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only organization admins can add members",
        )
    except MemberUserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No user with this email",
        )
    except AlreadyMemberError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already a member of this organization",
        )
    return OrganizationMemberRead(
        org_id=membership.org_id,
        user_id=membership.user_id,
        email=target_user.email,
        role=membership.role,
    )
