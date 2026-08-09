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

from app.models.identity import User, IdentityInformation
from app.models.product import Product, Variety
from app.models.order import (
    OrderModel as Order,
    OrderProduct, OrderStatusRecord, Discount,
    PayMethod, PostType,
)
from app.models.common import Address, ProvinceCity
from app.models.finance import PaymentRequest, Receipt
from app.models.invoice import Invoice, InvoiceProduct
from app.utils.persian_tools import to_farsi, to_farsi_full, from_farsi_date

# ── Order status display names (matches .NET OrderStatus_t enum) ──

ORDER_STATUS_NAMES = {
    "Ordering": "در حال سفارش",
    "AwaitingPayment": "در انتظار پرداخت",
    "Paid": "پرداخت شده",
    "ConfirmedPayment": "تائید پرداخت",
    "Processing": "در حال پردازش",
    "Collecting": "در حال جمع‌آوری",
    "Packing": "در حال بسته‌بندی",
    "Sending": "در حال ارسال",
    "Posted": "ارسال شده",
    "Canceled": "لغو شده",
    "NeedsToBeChecked": "نیاز به بررسی",
    "NextOrder": "سفارش بعدی",
}

RECEIPT_STATUS_NAMES = {
    "AwaitingConfirmation": "در انتظار تائید",
    "Confirmed": "تائید شده",
    "Failed": "ناموفق",
}

PAYMENT_STATUS_NAMES = {
    "Success": "موفق",
    "Failed": "ناموفق",
    "Pending": "در انتظار",
    "Canceled": "لغو شده",
}
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
        pay_date=datetime.now(timezone.utc),
        email=user.email,

        total_price=subtotal,
        total_price_plus_taxes=0,
        total_taxes_and_duties=0,
        total_price_after_discount=total_after_discount,
        total_discount_price=discount_value,
        discount_price=discount_value,
        payable=payable,
        vat=0,
        packaging_cost=0,
        packaging_vat=0,
        packaging_vat_rate=0,
        postage_fee=postage_fee,
        post_vat=post_vat,
        post_vat_rate=post_vat_rate,

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
            discount=0,
            price_after_discount=unit_price,
            total_price_after_discount=total,
            vat_rate=0,
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


# ── OrderingStep (multi-step checkout, mirrors .NET OrderController.OrderingStep) ──

async def get_ordering_order_full(db: AsyncSession, user_id: uuid.UUID) -> Optional[Order]:
    """Load the user's most recent persistent 'Ordering'-status order with all checkout relations."""
    stmt = (
        select(Order)
        .options(
            selectinload(Order.order_products).selectinload(OrderProduct.product),
            selectinload(Order.order_products).selectinload(OrderProduct.variety),
            selectinload(Order.post_type),
            selectinload(Order.pay_method),
            selectinload(Order.identity_information),
        )
        .where(Order.user_id == user_id, Order.order_status == "Ordering", Order.is_removed == False)
        .order_by(Order.date.desc(), Order.insert_date.desc())
    )
    result = await db.execute(stmt)
    orders = result.unique().scalars().all()
    return orders[0] if orders else None


async def _set_order_products_from_cart(db: AsyncSession, order: Order, items) -> None:
    """Persist cookie-cart items as OrderProduct rows on the ordering order."""
    for item in items:
        try:
            pid = uuid.UUID(item.product_id)
        except (ValueError, AttributeError):
            continue
        vid = None
        if getattr(item, "variety_id", None):
            try:
                vid = uuid.UUID(item.variety_id)
            except ValueError:
                vid = None
        quantity = int(getattr(item, "quantity", 1) or 1)
        unit_price = float(getattr(item, "price_after_discount", None) or getattr(item, "price", 0) or 0)
        total = unit_price * quantity
        order.order_products.append(OrderProduct(
            id=uuid.uuid4(),
            order_id=order.id,
            product_id=pid,
            variety_id=vid,
            count=quantity,
            unit_price=unit_price,
            total_price=total,
            discount=0,
            price_after_discount=unit_price,
            total_price_after_discount=total,
            vat_rate=float(getattr(item, "vat_rate", 0) or 0),
            variety_values=getattr(item, "variety_values_str", None),
            insert_date=datetime.now(timezone.utc),
            update_date=datetime.now(timezone.utc),
        ))
    await db.flush()


