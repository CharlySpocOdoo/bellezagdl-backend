import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Boolean, Integer, Numeric,
    DateTime, ForeignKey, Text, Date
)
from sqlalchemy.dialects.postgresql import UUID, JSON, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy import Enum as SAEnum

from app.database import Base
from app.modules.shared_enums import Gender, SyncStatus


class DeliveryPerson(Base):
    __tablename__ = "delivery_persons"

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    first_name       = Column(String(255), nullable=False)
    last_name        = Column(String(255), nullable=False)
    phone            = Column(String(50), nullable=False)
    vehicle_type     = Column(String(100), nullable=True)
    active           = Column(Boolean, default=True)
    notes            = Column(Text, nullable=True)
    total_deliveries = Column(Integer, default=0)
    total_failed     = Column(Integer, default=0)
    created_at       = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at       = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class Supplier(Base):
    __tablename__ = "suppliers"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name          = Column(String(255), nullable=False)
    branch_name   = Column(String(255), nullable=True)
    address       = Column(Text, nullable=True)
    phone         = Column(String(50), nullable=True)
    business_type = Column(ARRAY(String), nullable=True)
    active        = Column(Boolean, default=True)
    notes         = Column(Text, nullable=True)
    created_at    = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at    = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    contacts      = relationship("SupplierContact", back_populates="supplier")


class SupplierContact(Base):
    __tablename__ = "supplier_contacts"

    id                    = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    supplier_id           = Column(UUID(as_uuid=True), ForeignKey("suppliers.id"), nullable=False)
    first_name            = Column(String(255), nullable=False)
    last_name             = Column(String(255), nullable=False)
    gender                = Column(SAEnum(Gender), nullable=True)
    birth_date            = Column(Date, nullable=True)
    phone                 = Column(String(50), nullable=True)
    commission_percentage = Column(Numeric(5, 2), nullable=True)
    active                = Column(Boolean, default=True)
    notes                 = Column(Text, nullable=True)
    total_orders          = Column(Integer, default=0)
    created_at            = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at            = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    supplier              = relationship("Supplier", back_populates="contacts")


class CatalogSyncLog(Base):
    __tablename__ = "catalog_sync_logs"

    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source            = Column(String(50), nullable=True)
    triggered_by      = Column(String(50), nullable=True)
    triggered_by_user = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    status            = Column(SAEnum(SyncStatus), nullable=False, default=SyncStatus.running)
    products_scanned  = Column(Integer, default=0)
    products_updated  = Column(Integer, default=0)
    images_uploaded   = Column(Integer, default=0)
    errors            = Column(JSON, nullable=True)
    duration_ms       = Column(Integer, nullable=True)
    started_at        = Column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at       = Column(DateTime, nullable=True)


class Notification(Base):
    __tablename__ = "notifications"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id    = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    type       = Column(String(100), nullable=False)
    title      = Column(String(255), nullable=False)
    body       = Column(Text, nullable=False)
    data       = Column(JSON, nullable=True)
    read_at    = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id     = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    action      = Column(String(255), nullable=False)
    entity_type = Column(String(100), nullable=False)
    entity_id   = Column(UUID(as_uuid=True), nullable=True)
    before      = Column(JSON, nullable=True)
    after       = Column(JSON, nullable=True)
    ip_address  = Column(String(50), nullable=True)
    created_at  = Column(DateTime, default=datetime.utcnow, nullable=False)
