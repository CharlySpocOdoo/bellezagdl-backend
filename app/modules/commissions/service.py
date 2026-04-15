from decimal import Decimal
from typing import Optional, List, Tuple
from uuid import UUID
from datetime import datetime, date, timedelta

from sqlalchemy.orm import Session

from app.modules.auth.models import Vendor
from app.modules.commissions.models import (
    CommissionSettings, CommissionPeriod, CommissionPeriodStatus
)
from app.modules.orders.models import Order, OrderItem
from app.modules.shared_enums import OrderStatus
from app.modules.catalog.service import get_active_commission_percentage


# ── Commission settings ───────────────────────────────────────────────────────

def get_active_settings(db: Session) -> Optional[CommissionSettings]:
    """Obtiene la configuracion de comisiones activa."""
    return db.query(CommissionSettings).filter(
        CommissionSettings.active_to.is_(None)
    ).order_by(CommissionSettings.active_from.desc()).first()


# ── Calculos de semana ────────────────────────────────────────────────────────

def get_week_bounds(reference_date: date) -> Tuple[date, date]:
    """Obtiene el lunes y domingo de la semana que contiene reference_date."""
    week_start = reference_date - timedelta(days=reference_date.weekday())
    week_end = week_start + timedelta(days=6)
    return week_start, week_end


def get_previous_week_bounds() -> Tuple[date, date]:
    """Obtiene los limites de la semana anterior."""
    today = datetime.utcnow().date()
    last_week = today - timedelta(days=7)
    return get_week_bounds(last_week)


# ── Calculo de comisiones ─────────────────────────────────────────────────────

def calculate_commissions_for_week(
    db: Session,
    week_start: date,
    week_end: date,
) -> dict:
    """
    Calcula las comisiones de todos los vendedores para una semana especifica.
    Busca pedidos delivered_to_client en esa semana y agrupa por vendedor.
    """
    week_start_dt = datetime.combine(week_start, datetime.min.time())
    week_end_dt = datetime.combine(week_end, datetime.max.time())

    # Obtener pedidos entregados en la semana
    orders = db.query(Order).filter(
        Order.status == OrderStatus.delivered_to_client,
        Order.delivered_at >= week_start_dt,
        Order.delivered_at <= week_end_dt,
    ).all()

    global_commission_pct = get_active_commission_percentage(db)
    vendors_processed = set()
    periods_created = 0
    periods_updated = 0

    # Agrupar por vendedor
    vendor_data = {}
    for order in orders:
        vid = order.vendor_id
        if vid not in vendor_data:
            vendor_data[vid] = {
                "gross_sales": Decimal("0"),
                "cost": Decimal("0"),
                "commission": Decimal("0"),
                "shipping": Decimal("0"),
            }

        items = db.query(OrderItem).filter(
            OrderItem.order_id == order.id,
            OrderItem.cancelled_in_partial == False,
        ).all()

        for item in items:
            vendor_data[vid]["gross_sales"] += item.sale_price_snapshot * item.quantity
            vendor_data[vid]["cost"] += item.cost_price_snapshot * item.quantity
            vendor_data[vid]["commission"] += item.commission_amount_snapshot or Decimal("0")

        vendor_data[vid]["shipping"] += order.shipping_cost or Decimal("0")

    # Crear o actualizar commission_periods
    for vendor_id, data in vendor_data.items():
        # Usar tasa individual del vendedor si existe, si no la global
        from app.modules.auth.models import Vendor as VendorModel
        vendor_obj = db.query(VendorModel).filter(VendorModel.id == vendor_id).first()
        commission_pct = (
            vendor_obj.commission_percentage
            if vendor_obj and vendor_obj.commission_percentage
            else global_commission_pct
        )
        vendors_processed.add(vendor_id)
        gross_profit = data["gross_sales"] - data["cost"]
        net_commission = data["commission"] - data["shipping"]

        existing = db.query(CommissionPeriod).filter(
            CommissionPeriod.vendor_id == vendor_id,
            CommissionPeriod.week_start == week_start,
        ).first()

        if existing:
            existing.gross_sales_amount = data["gross_sales"]
            existing.cost_amount = data["cost"]
            existing.commission_base_amount = gross_profit
            existing.commission_rate = commission_pct
            existing.commission_amount = data["commission"]
            existing.shipping_charges = data["shipping"]
            existing.net_commission = net_commission
            periods_updated += 1
        else:
            period = CommissionPeriod(
                vendor_id=vendor_id,
                week_start=week_start,
                week_end=week_end,
                gross_sales_amount=data["gross_sales"],
                cost_amount=data["cost"],
                commission_base_amount=gross_profit,
                commission_rate=commission_pct,
                commission_amount=data["commission"],
                shipping_charges=data["shipping"],
                net_commission=net_commission,
                status=CommissionPeriodStatus.pending,
            )
            db.add(period)
            periods_created += 1

    db.commit()

    return {
        "week_start": week_start,
        "week_end": week_end,
        "vendors_processed": len(vendors_processed),
        "periods_created": periods_created,
        "periods_updated": periods_updated,
    }


# ── Confirmar pago ────────────────────────────────────────────────────────────

def confirm_commission_payment(
    db: Session,
    period_id: UUID,
    notes: Optional[str] = None,
) -> Optional[CommissionPeriod]:
    """Confirma el pago de una liquidacion semanal."""
    period = db.query(CommissionPeriod).filter(
        CommissionPeriod.id == period_id
    ).first()

    if not period:
        return None

    if period.status == CommissionPeriodStatus.paid:
        raise ValueError("Esta liquidacion ya fue pagada")

    period.status = CommissionPeriodStatus.paid
    period.paid_at = datetime.utcnow()
    if notes:
        period.notes = notes

    db.commit()
    db.refresh(period)
    return period


# ── Queries ───────────────────────────────────────────────────────────────────

def get_commission_periods(
    db: Session,
    status: Optional[CommissionPeriodStatus] = None,
    vendor_id: Optional[UUID] = None,
    week_start: Optional[date] = None,
) -> List[CommissionPeriod]:
    query = db.query(CommissionPeriod)
    if status:
        query = query.filter(CommissionPeriod.status == status)
    if vendor_id:
        query = query.filter(CommissionPeriod.vendor_id == vendor_id)
    if week_start:
        query = query.filter(CommissionPeriod.week_start == week_start)
    return query.order_by(CommissionPeriod.week_start.desc()).all()


def get_vendor_commission_summary(
    db: Session,
    vendor_id: UUID,
) -> dict:
    """Resumen de comisiones del vendedor — semana actual y pendientes."""
    today = datetime.utcnow().date()
    week_start, week_end = get_week_bounds(today)

    # Comision acumulada semana actual
    current_period = db.query(CommissionPeriod).filter(
        CommissionPeriod.vendor_id == vendor_id,
        CommissionPeriod.week_start == week_start,
    ).first()
    current_week_commission = current_period.net_commission if current_period else Decimal("0")

    # Total pendiente de pago
    pending_periods = db.query(CommissionPeriod).filter(
        CommissionPeriod.vendor_id == vendor_id,
        CommissionPeriod.status == CommissionPeriodStatus.pending,
    ).all()
    pending_payment = sum(p.net_commission for p in pending_periods)

    # Historial completo
    all_periods = get_commission_periods(db, vendor_id=vendor_id)

    return {
        "current_week_commission": current_week_commission,
        "pending_payment": pending_payment,
        "periods": all_periods,
    }
