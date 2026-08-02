"""Cart & Order business logic.

Mirrors Order.cs, OrderProduct.cs, OrderStatusRecord.cs, Discount.cs from the .NET domain.
"""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.identity import User
from app.models.product import Product, Variety
from app.models.order import (
    OrderModel as Order,
    OrderProduct, OrderStatusRecord, Discount,
    PayMethod, PostType,
)
from app.schemas.order import (
    CartItemCreate, CartItemUpdate, CartItemResponse,
    CreateOrderRequest, OrderAddressInput, OrderStatusUpdate,
    ApplyDiscountRequest,
)


# ── Cart (session-based: stored in-memory per request, ephemeral for now) ──

class CartItem:
    def __init__(
        self,
        product_id: uuid.UUID,
        quantity: int = 1,
        variety_id: Optional[uuid.UUID] = None,
        variety_value: Optional[str] = None,
    ):
        self.id = uuid.uuid4()
        self.product_id = product_id
        self.variety_id = variety_id
        self.variety_value = variety_value
        self.quantity = quantity
        self.product_name = ""
        self.product_slug = ""
        self.product_image = None
        self.unit_price = 0.0
        self.price_after_discount = 0.0
        self.stock_quantity = 0

    @property
    def total_price(self) -> float:
        return (self.price_after_discount or self.unit_price or 0) * self.quantity


class Cart:
    def __init__(self):
        self.items: dict[str, CartItem] = {}

    def add_item(self, item: CartItemCreate) -> CartItem:
        key = f"{item.product_id}_{item.variety_id or ''}"
        if key in self.items:
            self.items[key].quantity += item.quantity
        else:
            self.items[key] = CartItem(
                product_id=item.product_id,
                quantity=item.quantity,
                variety_id=item.variety_id,
            )
        return self.items[key]

    def remove_item(self, key: str) -> bool:
        if key in self.items:
            del self.items[key]
            return True
        return False

    def update_quantity(self, key: str, quantity: int) -> Optional[CartItem]:
        if key in self.items:
            if quantity <= 0:
                del self.items[key]
                return None
            self.items[key].quantity = quantity
            return self.items[key]
        return None

    def clear(self):
        self.items.clear()

    @property
    def total_items(self) -> int:
        return sum(item.quantity for item in self.items.values())

    @property
    def total_price(self) -> float:
        return sum(item.total_price for item in self.items.values())

    def to_dict(self) -> dict:
        return {
            "items": [
                {
                    "id": str(item.id),
                    "product_id": str(item.product_id),
                    "product_name": item.product_name,
                    "product_slug": item.product_slug,
                    "product_image": item.product_image,
                    "variety_id": str(item.variety_id) if item.variety_id else None,
                    "variety_value": item.variety_value,
                    "quantity": item.quantity,
                    "unit_price": item.unit_price,
                    "price_after_discount": item.price_after_discount,
                    "total_price": item.total_price,
                    "stock_quantity": item.stock_quantity,
                }
                for item in self.items.values()
            ],
            "total_items": self.total_items,
            "total_price": self.total_price,
        }


# In-memory cart store (per user). In production, use Redis.
_carts: dict[str, Cart] = {}


def _get_cart_key(user_id: uuid.UUID) -> str:
    return str(user_id)


def get_cart(user_id: uuid.UUID) -> Cart:
    key = _get_cart_key(user_id)
    if key not in _carts:
        _carts[key] = Cart()
    return _carts[key]


def save_cart(user_id: uuid.UUID, cart: Cart):
    _carts[_get_cart_key(user_id)] = cart


async def enrich_cart_with_products(db: AsyncSession, cart: Cart):
    """Load product details for all cart items."""
    for item in cart.items.values():
        stmt = select(Product).where(Product.id == item.product_id, Product.is_removed == False)
        result = await db.execute(stmt)
        product = result.scalar_one_or_none()
        if product:
            item.product_name = product.name
            item.product_slug = product.slug or ""
            item.product_image = product.medium_image_url
            item.unit_price = float(product.price or 0)
            item.price_after_discount = float(product.price_after_discount or product.price or 0)
            item.stock_quantity = product.stock_quantity

            # If variety selected, get variety pricing
            if item.variety_id:
                v_stmt = select(Variety).where(Variety.id == item.variety_id)
                v_result = await db.execute(v_stmt)
                variety = v_result.scalar_one_or_none()
                if variety:
                    item.unit_price = float(variety.price or 0)
                    item.price_after_discount = float(variety.price_after_discount or variety.price or 0)
                    item.stock_quantity = variety.stock_quantity


# ── Pay Methods & Post Types ──

async def get_pay_methods(db: AsyncSession) -> list[PayMethod]:
    stmt = select(PayMethod).where(PayMethod.is_removed == False, PayMethod.enable == True)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_post_types(db: AsyncSession) -> list[PostType]:
    stmt = select(PostType).where(PostType.is_removed == False)
    result = await db.execute(stmt)
    return list(result.scalars().all())