async def _refresh_ordering_totals(db: AsyncSession, order: Order) -> None:
    """Recalculate order totals from products + selected post type (mirrors .NET Order.Refresh)."""
    total = sum(float(op.unit_price or 0) * op.count for op in order.order_products)
    total_after = sum(float(op.price_after_discount or 0) * op.count for op in order.order_products)
    order.count = sum(op.count for op in order.order_products)
    order.total_price = total
    order.total_price_after_discount = total_after
    post_type = None
    if order.post_type_id:
        post_type = await db.get(PostType, order.post_type_id)
    if post_type:
        order.postage_fee = float(post_type.price or 0)
        order.post_vat_rate = float(post_type.post_vat_rate or 0)
        order.post_vat = round(order.postage_fee * order.post_vat_rate / 100, 2)
    else:
        order.postage_fee = 0
        order.post_vat = 0
        order.post_vat_rate = 0
    order.payable = (
        float(order.total_price_after_discount or 0)
        + float(order.postage_fee or 0)
        + float(order.post_vat or 0)
    )
    await db.flush()


async def sync_ordering_order_from_cart(
    db: AsyncSession, user: User, cookie_cart
) -> tuple[Optional[Order], bool]:
    """Create or refresh the user's persistent 'Ordering' order from the cookie cart.

    Returns (order, consumed). ``consumed`` is True when the cookie cart items were
    moved into the order and the cookie cart should be cleared.
    """
    order = await get_ordering_order_full(db, user.id)
    items = getattr(cookie_cart, "items", None) or []
    if not items:
        return order, False

    # Consolidate any leftover 'Ordering' orders into a single one (legacy cleanup).
    stmt = (
        select(Order)
        .options(
            selectinload(Order.order_products).selectinload(OrderProduct.product),
            selectinload(Order.order_products).selectinload(OrderProduct.variety),
        )
        .where(Order.user_id == user.id, Order.order_status == "Ordering", Order.is_removed == False)
        .order_by(Order.date.desc(), Order.insert_date.desc())
    )
    existing = (await db.execute(stmt)).unique().scalars().all()
    order = existing[0] if existing else None
    for extra in existing[1:]:
        for op in list(extra.order_products or []):
            await db.delete(op)
        await db.delete(extra)
    if len(existing) > 1:
        await db.flush()

    if order:
        for op in list(order.order_products or []):
            await db.delete(op)
        await db.flush()
        order.order_products = []
    else:
        order = Order(
            id=uuid.uuid4(),
            reference_code=await _generate_reference_code(db),
            order_status="Ordering",
            user_id=user.id,
            email=user.email,
            count=0,
            total_price=0,
            total_price_plus_taxes=0,
            total_taxes_and_duties=0,
            total_price_after_discount=0,
            total_discount_price=0,
            discount_price=0,
            payable=0,
            vat=0,
            packaging_cost=0,
            packaging_vat=0,
            packaging_vat_rate=0,
            postage_fee=0,
            post_vat=0,
            post_vat_rate=0,
            date=datetime.now(timezone.utc),
            pay_date=datetime.now(timezone.utc),
            insert_date=datetime.now(timezone.utc),
            update_date=datetime.now(timezone.utc),
        )
        order.order_products = []
        db.add(order)
        await db.flush()

    await _set_order_products_from_cart(db, order, items)
    await _refresh_ordering_totals(db, order)
    await db.commit()
    return order, True


async def set_ordering_identity(db: AsyncSession, user: User, order: Order, identity_id: uuid.UUID) -> None:
    identity = await db.get(IdentityInformation, identity_id)
    if not identity or identity.user_id != user.id:
        raise ValueError("اطلاعات هویتی انتخاب شده معتبر نیست")
    order.identity_information_id = identity.id
    await db.flush()


async def set_ordering_address(db: AsyncSession, user: User, order: Order, address_id: uuid.UUID) -> None:
    address = await db.get(Address, address_id)
    if not address or address.user_id != user.id:
        raise ValueError("آدرس انتخاب شده معتبر نیست")
    order.address_id = address.id
    order.first_name = address.first_name
    order.last_name = address.last_name
    order.phone_number = address.phone_number
    order.telephone = address.telephone or ""
    order.address_description = address.address_description
    order.postal_code = address.postal_code
    order.country = address.country

    city = await db.get(ProvinceCity, address.province_city_id)
    order.city = city.name if city else ""
    province = None
    if address.province_id:
        stmt = select(ProvinceCity).where(
            ProvinceCity.int_id == address.province_id, ProvinceCity.province_id.is_(None)
        )
        province = (await db.execute(stmt)).scalar_one_or_none()
    order.province = province.name if province else (city.name if city else "")
    await db.flush()


