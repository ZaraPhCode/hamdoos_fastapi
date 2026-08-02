"""Payment API routes — initiate, callback, status."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.dependencies import get_current_active_user
from app.models.identity import User
from app.schemas.payment import (
    PaymentRequestCreate, PaymentRequestResponse, PaymentVerifyResponse, PaymentStatusResponse,
)
from app.services.payment_service import ZarinPalGateway

router = APIRouter(prefix="/payment", tags=["Payment"])


@router.post("/request", response_model=PaymentRequestResponse)
async def initiate_payment(
    request_data: PaymentRequestCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Initiate a ZarinPal payment for an order."""
    gateway = ZarinPalGateway()
    try:
        result = await gateway.payment_request(
            db=db,
            order_id=request_data.order_id,
            user_id=current_user.id,
            user_mobile=current_user.phone_number or "",
            user_email=current_user.email or "",
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Payment gateway error: {str(e)}")


@router.get("/callback", response_model=PaymentVerifyResponse)
async def payment_callback(
    Authority: str = Query(...),
    Status: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Handle ZarinPal payment callback."""
    # The payment_id is encoded in the callback URL path
    # We need to extract it from the referrer or from the Authority
    # For now, find the payment by authority
    from sqlalchemy import select
    from app.models.finance import PaymentRequest

    stmt = select(PaymentRequest).where(
        PaymentRequest.authority == Authority,
        PaymentRequest.is_removed == False,
    )
    result = await db.execute(stmt)
    payment = result.scalar_one_or_none()
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment request not found")

    gateway = ZarinPalGateway()
    try:
        verify_result = await gateway.verify_payment(db, payment.id, Authority, Status)
        return verify_result
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Verification error: {str(e)}")


@router.get("/callback/{payment_id}", response_model=PaymentVerifyResponse)
async def payment_callback_with_id(
    payment_id: str,
    Authority: str = Query(...),
    Status: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Handle ZarinPal payment callback with payment ID from URL."""
    try:
        pid = uuid.UUID(payment_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payment ID")

    gateway = ZarinPalGateway()
    try:
        verify_result = await gateway.verify_payment(db, pid, Authority, Status)
        return verify_result
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Verification error: {str(e)}")


@router.get("/status/{payment_id}", response_model=PaymentStatusResponse)
async def get_payment_status(
    payment_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Check payment status."""
    try:
        pid = uuid.UUID(payment_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid payment ID")

    gateway = ZarinPalGateway()
    payment = await gateway.get_payment_status(db, pid)
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")

    return PaymentStatusResponse(
        id=payment.id,
        order_id=payment.order_id,
        amount=float(payment.amount or 0),
        authority=payment.authority,
        ref_id=payment.ref_id,
        status=payment.status or "Unknown",
        is_paying=payment.is_paying,
        result_code=payment.result_code,
        card_pan=payment.card_pan,
        wage=payment.wage or 0,
        pay_date=payment.pay_date,
    )


@router.get("/order/{order_id}", response_model=list[PaymentRequestResponse])
async def get_order_payments(
    order_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all payment attempts for an order."""
    from sqlalchemy import select
    from app.models.finance import PaymentRequest

    try:
        oid = uuid.UUID(order_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid order ID")

    stmt = select(PaymentRequest).where(
        PaymentRequest.order_id == oid,
        PaymentRequest.is_removed == False,
    ).order_by(PaymentRequest.insert_date.desc())

    result = await db.execute(stmt)
    payments = result.scalars().all()

    return [
        PaymentRequestResponse(
            id=p.id,
            order_id=p.order_id,
            amount=float(p.amount or 0),
            authority=p.authority,
            ref_id=p.ref_id,
            status=p.status or "Unknown",
            is_paying=p.is_paying,
            message=p.message,
        )
        for p in payments
    ]