"""Shop authentication pages — the buyer-side multi-step login/signup flow.

Mirrors the .NET Identity Account razor pages:
RegisterOrLogin -> Login / Register / SmsConfirmation
plus ForgotPassword, ResetBySms, ResetPassword, ConfirmEmail.
"""

from __future__ import annotations

import re
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.dependencies import get_optional_user_from_cookie
from app.models.identity import User, Role, UserRole
from app.models.common import SiteSetting, Captcha
from app.services import auth_flow
from app.services.auth_service import create_token_response
from app.config.site_config import register_template_globals

templates = register_template_globals(Jinja2Templates(directory="app/templates"))
router = APIRouter(tags=["Shop Auth Pages"])

PHONE_RE = re.compile(r"^09\d{9}$")
ADMIN_ROLES = {"Admin", "Product Manager", "Orders Manager", "Financial Manager", "Warehouse Keeper"}


async def _captcha_disabled(db: AsyncSession) -> bool:
    result = await db.execute(select(SiteSetting).where(SiteSetting.is_removed == False).limit(1))
    ss = result.scalar_one_or_none()
    return bool(ss and ss.disable_captcha)


async def _load_captcha(db: AsyncSession, user_id: uuid.UUID, disabled: bool):
    """Return (cap_url, cap_id) ensuring a valid CAPTCHA exists."""
    if disabled:
        return None, None
    res = await auth_flow.ensure_captcha(db, user_id)
    await db.flush()
    captcha = res.get("captcha")
    if not captcha:
        return None, None
    return captcha.url, str(captcha.id)


async def _set_auth_cookie(response, user) -> None:
    token = await create_token_response(user)
    response.set_cookie(
        key="access_token", value=token.access_token, httponly=True, max_age=7200, samesite="lax"
    )


def _admin_target(next_url: str, user: User) -> str:
    user_roles = {ur.role.name for ur in user.roles}
    if next_url and next_url.startswith("/"):
        if next_url.startswith("/administration"):
            if user_roles.intersection(ADMIN_ROLES):
                return next_url
            return "/home"
        return next_url
    return "/home"


# ── RegisterOrLogin (entry: email/phone) ──

@router.get("/login", response_class=HTMLResponse)
async def shop_register_or_login(
    request: Request,
    emailOrPhoneNumber: Optional[str] = None,
    returnUrl: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user_from_cookie),
):
    if current_user:
        return RedirectResponse(url="/home")
    return templates.TemplateResponse("shop/register_or_login.html", {
        "request": request,
        "email_or_phone_number": emailOrPhoneNumber or "",
        "return_url": returnUrl or "/",
    })


@router.post("/login", response_class=HTMLResponse)
async def shop_register_or_login_submit(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user_from_cookie),
):
    form = await request.form()
    value = (form.get("emailOrPhoneNumber") or "").strip()
    return_url = form.get("returnUrl") or "/"
    if current_user:
        return RedirectResponse(url="/home")

    detection = auth_flow.email_or_phone(value)
    if detection is None:
        return templates.TemplateResponse("shop/register_or_login.html", {
            "request": request, "email_or_phone_number": value,
            "return_url": return_url, "field_error": "شماره موبایل یا ایمیل وارد شده معتبر نیست",
        })

    if detection == "phone":
        user = await auth_flow.find_user_by_phone(db, value)
        if user is None:
            return RedirectResponse(url=f"/auth/register?phoneNumber={value}", status_code=303)
        if user.phone_number_confirmed:
            return RedirectResponse(url=f"/auth/login?phoneNumber={value}&returnUrl={return_url}", status_code=303)
        await auth_flow.send_verification_sms(db, value, user)
        await db.commit()
        return RedirectResponse(url=f"/auth/sms-confirmation?phoneNumber={value}&needConfirmPhone=true", status_code=303)
    else:  # email
        user = await auth_flow.find_user_by_email(db, value)
        if user is None:
            return templates.TemplateResponse("shop/register_or_login.html", {
                "request": request, "email_or_phone_number": value,
                "return_url": return_url,
                "field_error": "حساب کاربری با مشخصات وارد شده وجود ندارد",
            })
        if user.phone_number_confirmed:
            return RedirectResponse(url=f"/auth/login?email={value}&returnUrl={return_url}", status_code=303)
        await auth_flow.send_verification_sms(db, user.phone_number, user)
        await db.commit()
        return RedirectResponse(url=f"/auth/sms-confirmation?phoneNumber={user.phone_number}&needConfirmPhone=true", status_code=303)


