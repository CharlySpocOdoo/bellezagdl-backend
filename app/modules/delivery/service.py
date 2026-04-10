from decimal import Decimal
from typing import Optional, List
from uuid import UUID
from datetime import datetime

from sqlalchemy.orm import Session

from app.modules.admin.models import DeliveryPerson
from app.modules.orders.models import Order, OrderStatusHistory, Shipment
from app.modules.shared_enums import OrderStatus


# ── CRUD de repartidores ──────────────────────────────────────────────────────

def create_delivery_person(
    db: Session,
    first_name: str,
    last_name: str,
    phone: str,
    vehicle_type: Optional[str] = None,
    notes: Optional[str] = None,
) -> DeliveryPerson:
    person = DeliveryPerson(
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        vehicle_type=vehicle_type,
        notes=notes,
        active=True,
        total_deliveries=0,
        total_failed=0,
    )
    db.add(person)
    db.commit()
    db.refresh(person)
    return person


def get_delivery_persons(
    db: Session,
    active_only: bool = True,
) -> List[DeliveryPerson]:
    query = db.query(DeliveryPerson)
    if active_only:
        query = query.filter(DeliveryPerson.active == True)
    return query.order_by(DeliveryPerson.first_name).all()


def get_delivery_person_by_id(
    db: Session,
    person_id: UUID,
) -> Optional[DeliveryPerson]:
    return db.query(DeliveryPerson).filter(DeliveryPerson.id == person_id).first()


def update_delivery_person(
    db: Session,
    person_id: UUID,
    **kwargs,
) -> Optional[DeliveryPerson]:
    person = db.query(DeliveryPerson).filter(DeliveryPerson.id == person_id).first()
    if not person:
        return None
    for key, value in kwargs.items():
        if value is not None:
            setattr(person, key, value)
    person.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(person)
    return person


def get_delivery_person_history(
    db: Session,
    person_id: UUID,
) -> List[OrderStatusHistory]:
    """Historial de entregas y fallos del repartidor."""
    return db.query(OrderStatusHistory).filter(
        OrderStatusHistory.delivery_person_id == person_id,
    ).order_by(OrderStatusHistory.created_at.desc()).limit(100).all()


# ── Shipments ─────────────────────────────────────────────────────────────────

def create_shipment(
    db: Session,
    delivery_person_id: UUID,
    vendor_id: UUID,
    order_ids: List[UUID],
    notes: Optional[str] = None,
) -> Shipment:
    """
    Crea un shipment agrupando pedidos del mismo repartidor al mismo vendedor.
    Todos los pedidos deben estar en estado delivered_to_vendor.
    """
    orders = []
    total_amount = Decimal("0.00")

    for order_id in order_ids:
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            raise ValueError(f"Pedido {order_id} no encontrado")
        if order.status != OrderStatus.delivered_to_vendor:
            raise ValueError(
                f"El pedido {order.order_number} no esta en estado delivered_to_vendor"
            )
        if order.vendor_id != vendor_id:
            raise ValueError(
                f"El pedido {order.order_number} no pertenece al vendedor indicado"
            )
        orders.append(order)
        total_amount += order.total

    # Calcular costo de envio
    # Por ahora: sin costo si el total supera $500, de lo contrario $50
    # Esto se reemplazara con shipping_tiers cuando se definan las reglas
    if total_amount >= Decimal("500.00"):
        shipping_cost = Decimal("0.00")
        shipping_cost_waived = True
    else:
        shipping_cost = Decimal("50.00")
        shipping_cost_waived = False

    shipment = Shipment(
        delivery_person_id=delivery_person_id,
        vendor_id=vendor_id,
        delivered_at=datetime.utcnow(),
        order_count=len(orders),
        total_amount=total_amount,
        shipping_cost=shipping_cost,
        shipping_cost_waived=shipping_cost_waived,
        notes=notes,
    )
    db.add(shipment)
    db.flush()

    # Vincular pedidos al shipment y actualizar shipping_cost
    for order in orders:
        order.shipment_id = shipment.id
        order.shipping_cost = shipping_cost
        order.total = order.subtotal + shipping_cost + order.tax_amount
        order.updated_at = datetime.utcnow()

    # Actualizar contador del repartidor
    person = db.query(DeliveryPerson).filter(
        DeliveryPerson.id == delivery_person_id
    ).first()
    if person:
        person.total_deliveries = (person.total_deliveries or 0) + len(orders)

    db.commit()
    db.refresh(shipment)
    return shipment


def get_shipments(
    db: Session,
    vendor_id: Optional[UUID] = None,
    delivery_person_id: Optional[UUID] = None,
) -> List[Shipment]:
    query = db.query(Shipment)
    if vendor_id:
        query = query.filter(Shipment.vendor_id == vendor_id)
    if delivery_person_id:
        query = query.filter(Shipment.delivery_person_id == delivery_person_id)
    return query.order_by(Shipment.delivered_at.desc()).all()
