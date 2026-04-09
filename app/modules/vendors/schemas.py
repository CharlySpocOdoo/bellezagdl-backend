from pydantic import BaseModel, EmailStr
from typing import Optional, List
from uuid import UUID
from datetime import datetime, date
from app.modules.shared_enums import Gender, WorkplaceType


# ── Request schemas ───────────────────────────────────────────────────────────

class CreateVendorRequest(BaseModel):
    email: EmailStr
    display_name: str
    first_name: str
    last_name: str
    phone: Optional[str] = None
    address: Optional[str] = None
    gender: Optional[Gender] = None
    birth_date: Optional[date] = None
    workplace: Optional[str] = None
    workplace_type: Optional[WorkplaceType] = None
    notes: Optional[str] = None


class UpdateVendorRequest(BaseModel):
    display_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    gender: Optional[Gender] = None
    birth_date: Optional[date] = None
    workplace: Optional[str] = None
    workplace_type: Optional[WorkplaceType] = None
    notes: Optional[str] = None
    active: Optional[bool] = None
    commission_percentage: Optional[float] = None


# ── Response schemas ──────────────────────────────────────────────────────────

class VendorResponse(BaseModel):
    id: UUID
    user_id: UUID
    display_name: str
    first_name: str
    last_name: str
    email: str
    phone: Optional[str] = None
    address: Optional[str] = None
    gender: Optional[Gender] = None
    birth_date: Optional[date] = None
    workplace: Optional[str] = None
    workplace_type: Optional[WorkplaceType] = None
    invitation_code: str
    active: bool
    notes: Optional[str] = None
    commission_percentage: Optional[float] = None

    class Config:
        from_attributes = True


class VendorProfileResponse(VendorResponse):
    invitation_link: str
    total_clients: int = 0
    total_orders: int = 0


class ClientResponse(BaseModel):
    id: UUID
    user_id: UUID
    first_name: str
    last_name: str
    email: str
    phone: Optional[str] = None
    delivery_address: Optional[str] = None
    gender: Optional[Gender] = None
    birth_date: Optional[date] = None
    active: bool
    last_order_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class NotificationResponse(BaseModel):
    id: UUID
    type: str
    title: str
    body: str
    read_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True
