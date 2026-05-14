import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Boolean, DateTime,
    ForeignKey, Text, Numeric, Date, Integer
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy import Enum as SAEnum

from app.database import Base
from app.modules.shared_enums import (
    Gender, UserRole, WorkplaceType, InvitationType
)


class User(Base):
    __tablename__ = "users"

    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email             = Column(String(255), unique=True, nullable=False)
    phone             = Column(String(50), nullable=True)
    password_hash     = Column(String(255), nullable=False)
    role              = Column(SAEnum(UserRole), nullable=False)
    active            = Column(Boolean, default=True)
    email_verified_at = Column(DateTime, nullable=True)
    last_login_at     = Column(DateTime, nullable=True)

    refresh_tokens    = relationship("RefreshToken", back_populates="user")
    vendor            = relationship("Vendor", back_populates="user", uselist=False)
    client            = relationship("Client", back_populates="user", uselist=False)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id     = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    token_hash  = Column(String(255), nullable=False)
    device_hint = Column(String(255), nullable=True)
    expires_at  = Column(DateTime, nullable=False)
    revoked_at  = Column(DateTime, nullable=True)

    user        = relationship("User", back_populates="refresh_tokens")


class Vendor(Base):
    __tablename__ = "vendors"

    id                    = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id               = Column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False)
    display_name          = Column(String(255), nullable=False)
    first_name            = Column(String(255), nullable=False)
    last_name             = Column(String(255), nullable=False)
    gender                = Column(SAEnum(Gender), nullable=True)
    birth_date            = Column(Date, nullable=True)
    phone                 = Column(String(50), nullable=True)
    address               = Column(Text, nullable=True)
    workplace             = Column(String(255), nullable=True)
    workplace_type        = Column(SAEnum(WorkplaceType), nullable=True)
    invitation_code       = Column(String(20), unique=True, nullable=False)
    invitation_token      = Column(String(255), unique=True, nullable=False)
    active                = Column(Boolean, default=True)
    notes                 = Column(Text, nullable=True)
    commission_percentage = Column(Numeric(5, 2), nullable=True)

    user                  = relationship("User", back_populates="vendor")
    clients               = relationship("Client", back_populates="vendor")
    invitations           = relationship("Invitation", back_populates="vendor")


class Client(Base):
    __tablename__ = "clients"

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id          = Column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False)
    vendor_id        = Column(UUID(as_uuid=True), ForeignKey("vendors.id"), nullable=False)
    first_name       = Column(String(255), nullable=False)
    last_name        = Column(String(255), nullable=False)
    gender           = Column(SAEnum(Gender), nullable=True)
    birth_date       = Column(Date, nullable=True)
    phone            = Column(String(50), nullable=True)
    delivery_address = Column(Text, nullable=True)
    active           = Column(Boolean, default=True)
    last_order_at    = Column(DateTime, nullable=True)
    notes            = Column(Text, nullable=True)
    created_at       = Column(DateTime, default=datetime.utcnow, nullable=True)

    user             = relationship("User", back_populates="client")
    vendor           = relationship("Vendor", back_populates="clients")


class Invitation(Base):
    __tablename__ = "invitations"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vendor_id   = Column(UUID(as_uuid=True), ForeignKey("vendors.id"), nullable=True)
    created_by  = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    token       = Column(String(255), unique=True, nullable=False)
    type        = Column(SAEnum(InvitationType), nullable=False)
    email_hint  = Column(String(255), nullable=True)
    max_uses    = Column(Integer, nullable=True)
    use_count   = Column(Integer, default=0, nullable=False)
    expires_at  = Column(DateTime, nullable=True)

    vendor      = relationship("Vendor", back_populates="invitations")
