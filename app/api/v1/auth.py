"""Auth API routes — register, login, refresh, profile, admin."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.dependencies import get_current_active_user, get_admin_user
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
    VerifyPhoneRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    ChangePasswordRequest,
    UserProfileUpdate,
)
from app.models.identity import User
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    try:
        user = await auth_service.register_user(db, request)
        return await auth_service.create_token_response(user)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await auth_service.authenticate_user(db, request)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    return await auth_service.create_token_response(user)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(refresh_token: str):
    try:
        return await auth_service.refresh_access_token(refresh_token)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_active_user)):
    return auth_service._build_user_response(current_user)


@router.put("/me", response_model=UserResponse)
async def update_me(
    request: UserProfileUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    user = await auth_service.update_user_profile(current_user, db, request)
    return auth_service._build_user_response(user)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        await auth_service.change_user_password(current_user, db, request)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/send-verification-code")
async def send_verification_code(phone_number: str, db: AsyncSession = Depends(get_db)):
    code = await auth_service.send_verification_code(db, phone_number)
    # In production, send via SMS service
    return {"message": "Verification code sent", "code": code}


@router.post("/verify-phone")
async def verify_phone(request: VerifyPhoneRequest, db: AsyncSession = Depends(get_db)):
    success = await auth_service.verify_phone_code(db, request.phone_number, request.code)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid code")
    return {"message": "Phone number verified successfully"}


# ── Admin endpoints ──

@router.get("/users", response_model=list[UserResponse])
async def get_all_users(
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models.identity import UserRole

    stmt = (
        select(User)
        .options(selectinload(User.roles).selectinload(UserRole.role))
        .where(User.is_removed == False)
    )
    result = await db.execute(stmt)
    users = result.unique().scalars().all()
    return [auth_service._build_user_response(u) for u in users]


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    import uuid
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user ID")
    user = await auth_service.get_user_by_id(db, uid)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return auth_service._build_user_response(user)