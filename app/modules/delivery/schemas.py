from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from decimal import Decimal
from app.modules.shared_enums import OrderStatus


# ── Request schemas ───────────────────────────────────────────────────────────

class CreateDeliveryPersonRequest(BaseModel):
    first_name: str
    last_name: str
    phone: str
    vehicle_type: Optional[str] = None
    notes: Optional[str] = None


class UpdateDeliveryPersonRequest(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    vehicle_type: Optional[str] = None
    notes: Optional[str] = None
    active: Optional[bool] = None


class CreateShipmentRequest(BaseModel):
    delivery_person_id: UUID
    vendor_id: UUID
    order_ids: List[UUID]
    notes: Optional[str] = None


# ── Response schemas ──────────────────────────────────────────────────────────

class DeliveryPersonResponse(BaseModel):
    id: UUID
    first_name: str
    last_name: str
    phone: str
    vehicle_type: Optional[str] = None
    active: bool
    notes: Optional[str] = None
    total_deliveries: int = 0
    total_failed: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class DeliveryHistoryResponse(BaseModel):
    order_id: UUID
    order_number: str
    vendor_id: UUID
    status: OrderStatus
    delivery_attempt_number: Optional[int] = None
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ShipmentResponse(BaseModel):
    id: UUID
    delivery_person_id: UUID
    vendor_id: UUID
    order_count: int
    total_amount: Decimal
    shipping_cost: Decimal
    shipping_cost_waived: bool
    notes: Optional[str] = None
    delivered_at: Optional[datetime] = None

    class Config:
        from_attributes = True