# ── Discounts ──

async def validate_discount_code(db: AsyncSession, code: str, user_id: uuid.UUID, total_price: float) -> Optional[Discount]:
    now = datetime.now(timezone.utc)
    stmt = (
        select(Discount)
        .where(
            Discount.code == code,
            Discount.is_enable == True,
            Discount.is_removed == False,
            Discount.start_date <= now,
            Discount.end_date >= now,
        )
    )
    result = await db.execute(stmt)
    discount = result.scalar_one_or_none()
    if discount is None:
        return None
    if discount.minimum_purchase and total_price < float(discount.minimum_purchase):
        return None
    return discount


def calculate_discount_value(discount: Discount, total_price: float) -> float:
    if discount.discount_target == "Amount" or not discount.percent:
        return float(discount.amount or 0)
    # Percentage
    value = total_price * float(discount.percent) / 100
    if discount.max_percent_amount:
        value = min(value, float(discount.max_percent_amount))
    return value


# ── Orders ──

async def _generate_reference_code(db: AsyncSession) -> int:
    """Generate a unique sequential reference code matching .NET's logic."""
    stmt = select(func.max(Order.reference_code))
    result = await db.execute(stmt)
    max_code = result.scalar()
    return (max_code or 1000) + 1


async def create_order(
    db: AsyncSession,
    user: User,
    request: CreateOrderRequest,
    cart: Cart,
) -> Order:
    if not cart.items:
        raise ValueError("Cart is empty")

    await enrich_cart_with_products(db, cart)

    # Calculate totals
    subtotal = cart.total_price
    discount_value = 0.0
    applied_discount = None

    if request.discount_code:
        applied_discount = await validate_discount_code(db, request.discount_code, user.id, subtotal)
        if applied_discount:
            discount_value = calculate_discount_value(applied_discount, subtotal)

    total_after_discount = max(0, subtotal - discount_value)

    # Get pay method and post type
    pay_method = await db.get(PayMethod, request.pay_method_id)
    post_type = await db.get(PostType, request.post_type_id)

    postage_fee = float(post_type.price or 0) if post_type else 0
    post_vat_rate = float(post_type.post_vat_rate or 0) if post_type else 0
    post_vat = postage_fee * post_vat_rate / 100 if post_vat_rate else 0

    payable = total_after_discount + postage_fee + post_vat

    ref_code = await _generate_reference_code(db)

    order = Order(
        id=uuid.uuid4(),
        reference_code=ref_code,
        order_status="Ordering",
        count=cart.total_items,
        user_id=user.id,
        pay_method_id=request.pay_method_id,
        post_type_id=request.post_type_id,
        notes=request.notes,
        date=datetime.now(timezone.utc),
        email=user.email,

        total_price=subtotal,
        total_price_after_discount=total_after_discount,
        total_discount_price=discount_value,
        discount_price=discount_value,
        payable=payable,
        postage_fee=postage_fee,
        post_vat=post_vat,
        post_vat_rate=post_vat_rate,
        vat=0,

        first_name=request.address.first_name,
        last_name=request.address.last_name,
        phone_number=request.address.phone_number,
        telephone=request.address.telephone,
        address_description=request.address.address_description,
        postal_code=request.address.postal_code,
        country=request.address.country,
        province=request.address.province,
        city=request.address.city,

        insert_date=datetime.now(timezone.utc),
        update_date=datetime.now(timezone.utc),
    )
    db.add(order)
    await db.flush()

    # Create order products
    for cart_item in cart.items.values():
        unit_price = cart_item.price_after_discount or cart_item.unit_price
        total = unit_price * cart_item.quantity
        order_product = OrderProduct(
            id=uuid.uuid4(),
            order_id=order.id,
            product_id=cart_item.product_id,
            variety_id=cart_item.variety_id,
            count=cart_item.quantity,
            unit_price=unit_price,
            total_price=total,
            price_after_discount=unit_price,
            total_price_after_discount=total,
            variety_values=cart_item.variety_value,
            insert_date=datetime.now(timezone.utc),
            update_date=datetime.now(timezone.utc),
        )
        db.add(order_product)

    # Create initial status record
    status_record = OrderStatusRecord(
        id=uuid.uuid4(),
        order_id=order.id,
        status="Ordering",
        comment="سفارش ثبت شد",
        insert_date=datetime.now(timezone.utc),
        update_date=datetime.now(timezone.utc),
    )
    db.add(status_record)
    await db.flush()

    # Clear cart
    cart.clear()
    save_cart(user.id, cart)

    return order


