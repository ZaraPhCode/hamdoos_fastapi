"""Authentication & authorization FastAPI dependencies."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import decode_token
from app.database import get_db
from app.models.identity import User, Role, UserRole

security_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    token = None
    if credentials is not None:
        token = credentials.credentials
    else:
        token = request.cookies.get("access_token")
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    try:
        uid = UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user ID")

    stmt = (
        select(User)
        .options(
            selectinload(User.roles).selectinload(UserRole.role),
        )
        .where(User.id == uid, User.is_removed == False)
    )
    result = await db.execute(stmt)
    user = result.unique().scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Returns None instead of raising 401 if no token is provided."""
    if credentials is None:
        return None
    payload = decode_token(credentials.credentials)
    if payload is None:
        return None
    user_id = payload.get("sub")
    if user_id is None:
        return None
    try:
        uid = UUID(user_id)
    except ValueError:
        return None
    stmt = (
        select(User)
        .options(selectinload(User.roles).selectinload(UserRole.role))
        .where(User.id == uid, User.is_removed == False)
    )
    result = await db.execute(stmt)
    return result.unique().scalar_one_or_none()


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    return current_user


def require_role(role_name: str):
    """Dependency factory: require a specific role."""

    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        user_role_names = {ur.role.name for ur in current_user.roles}
        if role_name not in user_role_names:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role: {role_name}",
            )
        return current_user

    return role_checker


def require_any_role(*role_names: str):
    """Dependency factory: require at least one of the given roles."""

    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        user_role_names = {ur.role.name for ur in current_user.roles}
        if not user_role_names.intersection(role_names):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {', '.join(role_names)}",
            )
        return current_user

    return role_checker


async def get_optional_user_from_cookie(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Reads JWT from 'access_token' cookie, returns User or None."""
    token = request.cookies.get("access_token")
    if not token:
        return None
    from app.core.security import decode_token
    payload = decode_token(token)
    if payload is None:
        return None
    user_id = payload.get("sub")
    if user_id is None:
        return None
    try:
        uid = UUID(user_id)
    except ValueError:
        return None
    stmt = (
        select(User)
        .options(selectinload(User.roles).selectinload(UserRole.role))
        .where(User.id == uid, User.is_removed == False)
    )
    result = await db.execute(stmt)
    return result.unique().scalar_one_or_none()


async def get_admin_user(
    current_user: User = Depends(get_current_user),
) -> User:
    user_role_names = {ur.role.name for ur in current_user.roles}
    if "Admin" not in user_role_names:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user