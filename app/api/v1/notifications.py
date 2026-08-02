"""Notification API routes — send SMS and email."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.dependencies import get_admin_user
from app.models.identity import User
from app.services.sms_service import SelectedSmsSender
from app.services.email_service import EmailSender

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.post("/sms/verify")
async def send_verification_sms(
    phone_number: str = Query(..., description="Phone number (09xxxxxxxxx)"),
    code: str = Query(..., min_length=4, max_length=10),
    full_name: str = Query(""),
    current_user: User = Depends(get_admin_user),
):
    """Send verification code via SMS (all configured providers)."""
    sms = SelectedSmsSender()
    success = await sms.send_verification_code(phone_number, code, full_name)
    if not success:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="SMS send failed")
    return {"message": "Verification SMS sent"}


@router.post("/sms/order")
async def send_order_sms(
    phone_number: str = Query(...),
    full_name: str = Query(""),
    reference_code: int = Query(...),
    price: float = Query(...),
    current_user: User = Depends(get_admin_user),
):
    """Send order notification via SMS."""
    sms = SelectedSmsSender()
    success = await sms.send_order_notification(phone_number, full_name, reference_code, price, datetime.utcnow())
    if not success:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="SMS send failed")
    return {"message": "Order SMS sent"}


@router.post("/sms/product-notify")
async def send_product_notify_sms(
    phone_number: str = Query(...),
    full_name: str = Query(""),
    product_name: str = Query(...),
    part_number: str = Query(""),
    current_user: User = Depends(get_admin_user),
):
    """Send product availability notification via SMS."""
    sms = SelectedSmsSender()
    success = await sms.send_notify_product(phone_number, full_name, product_name, part_number)
    if not success:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="SMS send failed")
    return {"message": "Product notification SMS sent"}


@router.post("/email/verify")
async def send_verification_email(
    to: str = Query(...),
    code: str = Query(..., min_length=4, max_length=10),
    full_name: str = Query(""),
    current_user: User = Depends(get_admin_user),
):
    """Send verification code via email."""
    email = EmailSender()
    success = await email.send_verification_code(to, code, full_name)
    if not success:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Email send failed")
    return {"message": "Verification email sent"}


@router.post("/email/order-confirmation")
async def send_order_confirmation_email(
    to: str = Query(...),
    full_name: str = Query(""),
    reference_code: int = Query(...),
    total_price: float = Query(...),
    current_user: User = Depends(get_admin_user),
):
    """Send order confirmation email."""
    email = EmailSender()
    success = await email.send_order_confirmation(to, full_name, reference_code, total_price, datetime.utcnow())
    if not success:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Email send failed")
    return {"message": "Order confirmation email sent"}


@router.post("/email/payment-confirmation")
async def send_payment_confirmation_email(
    to: str = Query(...),
    full_name: str = Query(""),
    reference_code: int = Query(...),
    ref_id: int = Query(...),
    amount: float = Query(...),
    current_user: User = Depends(get_admin_user),
):
    """Send payment confirmation email."""
    email = EmailSender()
    success = await email.send_payment_confirmation(to, full_name, reference_code, ref_id, amount)
    if not success:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Email send failed")
    return {"message": "Payment confirmation email sent"}