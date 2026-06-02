from decimal import Decimal
from typing import Optional
from uuid import UUID
from datetime import datetime, date, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.modules.orders.models import Order, OrderItem, Shipment
from app.modules.commissions.models import CommissionPeriod, CommissionPeriodStatus
from app.modules.auth.models import Vendor
from app.modules.catalog.models import Product, ProductVariant
from app.modules.shared_enums import OrderStatus, SaleType  # ── NUEVO: SaleType ──


def get_financial_report(
    db: Session,
    date_from: date,
    date_to: date,
    vendor_id: Optional[UUID] = None,
) -> dict:
    from_dt = datetime.combine(date_from, datetime.min.time())
    to_dt = datetime.combine(date_to, datetime.max.time())

    query = db.query(Order).filter(
        Order.status == OrderStatus.delivered_to_client,
        Order.delivered_at >= from_dt,
        Order.delivered_at <= to_dt,
    )
    if vendor_id:
        query = query.filter(Order.vendor_id == vendor_id)

    orders = query.all()
    order_ids = [o.id for o in orders]

    gross_revenue = Decimal("0")
    total_cost = Decimal("0")
    tax_amount = Decimal("0")
    retail_revenue = Decimal("0")   # ── NUEVO ──
    retail_cost = Decimal("0")      # ── NUEVO ──
    wholesale_revenue = Decimal("0")  # ── NUEVO ──
    wholesale_cost = Decimal("0")     # ── NUEVO ──

    if order_ids:
        items = db.query(OrderItem).filter(
            OrderItem.order_id.in_(order_ids),
            OrderItem.cancelled_in_partial == False,
        ).all()

        # Mapa order_id → sale_type para clasificar items
        # ── NUEVO ──
        order_sale_type = {o.id: o.sale_type for o in orders}

        for item in items:
            item_revenue = item.sale_price_snapshot * item.quantity
            item_cost = item.cost_price_snapshot * item.quantity
            gross_revenue += item_revenue
            total_cost += item_cost

            # ── NUEVO: separar por sale_type ──
            sale_type = order_sale_type.get(item.order_id)
            if sale_type == SaleType.wholesale:
                wholesale_revenue += item_revenue
                wholesale_cost += item_cost
            else:
                retail_revenue += item_revenue
                retail_cost += item_cost

        for order in orders:
            tax_amount += order.tax_amount or Decimal("0")

    gross_profit = gross_revenue - total_cost
    retail_profit = retail_revenue - retail_cost        # ── NUEVO ──
    wholesale_profit = wholesale_revenue - wholesale_cost  # ── NUEVO ──

    commissions_query = db.query(CommissionPeriod).filter(
        CommissionPeriod.status == CommissionPeriodStatus.paid,
        CommissionPeriod.paid_at >= from_dt,
        CommissionPeriod.paid_at <= to_dt,
    )
    if vendor_id:
        commissions_query = commissions_query.filter(
            CommissionPeriod.vendor_id == vendor_id
        )
    commissions = commissions_query.all()
    commissions_paid = sum(c.net_commission for c in commissions)

    shipments_query = db.query(Shipment).filter(
        Shipment.delivered_at >= from_dt,
        Shipment.delivered_at <= to_dt,
        Shipment.shipping_cost_waived == False,
    )
    if vendor_id:
        shipments_query = shipments_query.filter(Shipment.vendor_id == vendor_id)
    shipments = shipments_query.all()
    shipping_costs = sum(s.shipping_cost for s in shipments)

    net_profit = gross_profit - commissions_paid - shipping_costs - tax_amount
    gross_margin_pct = round(
        (gross_profit / gross_revenue * 100) if gross_revenue > 0 else Decimal("0"), 2
    )

    total_query = db.query(func.count(Order.id)).filter(
        Order.created_at >= from_dt,
        Order.created_at <= to_dt,
    )
    if vendor_id:
        total_query = total_query.filter(Order.vendor_id == vendor_id)
    total_orders = total_query.scalar() or 0

    return {
        "period_from": date_from,
        "period_to": date_to,
        "total_orders": total_orders,
        "delivered_orders": len(orders),
        "gross_revenue": gross_revenue,
        "total_cost": total_cost,
        "gross_profit": gross_profit,
        "commissions_paid": commissions_paid,
        "shipping_costs": shipping_costs,
        "tax_amount": tax_amount,
        "net_profit": net_profit,
        "gross_margin_pct": gross_margin_pct,
        "retail_revenue": retail_revenue,       # ── NUEVO ──
        "retail_profit": retail_profit,         # ── NUEVO ──
        "wholesale_revenue": wholesale_revenue, # ── NUEVO ──
        "wholesale_profit": wholesale_profit,   # ── NUEVO ──
    }


def get_dashboard(db: Session) -> dict:
    today = datetime.utcnow().date()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())

    status_counts = []
    for status in OrderStatus:
        count = db.query(func.count(Order.id)).filter(
            Order.status == status
        ).scalar() or 0
        if count > 0:
            status_counts.append({"label": status.value, "value": count})

    todays_orders = db.query(Order).filter(
        Order.status == OrderStatus.delivered_to_client,
        Order.delivered_at >= today_start,
        Order.delivered_at <= today_end,
    ).all()

    todays_revenue = Decimal("0")
    for order in todays_orders:
        todays_revenue += order.total

    pending_commissions = db.query(CommissionPeriod).filter(
        CommissionPeriod.status == CommissionPeriodStatus.pending,
    ).all()
    pending_total = sum(p.net_commission for p in pending_commissions)

    active_vendors = db.query(func.count(Vendor.id)).filter(
        Vendor.active == True
    ).scalar() or 0

    low_stock = db.query(func.count(ProductVariant.id)).filter(
        ProductVariant.active == True,
        (ProductVariant.stock_qty + ProductVariant.returned_stock_qty) < 5,
        (ProductVariant.stock_qty + ProductVariant.returned_stock_qty) > 0,
    ).scalar() or 0

    return {
        "date": today,
        "orders_by_status": status_counts,
        "todays_revenue": todays_revenue,
        "todays_orders": len(todays_orders),
        "pending_commissions": pending_total,
        "active_vendors": active_vendors,
        "low_stock_products": low_stock,
    }