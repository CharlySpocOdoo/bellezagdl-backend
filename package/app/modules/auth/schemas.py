from pydantic import BaseModel, EmailStr
from typing import Optional
from uuid import UUID
from datetime import datetime
from app.modules.shared_enums import UserRole


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class RegisterClientRequest(BaseModel):
    invitation_token: str
    first_name: str
    last_name: str
    email: EmailStr
    password: str
    phone: Optional[str] = None
    delivery_address: Optional[str] = None


class ActivateVendorRequest(BaseModel):
    invitation_token: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserProfileResponse(BaseModel):
    id: UUID
    email: str
    role: UserRole
    active: bool
    profile_id: Optional[UUID] = None
    display_name: Optional[str] = None

    class Config:
        from_attributes = True


class InviteValidationResponse(BaseModel):
    valid: bool
    type: str
    vendor_name: Optional[str] = None
    email_hint: Optional[str] = None
