import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Tuple
from uuid import UUID

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app.modules.auth.models import User, RefreshToken, Vendor, Client, Invitation
from app.modules.shared_enums import UserRole, InvitationType

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(user: User, profile_id: Optional[UUID] = None) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    payload = {
        "sub": str(user.id),
        "role": user.role.value,
        "email": user.email,
        "profile_id": str(profile_id) if profile_id else None,
        "exp": expire,
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])


def create_refresh_token() -> str:
    return secrets.token_urlsafe(64)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def save_refresh_token(db: Session, user_id: UUID, token: str, device_hint: Optional[str] = None) -> RefreshToken:
    expire = datetime.utcnow() + timedelta(days=settings.jwt_refresh_token_expire_days)
    db_token = RefreshToken(
        user_id=user_id,
        token_hash=hash_token(token),
        device_hint=device_hint,
        expires_at=expire,
    )
    db.add(db_token)
    db.commit()
    db.refresh(db_token)
    return db_token


def revoke_refresh_token(db: Session, token: str) -> bool:
    token_hash = hash_token(token)
    db_token = db.query(RefreshToken).filter(
        RefreshToken.token_hash == token_hash,
        RefreshToken.revoked_at.is_(None),
    ).first()
    if not db_token:
        return False
    db_token.revoked_at = datetime.utcnow()
    db.commit()
    return True


def get_valid_refresh_token(db: Session, token: str) -> Optional[RefreshToken]:
    token_hash = hash_token(token)
    return db.query(RefreshToken).filter(
        RefreshToken.token_hash == token_hash,
        RefreshToken.revoked_at.is_(None),
        RefreshToken.expires_at > datetime.utcnow(),
    ).first()


def get_profile_id(db: Session, user: User) -> Optional[UUID]:
    if user.role == UserRole.vendor:
        vendor = db.query(Vendor).filter(Vendor.user_id == user.id).first()
        return vendor.id if vendor else None
    elif user.role == UserRole.client:
        client = db.query(Client).filter(Client.user_id == user.id).first()
        return client.id if client else None
    return None


def get_display_name(db: Session, user: User) -> Optional[str]:
    if user.role == UserRole.vendor:
        vendor = db.query(Vendor).filter(Vendor.user_id == user.id).first()
        return vendor.display_name if vendor else None
    elif user.role == UserRole.client:
        client = db.query(Client).filter(Client.user_id == user.id).first()
        return f"{client.first_name} {client.last_name}" if client else None
    return "Administrador"


def login(db: Session, email: str, password: str, device_hint: Optional[str] = None) -> Tuple[str, str]:
    user = db.query(User).filter(
        User.email == email.lower(),
        User.active == True,
    ).first()

    if not user or not verify_password(password, user.password_hash):
        raise ValueError("Credenciales incorrectas")

    user.last_login_at = datetime.utcnow()
    db.commit()

    profile_id = get_profile_id(db, user)
    access_token = create_access_token(user, profile_id)
    refresh_token = create_refresh_token()
    save_refresh_token(db, user.id, refresh_token, device_hint)

    return access_token, refresh_token


def refresh_access_token(db: Session, refresh_token: str) -> Tuple[str, str]:
    db_token = get_valid_refresh_token(db, refresh_token)
    if not db_token:
        raise ValueError("Refresh token invalido o expirado")

    user = db.query(User).filter(
        User.id == db_token.user_id,
        User.active == True,
    ).first()

    if not user:
        raise ValueError("Usuario no encontrado o inactivo")

    profile_id = get_profile_id(db, user)
    new_access_token = create_access_token(user, profile_id)

    return new_access_token, refresh_token


def get_valid_invitation(db: Session, token: str) -> Optional[Invitation]:
    inv = db.query(Invitation).filter(Invitation.token == token).first()
    if not inv:
        return None
    if inv.expires_at and inv.expires_at < datetime.utcnow():
        return None
    if inv.max_uses and inv.use_count >= inv.max_uses:
        return None
    return inv


def register_client(db: Session, invitation_token: str, first_name: str, last_name: str,
                    email: str, password: str, phone: Optional[str] = None,
                    delivery_address: Optional[str] = None) -> Tuple[str, str]:
    inv = get_valid_invitation(db, invitation_token)
    if not inv or inv.type != InvitationType.client_signup:
        raise ValueError("Invitacion invalida o expirada")

    existing = db.query(User).filter(User.email == email.lower()).first()
    if existing:
        raise ValueError("El email ya esta registrado")

    user = User(
        email=email.lower(),
        password_hash=hash_password(password),
        role=UserRole.client,
        active=True,
        email_verified_at=datetime.utcnow(),
    )
    db.add(user)
    db.flush()

    client = Client(
        user_id=user.id,
        vendor_id=inv.vendor_id,
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        delivery_address=delivery_address,
    )
    db.add(client)
    inv.use_count += 1
    db.commit()
    db.refresh(user)

    access_token = create_access_token(user, client.id)
    refresh_token = create_refresh_token()
    save_refresh_token(db, user.id, refresh_token)

    return access_token, refresh_token


def activate_vendor(db: Session, invitation_token: str, password: str) -> Tuple[str, str]:
    inv = get_valid_invitation(db, invitation_token)
    if not inv or inv.type != InvitationType.vendor_onboarding:
        raise ValueError("Invitacion invalida o expirada")

    vendor = db.query(Vendor).filter(Vendor.id == inv.vendor_id).first()
    if not vendor:
        raise ValueError("Vendedor no encontrado")

    user = db.query(User).filter(User.id == vendor.user_id).first()
    if not user:
        raise ValueError("Usuario no encontrado")

    user.password_hash = hash_password(password)
    user.active = True
    user.email_verified_at = datetime.utcnow()
    vendor.active = True
    inv.use_count += 1
    db.commit()
    db.refresh(user)

    access_token = create_access_token(user, vendor.id)
    refresh_token = create_refresh_token()
    save_refresh_token(db, user.id, refresh_token)

    return access_token, refresh_token
