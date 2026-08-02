"""ZarinPal payment gateway integration.

Mirrors ZarinPalGateway.cs from the .NET project:
- Request: POST /pg/v4/payment/request.json
- Verify: POST /pg/v4/payment/verify.json
- StartPay: https://zarinpal.com/pg/StartPay/{authority}
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.models.finance import PaymentRequest
from app.models.order import OrderModel as Order, OrderStatusRecord
from app.schemas.payment import PaymentRequestResponse, PaymentVerifyResponse


class ZarinPalGateway:
    REQUEST_URL = "https://api.zarinpal.com/pg/v4/payment/request.json"
    VERIFY_URL = "https://api.zarinpal.com/pg/v4/payment/verify.json"
    START_PAY_URL = "https://zarinpal.com/pg/StartPay/"

    def __init__(self):
        self.merchant_id = settings.ZARINPAL_MERCHANT_ID
        self.site_url = settings.ZARINPAL_SITE_URL
        self.callback_path = settings.ZARINPAL_CALLBACK_URL

    async def payment_request(
        self, db: AsyncSession, order_id: uuid.UUID, user_id: uuid.UUID, user_mobile: str, user_email: str
    ) -> PaymentRequestResponse:
        # Get the order
        stmt = select(Order).where(Order.id == order_id, Order.is_removed == False)
        result = await db.execute(stmt)
        order = result.scalar_one_or_none()
        if not order:
            raise ValueError("Order not found")
        if order.order_status not in ("Ordering", "AwaitingPayment"):
            raise ValueError(f"Cannot pay for order in status: {order.order_status}")

        amount = int(order.payable or 0)
        if amount <= 0:
            raise ValueError("Order amount must be greater than zero")

        description = f"سفارش شماره {order.reference_code or order_id}"
        callback_url = f"{self.site_url}{self.callback_path}"

        # Create payment request record
        payment = PaymentRequest(
            id=uuid.uuid4(),
            amount=float(amount),
            order_id=order_id,
            user_id=user_id,
            mobile=user_mobile,
            email=user_email,
            is_paying=True,
            status="Paying",
            insert_date=datetime.now(timezone.utc),
            update_date=datetime.now(timezone.utc),
        )
        db.add(payment)
        await db.flush()

        # Call ZarinPal API
        callback_url_with_id = f"{callback_url}{payment.id}"
        payload = {
            "merchant_id": self.merchant_id,
            "amount": amount,
            "description": description,
            "callback_url": callback_url_with_id,
            "metadata": {
                "mobile": user_mobile,
                "email": user_email,
            },
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.REQUEST_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            data = response.json()

        # Parse response
        errors = data.get("errors", {})
        if errors and errors.get("code"):
            payment.is_paying = False
            payment.status = "Canceled"
            payment.result_code = str(errors.get("code"))
            payment.message = errors.get("message", "Payment request failed")
            await db.flush()
            raise ValueError(f"ZarinPal error {errors.get('code')}: {errors.get('message', 'Unknown error')}")

        resp_data = data.get("data", {})
        authority = resp_data.get("authority", "")
        payment.authority = authority
        await db.flush()

        # Update order status to awaiting payment
        if order.order_status == "Ordering":
            order.order_status = "AwaitingPayment"
            order.update_date = datetime.now(timezone.utc)

        return PaymentRequestResponse(
            id=payment.id,
            order_id=order_id,
            amount=float(amount),
            authority=authority,
            status="Paying",
            is_paying=True,
            gateway_url=f"{self.START_PAY_URL}{authority}",
        )

    async def verify_payment(
        self, db: AsyncSession, payment_id: uuid.UUID, authority: str, status_str: str
    ) -> PaymentVerifyResponse:
        stmt = select(PaymentRequest).where(PaymentRequest.id == payment_id, PaymentRequest.is_removed == False)
        result = await db.execute(stmt)
        payment = result.scalar_one_or_none()
        if not payment:
            return PaymentVerifyResponse(success=False, message="Payment record not found")

        if status_str.lower() != "ok":
            payment.is_paying = False
            payment.status = "Canceled"
            payment.result_code = "CANCELED_BY_USER"
            await db.flush()

            # Update order status
            order = await db.get(Order, payment.order_id)
            if order:
                order.order_status = "Canceled"
                order.update_date = datetime.now(timezone.utc)
                status_record = OrderStatusRecord(
                    id=uuid.uuid4(),
                    order_id=order.id,
                    status="Canceled",
                    comment="پرداخت توسط کاربر لغو شد",
                    insert_date=datetime.now(timezone.utc),
                    update_date=datetime.now(timezone.utc),
                )
                db.add(status_record)

            return PaymentVerifyResponse(
                success=False, message="Payment was canceled by user", order_id=payment.order_id
            )

        # Verify with ZarinPal
        payload = {
            "merchant_id": self.merchant_id,
            "amount": int(payment.amount),
            "authority": authority,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.VERIFY_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            data = response.json()

        # Parse verification response
        resp_data = data.get("data", {})
        errors = data.get("errors", {})

        code = None
        if resp_data:
            code = resp_data.get("code")
        elif errors:
            code = errors.get("code")

        payment.result_code = str(code) if code else None
        payment.authority = authority

        order = await db.get(Order, payment.order_id)

        if code in (100, 101):
            # Success
            ref_id = resp_data.get("ref_id")
            payment.is_paying = False
            payment.status = "Success"
            payment.ref_id = int(ref_id) if ref_id else None
            payment.card_pan = resp_data.get("card_pan", "")
            payment.card_hash = resp_data.get("card_hash", "")
            payment.wage = int(resp_data.get("fee", 0))
            payment.wage_type = "Merchant" if resp_data.get("fee_type") == "Merchant" else "Unknown"
            payment.approval = datetime.now(timezone.utc)
            payment.pay_date = datetime.now(timezone.utc)

            # Update order status
            if order:
                order.order_status = "Paid"
                order.update_date = datetime.now(timezone.utc)
                status_record = OrderStatusRecord(
                    id=uuid.uuid4(),
                    order_id=order.id,
                    status="Paid",
                    comment=f"پرداخت موفق - کد پیگیری: {ref_id}",
                    insert_date=datetime.now(timezone.utc),
                    update_date=datetime.now(timezone.utc),
                )
                db.add(status_record)

            await db.flush()
            return PaymentVerifyResponse(
                success=True,
                ref_id=int(ref_id) if ref_id else None,
                card_pan=resp_data.get("card_pan", ""),
                message=f"Payment successful. Ref ID: {ref_id}",
                order_id=payment.order_id,
                order_status="Paid",
            )
        else:
            # Failed
            payment.is_paying = False
            payment.status = "Canceled"
            if order:
                order.order_status = "Canceled"
                order.update_date = datetime.now(timezone.utc)
                status_record = OrderStatusRecord(
                    id=uuid.uuid4(),
                    order_id=order.id,
                    status="Canceled",
                    comment=f"پرداخت ناموفق - کد خطا: {code}",
                    insert_date=datetime.now(timezone.utc),
                    update_date=datetime.now(timezone.utc),
                )
                db.add(status_record)

            await db.flush()
            return PaymentVerifyResponse(
                success=False,
                message=f"Payment verification failed. Code: {code}",
                order_id=payment.order_id,
                order_status="Canceled",
            )

    async def get_payment_status(self, db: AsyncSession, payment_id: uuid.UUID) -> Optional[PaymentRequest]:
        stmt = select(PaymentRequest).where(PaymentRequest.id == payment_id, PaymentRequest.is_removed == False)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()