async def set_ordering_post(db: AsyncSession, order: Order, post_type_id: uuid.UUID, note: Optional[str] = None) -> None:
    post_type = await db.get(PostType, post_type_id)
    if not post_type:
        raise ValueError("روش ارسال انتخاب شده معتبر نیست")
    order.post_type_id = post_type.id
    if note:
        order.notes = note
    await _refresh_ordering_totals(db, order)
    await db.flush()


async def pay_ordering_order(db: AsyncSession, order: Order, pay_method_id: uuid.UUID) -> Order:
    """Finalize the ordering order: set pay method and transition to AwaitingPayment."""
    pay_method = await db.get(PayMethod, pay_method_id)
    if not pay_method:
        raise ValueError("روش پرداخت انتخاب شده معتبر نیست")
    if not order.address_id or not order.post_type_id:
        raise ValueError("مراحل سفارش کامل نشده است")
    order.pay_method_id = pay_method.id
    order.pay_method_name = pay_method.name
    order.order_status = "AwaitingPayment"
    order.date = datetime.now(timezone.utc)
    order.pay_date = datetime.now(timezone.utc)
    db.add(OrderStatusRecord(
        id=uuid.uuid4(),
        order_id=order.id,
        status="AwaitingPayment",
        comment="ثبت سفارش",
        insert_date=datetime.now(timezone.utc),
        update_date=datetime.now(timezone.utc),
    ))
    await db.commit()
    return order


