from datetime import datetime
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field

T = TypeVar("T")

__all__ = [
    "AddOrganizationMember",
    "AuditLogRead",
    "ItemCreate",
    "ItemCreated",
    "ItemRead",
    "OrganizationCreate",
    "OrganizationMemberListItem",
    "OrganizationMemberRead",
    "OrganizationRead",
    "Page",
    "Token",
    "UserCreate",
    "UserLogin",
    "UserRead",
]

# shared generic page response model
class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class UserCreate(BaseModel):
    full_name: str = Field(max_length=255)
    email: EmailStr = Field(max_length=320)
    password: str = Field(max_length=255)


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str = Field(max_length=255)
    email: EmailStr = Field(max_length=320)


class UserLogin(BaseModel):
    email: EmailStr = Field(max_length=320)
    password: str = Field(max_length=255)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class OrganizationCreate(BaseModel):
    org_name: str = Field(max_length=255)


class OrganizationRead(BaseModel):
    org_id: int
    org_name: str = Field(max_length=255)


class AddOrganizationMember(BaseModel):
    email: EmailStr = Field(max_length=320)
    role: Literal["admin", "member"]


class OrganizationMemberRead(BaseModel):
    org_id: int
    user_id: int
    email: EmailStr
    role: str


class OrganizationMemberListItem(BaseModel):
    user_id: int
    full_name: str
    email: EmailStr
    role: str


class ItemCreate(BaseModel):
    item_details: dict[str, Any]


class ItemCreated(BaseModel):
    item_id: int


class ItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    item_id: int
    org_id: int
    user_id: int
    created_at: datetime
    item_details: dict[str, Any]


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    audit_id: int
    created_at: datetime
    org_id: int | None
    user_id: int | None
    action: str
    resource_type: str
    resource_id: int | None
    details: dict[str, Any] | None
