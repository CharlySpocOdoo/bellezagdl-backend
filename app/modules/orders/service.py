from decimal import Decimal
from typing import Optional, List, Tuple
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.modules.auth.models import User, Vendor, Client
from app.modules.catalog.models import Product, ProductVariant, Brand
from app.modules.catalog.service import (
    calculate_sale_price, calculate_vendor_price,
    calculate_gross_profit, get_active_commission_percentage,
    calculate_vendor_commission,  # ── NUEVO ──
)
from app.modules.orders.models import Order, OrderItem, OrderStatusHistory, Shipment
from app.modules.commissions.models import CommissionPeriod, CommissionSettings
from app.modules.shared_enums import OrderStatus, UserRole, FailureReason, SaleType  # ── NUEVO: SaleType


# ── Numero de pedido ──────────────────────────────────────────────────────────

def generate_order_number(db: Session) -> str:
    year = datetime.utcnow().year
    count = db.query(func.count(Order.id)).scalar() or 0
    return f"ORD-{year}-{str(count + 1).zfill(5)}"


# ── Validaciones de transicion ────────────────────────────────────────────────

VALID_TRANSITIONS = {
    OrderStatus.pending: [
        OrderStatus.partially_available,
        OrderStatus.confirmed,
        OrderStatus.cancelled,
    ],
    OrderStatus.partially_available: [
        OrderStatus.confirmed,
        OrderStatus.cancelled,
    ],
    OrderStatus.confirmed: [
        OrderStatus.preparing,
        OrderStatus.cancelled,
    ],
    OrderStatus.preparing: [
        OrderStatus.in_delivery,
    ],
    OrderStatus.in_delivery: [
        OrderStatus.delivered_to_vendor,
        OrderStatus.delivery_failed,
        OrderStatus.delivered_to_client,  # ── NUEVO: wholesale va directo ──
    ],
    OrderStatus.delivery_failed: [
        OrderStatus.preparing,
    ],
    OrderStatus.delivered_to_vendor: [
        OrderStatus.delivered_to_client,
    ],
}

FINAL_STATES = {
    OrderStatus.delivered_to_client,
    OrderStatus.cancelled,
}

ADMIN_ONLY_TRANSITIONS = {
    OrderStatus.partially_available,
    OrderStatus.confirmed,
    OrderStatus.preparing,
    OrderStatus.in_delivery,
    OrderStatus.delivered_to_vendor,
    OrderStatus.delivery_failed,
}

CLIENT_ALLOWED_FROM = {
    OrderStatus.pending: [OrderStatus.cancelled],
    OrderStatus.partially_available: [OrderStatus.confirmed, OrderStatus.cancelled],
}

VENDOR_ALLOWED_FROM = {
    OrderStatus.delivered_to_vendor: [OrderStatus.delivered_to_client],
}


def validate_transition(
    current_status: OrderStatus,
    new_status: OrderStatus,
    role: UserRole,
) -> bool:
    allowed = VALID_TRANSITIONS.get(current_status, [])
    if new_status not in allowed:
        return False
    if role == UserRole.vendor:
        allowed = VENDOR_ALLOWED_FROM.get(current_status, [])
        if new_status not in allowed:
            raise ValueError(
                f"El vendedor no puede cambiar el estado de "
                f"{current_status.value} a {new_status.value}"
            )
        return True
    if role == UserRole.client:
        client_allowed = CLIENT_ALLOWED_FROM.get(current_status, [])
        return new_status in client_allowed
    return True  # Admin puede hacer cualquier transicion valida


# ── Calculo de precios ────────────────────────────────────────────────────────

