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
from app.modules.shared_enums import OrderStatus


def get_financial_report(
    db: Session,
    date_from: date,
    date_to: date,
    vendor_id: Optional[UUID] = None,
) -> dict:
    """Reporte financiero completo para un periodo."""
    from_dt = datetime.combine(date_from, datetime.min.time())
    to_dt = datetime.combine(date_to, datetime.max.time())

    # Pedidos entregados en el periodo
    query = db.query(Order).filter(
        Order.status == OrderStatus.delivered_to_client,
        Order.delivered_at >= from_dt,
        Order.delivered_at <= to_dt,
    )
    if vendor_id:
        query = query.filter(Order.vendor_id == vendor_id)

    orders = query.all()
    order_ids = [o.id for o in orders]

    # Totales de items
    gross_revenue = Decimal("0")
    total_cost = Decimal("0")
    tax_amount = Decimal("0")

    if order_ids:
        items = db.query(OrderItem).filter(
            OrderItem.order_id.in_(order_ids),
            OrderItem.cancelled_in_partial == False,
        ).all()

        for item in items:
            gross_revenue += item.sale_price_snapshot * item.quantity
            total_cost += item.cost_price_snapshot * item.quantity

        for order in orders:
            tax_amount += order.tax_amount or Decimal("0")

    gross_profit = gross_revenue - total_cost

    # Comisiones pagadas en el periodo
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

    # Costos de envio en el periodo
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

    # Total de pedidos en el periodo (todos los estados)
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
    }


def get_dashboard(db: Session) -> dict:
    """Metricas del dia para el dashboard del admin."""
    today = datetime.utcnow().date()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())

    # Pedidos por estado
    status_counts = []
    for status in OrderStatus:
        count = db.query(func.count(Order.id)).filter(
            Order.status == status
        ).scalar() or 0
        if count > 0:
            status_counts.append({"label": status.value, "value": count})

    # Ingresos del dia
    todays_orders = db.query(Order).filter(
        Order.status == OrderStatus.delivered_to_client,
        Order.delivered_at >= today_start,
        Order.delivered_at <= today_end,
    ).all()

    todays_revenue = Decimal("0")
    for order in todays_orders:
        todays_revenue += order.total

    # Comisiones pendientes de pago
    pending_commissions = db.query(CommissionPeriod).filter(
        CommissionPeriod.status == CommissionPeriodStatus.pending,
    ).all()
    pending_total = sum(p.net_commission for p in pending_commissions)

    # Vendedores activos
    active_vendors = db.query(func.count(Vendor.id)).filter(
        Vendor.active == True
    ).scalar() or 0

    # Productos con stock bajo (menos de 5 unidades)
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
