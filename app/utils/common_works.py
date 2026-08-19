"""Comprehensive shared utilities — mirrors 0_Framework/Application/ from .NET."""

from __future__ import annotations

import re
import uuid
from typing import Any, Optional
from dataclasses import dataclass, field
from datetime import datetime


# ── GenerateSlug (mirrors GenerateSlug.cs) ──

def generate_slug(text: str, max_length: int = 200) -> str:
    """Generate a URL-safe slug from Persian/English text."""
    if not text:
        return ""
    text = text.strip().lower()
    text = re.sub(r"[^\w\s\-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    text = text[:max_length].strip("-")
    return text


# ── TableResult (mirrors TableResult.cs) ──

@dataclass
class TableResult:
    """Paginated table result wrapper."""
    data: list[Any] = field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20
    draw: Optional[int] = None

    @property
    def total_pages(self) -> int:
        return max(1, (self.total + self.page_size - 1) // self.page_size)

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    def to_dict(self) -> dict:
        return {
            "data": self.data,
            "recordsTotal": self.total,
            "recordsFiltered": self.total,
            "draw": self.draw,
            "page": self.page,
            "page_size": self.page_size,
            "total_pages": self.total_pages,
        }


# ── OrderProductResponse (mirrors OrderProductResponse.cs) ──

@dataclass
class OrderProductResponse:
    product_id: uuid.UUID
    product_name: str = ""
    part_number: str = ""
    quantity: int = 1
    unit_price: float = 0.0
    total_price: float = 0.0
    discount: float = 0.0
    price_after_discount: float = 0.0
    variety_id: Optional[uuid.UUID] = None
    variety_value: str = ""
    image_url: str = ""


# ── FavoriteProductListResponse (mirrors FavoriteProductListResponse.cs) ──

@dataclass
class FavoriteProductListResponse:
    list_id: uuid.UUID
    list_name: str = ""
    product_count: int = 0
    token: str = ""
    is_default: bool = False
    products: list[dict] = field(default_factory=list)


# ── CommonWorks (mirrors CommonWorks.cs) ──

class CommonWorks:
    """Shared workspace utilities."""

    @staticmethod
    def truncate(text: str, max_length: int = 100) -> str:
        if len(text) <= max_length:
            return text
        return text[:max_length - 3] + "..."

    @staticmethod
    def extract_numbers(text: str) -> str:
        return re.sub(r"[^0-9]", "", text)

    @staticmethod
    def is_valid_national_code(code: str) -> bool:
        """Validate Iranian national code (melli code)."""
        if not re.match(r"^\d{10}$", code):
            return False
        checksum = sum(int(code[i]) * (10 - i) for i in range(9))
        remainder = checksum % 11
        control = int(code[9])
        return (remainder < 2 and control == remainder) or (remainder >= 2 and control == 11 - remainder)

    @staticmethod
    def is_valid_sheba(sheba: str) -> bool:
        """Validate Iranian Sheba (IBAN) number."""
        sheba = sheba.replace(" ", "").upper()
        if not sheba.startswith("IR") or len(sheba) != 26:
            return False
        return True

    @staticmethod
    def mask_card_number(card: str) -> str:
        """Mask credit card number: 1234-****-****-5678."""
        if len(card) >= 12:
            return card[:4] + "-****-****-" + card[-4:]
        return card

    @staticmethod
    def normalize_phone(phone: str) -> str:
        phone = re.sub(r"[^0-9]", "", phone)
        if phone.startswith("98") and len(phone) == 12:
            return "0" + phone[2:]
        if phone.startswith("+98"):
            return "0" + phone[3:]
        if phone.startswith("0098"):
            return "0" + phone[4:]
        return phone


# ── SessionExtensions (mirrors SessionExtensions.cs) ──

class SessionExtensions:
    """Session helper methods for cart, temp data, etc."""

    @staticmethod
    def get_cart_key(user_id: uuid.UUID) -> str:
        return f"cart_{user_id}"

    @staticmethod
    def get_temp_data_key(user_id: uuid.UUID) -> str:
        return f"temp_{user_id}"

    @staticmethod
    def serialize_cart(items: list[dict]) -> str:
        import json
        return json.dumps(items, default=str)

    @staticmethod
    def deserialize_cart(data: str) -> list[dict]:
        import json
        if not data:
            return []
        return json.loads(data)


# ── CookiesManager (mirrors CookiesManager.cs) ──

class CookiesManager:
    """Cookie management utilities."""

    @staticmethod
    def set_cookie(
        response,
        key: str,
        value: str,
        max_age: int = 3600,
        http_only: bool = True,
        secure: bool = False,
        path: str = "/",
    ):
        response.set_cookie(
            key=key,
            value=value,
            max_age=max_age,
            expires=max_age,
            path=path,
            httponly=http_only,
            secure=secure,
            samesite="lax",
        )

    @staticmethod
    def delete_cookie(response, key: str, path: str = "/"):
        response.delete_cookie(key=key, path=path)


# ── Captcha (mirrors CaptchaExtention.cs) ──

import random
import string
from io import BytesIO


class CaptchaGenerator:
    """Simple CAPTCHA code generator (no image rendering)."""

    @staticmethod
    def generate_code(length: int = 6) -> str:
        return "".join(random.choices(string.digits, k=length))

    @staticmethod
    def validate_code(input_code: str, expected_code: str) -> bool:
        if not input_code or not expected_code:
            return False
        return input_code.strip().lower() == expected_code.strip().lower()


# ── TimedHostedService (mirrors TimedHostedService.cs) ──

import asyncio
from loguru import logger


class TimedHostedService:
    """Background task scheduler — runs periodic jobs."""

    def __init__(self, interval_seconds: int = 3600, handler=None):
        self.interval = interval_seconds
        self._handler = handler
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        logger.info(f"TimedHostedService started (interval={self.interval}s)")
        self._task = asyncio.create_task(self._run())

    async def stop(self):
        if self._task:
            self._task.cancel()
            logger.info("TimedHostedService stopped")

    async def _run(self):
        while True:
            try:
                if self._handler:
                    await self._handler()
                else:
                    await self._execute()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"TimedHostedService error: {e}")
            await asyncio.sleep(self.interval)

    async def _execute(self):
        """Override this in subclasses for custom periodic tasks."""
        pass


# ── InvoiceProductHelper (mirrors InvoiceProductHelper.cs) ──

class InvoiceProductHelper:
    """Helper for invoice product calculations."""

    @staticmethod
    def calculate_total_price(unit_price: float, quantity: int, discount: float = 0) -> float:
        return unit_price * quantity - discount

    @staticmethod
    def calculate_vat(amount: float, vat_rate: float) -> float:
        return amount * vat_rate / 100

    @staticmethod
    def calculate_final_price(
        unit_price: float,
        quantity: int,
        discount: float,
        vat_rate: float,
    ) -> dict:
        subtotal = unit_price * quantity
        total_discount = discount * quantity
        after_discount = subtotal - total_discount
        vat = after_discount * vat_rate / 100
        final = after_discount + vat
        return {
            "subtotal": subtotal,
            "total_discount": total_discount,
            "after_discount": after_discount,
            "vat": vat,
            "final": final,
        }


# ── SmsExtention (mirrors SmsExtention.cs) ──

class SmsExtention:
    """SMS helper methods."""

    @staticmethod
    def normalize_phone(phone: str) -> str:
        phone = re.sub(r"[^0-9]", "", phone)
        if phone.startswith("0"):
            return "98" + phone[1:]
        if phone.startswith("98") and len(phone) == 12:
            return phone
        return phone

    @staticmethod
    def mask_phone(phone: str) -> str:
        if len(phone) >= 7:
            return phone[:4] + "***" + phone[-3:]
        return phone