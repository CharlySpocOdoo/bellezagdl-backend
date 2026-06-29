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
from app.modules.shared_enums import OrderStatus, SaleType  # ── NUEVO: SaleType ──
from app.modules.catalog.service import get_active_commission_percentage


def get_active_settings(db: Session) -> Optional[CommissionSettings]:
    return db.query(CommissionSettings).filter(
        CommissionSettings.active_to.is_(None)
    ).order_by(CommissionSettings.active_from.desc()).first()


def get_week_bounds(reference_date: date) -> Tuple[date, date]:
    week_start = reference_date - timedelta(days=reference_date.weekday())
    week_end = week_start + timedelta(days=6)
    return week_start, week_end


def get_previous_week_bounds() -> Tuple[date, date]:
    today = datetime.utcnow().date()
    last_week = today - timedelta(days=7)
    return get_week_bounds(last_week)


def calculate_commissions_for_week(
    db: Session,
    week_start: date,
    week_end: date,
) -> dict:
    """
    Recalcula desde cero las comisiones de la semana.
    Formula: commission = sum(order.total) * commission_rate / 100 — la misma
    formula que _register_vendor_commission() en orders/service.py, para que
    este recalculo no pise el acumulado con un numero distinto.
    """
    week_start_dt = datetime.combine(week_start, datetime.min.time())
    week_end_dt = datetime.combine(week_end, datetime.max.time())

    orders = db.query(Order).filter(
        Order.status == OrderStatus.delivered_to_client,
        Order.delivered_at >= week_start_dt,
        Order.delivered_at <= week_end_dt,
        Order.sale_type != SaleType.wholesale,
    ).all()

    global_commission_pct = get_active_commission_percentage(db)
    vendors_processed = set()
    periods_created = 0
    periods_updated = 0

    vendor_data = {}
    for order in orders:
        vid = order.vendor_id
        if vid not in vendor_data:
            vendor_data[vid] = {
                "gross_sales": Decimal("0"),
                "cost": Decimal("0"),
                "commission_base": Decimal("0"),
            }

        items = db.query(OrderItem).filter(
            OrderItem.order_id == order.id,
            OrderItem.cancelled_in_partial == False,
        ).all()

        for item in items:
            vendor_data[vid]["gross_sales"] += item.sale_price_snapshot * item.quantity
            vendor_data[vid]["cost"] += item.cost_price_snapshot * item.quantity

        vendor_data[vid]["commission_base"] += order.total

    for vendor_id, data in vendor_data.items():
        from app.modules.auth.models import Vendor as VendorModel
        vendor_obj = db.query(VendorModel).filter(VendorModel.id == vendor_id).first()
        commission_pct = (
            vendor_obj.commission_percentage
            if vendor_obj and vendor_obj.commission_percentage
            else global_commission_pct
        )
        vendors_processed.add(vendor_id)
        commission_base = data["commission_base"]
        recalculated_commission = round(commission_base * commission_pct / 100, 2)
        net_commission = recalculated_commission

        existing = db.query(CommissionPeriod).filter(
            CommissionPeriod.vendor_id == vendor_id,
            CommissionPeriod.week_start == week_start,
        ).first()

        if existing:
            existing.gross_sales_amount = data["gross_sales"]
            existing.cost_amount = data["cost"]
            existing.commission_base_amount = commission_base
            existing.commission_rate = commission_pct
            existing.commission_amount = recalculated_commission
            existing.net_commission = net_commission
            periods_updated += 1
        else:
            period = CommissionPeriod(
                vendor_id=vendor_id,
                week_start=week_start,
                week_end=week_end,
                gross_sales_amount=data["gross_sales"],
                cost_amount=data["cost"],
                commission_base_amount=commission_base,
                commission_rate=commission_pct,
                commission_amount=recalculated_commission,
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


def confirm_commission_payment(
    db: Session,
    period_id: UUID,
    notes: Optional[str] = None,
) -> Optional[CommissionPeriod]:
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
    today = datetime.utcnow().date()
    week_start, week_end = get_week_bounds(today)

    current_period = db.query(CommissionPeriod).filter(
        CommissionPeriod.vendor_id == vendor_id,
        CommissionPeriod.week_start == week_start,
    ).first()
    current_week_commission = current_period.net_commission if current_period else Decimal("0")

    pending_periods = db.query(CommissionPeriod).filter(
        CommissionPeriod.vendor_id == vendor_id,
        CommissionPeriod.status == CommissionPeriodStatus.pending,
    ).all()
    pending_payment = sum(p.net_commission for p in pending_periods)

    all_periods = get_commission_periods(db, vendor_id=vendor_id)

    return {
        "current_week_commission": current_week_commission,
        "pending_payment": pending_payment,
        "periods": all_periods,
    }