from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from decimal import Decimal
from app.modules.shared_enums import OrderStatus, FailureReason


# ── Request schemas ───────────────────────────────────────────────────────────

class OrderItemRequest(BaseModel):
    variant_id: UUID
    quantity: int


class CreateOrderRequest(BaseModel):
    items: List[OrderItemRequest]
    delivery_address: Optional[str] = None
    notes: Optional[str] = None
    is_vendor_purchase: bool = False
    client_id: Optional[UUID] = None  # Solo si vendor crea para un cliente de su red


class UpdateStatusRequest(BaseModel):
    status: OrderStatus
    notes: Optional[str] = None
    failure_reason: Optional[FailureReason] = None
    delivery_person_id: Optional[UUID] = None


class MarkUnavailableRequest(BaseModel):
    unavailable_variant_ids: List[UUID]
    notes: Optional[str] = None


class PartialAcceptRequest(BaseModel):
    accept: bool  # True = acepta parcial, False = cancela todo
    notes: Optional[str] = None


class AddNotesRequest(BaseModel):
    vendor_notes: Optional[str] = None
    notes: Optional[str] = None


# ── Response schemas ──────────────────────────────────────────────────────────

class OrderItemResponse(BaseModel):
    id: UUID
    product_id: UUID
    variant_id: Optional[UUID] = None
    product_name_snapshot: str
    variant_name_snapshot: Optional[str] = None
    sku_snapshot: str
    cost_price_snapshot: Decimal
    sale_price_snapshot: Decimal
    unit_price: Decimal
    quantity: int
    subtotal: Decimal
    commission_amount_snapshot: Optional[Decimal] = None
    cancelled_in_partial: bool = False
    returned_quantity: Optional[int] = 0
    return_reason: Optional[str] = None

    class Config:
        from_attributes = True


class StatusHistoryResponse(BaseModel):
    id: UUID
    from_status: Optional[OrderStatus] = None
    to_status: OrderStatus
    notes: Optional[str] = None
    failure_reason: Optional[FailureReason] = None
    delivery_attempt_number: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class OrderResponse(BaseModel):
    id: UUID
    order_number: str
    client_id: UUID
    vendor_id: UUID
    client_name: Optional[str] = None
    status: OrderStatus
    subtotal: Decimal
    shipping_cost: Decimal
    tax_amount: Decimal
    total: Decimal
    original_total: Optional[Decimal] = None
    delivery_address: Optional[str] = None
    notes: Optional[str] = None
    vendor_notes: Optional[str] = None
    is_vendor_purchase: bool
    delivery_attempts: int
    confirmed_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    items: List[OrderItemResponse] = []
    status_history: List[StatusHistoryResponse] = []

    class Config:
        from_attributes = True


class OrderListResponse(BaseModel):
    id: UUID
    order_number: str
    client_id: UUID
    vendor_id: UUID
    client_name: Optional[str] = None
    status: OrderStatus
    total: Decimal
    is_vendor_purchase: bool
    vendor_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
