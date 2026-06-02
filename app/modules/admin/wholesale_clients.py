import secrets
import boto3
from botocore.exceptions import ClientError
from datetime import datetime, timedelta
from typing import Optional, List
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.modules.auth.dependencies import require_admin
from app.modules.auth.models import User, Client, Invitation
from app.modules.shared_enums import UserRole, InvitationType
from app.modules.vendors.schemas import ClientResponse

router_admin = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────────

class CreateWholesaleClientRequest(BaseModel):
    email: EmailStr
    first_name: str
    last_name: str
    phone: Optional[str] = None
    delivery_address: Optional[str] = None
    business_name: Optional[str] = None
    rfc: Optional[str] = None
    fiscal_address: Optional[str] = None


class UpdateWholesaleClientRequest(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    delivery_address: Optional[str] = None
    business_name: Optional[str] = None
    rfc: Optional[str] = None
    fiscal_address: Optional[str] = None
    active: Optional[bool] = None


# ── Email de activacion ───────────────────────────────────────────────────────

def send_wholesale_activation_email(email: str, first_name: str, activation_token: str) -> None:
    activation_link = f"https://rosadelima.shop/activar?token={activation_token}"

    text = f"""
Hola {first_name},

Has sido registrado como cliente mayoreo en BellezaGDL.
Activa tu cuenta aqui:
{activation_link}

Este link expira en 24 horas.
BellezaGDL
    """

    html = f"""
<html>
<body>
<h2>Hola {first_name},</h2>
<p>Has sido registrado como cliente mayoreo en <strong>BellezaGDL</strong>.</p>
<p>
  <a href="{activation_link}"
     style="background:#1F3864;color:white;padding:12px 24px;
            text-decoration:none;border-radius:4px;display:inline-block;">
    Activar mi cuenta
  </a>
</p>
<p>Este link expira en 24 horas.</p>
<p>BellezaGDL</p>
</body>
</html>
    """

    client = boto3.client('ses', region_name=settings.aws_region)
    try:
        client.send_email(
            Source=settings.emails_from,
            Destination={'ToAddresses': [email]},
            Message={
                'Subject': {'Data': 'Activa tu cuenta de mayoreo — BellezaGDL'},
                'Body': {
                    'Text': {'Data': text},
                    'Html': {'Data': html},
                }
            }
        )
    except ClientError as e:
        print(f"Error enviando email: {e}")


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router_admin.post("", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
def create_wholesale_client(
    request: CreateWholesaleClientRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Crea un cliente mayoreo y envía email de activación."""
    existing = db.query(User).filter(User.email == request.email.lower()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El email ya esta registrado",
        )

    # Crear user con rol wholesale — inactivo hasta que active su cuenta
    user = User(
        email=request.email.lower(),
        password_hash="",
        role=UserRole.wholesale,
        active=False,
    )
    db.add(user)
    db.flush()

    # Crear client con vendor_id=null
    client = Client(
        user_id=user.id,
        vendor_id=None,
        first_name=request.first_name,
        last_name=request.last_name,
        phone=request.phone,
        delivery_address=request.delivery_address,
        business_name=request.business_name,
        rfc=request.rfc,
        fiscal_address=request.fiscal_address,
        active=False,
    )
    db.add(client)
    db.flush()

    # Crear invitacion de activacion — uso unico, expira en 24h
    activation_token = secrets.token_urlsafe(32)
    invitation = Invitation(
        vendor_id=None,
        created_by=current_user.id,
        token=activation_token,
        type=InvitationType.vendor_onboarding,
        email_hint=request.email.lower(),
        max_uses=1,
        use_count=0,
        expires_at=datetime.utcnow() + timedelta(hours=24),
    )
    db.add(invitation)
    db.commit()
    db.refresh(client)

    try:
        send_wholesale_activation_email(request.email, request.first_name, activation_token)
    except Exception as e:
        print(f"Error enviando email: {e}")

    return ClientResponse(
        id=client.id,
        user_id=client.user_id,
        first_name=client.first_name,
        last_name=client.last_name,
        email=request.email.lower(),
        phone=client.phone,
        delivery_address=client.delivery_address,
        gender=client.gender,
        birth_date=client.birth_date,
        active=client.active,
        last_order_at=client.last_order_at,
        created_at=client.created_at,
        business_name=client.business_name,
        rfc=client.rfc,
        fiscal_address=client.fiscal_address,
    )


@router_admin.get("", response_model=List[ClientResponse])
def list_wholesale_clients(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Lista todos los clientes mayoreo."""
    wholesale_users = db.query(User).filter(User.role == UserRole.wholesale).all()
    result = []
    for u in wholesale_users:
        client = db.query(Client).filter(Client.user_id == u.id).first()
        if client:
            result.append(ClientResponse(
                id=client.id,
                user_id=client.user_id,
                first_name=client.first_name,
                last_name=client.last_name,
                email=u.email,
                phone=client.phone,
                delivery_address=client.delivery_address,
                gender=client.gender,
                birth_date=client.birth_date,
                active=client.active,
                last_order_at=client.last_order_at,
                created_at=client.created_at,
                business_name=client.business_name,
                rfc=client.rfc,
                fiscal_address=client.fiscal_address,
            ))
    return result


@router_admin.get("/{client_id}", response_model=ClientResponse)
def get_wholesale_client(
    client_id: UUID,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Detalle de un cliente mayoreo específico."""
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    user = db.query(User).filter(
        User.id == client.user_id,
        User.role == UserRole.wholesale,
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="Cliente mayoreo no encontrado")

    return ClientResponse(
        id=client.id,
        user_id=client.user_id,
        first_name=client.first_name,
        last_name=client.last_name,
        email=user.email,
        phone=client.phone,
        delivery_address=client.delivery_address,
        gender=client.gender,
        birth_date=client.birth_date,
        active=client.active,
        last_order_at=client.last_order_at,
        created_at=client.created_at,
        business_name=client.business_name,
        rfc=client.rfc,
        fiscal_address=client.fiscal_address,
    )


@router_admin.patch("/{client_id}", response_model=ClientResponse)
def update_wholesale_client(
    client_id: UUID,
    request: UpdateWholesaleClientRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Edita datos de un cliente mayoreo."""
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    user = db.query(User).filter(
        User.id == client.user_id,
        User.role == UserRole.wholesale,
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="Cliente mayoreo no encontrado")

    update_data = request.model_dump(exclude_none=True)
    for key, value in update_data.items():
        setattr(client, key, value)

    db.commit()
    db.refresh(client)

    return ClientResponse(
        id=client.id,
        user_id=client.user_id,
        first_name=client.first_name,
        last_name=client.last_name,
        email=user.email,
        phone=client.phone,
        delivery_address=client.delivery_address,
        gender=client.gender,
        birth_date=client.birth_date,
        active=client.active,
        last_order_at=client.last_order_at,
        created_at=client.created_at,
        business_name=client.business_name,
        rfc=client.rfc,
        fiscal_address=client.fiscal_address,
    )