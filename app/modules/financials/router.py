from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID
from datetime import date, timedelta
from datetime import datetime

from app.database import get_db
from app.modules.auth.dependencies import require_admin
from app.modules.auth.models import User
from app.modules.financials import service
from app.modules.financials.schemas import (
    FinancialReportResponse, DashboardResponse, DashboardMetric,
)

router = APIRouter()


@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Metricas del dia para el admin."""
    data = service.get_dashboard(db)
    return DashboardResponse(
        date=data["date"],
        orders_by_status=[
            DashboardMetric(label=item["label"], value=item["value"])
            for item in data["orders_by_status"]
        ],
        todays_revenue=data["todays_revenue"],
        todays_orders=data["todays_orders"],
        pending_commissions=data["pending_commissions"],
        active_vendors=data["active_vendors"],
        low_stock_products=data["low_stock_products"],
    )


@router.get("/financials", response_model=FinancialReportResponse)
def get_financial_report(
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    vendor_id: Optional[UUID] = Query(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Reporte financiero completo.
    Si no se especifican fechas usa el mes actual.
    """
    if not date_from:
        today = datetime.utcnow().date()
        date_from = today.replace(day=1)
    if not date_to:
        date_to = datetime.utcnow().date()

    data = service.get_financial_report(
        db=db,
        date_from=date_from,
        date_to=date_to,
        vendor_id=vendor_id,
    )
    return FinancialReportResponse(**data)
