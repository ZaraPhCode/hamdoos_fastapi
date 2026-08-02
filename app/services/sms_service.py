"""Multi-provider SMS service.

Mirrors ASHA.Shop.Presentation/Tools/SmsSender.cs:
- FarazSMS (pattern-based)
- Melipayamak (base service number)
- Bale (OTP bot)
"""

from __future__ import annotations

import asyncio
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Optional

import httpx
from loguru import logger

from app.config.settings import settings


class SmsPattern(str, Enum):
    VERIFICATION_CODE = "VerificationCode"
    PRODUCT_NOTIFICATION = "ProductNotification"
    ORDER_NOTIFICATION = "OrderNotification"


class SmsSender(ABC):
    @abstractmethod
    async def send_verification_code(self, phone_number: str, code: str, full_name: str = "") -> bool:
        ...

    @abstractmethod
    async def send_notify_product(self, phone_number: str, full_name: str, product_name: str, part_number: str) -> bool:
        ...

    @abstractmethod
    async def send_order_notification(
        self, phone_number: str, full_name: str, reference_code: int, price: float, date: datetime
    ) -> bool:
        ...


class FarazSmsSender(SmsSender):
    def __init__(self):
        self.endpoint = settings.FARAZSMS_ENDPOINT
        self.username = settings.FARAZSMS_USERNAME
        self.password = settings.FARAZSMS_PASSWORD
        self.from_number = settings.FARAZSMS_FROM_NUMBER
        self.patterns = {
            SmsPattern.VERIFICATION_CODE: settings.FARAZSMS_PATTERN_VERIFICATION,
            SmsPattern.PRODUCT_NOTIFICATION: settings.FARAZSMS_PATTERN_PRODUCT,
            SmsPattern.ORDER_NOTIFICATION: settings.FARAZSMS_PATTERN_ORDER,
        }

    def _shorten(self, value: str, length: int = 40) -> str:
        return value[:length] if len(value) > length else value

    async def _send_pattern(self, phone_number: str, pattern: SmsPattern, input_data: dict) -> bool:
        pattern_code = self.patterns.get(pattern)
        if not pattern_code:
            logger.warning(f"No FarazSMS pattern code for {pattern}")
            return False

        payload = {
            "op": "pattern",
            "user": self.username,
            "pass": self.password,
            "fromNum": self.from_number,
            "toNum": phone_number,
            "patternCode": pattern_code,
            "inputData": [input_data],
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(self.endpoint, json=payload)
                response.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"FarazSMS error: {e}")
            return False

    async def send_verification_code(self, phone_number: str, code: str, full_name: str = "") -> bool:
        return await self._send_pattern(
            phone_number, SmsPattern.VERIFICATION_CODE,
            {"verification-code": code},
        )

    async def send_notify_product(self, phone_number: str, full_name: str, product_name: str, part_number: str) -> bool:
        return await self._send_pattern(
            phone_number, SmsPattern.PRODUCT_NOTIFICATION,
            {"name": self._shorten(full_name), "pname": self._shorten(product_name), "partNumber": self._shorten(part_number)},
        )

    async def send_order_notification(
        self, phone_number: str, full_name: str, reference_code: int, price: float, date: datetime
    ) -> bool:
        return await self._send_pattern(
            phone_number, SmsPattern.ORDER_NOTIFICATION,
            {
                "name": full_name,
                "date": date.strftime("%Y/%m/%d"),
                "hour": date.strftime("%H:%M"),
                "order": str(reference_code),
                "price": f"{price:,.0f}",
            },
        )


