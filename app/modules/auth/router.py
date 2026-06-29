from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth import service
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User, Vendor, Client
from app.modules.auth.schemas import (
    LoginRequest, RefreshRequest, RegisterClientRequest,
    ActivateVendorRequest, TokenResponse, UserProfileResponse,
    InviteValidationResponse,
)
from app.modules.shared_enums import UserRole

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    try:
        access_token, refresh_token = service.login(
            db=db,
            email=request.email,
            password=request.password,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
def refresh(request: RefreshRequest, db: Session = Depends(get_db)):
    try:
        access_token, refresh_token = service.refresh_access_token(
            db=db,
            refresh_token=request.refresh_token,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/logout")
def logout(request: RefreshRequest, db: Session = Depends(get_db)):
    service.revoke_refresh_token(db=db, token=request.refresh_token)
    return {"message": "Sesion cerrada correctamente"}


@router.get("/invite/{token}", response_model=InviteValidationResponse)
def validate_invite(token: str, db: Session = Depends(get_db)):
    inv = service.get_valid_invitation(db=db, token=token)
    if not inv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitacion invalida o expirada",
        )
    vendor_name = None
    if inv.vendor_id:
        vendor = db.query(Vendor).filter(Vendor.id == inv.vendor_id).first()
        vendor_name = vendor.display_name if vendor else None

    return InviteValidationResponse(
        valid=True,
        type=inv.type.value,
        vendor_name=vendor_name,
        email_hint=inv.email_hint,
    )


@router.post("/register/client", response_model=TokenResponse)
def register_client(request: RegisterClientRequest, db: Session = Depends(get_db)):
    try:
        access_token, refresh_token = service.register_client(
            db=db,
            invitation_token=request.invitation_token,
            first_name=request.first_name,
            last_name=request.last_name,
            email=request.email,
            password=request.password,
            phone=request.phone,
            delivery_address=request.delivery_address,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/activate/vendor", response_model=TokenResponse)
def activate_vendor(request: ActivateVendorRequest, db: Session = Depends(get_db)):
    try:
        access_token, refresh_token = service.activate_vendor(
            db=db,
            invitation_token=request.invitation_token,
            password=request.password,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.get("/me", response_model=UserProfileResponse)
def get_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile_id = None
    display_name = None

    if current_user.role == UserRole.vendor:
        vendor = db.query(Vendor).filter(Vendor.user_id == current_user.id).first()
        if vendor:
            profile_id = vendor.id
            display_name = vendor.display_name
    elif current_user.role in (UserRole.client, UserRole.wholesale):
        client = db.query(Client).filter(Client.user_id == current_user.id).first()
        if client:
            profile_id = client.id
            display_name = f"{client.first_name} {client.last_name}"
    else:
        display_name = "Administrador"

    return UserProfileResponse(
        id=current_user.id,
        email=current_user.email,
        role=current_user.role,
        active=current_user.active,
        profile_id=profile_id,
        display_name=display_name,
    )