def calculate_item_prices(
    db: Session,
    variant: ProductVariant,
    quantity: int,
    sale_type: SaleType,  # ── NUEVO: reemplaza is_vendor_purchase ──
    vendor_commission_pct: Optional[Decimal] = None,
) -> dict:
    product = db.query(Product).filter(Product.id == variant.product_id).first()

    cost_price = variant.cost_price_override or product.cost_price
    list_price = product.list_price
    sale_price = calculate_sale_price(list_price)  # ── CAMBIO: antes pasaba cost_price y margen ──

    commission_pct = vendor_commission_pct or get_active_commission_percentage(db)

    # ── CAMBIO: comisión sobre (sale_price - list_price) ──
    if sale_type == SaleType.wholesale:
        unit_price = list_price
        commission_amount = Decimal("0.00")
    else:
        commission_amount = round(
            calculate_vendor_commission(sale_price, list_price, commission_pct) * quantity, 2
        )
        unit_price = sale_price

    return {
        "cost_price_snapshot": cost_price,
        "sale_price_snapshot": sale_price,
        "unit_price": unit_price,
        "commission_amount_snapshot": commission_amount,
        "subtotal": round(unit_price * quantity, 2),
        "product_name_snapshot": product.name,
        "variant_name_snapshot": variant.variant_name,
        "sku_snapshot": variant.sku,
    }


# ── Crear pedido ──────────────────────────────────────────────────────────────

def create_order(
    db: Session,
    client_id: UUID,
    vendor_id: Optional[UUID],
    items_data: List[dict],
    role: UserRole,  # ── NUEVO: para determinar sale_type ──
    delivery_address: Optional[str] = None,
    notes: Optional[str] = None,
    is_vendor_purchase: bool = False,
    vendor_commission_pct: Optional[Decimal] = None,
) -> Order:
    # ── NUEVO: determinar sale_type según rol ──
    sale_type = SaleType.wholesale if role == UserRole.wholesale else SaleType.retail

    for item in items_data:
        variant = db.query(ProductVariant).filter(
            ProductVariant.id == item["variant_id"],
            ProductVariant.active == True,
        ).first()
        if not variant:
            raise ValueError(f"Variante {item['variant_id']} no encontrada")

    order_items = []
    subtotal = Decimal("0.00")

    for item in items_data:
        variant = db.query(ProductVariant).filter(
            ProductVariant.id == item["variant_id"]
        ).first()

        prices = calculate_item_prices(
            db, variant, item["quantity"],
            sale_type, vendor_commission_pct,  # ── CAMBIO: pasa sale_type ──
        )
        prices["variant_id"] = variant.id
        prices["product_id"] = variant.product_id
        prices["quantity"] = item["quantity"]
        order_items.append(prices)
        subtotal += prices["subtotal"]

    order = Order(
        order_number=generate_order_number(db),
        client_id=client_id,
        vendor_id=vendor_id,
        status=OrderStatus.pending,
        sale_type=sale_type,  # ── NUEVO ──
        subtotal=subtotal,
        shipping_cost=Decimal("0.00"),
        tax_amount=Decimal("0.00"),
        total=subtotal,
        delivery_address=delivery_address,
        notes=notes,
        is_vendor_purchase=is_vendor_purchase,
        delivery_attempts=0,
    )
    db.add(order)
    db.flush()

    for item_data in order_items:
        order_item = OrderItem(
            order_id=order.id,
            product_id=item_data["product_id"],
            variant_id=item_data["variant_id"],
            product_name_snapshot=item_data["product_name_snapshot"],
            variant_name_snapshot=item_data["variant_name_snapshot"],
            sku_snapshot=item_data["sku_snapshot"],
            cost_price_snapshot=item_data["cost_price_snapshot"],
            sale_price_snapshot=item_data["sale_price_snapshot"],
            unit_price=item_data["unit_price"],
            quantity=item_data["quantity"],
            subtotal=item_data["subtotal"],
            commission_amount_snapshot=item_data["commission_amount_snapshot"],
            cancelled_in_partial=False,
        )
        db.add(order_item)

    _record_status_change(db, order.id, None, OrderStatus.pending, None, "Pedido creado")

    db.commit()
    db.refresh(order)
    return order


# ── Cambiar estado ────────────────────────────────────────────────────────────

