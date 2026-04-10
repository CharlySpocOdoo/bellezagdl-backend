from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from datetime import date

from app.database import get_db
from app.modules.auth.dependencies import require_admin, require_vendor
from app.modules.auth.models import User, Vendor
from app.modules.commissions import service
from app.modules.commissions.models import CommissionPeriodStatus
from app.modules.commissions.schemas import (
    CommissionSettingsResponse, CommissionPeriodResponse,
    ConfirmCommissionRequest, CalculateCommissionsResponse,
    VendorCommissionSummaryResponse,
)

router_admin = APIRouter()
router_vendor = APIRouter()


# ── Admin endpoints ───────────────────────────────────────────────────────────

@router_admin.get("/settings", response_model=CommissionSettingsResponse)
def get_commission_settings(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Configuracion actual de comisiones."""
    settings = service.get_active_settings(db)
    if not settings:
        raise HTTPException(status_code=404, detail="No hay configuracion de comisiones activa")
    return settings


@router_admin.get("", response_model=List[CommissionPeriodResponse])
def list_commissions(
    status: Optional[CommissionPeriodStatus] = Query(None),
    vendor_id: Optional[UUID] = Query(None),
    week_start: Optional[date] = Query(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Lista liquidaciones con filtros opcionales."""
    periods = service.get_commission_periods(db, status, vendor_id, week_start)
    return periods


@router_admin.post("/calculate", response_model=CalculateCommissionsResponse)
def calculate_commissions(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Calcula comisiones de la semana anterior para todos los vendedores."""
    week_start, week_end = service.get_previous_week_bounds()
    result = service.calculate_commissions_for_week(db, week_start, week_end)
    return CalculateCommissionsResponse(**result)


@router_admin.patch("/{period_id}/confirm", response_model=CommissionPeriodResponse)
def confirm_commission(
    period_id: UUID,
    request: ConfirmCommissionRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Confirma el pago de una liquidacion semanal."""
    try:
        period = service.confirm_commission_payment(db, period_id, request.notes)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    if not period:
        raise HTTPException(status_code=404, detail="Liquidacion no encontrada")
    return period


# ── Vendor endpoints ──────────────────────────────────────────────────────────

@router_vendor.get("/me/commissions", response_model=VendorCommissionSummaryResponse)
def get_vendor_commissions(
    current_user: User = Depends(require_vendor),
    db: Session = Depends(get_db),
):
    """Historial de comisiones y resumen del vendedor autenticado."""
    vendor = db.query(Vendor).filter(Vendor.user_id == current_user.id).first()
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendedor no encontrado")

    summary = service.get_vendor_commission_summary(db, vendor.id)
    return VendorCommissionSummaryResponse(
        current_week_commission=summary["current_week_commission"],
        pending_payment=summary["pending_payment"],
        periods=summary["periods"],
    )
