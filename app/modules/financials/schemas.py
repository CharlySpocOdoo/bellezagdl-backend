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
    gross_revenue: Decimal        # Suma de Precio Venta x cantidad
    total_cost: Decimal           # Suma de Precio Costo x cantidad
    gross_profit: Decimal         # gross_revenue - total_cost
    commissions_paid: Decimal     # Comisiones pagadas a vendedores
    shipping_costs: Decimal       # Costos de envio de shipments
    tax_amount: Decimal           # Impuestos (0 por ahora)
    net_profit: Decimal           # gross_profit - comisiones - envios - impuestos
    gross_margin_pct: Decimal     # gross_profit / gross_revenue x 100


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