def change_order_status(
    db: Session,
    order: Order,
    new_status: OrderStatus,
    changed_by_id: UUID,
    role: UserRole,
    notes: Optional[str] = None,
    failure_reason: Optional[FailureReason] = None,
    delivery_person_id: Optional[UUID] = None,
) -> Order:
    if order.status in FINAL_STATES:
        raise ValueError(f"El pedido {order.order_number} esta en estado final y no puede cambiar")

    # ── NUEVO: bloquear delivered_to_vendor en pedidos wholesale ──
    if new_status == OrderStatus.delivered_to_vendor and order.sale_type == SaleType.wholesale:
        raise ValueError("Los pedidos de mayoreo no pasan por delivered_to_vendor")

    if not validate_transition(order.status, new_status, role):
        raise ValueError(
            f"Transicion invalida: {order.status.value} -> {new_status.value} "
            f"para rol {role.value}"
        )

    attempt_number = None
    if new_status == OrderStatus.delivery_failed:
        order.delivery_attempts = (order.delivery_attempts or 0) + 1
        attempt_number = order.delivery_attempts

    if delivery_person_id:
        order.delivery_person_id = delivery_person_id

    if new_status == OrderStatus.confirmed:
        order.confirmed_at = datetime.utcnow()
    elif new_status == OrderStatus.delivered_to_client:
        order.delivered_at = datetime.utcnow()
        _register_vendor_commission(db, order)
    elif new_status == OrderStatus.cancelled:
        order.cancelled_at = datetime.utcnow()

    old_status = order.status
    order.status = new_status
    order.updated_at = datetime.utcnow()

    _record_status_change(
        db, order.id, old_status, new_status, changed_by_id,
        notes, failure_reason, attempt_number,
        delivery_person_id or order.delivery_person_id,
    )

    db.commit()
    db.refresh(order)
    return order


def _record_status_change(
    db: Session,
    order_id: UUID,
    from_status: Optional[OrderStatus],
    to_status: OrderStatus,
    changed_by: Optional[UUID],
    notes: Optional[str] = None,
    failure_reason: Optional[FailureReason] = None,
    delivery_attempt_number: Optional[int] = None,
    delivery_person_id: Optional[UUID] = None,
) -> None:
    history = OrderStatusHistory(
        order_id=order_id,
        from_status=from_status,
        to_status=to_status,
        changed_by=changed_by,
        notes=notes,
        failure_reason=failure_reason,
        delivery_attempt_number=delivery_attempt_number,
        delivery_person_id=delivery_person_id,
    )
    db.add(history)


def _register_vendor_commission(db: Session, order: Order) -> None:
    """Registra la comision del vendedor al llegar a delivered_to_client."""
    from app.modules.commissions.models import CommissionPeriod, CommissionPeriodStatus
    from datetime import timedelta

    # ── NUEVO: pedidos wholesale no generan comisión ──
    if order.sale_type == SaleType.wholesale:
        return

    items = db.query(OrderItem).filter(
        OrderItem.order_id == order.id,
        OrderItem.cancelled_in_partial == False,
    ).all()

    total_commission = sum(item.commission_amount_snapshot or Decimal("0") for item in items)
    gross_sales = sum(item.sale_price_snapshot * item.quantity for item in items)
    cost_amount = sum(item.cost_price_snapshot * item.quantity for item in items)

    today = datetime.utcnow().date()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    period = db.query(CommissionPeriod).filter(
        CommissionPeriod.vendor_id == order.vendor_id,
        CommissionPeriod.week_start == week_start,
    ).first()

    vendor = db.query(Vendor).filter(Vendor.id == order.vendor_id).first()
    commission_pct = (
        vendor.commission_percentage
        if vendor and vendor.commission_percentage
        else get_active_commission_percentage(db)
    )

    if period:
        period.gross_sales_amount += gross_sales
        period.cost_amount += cost_amount
        period.commission_base_amount += (gross_sales - cost_amount)
        period.commission_amount += total_commission
        period.net_commission += total_commission
    else:
        period = CommissionPeriod(
            vendor_id=order.vendor_id,
            week_start=week_start,
            week_end=week_end,
            gross_sales_amount=gross_sales,
            cost_amount=cost_amount,
            commission_base_amount=gross_sales - cost_amount,
            commission_rate=commission_pct,
            commission_amount=total_commission,
            shipping_charges=Decimal("0.00"),
            net_commission=total_commission,
            status=CommissionPeriodStatus.pending,
        )
        db.add(period)


