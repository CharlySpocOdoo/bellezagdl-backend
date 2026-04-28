from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime, date
from decimal import Decimal
from app.modules.commissions.models import CommissionPeriodStatus


# ── Response schemas ──────────────────────────────────────────────────────────

class CommissionSettingsResponse(BaseModel):
    id: UUID
    commission_percentage: Decimal
    commission_base: Optional[str] = None
    min_shipment_amount_for_free_shipping: Optional[Decimal] = None
    active_from: datetime
    active_to: Optional[datetime] = None

    class Config:
        from_attributes = True


class CommissionPeriodResponse(BaseModel):
    id: UUID
    vendor_id: UUID
    week_start: date
    week_end: date
    gross_sales_amount: Decimal
    cost_amount: Decimal
    commission_base_amount: Decimal
    commission_rate: Decimal
    commission_amount: Decimal
    shipping_charges: Decimal
    net_commission: Decimal
    status: CommissionPeriodStatus
    confirmed_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    notes: Optional[str] = None

    class Config:
        from_attributes = True


class ConfirmCommissionRequest(BaseModel):
    notes: Optional[str] = None


class CalculateCommissionsResponse(BaseModel):
    week_start: date
    week_end: date
    vendors_processed: int
    periods_created: int
    periods_updated: int


class VendorCommissionSummaryResponse(BaseModel):
    current_week_commission: Decimal
    pending_payment: Decimal
    periods: List[CommissionPeriodResponse] = []
