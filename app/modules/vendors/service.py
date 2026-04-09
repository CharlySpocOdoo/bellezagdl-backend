import secrets
import string
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List, Tuple
from uuid import UUID
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.modules.auth.models import User, Vendor, Client, Invitation
from app.modules.shared_enums import UserRole, InvitationType


# ── Helpers ───────────────────────────────────────────────────────────────────

def generate_invitation_code(length: int = 6) -> str:
    """Genera un codigo corto unico para el vendedor ej. JUAN42."""
    chars = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(chars) for _ in range(length))


def generate_unique_invitation_code(db: Session) -> str:
    """Genera un codigo de invitacion unico verificando que no exista en BD."""
    while True:
        code = generate_invitation_code()
        existing = db.query(Vendor).filter(Vendor.invitation_code == code).first()
        if not existing:
            return code


def send_activation_email(email: str, display_name: str, activation_token: str) -> None:
    """Envia el email de activacion al vendedor via SMTP."""
    activation_link = f"https://bellezagdl.com/activar?token={activation_token}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Activa tu cuenta de vendedor — BellezaGDL"
    msg["From"] = settings.emails_from
    msg["To"] = email

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

    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
        server.starttls()
        server.login(settings.smtp_user, settings.smtp_password)
        server.sendmail(settings.emails_from, email, msg.as_string())


# ── CRUD de vendedores ────────────────────────────────────────────────────────

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
) -> Vendor:
    """Crea un vendedor, genera tokens y envia email de activacion."""

    # Verificar que el email no exista
    existing = db.query(User).filter(User.email == email.lower()).first()
    if existing:
        raise ValueError("El email ya esta registrado")

    # Crear usuario inactivo
    user = User(
        email=email.lower(),
        password_hash="",  # Se establece al activar
        role=UserRole.vendor,
        active=False,
    )
    db.add(user)
    db.flush()

    # Generar tokens
    invitation_code = generate_unique_invitation_code(db)
    invitation_token = secrets.token_urlsafe(32)

    # Crear vendor
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
        invitation_token=invitation_token,
        notes=notes,
        active=False,
    )
    db.add(vendor)
    db.flush()

    # Crear invitacion de activacion (expira en 24h, uso unico)
    invitation = Invitation(
        vendor_id=vendor.id,
        created_by=created_by_id,
        token=invitation_token,
        type=InvitationType.vendor_onboarding,
        email_hint=email,
        max_uses=1,
        use_count=0,
        expires_at=datetime.utcnow() + timedelta(hours=24),
    )
    db.add(invitation)
    db.commit()
    db.refresh(vendor)

    # Enviar email de activacion
    try:
        send_activation_email(email, display_name, invitation_token)
    except Exception as e:
        print(f"Error enviando email: {e}")
        # No falla si el email no se pudo enviar — el admin puede reenviar

    return vendor


def get_vendor_by_id(db: Session, vendor_id: UUID) -> Optional[Vendor]:
    """Obtiene un vendedor por su ID."""
    return db.query(Vendor).filter(Vendor.id == vendor_id).first()


def get_vendor_by_user_id(db: Session, user_id: UUID) -> Optional[Vendor]:
    """Obtiene el vendor vinculado a un usuario."""
    return db.query(Vendor).filter(Vendor.user_id == user_id).first()


def get_all_vendors(db: Session) -> List[Vendor]:
    """Lista todos los vendedores."""
    return db.query(Vendor).order_by(Vendor.display_name).all()


def update_vendor(db: Session, vendor_id: UUID, **kwargs) -> Optional[Vendor]:
    """Actualiza los campos de un vendedor."""
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
    """Lista los clientes de un vendedor."""
    return db.query(Client).filter(
        Client.vendor_id == vendor_id,
    ).order_by(Client.first_name).all()


def get_invitation_link(vendor: Vendor) -> str:
    """Construye el link de invitacion del vendedor para clientes."""
    return f"https://bellezagdl.com/registro?token={vendor.invitation_token}"


def get_or_create_client_invitation(db: Session, vendor: Vendor, created_by_id: UUID) -> Invitation:
    """Obtiene o crea la invitacion permanente del vendedor para clientes."""
    existing = db.query(Invitation).filter(
        Invitation.vendor_id == vendor.id,
        Invitation.type == InvitationType.client_signup,
    ).first()
    if existing:
        return existing
    invitation = Invitation(
        vendor_id=vendor.id,
        created_by=created_by_id,
        token=vendor.invitation_token,
        type=InvitationType.client_signup,
        max_uses=None,  # Ilimitado
        use_count=0,
        expires_at=None,  # Sin expiracion
    )
    db.add(invitation)
    db.commit()
    return invitation