async def get_user_identities(db: AsyncSession, user_id: uuid.UUID) -> list[IdentityInformation]:
    stmt = select(IdentityInformation).where(
        IdentityInformation.user_id == user_id,
        IdentityInformation.is_removed == False,
        IdentityInformation.status.in_(["AwaitingConfirmation", "Confirmed"]),
    ).order_by(IdentityInformation.insert_date.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_user_addresses(db: AsyncSession, user_id: uuid.UUID) -> list[Address]:
    stmt = (
        select(Address)
        .options(selectinload(Address.province_city))
        .where(Address.user_id == user_id, Address.is_removed == False)
        .order_by(Address.insert_date.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


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
            selectinload(Order.order_products).selectinload(OrderProduct.product),
            selectinload(Order.order_status_records),
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
            selectinload(Order.order_products).selectinload(OrderProduct.product),
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
            selectinload(Order.order_products).selectinload(OrderProduct.product),
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
# -- Admin helpers (Orders section) --

async def get_admin_orders(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    part_number: Optional[str] = None,
    search: Optional[str] = None,
) -> tuple[list[Order], int]:
    conditions = [Order.is_removed == False]
    if status:
        conditions.append(Order.order_status == status)
    if part_number:
        sub = select(OrderProduct.order_id).join(Product, OrderProduct.product_id == Product.id).where(
            Product.part_number.ilike(f"%{part_number}%"), OrderProduct.is_removed == False
        )
        conditions.append(Order.id.in_(sub))
    if search:
        conditions.append(
            or_(
                Order.reference_code.cast(str).ilike(f"%{search}%"),
                Order.first_name.ilike(f"%{search}%"),
                Order.last_name.ilike(f"%{search}%"),
                Order.tracking_number.ilike(f"%{search}%"),
            )
        )

    count_stmt = select(func.count(Order.id)).where(*conditions)
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = (
        select(Order)
        .options(
            selectinload(Order.user),
            selectinload(Order.pay_method),
            selectinload(Order.post_type),
            selectinload(Order.order_products).selectinload(OrderProduct.product),
            selectinload(Order.order_status_records),
        )
        .where(*conditions)
        .order_by(Order.insert_date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    return list(result.unique().scalars().all()), total


async def get_admin_order_detail(db: AsyncSession, order_id: uuid.UUID) -> Optional[Order]:
    stmt = (
        select(Order)
        .options(
            selectinload(Order.user),
            selectinload(Order.pay_method),
            selectinload(Order.post_type),
            selectinload(Order.identity_information),
            selectinload(Order.order_products).selectinload(OrderProduct.product),
            selectinload(Order.order_products).selectinload(OrderProduct.variety),
            selectinload(Order.order_status_records),
            selectinload(Order.payment_requests),
            selectinload(Order.receipts),
        )
        .where(Order.id == order_id, Order.is_removed == False)
    )
    result = await db.execute(stmt)
    return result.unique().scalar_one_or_none()


def build_admin_order_response(order: Order, has_invoice: bool = False) -> dict:
    """Build the dict used by admin order list/detail templates."""
    return {
        "id": str(order.id),
        "reference_code": order.reference_code,
        "tracking_number": order.tracking_number,
        "order_status": order.order_status,
        "order_status_name": ORDER_STATUS_NAMES.get(order.order_status, order.order_status or "-"),
        "count": order.count,
        "notes": order.notes,
        "weight": order.weight,
        "postage_date": order.postage_date,
        "postage_date_str": to_farsi(order.postage_date) if order.postage_date else "",
        "date": order.date,
        "date_str": to_farsi(order.date) if order.date else "",
        "paper_invoice": order.paper_invoice,
        "email": order.email,
        "total_price": float(order.total_price or 0),
        "total_price_plus_taxes": float(order.total_price_plus_taxes or 0),
        "total_taxes_and_duties": float(order.total_taxes_and_duties or 0),
        "total_discount_price": float(order.total_discount_price or 0),
        "discount_price": float(order.discount_price or 0),
        "total_price_after_discount": float(order.total_price_after_discount or 0),
        "payable": float(order.payable or 0),
        "vat": float(order.vat or 0),
        "packaging_cost": float(order.packaging_cost or 0),
        "packaging_vat": float(order.packaging_vat or 0),
        "packaging_vat_rate": float(order.packaging_vat_rate or 0),
        "postage_fee": float(order.postage_fee or 0),
        "post_vat": float(order.post_vat or 0),
        "post_vat_rate": float(order.post_vat_rate or 0),
        "first_name": order.first_name,
        "last_name": order.last_name,
        "full_name": f"{order.first_name or ''} {order.last_name or ''}".strip(),
        "phone_number": order.phone_number,
        "telephone": order.telephone,
        "address_description": order.address_description,
        "postal_code": order.postal_code,
        "province": order.province,
        "city": order.city,
        "alias": order.alias,
        "country": order.country,
        "user_id": str(order.user_id) if order.user_id else None,
        "user_full_name": order.user.full_name if order.user else "",
        "pay_method_id": str(order.pay_method_id) if order.pay_method_id else None,
        "pay_method_name": order.pay_method.name if order.pay_method else "",
        "post_type_id": str(order.post_type_id) if order.post_type_id else None,
        "post_type_name": order.post_type.name if order.post_type else "",
        "identity_information_id": str(order.identity_information_id) if order.identity_information_id else None,
        "identity_information_name": order.identity_information.name if order.identity_information else "",
        "insert_date": order.insert_date,
        "insert_date_str": to_farsi_full(order.insert_date) if order.insert_date else "",
        "has_invoice": has_invoice,
        "order_products": [
            {
                "id": str(op.id),
                "product_id": str(op.product_id) if op.product_id else None,
                "variety_id": str(op.variety_id) if op.variety_id else None,
                "part_number": op.product.part_number if op.product else (op.variety.part_number if op.variety else ""),
                "product_name": op.product.name if op.product else "",
                "count": op.count,
                "unit_price": float(op.unit_price or 0),
                "discount": float(op.discount or 0),
                "price_after_discount": float(op.price_after_discount or 0),
                "total_price": float(op.total_price or 0),
                "total_price_after_discount": float(op.total_price_after_discount or 0),
                "vat_rate": float(op.vat_rate or 0),
                "variety_values": op.variety_values,
            }
            for op in (order.order_products or [])
        ],
        "payment_requests": [
            {
                "id": str(pr.id),
                "pay_date": pr.pay_date,
                "pay_date_str": to_farsi_full(pr.pay_date) if pr.pay_date else "",
                "approval": pr.approval,
                "approval_str": to_farsi_full(pr.approval) if pr.approval else "",
                "amount": float(pr.amount or 0),
                "status": pr.status,
                "status_name": PAYMENT_STATUS_NAMES.get(pr.status, pr.status or "-"),
                "is_pay": pr.is_pay,
                "ref_id": pr.ref_id,
                "authority": pr.authority,
            }
            for pr in (order.payment_requests or [])
        ],
"receipts": [
            {
                "id": str(r.id),
                "reference_code": r.reference_code,
                "price": float(r.price or 0),
                "status": r.status,
                "status_name": RECEIPT_STATUS_NAMES.get(r.status, r.status or "-"),
                "description": r.description,
                "deposit_date": r.deposit_date,
                "deposit_date_str": to_farsi(r.deposit_date) if r.deposit_date else "",
                "destination_bank": r.destination_bank,
                "image_url": r.image_url,
            }
            for r in (order.receipts or [])
        ],
"order_status_records": [
            {
                "id": str(sr.id),
                "status": sr.status,
                "status_name": ORDER_STATUS_NAMES.get(sr.status, sr.status or "-"),
                "comment": sr.comment,
                "tracking_number": sr.tracking_number,
                "insert_date": sr.insert_date,
                "insert_date_str": to_farsi_full(sr.insert_date) if sr.insert_date else "",
                "created_by_user_id": str(sr.created_by_user_id) if sr.created_by_user_id else None,
            }
            for sr in (order.order_status_records or [])
        ],
    }


def order_product_detail(op: OrderProduct) -> dict:
    return {
        "id": str(op.id),
        "order_id": str(op.order_id),
        "product_id": str(op.product_id) if op.product_id else None,
        "variety_id": str(op.variety_id) if op.variety_id else None,
        "part_number": op.product.part_number if op.product else "",
        "product_name": op.product.name if op.product else "",
        "count": op.count,
        "unit_price": float(op.unit_price or 0),
        "discount": float(op.discount or 0),
        "price_after_discount": float(op.price_after_discount or 0),
        "total_price": float(op.total_price or 0),
        "total_price_after_discount": float(op.total_price_after_discount or 0),
        "vat_rate": float(op.vat_rate or 0),
        "variety_values": op.variety_values,
        "product_unit": op.product_unit,
    }


def product_picker_data(products: list[Product]) -> list[dict]:
    """JS-friendly structure for the order product picker (product -> varieties)."""
    return [
        {
            "id": str(p.id),
            "name": p.name or "",
            "part_number": p.part_number or "",
            "varieties": [
                {"id": str(v.id), "part_number": v.part_number or "", "price": float(v.price or 0)}
                for v in (p.varieties or [])
            ],
        }
        for p in products
    ]


async def build_proforma_invoice(db: AsyncSession, order: Order) -> dict:
    """Build a proforma invoice dict from an Order (mirrors .NET OrderController.ProformaInvoice)."""
    identity = order.identity_information
    invoice_products = []
    for op in (order.order_products or []):
        product = op.product
        unit_price = float(op.unit_price or 0)
        count = op.count or 1
        vat_rate = float(op.vat_rate or 0)
        taxes = round(unit_price * vat_rate / 100, 2)
        total = unit_price * count + taxes
        invoice_products.append({
            "part_number": product.part_number if product else "",
            "name": product.name if product else "",
            "product_unit": op.product_unit or (product.product_unit.name if product and product.product_unit else "عدد"),
            "count": count,
            "unit_price": unit_price,
            "vat_rate": vat_rate,
            "taxes_and_duties": taxes,
            "total_amount_plus_taxes": total,
        })
    # Reorder: skip 2 then append them (mirrors .NET template)
    ordered = invoice_products[2:] + invoice_products[:2]
    total_taxes = sum(p["taxes_and_duties"] for p in invoice_products)
    total_plus = sum(p["total_amount_plus_taxes"] for p in invoice_products)
    return {
        "order_reference_code": order.reference_code,
        "type": "پیش فاکتور",
        "date": order.date,
        "first_name": order.first_name or "",
        "last_name": order.last_name or "",
        "economic_code": identity.economic_code if identity else "",
        "national_code_or_id": identity.national_code_or_id if identity else "",
        "telephone": order.telephone or "",
        "postal_code": order.postal_code or "",
        "province": order.province or "",
        "identity_city": order.city or "",
        "identity_address": order.address_description or "",
        "total_taxes_and_duties": round(total_taxes, 2),
        "total_price_plus_taxes": round(total_plus, 2),
        "description": order.notes or "",
        "invoice_products": ordered,
    }