# ── Login (password + captcha) ──

async def _login_context(db, user: User, email_or_phone: str, return_url: str, disabled: bool):
    cap_url, cap_id = await _load_captcha(db, user.id, disabled)
    await db.flush()
    return {
        "email_or_phone": email_or_phone,
        "email_confirmed": user.email_confirmed,
        "user_id": str(user.id) if not user.email_confirmed else None,
        "disable_captcha": disabled,
        "cap_url": cap_url,
        "cap_id": cap_id,
        "return_url": return_url,
        "change_url": f"/login?emailOrPhoneNumber={auth_flow._quote(email_or_phone)}",
        "forgot_url": f"/auth/forgot-password?value={auth_flow._quote(email_or_phone)}",
        "sms_login_url": f"/auth/sms-confirmation?emailOrPhone={auth_flow._quote(email_or_phone)}&needConfirmPhone=false&handler=ResendCode",
    }


@router.get("/auth/login", response_class=HTMLResponse)
async def shop_login(
    request: Request,
    phoneNumber: Optional[str] = None,
    email: Optional[str] = None,
    returnUrl: Optional[str] = None,
    message: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user_from_cookie),
):
    if current_user:
        return RedirectResponse(url="/home")
    if not phoneNumber and not email:
        return RedirectResponse(url="/login")
    user = None
    email_or_phone = phoneNumber or email
    if email:
        user = await auth_flow.find_user_by_email(db, email)
    elif phoneNumber:
        user = await auth_flow.find_user_by_phone(db, phoneNumber)
    if user is None or not user.phone_number_confirmed:
        return HTMLResponse("Not found", status_code=404)

    disabled = await _captcha_disabled(db)
    ctx = await _login_context(db, user, email_or_phone, returnUrl or "/", disabled)
    ctx.update({"request": request, "message": message})
    return templates.TemplateResponse("shop/login.html", ctx)


@router.post("/auth/login", response_class=HTMLResponse)
async def shop_login_submit(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user_from_cookie),
):
    if current_user:
        return RedirectResponse(url="/home")
    form = await request.form()
    email_or_phone = (form.get("email_or_phone") or "").strip()
    password = form.get("password") or ""
    captcha_code = form.get("captcha_code")
    cap_id = form.get("cap_id")
    return_url = form.get("returnUrl") or "/"

    user = await auth_flow.find_user_via(db, email_or_phone)
    if user is None:
        return HTMLResponse("Not found", status_code=404)

    disabled = await _captcha_disabled(db)
    ctx_base = await _login_context(db, user, email_or_phone, return_url, disabled)

    errors = {}
    if not disabled and cap_id:
        try:
            cap = await db.get(Captcha, uuid.UUID(cap_id))
        except ValueError:
            cap = None
        if cap is None:
            return HTMLResponse("Not found", status_code=404)
        if cap.code != int(captcha_code or 0):
            errors["captcha"] = "کد کپچا اشتباه است"
        elif cap.insert_date.replace(tzinfo=None) + auth_flow.CAPTCHA_TTL < auth_flow.datetime.utcnow():
            errors["captcha"] = "کد منقضی شده"
        if errors.get("captcha"):
            await auth_flow._refresh_captcha(db, cap)
            await db.commit()
            ctx_base["cap_url"], ctx_base["cap_id"] = cap.url, str(cap.id)

    if not errors and not auth_flow.verify_login(user, password):
        errors["password"] = "رمز عبور معتبر نیست"
        if not disabled and cap_id:
            cap = await db.get(Captcha, uuid.UUID(cap_id))
            if cap:
                await auth_flow._refresh_captcha(db, cap)
                await db.commit()
                ctx_base["cap_url"], ctx_base["cap_id"] = cap.url, str(cap.id)

    if errors:
        ctx = dict(ctx_base)
        ctx.update({"request": request})
        ctx["password_error"] = errors.get("password")
        ctx["captcha_error"] = errors.get("captcha")
        return templates.TemplateResponse("shop/login.html", ctx)

    response = RedirectResponse(url=_admin_target(return_url, user), status_code=303)
    await _set_auth_cookie(response, user)
    return response


