"""Auth flow business logic — mirrors the .NET Identity Account pages.

Implements the multi-step login/signup journey used by:
- RegisterOrLogin (email/phone entry + routing)
- Login (password + captcha)
- Register
- SmsConfirmation (phone verification with 6-digit code + 2:30 timer)
- ForgotPassword / ResetBySms / ResetPassword
- ConfirmEmail
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone
from random import randint
from typing import Optional

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_token,
)
from app.models.identity import User, UserRole
from app.models.common import SmsCode
from app.services.sms_service import SelectedSmsSender
from app.services import captcha_service

PHONE_RE = re.compile(r"^09\d{9}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

SMS_TTL = timedelta(seconds=150)  # 2:30
CAPTCHA_TTL = timedelta(minutes=2)

sms_sender = SelectedSmsSender()


# ── Input detection (mirrors _0_Framework.Application.Tools.EmailOrPhone) ──

def email_or_phone(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    value = value.strip()
    if PHONE_RE.match(value):
        return "phone"
    if EMAIL_RE.match(value):
        return "email"
    return None


# ── Presentation helpers ──

def mask_phone(phone: Optional[str]) -> str:
    if not phone:
        return "*****"
    if len(phone) == 11:
        first = phone[:5]
        last = phone[9:]
        return f"{last}****{first}"
    return f"{phone[-1]}*****{phone[0]}"


def remaining_timer(insert_date: Optional[datetime]) -> str:
    """Remaining MM:SS until the SMS expires, or '-1:-1' if already expired."""
    if insert_date is None:
        return "-1:-1"
    insert = insert_date.replace(tzinfo=None) if insert_date.tzinfo else insert_date
    remaining = SMS_TTL - (datetime.utcnow() - insert)
    if remaining <= timedelta(0):
        return "-1:-1"
    total = int(remaining.total_seconds())
    return f"{total // 60:02d}:{total % 60:02d}"


# ── User lookup ──

async def find_user_by_phone(db: AsyncSession, phone_number: str) -> Optional[User]:
    result = await db.execute(
        select(User)
        .options(selectinload(User.roles).selectinload(UserRole.role))
        .where(User.phone_number == phone_number, User.is_removed == False)
    )
    return result.scalar_one_or_none()


async def find_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    result = await db.execute(
        select(User)
        .options(selectinload(User.roles).selectinload(UserRole.role))
        .where(
            or_(User.email == email, User.user_name == email),
            User.is_removed == False,
        )
    )
    return result.scalar_one_or_none()


async def find_user_via(db: AsyncSession, value: str) -> Optional[User]:
    return await find_user_by_email(db, value) or await find_user_by_phone(db, value)


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> Optional[User]:
    result = await db.execute(
        select(User)
        .options(selectinload(User.roles).selectinload(UserRole.role))
        .where(User.id == user_id, User.is_removed == False)
    )
    return result.scalar_one_or_none()


# ── SMS code management (mirrors SmsExtention) ──

async def check_sms_status(db: AsyncSession, phone_number: str, user_id: uuid.UUID):
    """Public wrapper: check SMS status and return timer."""
    return await _check_sms(db, phone_number, user_id)


async def _check_sms(db: AsyncSession, phone_number: str, user_id: uuid.UUID):
    result = await db.execute(
        select(SmsCode)
        .where(SmsCode.phone_number == phone_number, SmsCode.is_removed == False)
        .order_by(SmsCode.insert_date.desc())
        .limit(1)
    )
    sms = result.scalar_one_or_none()
    if sms is None:
        return {"status": "NotSent", "sms": None, "timer": "-1:-1"}
    if sms.insert_date.replace(tzinfo=None) + SMS_TTL >= datetime.utcnow():
        return {"status": "Sent", "sms": sms, "timer": remaining_timer(sms.insert_date)}
    return {"status": "Expired", "sms": sms, "timer": "-1:-1"}


async def _generate_sms_code(db: AsyncSession, phone_number: str, user: User) -> SmsCode:
    sms = SmsCode(
        id=uuid.uuid4(),
        created_by_user_id=user.id,
        code=str(randint(100000, 999999)),
        phone_number=phone_number,
        insert_date=datetime.utcnow(),
        update_date=datetime.utcnow(),
    )
    db.add(sms)
    return sms


async def _change_sms_code(db: AsyncSession, sms: SmsCode, user: User) -> None:
    sms.code = str(randint(100000, 999999))
    sms.insert_date = datetime.utcnow()
    db.add(sms)


async def send_verification_sms(
    db: AsyncSession, phone_number: str, user: User
) -> dict:
    """Ensure a fresh SMS code exists, dispatch it, and return status + timer."""
    res = await _check_sms(db, phone_number, user.id)
    if res["status"] == "NotSent":
        sms = await _generate_sms_code(db, phone_number, user)
        await db.flush()
        await sms_sender.send_verification_code(phone_number, sms.code, user.full_name)
        await db.flush()
        return {"status": "Sent", "timer": remaining_timer(sms.insert_date), "code": sms.code}
    if res["status"] == "Expired":
        await _change_sms_code(db, res["sms"], user)
        await db.flush()
        await sms_sender.send_verification_code(phone_number, res["sms"].code, user.full_name)
        await db.flush()
        return {"status": "Sent", "timer": remaining_timer(res["sms"].insert_date), "code": res["sms"].code}
    return {"status": "Sent", "timer": res["timer"], "code": res["sms"].code}


async def verify_sms_code(
    db: AsyncSession, user: User, phone_number: str, code: str
) -> dict:
    """Validate the submitted 6-digit code for the user/phone.

    Returns {'ok': bool, 'error': str|None, 'timer': str}.
    """
    result = await db.execute(
        select(SmsCode)
        .where(SmsCode.phone_number == phone_number, SmsCode.is_removed == False)
        .order_by(SmsCode.insert_date.desc())
        .limit(1)
    )
    sms = result.scalar_one_or_none()
    if sms is None:
        return {"ok": False, "error": "کد یافت نشد", "timer": "-1:-1"}

    timer = remaining_timer(sms.insert_date)
    if sms.insert_date.replace(tzinfo=None) + SMS_TTL < datetime.utcnow():
        return {
            "ok": False,
            "error": "کد منقضی شده می‌توانید روی دکمه ارسال مجدد کلیک کنید.",
            "timer": "-1:-1",
        }
    if code is None or len(code) != 6:
        return {
            "ok": False,
            "error": "کد باید ۶ رقم باشد",
            "timer": timer,
        }
    if sms.code != code or sms.phone_number != phone_number or sms.created_by_user_id != user.id:
        return {
            "ok": False,
            "error": "کد وارد شده صحیح نیست",
            "timer": timer,
        }
    return {"ok": True, "error": None, "timer": timer}


# ── CAPTCHA helpers ──

async def ensure_captcha(db: AsyncSession, user_id: uuid.UUID):
    res = await captcha_service.check(db, user_id)
    if res.status == captcha_service.CaptchaStatus.SENT:
        return {"captcha": res.captcha, "ok": True}
    if res.status == captcha_service.CaptchaStatus.EXPIRED and res.captcha is not None:
        await captcha_service.change_code(db, res.captcha)
        await db.flush()
        return {"captcha": res.captcha, "ok": True}
    gen = await captcha_service.generate(db, user_id)
    await db.flush()
    return {"captcha": gen.captcha, "ok": gen.captcha is not None}


async def validate_captcha(db: AsyncSession, user_id: uuid.UUID, code: int) -> dict:
    result = await db.execute(
        select(captcha_service.Captcha)
        .where(captcha_service.Captcha.created_by_user_id == user_id, captcha_service.Captcha.is_removed == False)
        .order_by(captcha_service.Captcha.insert_date.desc())
        .limit(1)
    )
    captcha = result.scalar_one_or_none()
    if captcha is None:
        return {"ok": False, "error": "کد کپچا یافت نشد"}
    if not captcha.disable:
        if captcha.code != int(code or 0):
            return {"ok": False, "error": "کد کپچا اشتباه است"}
        if captcha.insert_date.replace(tzinfo=None) + CAPTCHA_TTL < datetime.utcnow():
            return {"ok": False, "error": "کد منقضی شده"}
    return {"ok": True, "error": None}


# ── Token helpers (stateless, JWT-based — mirrors .NET DataProtection tokens) ──

def create_email_confirm_token(user_id: uuid.UUID) -> str:
    return create_access_token(data={"sub": str(user_id), "purpose": "email_confirm"}, expires_delta=timedelta(days=3))


def create_password_reset_token(user_id: uuid.UUID) -> str:
    return create_access_token(data={"sub": str(user_id), "purpose": "password_reset"}, expires_delta=timedelta(hours=24))


def decode_auth_token(token: str, purpose: str) -> Optional[uuid.UUID]:
    payload = decode_token(token)
    if not payload:
        return None
    if payload.get("purpose") != purpose:
        return None
    try:
        return uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        return None


# ── Password / account ──

def set_password(user: User, password: str) -> None:
    user.password_hash = hash_password(password)
    user.has_password = True
    user.update_date = datetime.utcnow()


def verify_login(user: User, password: str) -> bool:
    if not user.password_hash:
        return False
    return verify_password(password, user.password_hash)


def mask_phone_for_field(phone: Optional[str]) -> str:
    return mask_phone(phone)


async def _refresh_captcha(db: AsyncSession, captcha) -> None:
    """Regenerate a CAPTCHA row's code + image (mirrors ChangeCodeAsync)."""
    await captcha_service.change_code(db, captcha)
    await db.flush()


def _quote(value: Optional[str]) -> str:
    """URL-encode a string for safe inclusion in a query string value."""
    from urllib.parse import quote
    return quote(value or "")