# ── Pedido parcial ────────────────────────────────────────────────────────────

def mark_items_unavailable(
    db: Session,
    order: Order,
    unavailable_variant_ids: List[UUID],
    changed_by_id: UUID,
    notes: Optional[str] = None,
) -> Order:
    if order.status != OrderStatus.pending:
        raise ValueError("Solo se pueden marcar items en pedidos pendientes")

    for variant_id in unavailable_variant_ids:
        item = db.query(OrderItem).filter(
            OrderItem.order_id == order.id,
            OrderItem.variant_id == variant_id,
        ).first()
        if item:
            item.cancelled_in_partial = True
            item.partial_cancellation_reason = "No disponible en proveedor"
            item.partial_cancelled_at = datetime.utcnow()

    available_items = db.query(OrderItem).filter(
        OrderItem.order_id == order.id,
        OrderItem.cancelled_in_partial == False,
    ).all()

    if not available_items:
        raise ValueError("No quedan items disponibles — cancela el pedido completo")

    order.original_total = order.total
    new_subtotal = sum(item.subtotal for item in available_items)
    order.subtotal = new_subtotal
    order.total = new_subtotal + order.shipping_cost + order.tax_amount

    old_status = order.status
    order.status = OrderStatus.partially_available
    order.updated_at = datetime.utcnow()

    _record_status_change(
        db, order.id, old_status, OrderStatus.partially_available,
        changed_by_id, notes or "Items no disponibles en proveedor"
    )

    db.commit()
    db.refresh(order)
    return order


def accept_partial_order(
    db: Session,
    order: Order,
    accept: bool,
    changed_by_id: UUID,
    notes: Optional[str] = None,
) -> Order:
    if order.status != OrderStatus.partially_available:
        raise ValueError("El pedido no esta en estado parcialmente disponible")

    if accept:
        available_items = db.query(OrderItem).filter(
            OrderItem.order_id == order.id,
            OrderItem.cancelled_in_partial == False,
        ).all()
        new_subtotal = sum(item.subtotal for item in available_items)
        order.subtotal = new_subtotal
        order.total = new_subtotal + order.shipping_cost + order.tax_amount

        order.partial_accepted_at = datetime.utcnow()
        new_status = OrderStatus.confirmed
        order.confirmed_at = datetime.utcnow()
        status_notes = notes or "Cliente acepto pedido parcial"
    else:
        new_status = OrderStatus.cancelled
        order.cancelled_at = datetime.utcnow()
        status_notes = notes or "Cliente rechazo pedido parcial"

    old_status = order.status
    order.status = new_status
    order.updated_at = datetime.utcnow()

    _record_status_change(db, order.id, old_status, new_status, changed_by_id, status_notes)

    db.commit()
    db.refresh(order)
    return order


# ── Queries ───────────────────────────────────────────────────────────────────

def get_order_by_id(db: Session, order_id: UUID) -> Optional[Order]:
    return db.query(Order).filter(Order.id == order_id).first()


def get_orders_for_client(
    db: Session,
    client_id: UUID,
    status: Optional[OrderStatus] = None,
) -> List[Order]:
    query = db.query(Order).filter(Order.client_id == client_id)
    if status:
        query = query.filter(Order.status == status)
    return query.order_by(Order.created_at.desc()).all()


def get_orders_for_vendor(
    db: Session,
    vendor_id: UUID,
    status: Optional[OrderStatus] = None,
) -> List[Order]:
    query = db.query(Order).filter(Order.vendor_id == vendor_id)
    if status:
        query = query.filter(Order.status == status)
    return query.order_by(Order.created_at.desc()).all()


def get_all_orders(
    db: Session,
    status: Optional[OrderStatus] = None,
    vendor_id: Optional[UUID] = None,
    delivery_person_id: Optional[UUID] = None,
) -> List[Order]:
    query = db.query(Order)
    if status:
        query = query.filter(Order.status == status)
    if vendor_id:
        query = query.filter(Order.vendor_id == vendor_id)
    if delivery_person_id:
        query = query.filter(Order.delivery_person_id == delivery_person_id)
    return query.order_by(Order.created_at.desc()).all()