# ── Register (create account) ──

def _validate_password(pw: str) -> Optional[str]:
    if not pw or len(pw) < 6:
        return "رمز عبور باید حداقل ۶ کاراکتر باشد"
    if not any(c.isdigit() for c in pw):
        return "رمز عبور باید حداقل یک رقم داشته باشد"
    if not any(c.isupper() for c in pw):
        return "رمز عبور باید حداقل یک حرف بزرگ داشته باشد"
    if not any(c.islower() for c in pw):
        return "رمز عبور باید حداقل یک حرف کوچک داشته باشد"
    return None


async def _create_customer(db, first_name, last_name, email, phone_number, password) -> User:
    user = User(
        id=uuid.uuid4(),
        user_name=email,
        email=email,
        phone_number=phone_number,
        first_name=first_name,
        last_name=last_name,
        password_hash=auth_flow.hash_password(password),
        phone_number_confirmed=False,
        email_confirmed=False,
        has_password=True,
        gender="Unknown",
        insert_date=auth_flow.datetime.utcnow(),
        update_date=auth_flow.datetime.utcnow(),
    )
    db.add(user)
    await db.flush()
    role_stmt = select(Role).where(Role.name == "Customer", Role.is_removed == False)
    role = (await db.execute(role_stmt)).scalar_one_or_none()
    if role:
        db.add(UserRole(
            id=uuid.uuid4(), user_id=user.id, role_id=role.id,
            insert_date=auth_flow.datetime.utcnow(), update_date=auth_flow.datetime.utcnow(),
        ))
        await db.flush()
    return user


