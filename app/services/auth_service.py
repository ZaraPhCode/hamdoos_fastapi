"""Authentication business logic.

Mirrors ASP.NET Core Identity functionality:
- Register with phone/email
- Login with phone/email + password
- Phone verification via SMS
- Password reset via SMS code
- Role management
- Token management (access + refresh)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional
from random import randint

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.models.identity import User, Role, UserRole
from app.models.common import SmsCode
from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    TokenResponse,
    UserResponse,
    ChangePasswordRequest,
    UserProfileUpdate,
)


def _generate_verification_code() -> str:
    return str(randint(10000, 99999))


async def _get_user_by_username(db: AsyncSession, username: str) -> Optional[User]:
    stmt = (
        select(User)
        .options(selectinload(User.roles).selectinload(UserRole.role))
        .where(
            or_(User.user_name == username, User.phone_number == username, User.email == username),
            User.is_removed == False,
        )
    )
    result = await db.execute(stmt)
    return result.unique().scalar_one_or_none()


def _build_user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        first_name=user.first_name,
        last_name=user.last_name,
        full_name=user.full_name,
        email=user.email,
        phone_number=user.phone_number,
        gender=user.gender,
        is_phone_confirmed=user.phone_number_confirmed,
        is_email_confirmed=user.email_confirmed,
        roles=[ur.role.name for ur in user.roles],
    )


async def register_user(db: AsyncSession, request: RegisterRequest) -> User:
    existing = await _get_user_by_username(db, request.phone_number)
    if existing:
        raise ValueError("Phone number already registered")

    if request.email:
        existing_email = await _get_user_by_username(db, request.email)
        if existing_email:
            raise ValueError("Email already registered")

    user = User(
        id=uuid.uuid4(),
        user_name=request.phone_number,
        first_name=request.first_name,
        last_name=request.last_name,
        phone_number=request.phone_number,
        email=request.email,
        gender=request.gender,
        password_hash=hash_password(request.password),
        phone_number_confirmed=False,
        email_confirmed=False,
        has_password=True,
        insert_date=datetime.now(timezone.utc),
        update_date=datetime.now(timezone.utc),
    )
    db.add(user)
    await db.flush()

    # Assign default "Customer" role if it exists
    role_stmt = select(Role).where(Role.name == "Customer", Role.is_removed == False)
    role_result = await db.execute(role_stmt)
    customer_role = role_result.scalar_one_or_none()
    if customer_role:
        user_role = UserRole(
            id=uuid.uuid4(),
            user_id=user.id,
            role_id=customer_role.id,
            insert_date=datetime.now(timezone.utc),
            update_date=datetime.now(timezone.utc),
        )
        db.add(user_role)
        await db.flush()

    return user


async def authenticate_user(db: AsyncSession, request: LoginRequest) -> Optional[User]:
    user = await _get_user_by_username(db, request.username)
    if user is None:
        return None
    if not user.password_hash or not verify_password(request.password, user.password_hash):
        return None
    return user


async def create_token_response(user: User) -> TokenResponse:
    token_data = {"sub": str(user.id), "username": user.user_name}
    return TokenResponse(
        access_token=create_access_token(data=token_data),
        refresh_token=create_refresh_token(data=token_data),
    )


async def refresh_access_token(refresh_token: str) -> TokenResponse:
    payload = decode_token(refresh_token)
    if payload is None or payload.get("type") != "refresh":
        raise ValueError("Invalid or expired refresh token")

    token_data = {"sub": payload["sub"], "username": payload.get("username", "")}
    return TokenResponse(
        access_token=create_access_token(data=token_data),
        refresh_token=create_refresh_token(data=token_data),
    )


async def send_verification_code(db: AsyncSession, phone_number: str) -> str:
    code = _generate_verification_code()

    # Store code
    sms_code = SmsCode(
        id=uuid.uuid4(),
        phone_number=phone_number,
        code=code,
        insert_date=datetime.now(timezone.utc),
        update_date=datetime.now(timezone.utc),
    )
    db.add(sms_code)
    await db.flush()

    # In production, dispatch via SMS service here
    return code


async def verify_phone_code(db: AsyncSession, phone_number: str, code: str) -> bool:
    stmt = (
        select(SmsCode)
        .where(
            SmsCode.phone_number == phone_number,
            SmsCode.code == code,
            SmsCode.is_removed == False,
        )
        .order_by(SmsCode.insert_date.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    sms_code = result.scalar_one_or_none()
    if sms_code is None:
        return False

    # Mark user phone as confirmed
    user_stmt = select(User).where(User.phone_number == phone_number)
    user_result = await db.execute(user_stmt)
    user = user_result.scalar_one_or_none()
    if user:
        user.phone_number_confirmed = True
        user.update_date = datetime.now(timezone.utc)

    # Invalidate the code
    sms_code.is_removed = True
    return True


async def change_user_password(
    user: User, db: AsyncSession, request: ChangePasswordRequest
) -> None:
    if not user.password_hash or not verify_password(request.current_password, user.password_hash):
        raise ValueError("Current password is incorrect")
    user.password_hash = hash_password(request.new_password)
    user.has_password = True
    user.update_date = datetime.now(timezone.utc)


async def update_user_profile(
    user: User, db: AsyncSession, request: UserProfileUpdate
) -> User:
    if request.first_name is not None:
        user.first_name = request.first_name
    if request.last_name is not None:
        user.last_name = request.last_name
    if request.email is not None:
        user.email = request.email
    if request.national_id is not None:
        user.national_id = request.national_id
    if request.gender is not None:
        user.gender = request.gender
    user.update_date = datetime.now(timezone.utc)
    return user


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> Optional[User]:
    stmt = (
        select(User)
        .options(selectinload(User.roles).selectinload(UserRole.role))
        .where(User.id == user_id, User.is_removed == False)
    )
    result = await db.execute(stmt)
    return result.unique().scalar_one_or_none()