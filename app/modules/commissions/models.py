import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Boolean, Numeric,
    DateTime, ForeignKey, Text, Date
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy import Enum as SAEnum
import enum

from app.database import Base


class CommissionBase(str, enum.Enum):
    purchase_price = "purchase_price"
    sale_price     = "sale_price"


class CommissionPeriodStatus(str, enum.Enum):
    pending   = "pending"
    confirmed = "confirmed"
    paid      = "paid"


class CommissionSettings(Base):
    __tablename__ = "commission_settings"

    id                                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    commission_percentage               = Column(Numeric(5, 2), nullable=False)
    commission_base                     = Column(SAEnum(CommissionBase), nullable=True)
    active_from                         = Column(DateTime, nullable=False, default=datetime.utcnow)
    active_to                           = Column(DateTime, nullable=True)


class CommissionPeriod(Base):
    __tablename__ = "commission_periods"

    id                     = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vendor_id              = Column(UUID(as_uuid=True), ForeignKey("vendors.id"), nullable=False)
    week_start             = Column(Date, nullable=False)
    week_end               = Column(Date, nullable=False)
    gross_sales_amount     = Column(Numeric(10, 2), default=0, nullable=False)
    cost_amount            = Column(Numeric(10, 2), default=0, nullable=False)
    commission_base_amount = Column(Numeric(10, 2), default=0, nullable=False)
    commission_rate        = Column(Numeric(5, 2), nullable=False)
    commission_amount      = Column(Numeric(10, 2), default=0, nullable=False)
    net_commission         = Column(Numeric(10, 2), default=0, nullable=False)
    status                 = Column(SAEnum(CommissionPeriodStatus), nullable=False, default=CommissionPeriodStatus.pending)
    confirmed_at           = Column(DateTime, nullable=True)
    paid_at                = Column(DateTime, nullable=True)
    notes                  = Column(Text, nullable=True)

    vendor                 = relationship("Vendor", foreign_keys=[vendor_id])


class TaxSettings(Base):
    __tablename__ = "tax_settings"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tax_name     = Column(String(100), nullable=False)
    tax_percentage = Column(Numeric(5, 2), default=0, nullable=False)
    active       = Column(Boolean, default=False, nullable=False)
    applies_from = Column(DateTime, nullable=True)
