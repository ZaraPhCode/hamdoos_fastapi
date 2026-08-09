"""Cookie-based cart service — matches .NET VMOrder cookie approach."""

from __future__ import annotations

import json
import uuid
from typing import Optional
from urllib.parse import quote, unquote

from fastapi import Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product import Product, Variety
from app.utils.persian_tools import normalize_image_url

CART_COOKIE_NAME = "Cart"
CART_COOKIE_MAX_AGE = 86400 * 30  # 30 days


class CartItem:
    def __init__(
        self,
        product_id: str,
        variety_id: str = "",
        quantity: int = 1,
        variety_values_str: str = "",
    ):
        self.id = str(uuid.uuid4())
        self.product_id = product_id
        self.variety_id = variety_id
        self.variety_values_str = variety_values_str
        self.quantity = quantity
        self.feature_image_url: Optional[str] = None
        self.image_description: Optional[str] = None
        self.name: str = ""
        self.part_number: str = ""
        self.price: float = 0
        self.price_after_discount: float = 0
        self.vat_rate: float = 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "product_id": self.product_id,
            "variety_id": self.variety_id,
            "variety_values_str": self.variety_values_str,
            "quantity": self.quantity,
            "feature_image_url": self.feature_image_url,
            "image_description": self.image_description,
            "name": self.name,
            "part_number": self.part_number,
            "price": self.price,
            "price_after_discount": self.price_after_discount,
            "vat_rate": self.vat_rate,
        }

    @classmethod
    def from_dict(cls, d: dict) -> CartItem:
        item = cls(
            product_id=d.get("product_id", ""),
            variety_id=d.get("variety_id", ""),
            quantity=d.get("quantity", 1),
            variety_values_str=d.get("variety_values_str", ""),
        )
        item.id = d.get("id", item.id)
        item.feature_image_url = d.get("feature_image_url")
        item.image_description = d.get("image_description")
        item.name = d.get("name", "")
        item.part_number = d.get("part_number", "")
        item.price = float(d.get("price", 0) or 0)
        item.price_after_discount = float(d.get("price_after_discount", 0) or 0)
        item.vat_rate = float(d.get("vat_rate", 0) or 0)
        return item


class Cart:
    """Matches .NET VMOrder."""

    def __init__(self):
        self.items: list[CartItem] = []
        self.total_price_after_discount: float = 0
        self.count: int = 0

    def to_dict(self) -> dict:
        return {
            "items": [i.to_dict() for i in self.items],
            "total_price_after_discount": self.total_price_after_discount,
            "count": self.count,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Cart:
        cart = cls()
        cart.items = [CartItem.from_dict(i) for i in d.get("items", [])]
        cart.total_price_after_discount = float(d.get("total_price_after_discount", 0) or 0)
        cart.count = int(d.get("count", 0) or 0)
        return cart

    def refresh(self):
        self.total_price_after_discount = sum(
            (it.price_after_discount or it.price or 0) * it.quantity
            for it in self.items
        )
        self.count = sum(it.quantity for it in self.items)

    def find_item(self, product_id: str, variety_id: str) -> Optional[CartItem]:
        for it in self.items:
            if it.product_id == product_id and it.variety_id == variety_id:
                return it
        return None

    def find_item_by_id(self, item_id: str) -> Optional[CartItem]:
        for it in self.items:
            if it.id == item_id:
                return it
        return None

    def remove_item(self, item_id: str) -> bool:
        before = len(self.items)
        self.items = [i for i in self.items if i.id != item_id]
        return len(self.items) < before

    def clear(self):
        self.items.clear()
        self.total_price_after_discount = 0
        self.count = 0


def parse_cart(request: Request) -> Cart:
    raw = request.cookies.get(CART_COOKIE_NAME)
    if not raw:
        return Cart()
    try:
        decoded = unquote(raw)
        data = json.loads(decoded)
        return Cart.from_dict(data)
    except (json.JSONDecodeError, TypeError):
        return Cart()


def save_cart_response(cart: Cart, response: Response):
    raw = json.dumps(cart.to_dict(), ensure_ascii=False)
    encoded = quote(raw, safe='')
    response.set_cookie(
        key=CART_COOKIE_NAME,
        value=encoded,
        max_age=CART_COOKIE_MAX_AGE,
        path="/",
        httponly=False,
        samesite="lax",
    )


async def enrich_cart(db: AsyncSession, cart: Cart):
    """Load product/variety details into each cart item."""
    for item in cart.items:
        try:
            pid = uuid.UUID(item.product_id)
        except ValueError:
            continue
        stmt = select(Product).where(Product.id == pid, Product.is_removed == False)
        result = await db.execute(stmt)
        product = result.scalar_one_or_none()
        if not product:
            continue
        item.name = product.name or ""
        item.part_number = product.part_number or ""
        item.feature_image_url = normalize_image_url(
            product.feature_image_url or product.medium_image_url or ""
        )
        item.image_description = product.image_description
        item.vat_rate = float(product.vat_rate or 0)

        if item.variety_id:
            try:
                vid = uuid.UUID(item.variety_id)
                v_stmt = select(Variety).where(Variety.id == vid)
                v_res = await db.execute(v_stmt)
                variety = v_res.scalar_one_or_none()
                if variety:
                    item.price = float(variety.price or 0)
                    item.price_after_discount = float(variety.price_after_discount or variety.price or 0)
                    if variety.feature_image_url:
                        item.feature_image_url = normalize_image_url(variety.feature_image_url)
                    continue
            except ValueError:
                pass
        item.price = float(product.price or 0)
        item.price_after_discount = float(product.price_after_discount or product.price or 0)

    cart.refresh()


def cart_context(cart: Cart) -> dict:
    """Return template context vars for cart header."""
    return {
        "cart_count": cart.count,
        "cart_total": "{:,.0f}".format(cart.total_price_after_discount or 0),
        "cart_items": [
            {
                "id": it.id,
                "product_id": it.product_id,
                "name": it.name,
                "part_number": it.part_number,
                "image_url": it.feature_image_url or "/static/ThemeLayout/img/placeholder.png",
                "regular_price": "{:,.0f}".format(it.price) if it.price and it.price != it.price_after_discount else None,
                "price": "{:,.0f}".format(it.price_after_discount or it.price or 0),
                "quantity": it.quantity,
                "variety_values_str": it.variety_values_str,
            }
            for it in cart.items
        ],
    }