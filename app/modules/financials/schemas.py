from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime, date
from decimal import Decimal


class FinancialReportResponse(BaseModel):
    period_from: date
    period_to: date
    total_orders: int
    delivered_orders: int
    gross_revenue: Decimal
    total_cost: Decimal
    gross_profit: Decimal
    commissions_paid: Decimal
    tax_amount: Decimal
    net_profit: Decimal
    gross_margin_pct: Decimal
    # ── NUEVO: separación por sale_type ──
    retail_revenue: Optional[Decimal] = None       # Ingresos menudeo
    retail_profit: Optional[Decimal] = None        # Ganancia menudeo
    wholesale_revenue: Optional[Decimal] = None    # Ingresos mayoreo
    wholesale_profit: Optional[Decimal] = None     # Ganancia mayoreo (100% admin)


class DashboardMetric(BaseModel):
    label: str
    value: int


class DashboardResponse(BaseModel):
    date: date
    orders_by_status: List[DashboardMetric]
    todays_revenue: Decimal
    todays_orders: int
    pending_commissions: Decimal
    active_vendors: int
    low_stock_products: int