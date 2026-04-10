from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from app.database import get_db
from app.modules.auth.dependencies import require_admin
from app.modules.auth.models import User
from app.modules.orders.models import Order, OrderStatusHistory
from app.modules.delivery import service
from app.modules.delivery.schemas import (
    CreateDeliveryPersonRequest, UpdateDeliveryPersonRequest,
    CreateShipmentRequest, DeliveryPersonResponse,
    DeliveryHistoryResponse, ShipmentResponse,
)

router_delivery = APIRouter()
router_shipments = APIRouter()


# ── Repartidores ──────────────────────────────────────────────────────────────

@router_delivery.get("", response_model=List[DeliveryPersonResponse])
def list_delivery_persons(
    available: Optional[bool] = Query(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Lista repartidores. ?available=true para asignacion de pedidos."""
    persons = service.get_delivery_persons(db, active_only=True)
    return persons


@router_delivery.post("", response_model=DeliveryPersonResponse, status_code=status.HTTP_201_CREATED)
def create_delivery_person(
    request: CreateDeliveryPersonRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Alta de nuevo repartidor."""
    person = service.create_delivery_person(
        db=db,
        first_name=request.first_name,
        last_name=request.last_name,
        phone=request.phone,
        vehicle_type=request.vehicle_type,
        notes=request.notes,
    )
    return person


@router_delivery.patch("/{person_id}", response_model=DeliveryPersonResponse)
def update_delivery_person(
    person_id: UUID,
    request: UpdateDeliveryPersonRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Actualiza datos o desactiva un repartidor. Nunca se borra."""
    update_data = request.model_dump(exclude_none=True)
    person = service.update_delivery_person(db, person_id, **update_data)
    if not person:
        raise HTTPException(status_code=404, detail="Repartidor no encontrado")
    return person


@router_delivery.get("/{person_id}/history", response_model=List[DeliveryHistoryResponse])
def get_delivery_history(
    person_id: UUID,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Historial de entregas y fallos del repartidor."""
    person = service.get_delivery_person_by_id(db, person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Repartidor no encontrado")

    history = service.get_delivery_person_history(db, person_id)
    result = []
    for h in history:
        order = db.query(Order).filter(Order.id == h.order_id).first()
        if order:
            result.append(DeliveryHistoryResponse(
                order_id=order.id,
                order_number=order.order_number,
                vendor_id=order.vendor_id,
                status=h.to_status,
                delivery_attempt_number=h.delivery_attempt_number,
                notes=h.notes,
                created_at=h.created_at,
            ))
    return result


# ── Shipments ─────────────────────────────────────────────────────────────────

@router_shipments.post("", response_model=ShipmentResponse, status_code=status.HTTP_201_CREATED)
def create_shipment(
    request: CreateShipmentRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Crea un shipment agrupando pedidos del mismo viaje.
    Todos los pedidos deben estar en delivered_to_vendor.
    """
    try:
        shipment = service.create_shipment(
            db=db,
            delivery_person_id=request.delivery_person_id,
            vendor_id=request.vendor_id,
            order_ids=request.order_ids,
            notes=request.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return shipment


@router_shipments.get("", response_model=List[ShipmentResponse])
def list_shipments(
    vendor_id: Optional[UUID] = Query(None),
    delivery_person_id: Optional[UUID] = Query(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Lista shipments con filtros opcionales."""
    shipments = service.get_shipments(db, vendor_id, delivery_person_id)
    return shipments
