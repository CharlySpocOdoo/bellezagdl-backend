import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Boolean, Integer, Numeric,
    DateTime, ForeignKey, Text
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy import Enum as SAEnum

from app.database import Base
from app.modules.shared_enums import OrderStatus, FailureReason, SaleType  # ── NUEVO: SaleType


class Order(Base):
    __tablename__ = "orders"

    id                      = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_number            = Column(String(50), unique=True, nullable=False)
    client_id               = Column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=False)
    vendor_id               = Column(UUID(as_uuid=True), ForeignKey("vendors.id"), nullable=True)
    delivery_person_id      = Column(UUID(as_uuid=True), ForeignKey("delivery_persons.id"), nullable=True)
    shipment_id             = Column(UUID(as_uuid=True), ForeignKey("shipments.id"), nullable=True)
    supplier_id             = Column(UUID(as_uuid=True), ForeignKey("suppliers.id"), nullable=True)
    supplier_contact_id     = Column(UUID(as_uuid=True), ForeignKey("supplier_contacts.id"), nullable=True)
    status                  = Column(SAEnum(OrderStatus), nullable=False, default=OrderStatus.pending)
    sale_type               = Column(SAEnum(SaleType), nullable=True, default=SaleType.retail)  # ── NUEVO
    subtotal                = Column(Numeric(10, 2), nullable=False)
    vendor_discount_amount  = Column(Numeric(10, 2), default=0)
    shipping_cost           = Column(Numeric(10, 2), default=0)
    tax_amount              = Column(Numeric(10, 2), default=0)
    total                   = Column(Numeric(10, 2), nullable=False)
    original_total          = Column(Numeric(10, 2), nullable=True)
    delivery_address        = Column(Text, nullable=True)
    notes                   = Column(Text, nullable=True)
    vendor_notes            = Column(Text, nullable=True)
    is_vendor_purchase      = Column(Boolean, default=False)
    delivery_attempts       = Column(Integer, default=0)
    supplier_assigned_at    = Column(DateTime, nullable=True)
    partial_accepted_at     = Column(DateTime, nullable=True)
    confirmed_at            = Column(DateTime, nullable=True)
    delivered_at            = Column(DateTime, nullable=True)
    cancelled_at            = Column(DateTime, nullable=True)
    created_at              = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at              = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    items                   = relationship("OrderItem", back_populates="order")
    status_history          = relationship("OrderStatusHistory", back_populates="order")


class OrderItem(Base):
    __tablename__ = "order_items"

    id                          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id                    = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False)
    product_id                  = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    variant_id                  = Column(UUID(as_uuid=True), ForeignKey("product_variants.id"), nullable=True)
    product_name_snapshot       = Column(String(255), nullable=False)
    variant_name_snapshot       = Column(String(255), nullable=True)
    sku_snapshot                = Column(String(100), nullable=False)
    cost_price_snapshot         = Column(Numeric(10, 2), nullable=False)
    sale_price_snapshot         = Column(Numeric(10, 2), nullable=False)
    unit_price                  = Column(Numeric(10, 2), nullable=False)
    quantity                    = Column(Integer, nullable=False)
    subtotal                    = Column(Numeric(10, 2), nullable=False)
    commission_amount_snapshot  = Column(Numeric(10, 2), nullable=True)
    cancelled_in_partial        = Column(Boolean, default=False)
    partial_cancellation_reason = Column(Text, nullable=True)
    partial_cancelled_at        = Column(DateTime, nullable=True)
    returned_quantity           = Column(Integer, default=0, nullable=True)
    return_reason               = Column(String(50), nullable=True)
    returned_at                 = Column(DateTime, nullable=True)

    order                       = relationship("Order", back_populates="items")


class OrderStatusHistory(Base):
    __tablename__ = "order_status_history"

    id                      = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id                = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False)
    from_status             = Column(SAEnum(OrderStatus), nullable=True)
    to_status               = Column(SAEnum(OrderStatus), nullable=False)
    changed_by              = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    notes                   = Column(Text, nullable=True)
    failure_reason          = Column(SAEnum(FailureReason), nullable=True)
    delivery_attempt_number = Column(Integer, nullable=True)
    delivery_person_id      = Column(UUID(as_uuid=True), ForeignKey("delivery_persons.id"), nullable=True)
    created_at              = Column(DateTime, default=datetime.utcnow, nullable=False)

    order                   = relationship("Order", back_populates="status_history")


class Shipment(Base):
    __tablename__ = "shipments"

    id                   = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    delivery_person_id   = Column(UUID(as_uuid=True), ForeignKey("delivery_persons.id"), nullable=False)
    vendor_id            = Column(UUID(as_uuid=True), ForeignKey("vendors.id"), nullable=True)          # ── NUEVO: nullable
    delivered_at         = Column(DateTime, nullable=True)
    order_count          = Column(Integer, default=0)
    total_amount         = Column(Numeric(10, 2), default=0)
    shipping_cost        = Column(Numeric(10, 2), default=0)
    shipping_cost_waived = Column(Boolean, default=False)
    notes                = Column(Text, nullable=True)
    wholesale_client_id  = Column(UUID(as_uuid=True), ForeignKey("clients.id"), nullable=True)          # ── NUEVO
    sale_type            = Column(SAEnum(SaleType), nullable=True)                                       # ── NUEVO