async def update_order_status(
    db: AsyncSession,
    order: Order,
    request: OrderStatusUpdate,
) -> Order:
    order.order_status = request.status
    order.update_date = datetime.now(timezone.utc)

    if request.tracking_number:
        order.tracking_number = request.tracking_number

    status_record = OrderStatusRecord(
        id=uuid.uuid4(),
        order_id=order.id,
        status=request.status,
        comment=request.comment,
        tracking_number=request.tracking_number,
        insert_date=datetime.now(timezone.utc),
        update_date=datetime.now(timezone.utc),
    )
    db.add(status_record)
    await db.flush()
    return order


async def get_order_by_id(db: AsyncSession, order_id: uuid.UUID) -> Optional[Order]:
    stmt = (
        select(Order)
        .options(
            selectinload(Order.order_products),
            selectinload(Order.order_status_records).order_by(OrderStatusRecord.insert_date),
        )
        .where(Order.id == order_id, Order.is_removed == False)
    )
    result = await db.execute(stmt)
    return result.unique().scalar_one_or_none()


async def get_user_orders(
    db: AsyncSession, user_id: uuid.UUID, page: int = 1, page_size: int = 20
) -> tuple[list[Order], int]:
    count_stmt = select(func.count(Order.id)).where(
        Order.user_id == user_id, Order.is_removed == False
    )
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    stmt = (
        select(Order)
        .options(
            selectinload(Order.order_products),
            selectinload(Order.order_status_records),
        )
        .where(Order.user_id == user_id, Order.is_removed == False)
        .order_by(Order.insert_date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    orders = result.unique().scalars().all()
    return list(orders), total


async def get_all_orders(
    db: AsyncSession, page: int = 1, page_size: int = 20, status_filter: Optional[str] = None
) -> tuple[list[Order], int]:
    conditions = [Order.is_removed == False]
    if status_filter:
        conditions.append(Order.order_status == status_filter)

    count_stmt = select(func.count(Order.id)).where(*conditions)
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    stmt = (
        select(Order)
        .options(
            selectinload(Order.order_products),
            selectinload(Order.order_status_records),
            selectinload(Order.user),
        )
        .where(*conditions)
        .order_by(Order.insert_date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    orders = result.unique().scalars().all()
    return list(orders), total


def build_order_response(order: Order) -> dict:
    return {
        "id": order.id,
        "reference_code": order.reference_code,
        "tracking_number": order.tracking_number,
        "order_status": order.order_status,
        "count": order.count,
        "notes": order.notes,
        "date": order.date,
        "email": order.email,
        "total_price": float(order.total_price) if order.total_price else None,
        "total_discount_price": float(order.total_discount_price) if order.total_discount_price else None,
        "discount_price": float(order.discount_price) if order.discount_price else None,
        "total_price_after_discount": float(order.total_price_after_discount) if order.total_price_after_discount else None,
        "total_taxes_and_duties": float(order.total_taxes_and_duties) if order.total_taxes_and_duties else None,
        "payable": float(order.payable) if order.payable else None,
        "vat": float(order.vat) if order.vat else None,
        "postage_fee": float(order.postage_fee) if order.postage_fee else None,
        "post_vat": float(order.post_vat) if order.post_vat else None,
        "packaging_cost": float(order.packaging_cost) if order.packaging_cost else None,
        "packaging_vat": float(order.packaging_vat) if order.packaging_vat else None,
        "first_name": order.first_name,
        "last_name": order.last_name,
        "phone_number": order.phone_number,
        "address_description": order.address_description,
        "postal_code": order.postal_code,
        "province": order.province,
        "city": order.city,
        "user_id": order.user_id,
        "pay_method_id": order.pay_method_id,
        "post_type_id": order.post_type_id,
        "insert_date": order.insert_date,
        "order_products": [
            {
                "id": op.id,
                "product_id": op.product_id,
                "product_name": op.product.name if hasattr(op, 'product') and op.product else "",
                "product_image": op.product.medium_image_url if hasattr(op, 'product') and op.product else None,
                "variety_id": op.variety_id,
                "variety_value": op.variety_values,
                "part_number": op.product.part_number if hasattr(op, 'product') and op.product else None,
                "count": op.count,
                "unit_price": float(op.unit_price) if op.unit_price else None,
                "discount": float(op.discount) if op.discount else None,
                "price_after_discount": float(op.price_after_discount) if op.price_after_discount else None,
                "total_price": float(op.total_price) if op.total_price else None,
                "total_price_after_discount": float(op.total_price_after_discount) if op.total_price_after_discount else None,
                "vat_rate": float(op.vat_rate) if op.vat_rate else None,
            }
            for op in (order.order_products or [])
        ],
        "order_status_records": [
            {
                "id": sr.id,
                "status": sr.status,
                "comment": sr.comment,
                "tracking_number": sr.tracking_number,
                "insert_date": sr.insert_date,
            }
            for sr in (order.order_status_records or [])
        ],
    }