"""Identity admin business logic — Users, Roles, RoleClaims, UserRoles, IdentityInformations.

Mirrors the .NET Security controllers.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import hash_password
from app.models.identity import User, Role, UserRole, RoleClaim, Claim, IdentityInformation
from app.models.common import Log
from app.models.enums import IdentityType, IdentityStatus


# ── Users ──

async def get_users_paginated(db: AsyncSession, page: int = 1, page_size: int = 20, search: str = ""):
    query = select(User).where(User.is_removed == False)
    count_query = select(func.count(User.id)).where(User.is_removed == False)

    if search:
        pattern = f"%{search}%"
        query = query.where(
            User.first_name.ilike(pattern) |
            User.last_name.ilike(pattern) |
            User.user_name.ilike(pattern) |
            User.phone_number.ilike(pattern) |
            User.email.ilike(pattern)
        )
        count_query = count_query.where(
            User.first_name.ilike(pattern) |
            User.last_name.ilike(pattern) |
            User.user_name.ilike(pattern) |
            User.phone_number.ilike(pattern) |
            User.email.ilike(pattern)
        )

    total = (await db.execute(count_query)).scalar() or 0
    users = (await db.execute(
        query.options(selectinload(User.roles).selectinload(UserRole.role))
        .order_by(User.insert_date.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).unique().scalars().all()
    return users, total


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> Optional[User]:
    result = await db.execute(
        select(User)
        .options(selectinload(User.roles).selectinload(UserRole.role))
        .where(User.id == user_id, User.is_removed == False)
    )
    return result.unique().scalar_one_or_none()


async def create_user(db: AsyncSession, form_data: dict, current_user_id: uuid.UUID) -> User:
    user = User(
        id=uuid.uuid4(),
        user_name=form_data.get("user_name", "").strip(),
        first_name=form_data.get("first_name", "").strip(),
        last_name=form_data.get("last_name", "").strip(),
        email=(form_data.get("email") or "").strip() or None,
        phone_number=(form_data.get("phone_number") or "").strip() or None,
        gender=form_data.get("gender", "Unknown"),
        national_id=(form_data.get("national_id") or "").strip() or None,
        password_hash=hash_password(form_data.get("password", "@Aa123456")),
        has_password=True,
        phone_number_confirmed=True,
        created_by_user_id=current_user_id,
        insert_date=datetime.now(timezone.utc),
        update_date=datetime.now(timezone.utc),
    )
    db.add(user)
    await db.flush()

    db.add(Log(
        record_id=user.id,
        table_name="users",
        description=f"ایجاد کاربر: {user.full_name or user.user_name}",
        type="Create",
        created_by_user_id=current_user_id,
    ))
    return user


async def update_user(db: AsyncSession, user: User, form_data: dict, current_user_id: uuid.UUID) -> User:
    user.first_name = form_data.get("first_name", user.first_name or "").strip()
    user.last_name = form_data.get("last_name", user.last_name or "").strip()
    user.email = (form_data.get("email") or "").strip() or None
    user.phone_number = (form_data.get("phone_number") or "").strip() or None
    user.gender = form_data.get("gender", user.gender or "Unknown")
    user.national_id = (form_data.get("national_id") or "").strip() or None
    user.update_date = datetime.now(timezone.utc)

    new_password = form_data.get("password", "").strip()
    if new_password:
        user.password_hash = hash_password(new_password)
        user.has_password = True

    await db.flush()

    db.add(Log(
        record_id=user.id,
        table_name="users",
        description=f"ویرایش کاربر: {user.full_name or user.user_name}",
        type="Update",
        created_by_user_id=current_user_id,
    ))
    return user


async def soft_delete_user(db: AsyncSession, user: User, current_user_id: uuid.UUID) -> None:
    name = user.full_name or user.user_name
    user.is_removed = True
    user.update_date = datetime.now(timezone.utc)
    await db.flush()

    db.add(Log(
        record_id=user.id,
        table_name="users",
        description=f"حذف کاربر: {name}",
        created_by_user_id=current_user_id,
        type="Delete",
    ))


async def assign_role_to_user(db: AsyncSession, user_id: uuid.UUID, role_name: str, current_user_id: uuid.UUID) -> None:
    user = await db.get(User, user_id)
    if not user or user.is_removed:
        raise ValueError("User not found")

    role_result = await db.execute(select(Role).where(Role.name == role_name, Role.is_removed == False))
    role = role_result.scalar_one_or_none()
    if not role:
        raise ValueError(f"Role '{role_name}' not found")

    existing = await db.execute(
        select(UserRole).where(UserRole.user_id == user_id, UserRole.role_id == role.id, UserRole.is_removed == False)
    )
    if existing.scalar_one_or_none():
        raise ValueError("User already has this role")

    ur = UserRole(
        id=uuid.uuid4(),
        user_id=user_id,
        role_id=role.id,
        created_by_user_id=current_user_id,
        insert_date=datetime.now(timezone.utc),
        update_date=datetime.now(timezone.utc),
    )
    db.add(ur)

    db.add(Log(
        record_id=user_id,
        table_name="user_roles",
        description=f"اختصاص نقش {role_name} به کاربر {user.full_name or user.user_name}",
        type="Create",
        created_by_user_id=current_user_id,
    ))


# ── Roles ──

async def get_roles_with_counts(db: AsyncSession):
    roles = (await db.execute(
        select(Role).where(Role.is_removed == False).order_by(Role.insert_date.desc())
    )).scalars().all()

    result = []
    for role in roles:
        user_count = (await db.execute(
            select(func.count(UserRole.id)).where(
                UserRole.role_id == role.id, UserRole.is_removed == False
            )
        )).scalar() or 0
        permission_count = (await db.execute(
            select(func.count(RoleClaim.id)).where(
                RoleClaim.role_id == role.id, RoleClaim.is_removed == False
            )
        )).scalar() or 0
        result.append({
            "id": role.id,
            "name": role.name,
            "description": role.description,
            "user_count": user_count,
            "permission_count": permission_count,
            "insert_date": role.insert_date,
            "update_date": role.update_date,
        })
    return result


async def get_role_by_id(db: AsyncSession, role_id: uuid.UUID) -> Optional[Role]:
    return await db.get(Role, role_id)


async def create_role(db: AsyncSession, form_data: dict, current_user_id: uuid.UUID) -> Role:
    name = (form_data.get("name") or "").strip()
    role = Role(
        id=uuid.uuid4(),
        name=name,
        normalized_name=name.upper(),
        description=(form_data.get("description") or "").strip() or None,
        created_by_user_id=current_user_id,
        insert_date=datetime.now(timezone.utc),
        update_date=datetime.now(timezone.utc),
    )
    db.add(role)
    await db.flush()

    db.add(Log(
        record_id=role.id,
        table_name="roles",
        description=f"ایجاد نقش: {name}",
        type="Create",
        created_by_user_id=current_user_id,
    ))
    return role


async def update_role(db: AsyncSession, role: Role, form_data: dict, current_user_id: uuid.UUID) -> Role:
    old_name = role.name
    role.name = (form_data.get("name") or "").strip()
    role.normalized_name = role.name.upper()
    role.description = (form_data.get("description") or "").strip() or None
    role.update_date = datetime.now(timezone.utc)
    await db.flush()

    db.add(Log(
        record_id=role.id,
        table_name="roles",
        description=f"ویرایش نقش: {old_name} -> {role.name}",
        type="Update",
        created_by_user_id=current_user_id,
    ))
    return role


async def soft_delete_role(db: AsyncSession, role: Role, current_user_id: uuid.UUID) -> None:
    name = role.name
    role.is_removed = True
    role.update_date = datetime.now(timezone.utc)
    await db.flush()

    db.add(Log(
        record_id=role.id,
        table_name="roles",
        description=f"حذف نقش: {name}",
        created_by_user_id=current_user_id,
        type="Delete",
    ))


# ── Role Claims ──

async def get_role_claims_with_relations(db: AsyncSession, page: int = 1, page_size: int = 50):
    query = (
        select(RoleClaim)
        .options(selectinload(RoleClaim.role))
        .where(RoleClaim.is_removed == False)
        .order_by(RoleClaim.insert_date.desc())
    )
    total = (await db.execute(
        select(func.count(RoleClaim.id)).where(RoleClaim.is_removed == False)
    )).scalar() or 0
    items = (await db.execute(
        query.offset((page - 1) * page_size).limit(page_size)
    )).unique().scalars().all()
    return items, total


async def get_role_claim_by_id(db: AsyncSession, claim_id: uuid.UUID) -> Optional[RoleClaim]:
    result = await db.execute(
        select(RoleClaim)
        .options(selectinload(RoleClaim.role))
        .where(RoleClaim.id == claim_id, RoleClaim.is_removed == False)
    )
    return result.unique().scalar_one_or_none()


async def create_role_claim(db: AsyncSession, form_data: dict, current_user_id: uuid.UUID) -> RoleClaim:
    role_id_raw = form_data.get("role_id", "")
    if not role_id_raw:
        raise ValueError("نقش الزامی است")
    try:
        role_id = uuid.UUID(role_id_raw)
    except ValueError:
        raise ValueError("شناسه نقش نامعتبر است")

    # Verify role exists
    role = await db.get(Role, role_id)
    if not role or role.is_removed:
        raise ValueError("نقش مورد نظر یافت نشد")
    claim_type = form_data.get("claim_type", "Permission")
    claim_value = (form_data.get("claim_value") or "").strip()
    operation_type = form_data.get("operation_type", "Read")
    operation_name = form_data.get("operation_name") or f"{claim_value}.{operation_type}"

    # Check duplicate
    existing = await db.execute(
        select(RoleClaim).where(
            RoleClaim.role_id == role_id,
            RoleClaim.operation_name == operation_name,
            RoleClaim.is_removed == False,
        )
    )
    if existing.scalar_one_or_none():
        raise ValueError("این دسترسی از قبل برای این نقش وجود دارد")

    rc = RoleClaim(
        id=uuid.uuid4(),
        role_id=role_id,
        claim_type=claim_type,
        claim_value=claim_value,
        operation_type=operation_type,
        operation_name=operation_name,
        created_by_user_id=current_user_id,
        insert_date=datetime.now(timezone.utc),
        update_date=datetime.now(timezone.utc),
    )
    db.add(rc)
    await db.flush()

    db.add(Log(
        record_id=rc.id,
        record_int_id=None,
        table_name="role_claims",
        description=f"ایجاد دسترسی: {operation_name}",
        type="Create",
        created_by_user_id=current_user_id,
    ))
    return rc


async def update_role_claim(db: AsyncSession, rc: RoleClaim, form_data: dict, current_user_id: uuid.UUID) -> RoleClaim:
    role_id_raw = form_data.get("role_id", str(rc.role_id))
    try:
        new_role_id = uuid.UUID(role_id_raw)
    except ValueError:
        raise ValueError("شناسه نقش نامعتبر است")
    role = await db.get(Role, new_role_id)
    if not role or role.is_removed:
        raise ValueError("نقش مورد نظر یافت نشد")
    rc.role_id = new_role_id
    rc.claim_type = form_data.get("claim_type", rc.claim_type)
    rc.claim_value = (form_data.get("claim_value") or "").strip()
    rc.operation_type = form_data.get("operation_type", rc.operation_type or "Read")
    rc.operation_name = form_data.get("operation_name") or f"{rc.claim_value}.{rc.operation_type}"
    rc.update_date = datetime.now(timezone.utc)
    await db.flush()

    db.add(Log(
        record_id=rc.id,
        record_int_id=None,
        table_name="role_claims",
        description=f"ویرایش دسترسی: {rc.operation_name}",
        type="Update",
        created_by_user_id=current_user_id,
    ))
    return rc


async def soft_delete_role_claim(db: AsyncSession, rc: RoleClaim, current_user_id: uuid.UUID) -> None:
    name = rc.operation_name
    rc.is_removed = True
    rc.update_date = datetime.now(timezone.utc)
    await db.flush()

    db.add(Log(
        record_id=rc.id,
        record_int_id=None,
        table_name="role_claims",
        description=f"حذف دسترسی: {name}",
        created_by_user_id=current_user_id,
        type="Delete",
    ))


# ── User Roles ──

async def get_user_roles_with_relations(db: AsyncSession, page: int = 1, page_size: int = 50):
    query = (
        select(UserRole)
        .options(selectinload(UserRole.user), selectinload(UserRole.role))
        .where(UserRole.is_removed == False)
        .order_by(UserRole.insert_date.desc())
    )
    total = (await db.execute(
        select(func.count(UserRole.id)).where(UserRole.is_removed == False)
    )).scalar() or 0
    items = (await db.execute(
        query.offset((page - 1) * page_size).limit(page_size)
    )).unique().scalars().all()
    return items, total


async def get_user_role_by_id(db: AsyncSession, ur_id: uuid.UUID) -> Optional[UserRole]:
    result = await db.execute(
        select(UserRole)
        .options(selectinload(UserRole.user), selectinload(UserRole.role))
        .where(UserRole.id == ur_id, UserRole.is_removed == False)
    )
    return result.unique().scalar_one_or_none()


async def create_user_role(db: AsyncSession, form_data: dict, current_user_id: uuid.UUID) -> UserRole:
    user_id_raw = form_data.get("user_id", "")
    role_id_raw = form_data.get("role_id", "")
    if not user_id_raw or not role_id_raw:
        raise ValueError("کاربر و نقش الزامی هستند")
    try:
        user_id = uuid.UUID(user_id_raw)
        role_id = uuid.UUID(role_id_raw)
    except ValueError:
        raise ValueError("شناسه کاربر یا نقش نامعتبر است")

    existing = await db.execute(
        select(UserRole).where(
            UserRole.user_id == user_id,
            UserRole.role_id == role_id,
            UserRole.is_removed == False,
        )
    )
    if existing.scalar_one_or_none():
        raise ValueError("این کاربر از قبل این نقش را دارد")

    ur = UserRole(
        id=uuid.uuid4(),
        user_id=user_id,
        role_id=role_id,
        created_by_user_id=current_user_id,
        insert_date=datetime.now(timezone.utc),
        update_date=datetime.now(timezone.utc),
    )
    db.add(ur)
    await db.flush()

    db.add(Log(
        record_id=ur.id,
        table_name="user_roles",
        description="اختصاص نقش به کاربر",
        type="Create",
        created_by_user_id=current_user_id,
    ))
    return ur


async def update_user_role(db: AsyncSession, ur: UserRole, form_data: dict, current_user_id: uuid.UUID) -> UserRole:
    user_id_raw = form_data.get("user_id", str(ur.user_id))
    role_id_raw = form_data.get("role_id", str(ur.role_id))
    try:
        ur.user_id = uuid.UUID(user_id_raw)
        ur.role_id = uuid.UUID(role_id_raw)
    except ValueError:
        raise ValueError("شناسه کاربر یا نقش نامعتبر است")
    ur.update_date = datetime.now(timezone.utc)
    await db.flush()

    db.add(Log(
        record_id=ur.id,
        table_name="user_roles",
        description="ویرایش نقش کاربر",
        type="Update",
        created_by_user_id=current_user_id,
    ))
    return ur


async def soft_delete_user_role(db: AsyncSession, ur: UserRole, current_user_id: uuid.UUID) -> None:
    ur.is_removed = True
    ur.update_date = datetime.now(timezone.utc)
    await db.flush()

    db.add(Log(
        record_id=ur.id,
        table_name="user_roles",
        description="حذف نقش کاربر",
        created_by_user_id=current_user_id,
        type="Delete",
    ))


# ── Identity Informations ──

async def get_identity_infos_with_user(db: AsyncSession, page: int = 1, page_size: int = 20, type_filter: str = "", status_filter: str = "", user_filter: str = "", national_code_filter: str = ""):
    query = (
        select(IdentityInformation)
        .options(selectinload(IdentityInformation.user))
        .where(IdentityInformation.is_removed == False)
    )
    count_query = select(func.count(IdentityInformation.id)).where(IdentityInformation.is_removed == False)

    if type_filter:
        query = query.where(IdentityInformation.type == type_filter)
        count_query = count_query.where(IdentityInformation.type == type_filter)
    if status_filter:
        query = query.where(IdentityInformation.status == status_filter)
        count_query = count_query.where(IdentityInformation.status == status_filter)
    if user_filter:
        try:
            uid = uuid.UUID(user_filter)
            query = query.where(IdentityInformation.user_id == uid)
            count_query = count_query.where(IdentityInformation.user_id == uid)
        except ValueError:
            pass
    if national_code_filter:
        pattern = f"%{national_code_filter}%"
        query = query.where(IdentityInformation.national_code_or_id.ilike(pattern))
        count_query = count_query.where(IdentityInformation.national_code_or_id.ilike(pattern))

    total = (await db.execute(count_query)).scalar() or 0
    items = (await db.execute(
        query.order_by(IdentityInformation.insert_date.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).unique().scalars().all()
    return items, total


async def get_identity_info_by_id(db: AsyncSession, info_id: uuid.UUID) -> Optional[IdentityInformation]:
    result = await db.execute(
        select(IdentityInformation)
        .options(selectinload(IdentityInformation.user))
        .where(IdentityInformation.id == info_id, IdentityInformation.is_removed == False)
    )
    return result.unique().scalar_one_or_none()


def _validate_identity_info(form_data: dict) -> list[str]:
    errors = []
    id_type = form_data.get("type", "")
    national_code = form_data.get("national_code_or_id", "").strip()
    economic_code = (form_data.get("economic_code") or "").strip()
    final_consumer = form_data.get("final_consumer") == "on"

    if id_type == IdentityType.REAL.value:
        if economic_code and len(economic_code) != 14:
            if not final_consumer:
                errors.append("کد اقتصادی برای حقیقی باید 14 رقم باشد")
        if national_code and len(national_code) != 10:
            errors.append("کد ملی باید 10 رقم باشد")
    elif id_type == IdentityType.LEGAL.value:
        if economic_code and len(economic_code) != 11:
            errors.append("کد اقتصادی برای حقوقی باید 11 رقم باشد")
        if national_code and len(national_code) != 11:
            errors.append("شناسه ملی باید 11 رقم باشد")
        if final_consumer:
            errors.append("مصرف‌کننده نهایی برای نوع حقوقی مجاز نیست")
    elif id_type == IdentityType.CIVIC_PARTICIPATION.value:
        if economic_code and len(economic_code) != 11:
            errors.append("کد اقتصادی برای مشارکت مدنی باید 11 رقم باشد")
        if national_code and len(national_code) != 12:
            errors.append("شناسه ملی برای مشارکت مدنی باید 12 رقم باشد")
        if final_consumer:
            errors.append("مصرف‌کننده نهایی برای مشارکت مدنی مجاز نیست")
    elif id_type == IdentityType.NON_IRANIAN.value:
        if economic_code and len(economic_code) != 11:
            errors.append("کد اقتصادی برای اتباع غیر ایرانی باید 11 رقم باشد")
        if national_code and len(national_code) != 12:
            errors.append("شناسه ملی برای اتباع غیر ایرانی باید 12 رقم باشد")
        if final_consumer:
            errors.append("مصرف‌کننده نهایی برای اتباع غیر ایرانی مجاز نیست")

    return errors


async def create_identity_info(db: AsyncSession, form_data: dict, current_user_id: uuid.UUID) -> IdentityInformation:
    errors = _validate_identity_info(form_data)
    if errors:
        raise ValueError("; ".join(errors))

    user_id = uuid.UUID(form_data.get("user_id", ""))

    # Check duplicate
    name = (form_data.get("name") or "").strip()
    existing = await db.execute(
        select(IdentityInformation).where(
            IdentityInformation.name == name,
            IdentityInformation.user_id == user_id,
            IdentityInformation.is_removed == False,
        )
    )
    if existing.scalar_one_or_none():
        raise ValueError("این نام قبلاً برای این کاربر ثبت شده است")

    national_code = (form_data.get("national_code_or_id") or "").strip() or None
    info = IdentityInformation(
        id=uuid.uuid4(),
        user_id=user_id,
        name=name,
        national_code_or_id=national_code,
        economic_code=(form_data.get("economic_code") or "").strip() or None,
        postal_code=(form_data.get("postal_code") or "").strip() or None,
        type=form_data.get("type", IdentityType.REAL.value),
        status=IdentityStatus.AWAITING_CONFIRMATION.value,
        final_consumer=form_data.get("final_consumer") == "on",
        address=(form_data.get("address") or "").strip() or None,
        city=(form_data.get("city") or "").strip() or None,
        province=(form_data.get("province") or "").strip() or None,
        country=(form_data.get("country") or "").strip() or None,
        phone_number=(form_data.get("phone_number") or "").strip() or None,
        created_by_user_id=current_user_id,
        insert_date=datetime.now(timezone.utc),
        update_date=datetime.now(timezone.utc),
    )
    db.add(info)
    await db.flush()

    db.add(Log(
        record_id=info.id,
        table_name="identity_informations",
        description=f"ایجاد اطلاعات هویتی: {name}",
        type="Create",
        created_by_user_id=current_user_id,
    ))
    return info


async def update_identity_info(db: AsyncSession, info: IdentityInformation, form_data: dict, current_user_id: uuid.UUID) -> IdentityInformation:
    errors = _validate_identity_info(form_data)
    if errors:
        raise ValueError("; ".join(errors))

    info.name = (form_data.get("name") or "").strip()
    info.national_code_or_id = (form_data.get("national_code_or_id") or "").strip() or None
    info.economic_code = (form_data.get("economic_code") or "").strip() or None
    info.postal_code = (form_data.get("postal_code") or "").strip() or None
    info.type = form_data.get("type", info.type or IdentityType.REAL.value)
    info.final_consumer = form_data.get("final_consumer") == "on"
    info.address = (form_data.get("address") or "").strip() or None
    info.city = (form_data.get("city") or "").strip() or None
    info.province = (form_data.get("province") or "").strip() or None
    info.country = (form_data.get("country") or "").strip() or None
    info.phone_number = (form_data.get("phone_number") or "").strip() or None
    info.update_date = datetime.now(timezone.utc)
    await db.flush()

    db.add(Log(
        record_id=info.id,
        table_name="identity_informations",
        description=f"ویرایش اطلاعات هویتی: {info.name}",
        type="Update",
        created_by_user_id=current_user_id,
    ))
    return info


async def accept_identity_info(db: AsyncSession, info: IdentityInformation, current_user_id: uuid.UUID) -> None:
    if info.status != IdentityStatus.AWAITING_CONFIRMATION.value:
        raise ValueError("فقط آیتم‌های در انتظار تایید قابل تایید هستند")
    info.status = IdentityStatus.CONFIRMED.value
    info.update_date = datetime.now(timezone.utc)
    await db.flush()

    db.add(Log(
        record_id=info.id,
        table_name="identity_informations",
        description=f"تایید اطلاعات هویتی: {info.name}",
        type="Update",
        created_by_user_id=current_user_id,
    ))


async def reject_identity_info(db: AsyncSession, info: IdentityInformation, current_user_id: uuid.UUID) -> None:
    if info.status != IdentityStatus.AWAITING_CONFIRMATION.value:
        raise ValueError("فقط آیتم‌های در انتظار تایید قابل رد هستند")
    info.status = IdentityStatus.REJECTED.value
    info.update_date = datetime.now(timezone.utc)
    await db.flush()

    db.add(Log(
        record_id=info.id,
        table_name="identity_informations",
        description=f"رد اطلاعات هویتی: {info.name}",
        type="Update",
        created_by_user_id=current_user_id,
    ))


async def soft_delete_identity_info(db: AsyncSession, info: IdentityInformation, current_user_id: uuid.UUID) -> None:
    name = info.name
    info.is_removed = True
    info.update_date = datetime.now(timezone.utc)
    await db.flush()

    db.add(Log(
        record_id=info.id,
        table_name="identity_informations",
        description=f"حذف اطلاعات هویتی: {name}",
        created_by_user_id=current_user_id,
        type="Delete",
    ))