@router.get("/auth/register", response_class=HTMLResponse)
async def shop_register(
    request: Request,
    phoneNumber: Optional[str] = None,
    returnUrl: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    if not phoneNumber or not PHONE_RE.match(phoneNumber):
        return RedirectResponse(url="/login")
    existing = await auth_flow.find_user_by_phone(db, phoneNumber)
    if existing is not None:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("shop/register.html", {
        "request": request, "phone_number": phoneNumber, "return_url": returnUrl or "/",
    })


@router.post("/auth/register", response_class=HTMLResponse)
async def shop_register_submit(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    first_name = (form.get("first_name") or "").strip()
    last_name = (form.get("last_name") or "").strip()
    email = (form.get("email") or "").strip()
    phone = (form.get("phone") or "").strip()
    password = form.get("password") or ""
    return_url = form.get("returnUrl") or "/"

    field_errors = {}
    if not first_name:
        field_errors["first_name"] = "نام باید وارد شود"
    if not last_name:
        field_errors["last_name"] = "نام خانوادگی باید وارد شود"
    if not PHONE_RE.match(phone):
        field_errors["phone"] = "شماره موبایل معتبر نیست"
    if not email or not auth_flow.EMAIL_RE.match(email):
        field_errors["email"] = "ایمیل معتبر نیست"
    pw_err = _validate_password(password)
    if pw_err:
        field_errors["password"] = pw_err

    if not field_errors:
        if await auth_flow.find_user_by_phone(db, phone) is not None:
            field_errors["phone"] = "این شماره موبایل قبلاً ثبت شده است"
        elif await auth_flow.find_user_by_email(db, email) is not None:
            field_errors["email"] = "این ایمیل قبلاً ثبت شده است"

    if field_errors:
        return templates.TemplateResponse("shop/register.html", {
            "request": request, "first_name": first_name, "last_name": last_name,
            "email": email, "phone_number": phone, "return_url": return_url,
            "field_error": field_errors.get("first_name") or field_errors.get("last_name") or field_errors.get("email") or field_errors.get("phone"),
            "password_error": field_errors.get("password"),
            "error": field_errors.get("email") or field_errors.get("phone"),
        })

    user = await _create_customer(db, first_name, last_name, email, phone, password)
    await db.commit()

    # Send confirmation email (.NET procedure: template + callback link)
    token = auth_flow.create_email_confirm_token(user.id)
    base = str(request.base_url).rstrip("/")
    callback = f"{base}/auth/confirm-email?token={token}"
    from app.services.email_service import EmailSender
    await EmailSender().send_view_email(email, "همدوس - تأیید ایمیل", "email/confirm_email.html", {"callback_url": callback})

    await auth_flow.send_verification_sms(db, phone, user)
    await db.commit()

    return RedirectResponse(url=f"/auth/sms-confirmation?phoneNumber={phone}&needConfirmPhone=true", status_code=303)


# ── SMS Confirmation ──

@router.get("/auth/sms-confirmation", response_class=HTMLResponse)
async def shop_sms_confirmation(
    request: Request,
    needConfirmPhone: bool = True,
    phoneNumber: Optional[str] = None,
    email: Optional[str] = None,
    emailOrPhone: Optional[str] = None,
    handler: Optional[str] = None,
    code: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
):
    user = None
    email_or_phone = phoneNumber or email or emailOrPhone or ""
    if phoneNumber:
        user = await auth_flow.find_user_by_phone(db, phoneNumber)
    elif email:
        user = await auth_flow.find_user_by_email(db, email)
    elif emailOrPhone:
        user = await auth_flow.find_user_via(db, emailOrPhone)
    if user is None:
        return HTMLResponse("Not found", status_code=404)

    disabled = await _captcha_disabled(db)
    cap_url, cap_id = await _load_captcha(db, user.id, disabled)
    await db.flush()

    sms_res = await auth_flow.send_verification_sms(db, user.phone_number, user)
    await db.commit()

    return templates.TemplateResponse("shop/sms_confirmation.html", {
        "request": request,
        "masked_phone": auth_flow.mask_phone(user.phone_number),
        "email_or_phone": email_or_phone,
        "need_confirm_phone": needConfirmPhone,
        "timer": sms_res["timer"],
        "cap_url": cap_url,
        "cap_id": cap_id,
        "disable_captcha": disabled,
        "return_url": "/",
        "change_url": f"/login?emailOrPhoneNumber={auth_flow._quote(email_or_phone)}",
        "resend_url": (
            f"/auth/sms-confirmation?emailOrPhone={auth_flow._quote(email_or_phone)}"
            f"&needConfirmPhone={'true' if needConfirmPhone else 'false'}&handler=ResendCode"
        ),
    })


@router.post("/auth/sms-confirmation", response_class=HTMLResponse)
async def shop_sms_confirmation_submit(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    email_or_phone = form.get("email_or_phone") or ""
    sms_code = form.get("sms_code") or ""
    need_confirm_phone = (form.get("need_confirm_phone") or "false").lower() == "true"
    captcha_code = form.get("captcha_code")
    cap_id = form.get("cap_id")
    return_url = form.get("returnUrl") or "/"

    user = await auth_flow.find_user_via(db, email_or_phone)
    if user is None:
        return HTMLResponse("Not found", status_code=404)
    disabled = await _captcha_disabled(db)
    cap_url, new_cap_id = None, None
    captcha_error = None

    if not disabled and cap_id:
        cap = await db.get(Captcha, uuid.UUID(cap_id))
        if cap is None:
            return HTMLResponse("Not found", status_code=404)
        if cap.code != int(captcha_code or 0):
            captcha_error = "کد کپچا اشتباه است"
        elif cap.insert_date.replace(tzinfo=None) + auth_flow.CAPTCHA_TTL < auth_flow.datetime.utcnow():
            captcha_error = "کد منقضی شده"
        if captcha_error:
            await auth_flow._refresh_captcha(db, cap)
            await db.commit()
            cap_url, new_cap_id = cap.url, str(cap.id)

    res = await auth_flow.verify_sms_code(db, user, user.phone_number, sms_code)
    if not res["ok"]:
        if not captcha_error and not disabled:
            _, new_cap_id = await _load_captcha(db, user.id, disabled)
            await db.flush()
        return templates.TemplateResponse("shop/sms_confirmation.html", {
            "request": request,
            "masked_phone": auth_flow.mask_phone(user.phone_number),
            "email_or_phone": email_or_phone,
            "need_confirm_phone": need_confirm_phone,
            "timer": res["timer"],
            "sms_error": res["error"],
            "captcha_error": captcha_error,
            "cap_url": cap_url,
            "cap_id": new_cap_id,
            "disable_captcha": disabled,
            "return_url": return_url,
            "change_url": f"/login?emailOrPhoneNumber={auth_flow._quote(email_or_phone)}",
            "resend_url": (
                f"/auth/sms-confirmation?emailOrPhone={auth_flow._quote(email_or_phone)}"
                f"&needConfirmPhone={'true' if need_confirm_phone else 'false'}&handler=ResendCode"
            ),
        })

    if need_confirm_phone and not user.phone_number_confirmed:
        user.phone_number_confirmed = True
        user.update_date = auth_flow.datetime.utcnow()
        await db.commit()

    response = RedirectResponse(url=_admin_target(return_url, user), status_code=303)
    await _set_auth_cookie(response, user)
    return response


@router.get("/auth/resend-confirm-email/{user_id}", response_class=JSONResponse)
async def shop_resend_confirm_email(user_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    try:
        user = await auth_flow.get_user_by_id(db, uuid.UUID(user_id))
    except ValueError:
        user = None
    if user is None:
        return JSONResponse({"success": False})
    token = auth_flow.create_email_confirm_token(user.id)
    base = str(request.base_url).rstrip("/")
    callback = f"{base}/auth/confirm-email?token={token}"
    from app.services.email_service import EmailSender
    await EmailSender().send_view_email(user.email, "همدوس - تأیید ایمیل", "email/confirm_email.html", {"callback_url": callback})
    return JSONResponse({"success": True})


@router.get("/auth/confirm-email", response_class=HTMLResponse)
async def shop_confirm_email(
    request: Request,
    token: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    success = False
    if token:
        user_id = auth_flow.decode_auth_token(token, "email_confirm")
        if user_id:
            user = await auth_flow.get_user_by_id(db, user_id)
            if user and not user.email_confirmed:
                user.email_confirmed = True
                user.update_date = auth_flow.datetime.utcnow()
                await db.commit()
                success = True
    return templates.TemplateResponse("shop/confirm_email.html", {"request": request, "success": success})


# ── Forgot Password ──

@router.get("/auth/forgot-password", response_class=HTMLResponse)
async def shop_forgot_password(
    request: Request,
    value: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    if not value:
        return RedirectResponse(url="/login")
    user = await auth_flow.find_user_via(db, value)
    if user is None:
        return HTMLResponse("Not found", status_code=404)
    disabled = await _captcha_disabled(db)
    cap_url, cap_id = await _load_captcha(db, user.id, disabled)
    await db.flush()
    return templates.TemplateResponse("shop/forgot_password.html", {
        "request": request, "email": user.email,
        "cap_url": cap_url, "cap_id": cap_id, "disable_captcha": disabled,
    })


@router.post("/auth/forgot-password", response_class=HTMLResponse)
async def shop_forgot_password_submit(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    email = (form.get("email") or "").strip()
    reset_by_sms = (form.get("reset_by_sms") or "false").lower() == "true"
    captcha_code = form.get("captcha_code")
    cap_id = form.get("cap_id")

    user = await auth_flow.find_user_by_email(db, email)
    if user is None or not user.email_confirmed:
        return RedirectResponse(url="/login")

    disabled = await _captcha_disabled(db)
    cap_url, cap_id_out = None, None
    captcha_error = None
    if not disabled and cap_id:
        cap = await db.get(Captcha, uuid.UUID(cap_id))
        if cap is None:
            return HTMLResponse("Not found", status_code=404)
        if cap.code != int(captcha_code or 0):
            captcha_error = "کد کپچا اشتباه است"
        elif cap.insert_date.replace(tzinfo=None) + auth_flow.CAPTCHA_TTL < auth_flow.datetime.utcnow():
            captcha_error = "کد منقضی شده"
        if captcha_error:
            await auth_flow._refresh_captcha(db, cap)
            await db.commit()
            cap_url, cap_id_out = cap.url, str(cap.id)

    if captcha_error:
        return templates.TemplateResponse("shop/forgot_password.html", {
            "request": request, "email": email, "captcha_error": captcha_error,
            "cap_url": cap_url, "cap_id": cap_id_out, "disable_captcha": disabled,
        })

    if reset_by_sms:
        await auth_flow.send_verification_sms(db, user.phone_number, user)
        await db.commit()
        cap_code = ""
        if not disabled and cap_id:
            cap = await db.get(Captcha, uuid.UUID(cap_id))
            cap_code = cap.code if cap else ""
        reset_url = f"/auth/reset-by-sms?phoneNumber={user.phone_number}"
        if cap_code:
            reset_url += f"&code={cap_code}"
        return RedirectResponse(url=reset_url, status_code=303)

    # Email-based reset (.NET procedure: template + callback link)
    token = auth_flow.create_password_reset_token(user.id)
    base = str(request.base_url).rstrip("/")
    callback = f"{base}/auth/reset-password?token={token}"
    from app.services.email_service import EmailSender
    await EmailSender().send_view_email(email, "همدوس - بازیابی رمز عبور", "email/forget_password.html", {"callback_url": callback})
    return RedirectResponse(url="/auth/forgot-password-confirmation", status_code=303)


@router.get("/auth/forgot-password-confirmation", response_class=HTMLResponse)
async def shop_forgot_password_confirmation(request: Request):
    return templates.TemplateResponse("shop/forgot_password_confirmation.html", {"request": request})


# ── Reset by SMS ──

@router.get("/auth/reset-by-sms", response_class=HTMLResponse)
async def shop_reset_by_sms(
    request: Request,
    phoneNumber: Optional[str] = None,
    code: Optional[int] = 0,
    db: AsyncSession = Depends(get_db),
):
    if not phoneNumber:
        return RedirectResponse(url="/login")
    user = await auth_flow.find_user_by_phone(db, phoneNumber)
    if user is None:
        return HTMLResponse("Not found", status_code=404)
    disabled = await _captcha_disabled(db)
    if not disabled:
        cap = (await db.execute(
            select(Captcha).where(
                Captcha.created_by_user_id == user.id,
                Captcha.code == int(code or 0),
                Captcha.is_removed == False,
            ).limit(1)
        )).scalar_one_or_none()
        if cap is None:
            return HTMLResponse("Not found", status_code=404)

    sms_res = await auth_flow.send_verification_sms(db, phoneNumber, user)
    await db.commit()
    return templates.TemplateResponse("shop/reset_by_sms.html", {
        "request": request, "phone_number": phoneNumber,
        "captcha_code": code, "timer": sms_res["timer"],
        "resend_url": f"/auth/reset-by-sms/resend?phone_number={auth_flow._quote(phoneNumber)}&code={int(code or 0)}",
    })


@router.get("/auth/reset-by-sms/resend", response_class=HTMLResponse)
async def shop_reset_by_sms_resend(
    request: Request,
    phone_number: Optional[str] = None,
    code: Optional[int] = 0,
    db: AsyncSession = Depends(get_db),
):
    return RedirectResponse(url=f"/auth/reset-by-sms?phoneNumber={phone_number}&code={int(code or 0)}", status_code=303)


@router.post("/auth/reset-by-sms", response_class=HTMLResponse)
async def shop_reset_by_sms_submit(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    phone_number = form.get("phone_number") or ""
    password = form.get("password") or ""
    confirm_password = form.get("confirm_password") or ""
    sms_code = form.get("sms_code") or ""

    user = await auth_flow.find_user_by_phone(db, phone_number)
    if user is None:
        return HTMLResponse("Not found", status_code=404)

    errors = {}
    res = await auth_flow.verify_sms_code(db, user, phone_number, sms_code)
    if not res["ok"]:
        errors["sms"] = res["error"]
    if password != confirm_password:
        errors["confirm"] = "رمز عبور و تکرار آن مطابقت ندارند"
    pw_err = _validate_password(password)
    if pw_err:
        errors["password"] = pw_err

    if errors:
        return templates.TemplateResponse("shop/reset_by_sms.html", {
            "request": request, "phone_number": phone_number,
            "captcha_code": form.get("captcha_code") or 0,
            "timer": res["timer"],
            "sms_error": errors.get("sms"),
            "password_error": errors.get("password"),
            "confirm_error": errors.get("confirm"),
            "resend_url": f"/auth/reset-by-sms/resend?phone_number={auth_flow._quote(phone_number)}&code={form.get('captcha_code') or 0}",
        })

    auth_flow.set_password(user, password)
    await db.commit()
    return RedirectResponse(url=f"/auth/login?phoneNumber={phone_number}&message={auth_flow._quote('رمز عبور با موفقیت تغییر کرد')}", status_code=303)


# ── Reset by email link ──

@router.get("/auth/reset-password", response_class=HTMLResponse)
async def shop_reset_password(
    request: Request,
    token: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    if not token:
        return HTMLResponse("A code must be supplied for password reset.", status_code=400)
    user_id = auth_flow.decode_auth_token(token, "password_reset")
    user = await auth_flow.get_user_by_id(db, user_id) if user_id else None
    if user is None:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("shop/reset_password.html", {
        "request": request, "token": token, "email": user.email,
    })


@router.post("/auth/reset-password", response_class=HTMLResponse)
async def shop_reset_password_submit(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    token = form.get("code") or ""
    email = (form.get("email") or "").strip()
    new_password = form.get("new_password") or ""
    confirm_password = form.get("confirm_password") or ""

    user_id = auth_flow.decode_auth_token(token, "password_reset")
    user = await auth_flow.get_user_by_id(db, user_id) if user_id else None
    errors = {}
    if user is None or user.email.lower() != email.lower():
        errors["email"] = "ایمیل معتبر نیست"
    if new_password != confirm_password:
        errors["confirm"] = "رمز عبور و تکرار آن مطابقت ندارند"
    pw_err = _validate_password(new_password)
    if pw_err:
        errors["password"] = pw_err

    if errors:
        return templates.TemplateResponse("shop/reset_password.html", {
            "request": request, "token": token, "email": email,
            "email_error": errors.get("email"),
            "password_error": errors.get("password"),
            "confirm_error": errors.get("confirm"),
        })

    auth_flow.set_password(user, new_password)
    await db.commit()
    return RedirectResponse(url=f"/auth/reset-password-confirmation?phoneNumber={user.phone_number}", status_code=303)


@router.get("/auth/reset-password-confirmation", response_class=HTMLResponse)
async def shop_reset_password_confirmation(
    request: Request,
    phoneNumber: Optional[str] = None,
):
    return templates.TemplateResponse("shop/reset_password_confirmation.html", {
        "request": request, "phone_number": phoneNumber or "",
        "login_url": f"/auth/login?phoneNumber={auth_flow._quote(phoneNumber or '')}&message={auth_flow._quote('رمز عبور با موفقیت تغییر کرد')}",
    })


# ── Captcha refresh ──

@router.post("/auth/refresh-captcha", response_class=JSONResponse)
async def shop_refresh_captcha(request: Request, db: AsyncSession = Depends(get_db)):
    form = await request.form()
    cap_id = form.get("id")
    try:
        cap = await db.get(Captcha, uuid.UUID(cap_id))
    except (ValueError, TypeError):
        cap = None
    if cap is None:
        return JSONResponse({"success": False})
    await auth_flow._refresh_captcha(db, cap)
    await db.commit()
    return JSONResponse({"success": True, "url": cap.url})


# ── Logout ──

@router.get("/auth/logout", response_class=HTMLResponse)
async def shop_logout(request: Request):
    response = RedirectResponse(url="/home", status_code=303)
    response.delete_cookie("access_token")
    return response
