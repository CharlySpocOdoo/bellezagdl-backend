from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from app.database import get_db
from app.modules.auth.dependencies import get_current_user, require_admin
from app.modules.auth.models import User, Vendor, Client
from app.modules.orders import service
from app.modules.orders.models import Order, OrderItem, OrderStatusHistory
from app.modules.orders.schemas import (
    CreateOrderRequest, UpdateStatusRequest,
    MarkUnavailableRequest, PartialAcceptRequest,
    AddNotesRequest, OrderResponse, OrderListResponse,
    OrderItemResponse, StatusHistoryResponse,
)
from app.modules.shared_enums import OrderStatus, UserRole

router = APIRouter()
router_admin = APIRouter()


# ── Crear pedido ──────────────────────────────────────────────────────────────

@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_order(
    request: CreateOrderRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Crea un pedido. Valida stock y calcula snapshots financieros."""
    if current_user.role == UserRole.admin:
        raise HTTPException(status_code=403, detail="El admin no puede crear pedidos")

    # Obtener vendor_id y client_id segun el rol
    if current_user.role == UserRole.vendor:
        vendor = db.query(Vendor).filter(Vendor.user_id == current_user.id).first()
        if not vendor:
            raise HTTPException(status_code=404, detail="Vendedor no encontrado")

        if request.is_vendor_purchase:
            # Vendedor compra para si mismo
            client_id = None
            # Buscar o crear un client record para el vendor
            client = db.query(Client).filter(Client.user_id == current_user.id).first()
            if not client:
                raise HTTPException(
                    status_code=422,
                    detail="El vendedor no tiene perfil de cliente para compras propias"
                )
            client_id = client.id
        else:
            # Vendedor crea pedido para un cliente de su red
            if not request.client_id:
                raise HTTPException(status_code=422, detail="client_id requerido")
            client = db.query(Client).filter(
                Client.id == request.client_id,
                Client.vendor_id == vendor.id,
            ).first()
            if not client:
                raise HTTPException(
                    status_code=403,
                    detail="El cliente no pertenece a tu red"
                )
            client_id = client.id

        vendor_id = vendor.id
        vendor_commission_pct = vendor.commission_percentage

    else:  # client
        client = db.query(Client).filter(Client.user_id == current_user.id).first()
        if not client:
            raise HTTPException(status_code=404, detail="Cliente no encontrado")
        client_id = client.id
        vendor_id = client.vendor_id
        vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
        vendor_commission_pct = vendor.commission_percentage if vendor else None

    items_data = [
        {"variant_id": item.variant_id, "quantity": item.quantity}
        for item in request.items
    ]

    try:
        order = service.create_order(
            db=db,
            client_id=client_id,
            vendor_id=vendor_id,
            items_data=items_data,
            delivery_address=request.delivery_address,
            notes=request.notes,
            is_vendor_purchase=request.is_vendor_purchase,
            vendor_commission_pct=vendor_commission_pct,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return _order_to_response(db, order)


# ── Listar pedidos ────────────────────────────────────────────────────────────

@router.get("", response_model=List[OrderListResponse])
def list_orders(
    status: Optional[OrderStatus] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lista pedidos segun rol. Client ve los suyos, vendor los de su red."""
    if current_user.role == UserRole.client:
        client = db.query(Client).filter(Client.user_id == current_user.id).first()
        if not client:
            return []
        orders = service.get_orders_for_client(db, client.id, status)
    elif current_user.role == UserRole.vendor:
        vendor = db.query(Vendor).filter(Vendor.user_id == current_user.id).first()
        if not vendor:
            return []
        orders = service.get_orders_for_vendor(db, vendor.id, status)
    else:
        orders = service.get_all_orders(db, status)

    return [_order_to_list_response(order, db) for order in orders]


# ── Detalle de pedido ─────────────────────────────────────────────────────────

@router.get("/{order_id}", response_model=OrderResponse)
def get_order(
    order_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Detalle completo del pedido con items e historial de estados."""
    order = service.get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    # Verificar acceso segun rol
    if current_user.role == UserRole.client:
        client = db.query(Client).filter(Client.user_id == current_user.id).first()
        if not client or order.client_id != client.id:
            raise HTTPException(status_code=403, detail="No tienes acceso a este pedido")
    elif current_user.role == UserRole.vendor:
        vendor = db.query(Vendor).filter(Vendor.user_id == current_user.id).first()
        if not vendor or order.vendor_id != vendor.id:
            raise HTTPException(status_code=403, detail="No tienes acceso a este pedido")

    return _order_to_response(db, order)


# ── Cambiar estado ────────────────────────────────────────────────────────────

@router.patch("/{order_id}/status", response_model=OrderResponse)
def update_order_status(
    order_id: UUID,
    request: UpdateStatusRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cambia el estado del pedido. Valida transicion y permisos por rol."""
    order = service.get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    # Verificar acceso
    if current_user.role == UserRole.client:
        client = db.query(Client).filter(Client.user_id == current_user.id).first()
        if not client or order.client_id != client.id:
            raise HTTPException(status_code=403, detail="No tienes acceso a este pedido")
    elif current_user.role == UserRole.vendor:
        raise HTTPException(status_code=403, detail="Los vendedores no pueden cambiar estados")

    try:
        order = service.change_order_status(
            db=db,
            order=order,
            new_status=request.status,
            changed_by_id=current_user.id,
            role=current_user.role,
            notes=request.notes,
            failure_reason=request.failure_reason,
            delivery_person_id=request.delivery_person_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return _order_to_response(db, order)


# ── Marcar items no disponibles ───────────────────────────────────────────────

@router.patch("/{order_id}/mark-unavailable", response_model=OrderResponse)
def mark_unavailable(
    order_id: UUID,
    request: MarkUnavailableRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin marca items no disponibles — pedido pasa a partially_available."""
    order = service.get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    try:
        order = service.mark_items_unavailable(
            db=db,
            order=order,
            unavailable_variant_ids=request.unavailable_variant_ids,
            changed_by_id=current_user.id,
            notes=request.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return _order_to_response(db, order)


# ── Aceptar o rechazar pedido parcial ─────────────────────────────────────────

@router.patch("/{order_id}/partial-accept", response_model=OrderResponse)
def partial_accept(
    order_id: UUID,
    request: PartialAcceptRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cliente acepta o rechaza pedido reducido."""
    if current_user.role == UserRole.vendor:
        raise HTTPException(status_code=403, detail="Los vendedores no pueden aceptar pedidos parciales")

    order = service.get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    if current_user.role == UserRole.client:
        client = db.query(Client).filter(Client.user_id == current_user.id).first()
        if not client or order.client_id != client.id:
            raise HTTPException(status_code=403, detail="No tienes acceso a este pedido")

    try:
        order = service.accept_partial_order(
            db=db,
            order=order,
            accept=request.accept,
            changed_by_id=current_user.id,
            notes=request.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return _order_to_response(db, order)


# ── Agregar notas ─────────────────────────────────────────────────────────────

@router.patch("/{order_id}/notes", response_model=OrderResponse)
def add_notes(
    order_id: UUID,
    request: AddNotesRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Agrega notas internas al pedido."""
    order = service.get_order_by_id(db, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")

    if current_user.role == UserRole.vendor:
        vendor = db.query(Vendor).filter(Vendor.user_id == current_user.id).first()
        if not vendor or order.vendor_id != vendor.id:
            raise HTTPException(status_code=403, detail="No tienes acceso a este pedido")
        # Vendedor siempre guarda en vendor_notes — sin importar que campo mande
        nota = request.vendor_notes or request.notes
        if nota:
            order.vendor_notes = nota
    elif current_user.role == UserRole.admin:
        if request.notes:
            order.notes = request.notes
        if request.vendor_notes:
            order.vendor_notes = request.vendor_notes

    order.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(order)
    return _order_to_response(db, order)


# ── Admin — vista global ──────────────────────────────────────────────────────

@router_admin.get("", response_model=List[OrderListResponse])
def list_all_orders(
    status: Optional[OrderStatus] = Query(None),
    vendor_id: Optional[UUID] = Query(None),
    delivery_person_id: Optional[UUID] = Query(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Vista global de pedidos para el admin con filtros."""
    orders = service.get_all_orders(db, status, vendor_id, delivery_person_id)
    return [_order_to_list_response(order, db) for order in orders]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _order_to_response(db: Session, order: Order) -> OrderResponse:
    items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
    history = db.query(OrderStatusHistory).filter(
        OrderStatusHistory.order_id == order.id
    ).order_by(OrderStatusHistory.created_at).all()

    client_name = None
    if order.client_id:
        client = db.query(Client).filter(Client.id == order.client_id).first()
        if client:
            client_name = f"{client.first_name} {client.last_name}"

    return OrderResponse(
        id=order.id,
        order_number=order.order_number,
        client_id=order.client_id,
        client_name=client_name,
        vendor_id=order.vendor_id,
        status=order.status,
        subtotal=order.subtotal,
        shipping_cost=order.shipping_cost,
        tax_amount=order.tax_amount,
        total=order.total,
        original_total=order.original_total,
        delivery_address=order.delivery_address,
        notes=order.notes,
        vendor_notes=order.vendor_notes,
        is_vendor_purchase=order.is_vendor_purchase,
        delivery_attempts=order.delivery_attempts,
        confirmed_at=order.confirmed_at,
        delivered_at=order.delivered_at,
        cancelled_at=order.cancelled_at,
        created_at=order.created_at,
        updated_at=order.updated_at,
        items=[
            OrderItemResponse(
                id=item.id,
                product_id=item.product_id,
                variant_id=item.variant_id,
                product_name_snapshot=item.product_name_snapshot,
                variant_name_snapshot=item.variant_name_snapshot,
                sku_snapshot=item.sku_snapshot,
                cost_price_snapshot=item.cost_price_snapshot,
                sale_price_snapshot=item.sale_price_snapshot,
                unit_price=item.unit_price,
                quantity=item.quantity,
                subtotal=item.subtotal,
                commission_amount_snapshot=item.commission_amount_snapshot,
                cancelled_in_partial=item.cancelled_in_partial,
            ) for item in items
        ],
        status_history=[
            StatusHistoryResponse(
                id=h.id,
                from_status=h.from_status,
                to_status=h.to_status,
                notes=h.notes,
                failure_reason=h.failure_reason,
                delivery_attempt_number=h.delivery_attempt_number,
                created_at=h.created_at,
            ) for h in history
        ],
    )


def _order_to_list_response(order: Order, db=None) -> OrderListResponse:
    client_name = None
    if db and order.client_id:
        client = db.query(Client).filter(Client.id == order.client_id).first()
        if client:
            client_name = f"{client.first_name} {client.last_name}"
    return OrderListResponse(
        id=order.id,
        order_number=order.order_number,
        client_id=order.client_id,
        client_name=client_name,
        vendor_id=order.vendor_id,
        status=order.status,
        total=order.total,
        is_vendor_purchase=order.is_vendor_purchase,
        vendor_notes=order.vendor_notes,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


from datetime import datetime
