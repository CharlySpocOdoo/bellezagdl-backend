import secrets
import string
import boto3
from botocore.exceptions import ClientError
from typing import Optional, List, Tuple
from uuid import UUID
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.modules.auth.models import User, Vendor, Client, Invitation
from app.modules.shared_enums import UserRole, InvitationType


def generate_invitation_code(length: int = 6) -> str:
    chars = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(chars) for _ in range(length))


def generate_unique_invitation_code(db: Session) -> str:
    while True:
        code = generate_invitation_code()
        existing = db.query(Vendor).filter(Vendor.invitation_code == code).first()
        if not existing:
            return code


def send_activation_email(email: str, display_name: str, activation_token: str) -> None:
    import boto3
    from botocore.exceptions import ClientError
    
    activation_link = f"https://rosadelima.shop/activar?token={activation_token}"
    
    text = f"""
Hola {display_name},

Has sido registrado como vendedor en BellezaGDL.
Activa tu cuenta aqui:
{activation_link}

Este link expira en 24 horas.
BellezaGDL
    """
    
    html = f"""
<html>
<body>
<h2>Hola {display_name},</h2>
<p>Has sido registrado como vendedor en <strong>BellezaGDL</strong>.</p>
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
                'Subject': {'Data': 'Activa tu cuenta de vendedor — BellezaGDL'},
                'Body': {
                    'Text': {'Data': text},
                    'Html': {'Data': html}
                }
            }
        )
    except ClientError as e:
        print(f"Error enviando email: {e}")

def create_vendor(
    db: Session,
    email: str,
    display_name: str,
    first_name: str,
    last_name: str,
    created_by_id: UUID,
    phone: Optional[str] = None,
    address: Optional[str] = None,
    gender=None,
    birth_date=None,
    workplace: Optional[str] = None,
    workplace_type=None,
    notes: Optional[str] = None,
    commission_percentage: Optional[float] = None,
) -> Vendor:
    existing = db.query(User).filter(User.email == email.lower()).first()
    if existing:
        raise ValueError("El email ya esta registrado")

    user = User(
        email=email.lower(),
        password_hash="",
        role=UserRole.vendor,
        active=False,
    )
    db.add(user)
    db.flush()

    invitation_code          = generate_unique_invitation_code(db)
    activation_token         = secrets.token_urlsafe(32)  # Para activar cuenta — uso unico, 24h
    client_invitation_token  = secrets.token_urlsafe(32)  # Para invitar clientes — ilimitado, sin expiracion

    vendor = Vendor(
        user_id=user.id,
        display_name=display_name,
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        address=address,
        gender=gender,
        birth_date=birth_date,
        workplace=workplace,
        workplace_type=workplace_type,
        invitation_code=invitation_code,
        invitation_token=client_invitation_token,  # El token del vendor es el de clientes
        notes=notes,
        active=False,
        commission_percentage=commission_percentage,
    )
    db.add(vendor)
    db.flush()

    # Invitacion de activacion — uso unico, expira en 24h
    activation_invitation = Invitation(
        vendor_id=vendor.id,
        created_by=created_by_id,
        token=activation_token,
        type=InvitationType.vendor_onboarding,
        email_hint=email,
        max_uses=1,
        use_count=0,
        expires_at=datetime.utcnow() + timedelta(hours=24),
    )
    db.add(activation_invitation)

    # Invitacion para clientes — ilimitada, sin expiracion
    client_invitation = Invitation(
        vendor_id=vendor.id,
        created_by=created_by_id,
        token=client_invitation_token,
        type=InvitationType.client_signup,
        max_uses=None,
        use_count=0,
        expires_at=None,
    )
    db.add(client_invitation)

    db.commit()
    db.refresh(vendor)

    try:
        send_activation_email(email, display_name, activation_token)
    except Exception as e:
        print(f"Error enviando email: {e}")

    return vendor


def get_vendor_by_id(db: Session, vendor_id: UUID) -> Optional[Vendor]:
    return db.query(Vendor).filter(Vendor.id == vendor_id).first()


def get_vendor_by_user_id(db: Session, user_id: UUID) -> Optional[Vendor]:
    return db.query(Vendor).filter(Vendor.user_id == user_id).first()


def get_all_vendors(db: Session) -> List[Vendor]:
    return db.query(Vendor).order_by(Vendor.display_name).all()


def update_vendor(db: Session, vendor_id: UUID, **kwargs) -> Optional[Vendor]:
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
    if not vendor:
        return None
    for key, value in kwargs.items():
        if value is not None:
            setattr(vendor, key, value)
    db.commit()
    db.refresh(vendor)
    return vendor


def get_vendor_clients(db: Session, vendor_id: UUID) -> List[Client]:
    return db.query(Client).filter(
        Client.vendor_id == vendor_id,
    ).order_by(Client.first_name).all()


def get_invitation_link(vendor: Vendor) -> str:
    return f"https://bellezagdl.com/registro?token={vendor.invitation_token}"