class MelipayamakSmsSender(SmsSender):
    def __init__(self):
        self.endpoint = settings.MELIPAYAMAK_ENDPOINT
        self.username = settings.MELIPAYAMAK_USERNAME
        self.password = settings.MELIPAYAMAK_PASSWORD
        self.from_number = settings.MELIPAYAMAK_FROM_NUMBER
        self.patterns = {
            SmsPattern.VERIFICATION_CODE: settings.MELIPAYAMAK_PATTERN_VERIFICATION,
            SmsPattern.PRODUCT_NOTIFICATION: settings.MELIPAYAMAK_PATTERN_PRODUCT,
            SmsPattern.ORDER_NOTIFICATION: settings.MELIPAYAMAK_PATTERN_ORDER,
        }

    def _shorten(self, value: str, length: int = 40) -> str:
        return value[:length] if len(value) > length else value

    async def _send_base_number(self, phone_number: str, pattern: SmsPattern, *values: str) -> bool:
        pattern_code = self.patterns.get(pattern)
        if not pattern_code:
            logger.warning(f"No Melipayamak pattern code for {pattern}")
            return False

        data = {
            "username": self.username,
            "password": self.password,
            "text": ";".join(values),
            "to": phone_number,
            "bodyId": pattern_code,
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(self.endpoint + "BaseServiceNumber", data=data)
                response.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"Melipayamak error: {e}")
            return False

    async def send_verification_code(self, phone_number: str, code: str, full_name: str = "") -> bool:
        return await self._send_base_number(phone_number, SmsPattern.VERIFICATION_CODE, full_name, code)

    async def send_notify_product(self, phone_number: str, full_name: str, product_name: str, part_number: str) -> bool:
        return await self._send_base_number(
            phone_number, SmsPattern.PRODUCT_NOTIFICATION,
            self._shorten(full_name), self._shorten(product_name), self._shorten(part_number),
        )

    async def send_order_notification(
        self, phone_number: str, full_name: str, reference_code: int, price: float, date: datetime
    ) -> bool:
        return await self._send_base_number(
            phone_number, SmsPattern.ORDER_NOTIFICATION,
            full_name, date.strftime("%Y/%m/%d"), date.strftime("%H:%M"),
            str(reference_code), f"{price:,.0f}",
        )


class BaleSmsSender(SmsSender):
    def __init__(self):
        self.endpoint = settings.BALE_ENDPOINT.rstrip("/")
        self.access_key = settings.BALE_ACCESS_KEY
        self.bot_id = settings.BALE_BOT_ID

    def _normalize_phone(self, phone: str) -> str:
        if phone.startswith("09"):
            return "98" + phone[1:]
        if phone.startswith("+"):
            return phone[1:]
        return phone

    async def _send_otp(self, phone_number: str, code: str) -> bool:
        payload = {
            "request_id": str(uuid.uuid4()),
            "bot_id": self.bot_id,
            "phone_number": self._normalize_phone(phone_number),
            "message_data": {
                "otp_message": {"otp": code},
            },
        }
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.endpoint}/api/v3/send_message",
                    json=payload,
                    headers={"api-access-key": self.access_key},
                )
                response.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"Bale SMS error: {e}")
            return False

    async def send_verification_code(self, phone_number: str, code: str, full_name: str = "") -> bool:
        return await self._send_otp(phone_number, code)

    async def send_notify_product(self, phone_number: str, full_name: str, product_name: str, part_number: str) -> bool:
        return True

    async def send_order_notification(
        self, phone_number: str, full_name: str, reference_code: int, price: float, date: datetime
    ) -> bool:
        return True


class SelectedSmsSender(SmsSender):
    """Delegates to the configured provider. Mirrors SelectedSmsSender from .NET."""

    def __init__(self):
        provider = settings.SMS_PROVIDER.lower()
        self._primary: SmsSender
        if provider == "farazsms":
            self._primary = FarazSmsSender()
        else:
            self._primary = MelipayamakSmsSender()
        self._bale = BaleSmsSender()

    async def send_verification_code(self, phone_number: str, code: str, full_name: str = "") -> bool:
        results = await asyncio.gather(
            self._primary.send_verification_code(phone_number, code, full_name),
            self._bale.send_verification_code(phone_number, code, full_name),
        )
        return any(results)

    async def send_notify_product(self, phone_number: str, full_name: str, product_name: str, part_number: str) -> bool:
        return await self._primary.send_notify_product(phone_number, full_name, product_name, part_number)

    async def send_order_notification(
        self, phone_number: str, full_name: str, reference_code: int, price: float, date: datetime
    ) -> bool:
        return await self._primary.send_order_notification(phone_number, full_name, reference_code, price, date)