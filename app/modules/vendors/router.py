from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from app.database import get_db
from app.modules.auth.dependencies import require_admin, require_vendor
from app.modules.auth.models import User, Vendor, Client
from app.modules.admin.models import Notification
from app.modules.vendors import service
from app.modules.vendors.schemas import (
    CreateVendorRequest, UpdateVendorRequest, UpdateVendorProfileRequest,
    VendorResponse, VendorProfileResponse,
    ClientResponse, NotificationResponse,
)

router_admin = APIRouter()
router_vendor = APIRouter()


# ── Admin endpoints ───────────────────────────────────────────────────────────

@router_admin.post("", response_model=VendorResponse, status_code=status.HTTP_201_CREATED)
def create_vendor(
    request: CreateVendorRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Crea un vendedor y envia email de activacion."""
    try:
        vendor = service.create_vendor(
            db=db,
            email=request.email,
            display_name=request.display_name,
            first_name=request.first_name,
            last_name=request.last_name,
            created_by_id=current_user.id,
            phone=request.phone,
            address=request.address,
            gender=request.gender,
            birth_date=request.birth_date,
            workplace=request.workplace,
            workplace_type=request.workplace_type,
            notes=request.notes,
            commission_percentage=request.commission_percentage,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )

    user = db.query(User).filter(User.id == vendor.user_id).first()
    return _vendor_to_response(vendor, user)


@router_admin.get("", response_model=List[VendorResponse])
def list_vendors(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Lista todos los vendedores."""
    vendors = service.get_all_vendors(db)
    result = []
    for vendor in vendors:
        user = db.query(User).filter(User.id == vendor.user_id).first()
        result.append(_vendor_to_response(vendor, user))
    return result


@router_admin.patch("/{vendor_id}", response_model=VendorResponse)
def update_vendor(
    vendor_id: UUID,
    request: UpdateVendorRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Edita los datos de un vendedor."""
    update_data = request.model_dump(exclude_none=True)
    vendor = service.update_vendor(db, vendor_id, **update_data)
    if not vendor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vendedor no encontrado",
        )
    user = db.query(User).filter(User.id == vendor.user_id).first()
    return _vendor_to_response(vendor, user)


# ── Vendor endpoints ──────────────────────────────────────────────────────────

@router_vendor.get("/me", response_model=VendorProfileResponse)
def get_vendor_profile(
    current_user: User = Depends(require_vendor),
    db: Session = Depends(get_db),
):
    """Perfil del vendedor autenticado con su link de invitacion."""
    vendor = service.get_vendor_by_user_id(db, current_user.id)
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendedor no encontrado")

    total_clients = db.query(Client).filter(Client.vendor_id == vendor.id).count()

    user = db.query(User).filter(User.id == vendor.user_id).first()
    response = _vendor_to_response(vendor, user)

    return VendorProfileResponse(
        **response.model_dump(),
        invitation_link=service.get_invitation_link(vendor),
        total_clients=total_clients,
    )


@router_vendor.get("/me/clients", response_model=List[ClientResponse])
def get_vendor_clients(
    current_user: User = Depends(require_vendor),
    db: Session = Depends(get_db),
):
    """Lista de clientes del vendedor autenticado."""
    vendor = service.get_vendor_by_user_id(db, current_user.id)
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendedor no encontrado")

    clients = service.get_vendor_clients(db, vendor.id)
    result = []
    for client in clients:
        user = db.query(User).filter(User.id == client.user_id).first()
        result.append(ClientResponse(
            id=client.id,
            user_id=client.user_id,
            first_name=client.first_name,
            last_name=client.last_name,
            email=user.email if user else "",
            phone=client.phone,
            delivery_address=client.delivery_address,
            gender=client.gender,
            birth_date=client.birth_date,
            active=client.active,
            last_order_at=client.last_order_at,
        ))
    return result


@router_vendor.get("/me/notifications", response_model=List[NotificationResponse])
def get_vendor_notifications(
    unread: Optional[bool] = Query(None),
    current_user: User = Depends(require_vendor),
    db: Session = Depends(get_db),
):
    """Notificaciones del vendedor."""
    query = db.query(Notification).filter(Notification.user_id == current_user.id)
    if unread:
        query = query.filter(Notification.read_at.is_(None))
    notifications = query.order_by(Notification.created_at.desc()).limit(50).all()
    return notifications


# ── Helper ────────────────────────────────────────────────────────────────────

def _vendor_to_response(vendor: Vendor, user: User) -> VendorResponse:
    return VendorResponse(
        id=vendor.id,
        user_id=vendor.user_id,
        display_name=vendor.display_name,
        first_name=vendor.first_name,
        last_name=vendor.last_name,
        email=user.email if user else "",
        phone=vendor.phone,
        address=vendor.address,
        gender=vendor.gender,
        birth_date=vendor.birth_date,
        workplace=vendor.workplace,
        workplace_type=vendor.workplace_type,
        invitation_code=vendor.invitation_code,
        active=vendor.active,
        notes=vendor.notes,
        commission_percentage=float(vendor.commission_percentage) if vendor.commission_percentage else None,
    )


@router_vendor.patch("/me", response_model=VendorResponse)
def update_vendor_profile(
    request: UpdateVendorProfileRequest,
    current_user: User = Depends(require_vendor),
    db: Session = Depends(get_db),
):
    """El vendedor edita sus propios datos. Solo puede editar los suyos."""
    vendor = service.get_vendor_by_user_id(db, current_user.id)
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendedor no encontrado")

    update_data = request.model_dump(exclude_none=True)
    vendor = service.update_vendor(db, vendor.id, **update_data)
    user = db.query(User).filter(User.id == vendor.user_id).first()
    return _vendor_to_response(vendor, user)
