"""Cart API routes — add, remove, update, view cart, checkout."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.dependencies import get_current_active_user
from app.models.identity import User
from app.schemas.order import (
    CartItemCreate, CartItemUpdate, CartResponse,
    CreateOrderRequest, OrderResponse,
    PayMethodResponse, PostTypeResponse, ApplyDiscountRequest, DiscountResponse,
)
from app.services import order_service

router = APIRouter(prefix="/cart", tags=["Cart"])


@router.get("", response_model=CartResponse)
async def get_cart(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    cart = order_service.get_cart(current_user.id)
    await order_service.enrich_cart_with_products(db, cart)
    items = [
        {
            "id": item.id,
            "product_id": item.product_id,
            "product_name": item.product_name,
            "product_slug": item.product_slug,
            "product_image": item.product_image,
            "variety_id": item.variety_id,
            "variety_value": item.variety_value,
            "quantity": item.quantity,
            "unit_price": item.unit_price,
            "price_after_discount": item.price_after_discount,
            "total_price": item.total_price,
            "stock_quantity": item.stock_quantity,
        }
        for item in cart.items.values()
    ]
    return CartResponse(
        items=items,
        total_items=cart.total_items,
        total_price=cart.total_price,
    )


@router.post("/add", response_model=CartResponse)
async def add_to_cart(
    request: CartItemCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    cart = order_service.get_cart(current_user.id)
    cart.add_item(request)
    await order_service.enrich_cart_with_products(db, cart)
    order_service.save_cart(current_user.id, cart)
    return await _cart_to_response(cart, db)


@router.delete("/remove/{item_key}", response_model=CartResponse)
async def remove_from_cart(
    item_key: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    cart = order_service.get_cart(current_user.id)
    if not cart.remove_item(item_key):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found in cart")
    order_service.save_cart(current_user.id, cart)
    return await _cart_to_response(cart, db)


@router.put("/update/{item_key}", response_model=CartResponse)
async def update_cart_item(
    item_key: str,
    request: CartItemUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    cart = order_service.get_cart(current_user.id)
    item = cart.update_quantity(item_key, request.quantity)
    if item is None:
        # Item was removed (quantity <= 0)
        pass
    order_service.save_cart(current_user.id, cart)
    return await _cart_to_response(cart, db)


@router.post("/clear", response_model=CartResponse)
async def clear_cart(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    cart = order_service.get_cart(current_user.id)
    cart.clear()
    order_service.save_cart(current_user.id, cart)
    return await _cart_to_response(cart, db)


# ── Checkout / Order creation ──

@router.post("/checkout", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def checkout(
    request: CreateOrderRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    cart = order_service.get_cart(current_user.id)
    if not cart.items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cart is empty")

    try:
        order = await order_service.create_order(db, current_user, request, cart)
        await db.refresh(order)
        return order_service.build_order_response(await order_service.get_order_by_id(db, order.id))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ── Pay Methods & Post Types ──

@router.get("/pay-methods", response_model=list[PayMethodResponse])
async def get_pay_methods(db: AsyncSession = Depends(get_db)):
    methods = await order_service.get_pay_methods(db)
    return [
        PayMethodResponse(
            id=m.id, name=m.name, enable=m.enable,
            type=m.type, description=m.description,
        )
        for m in methods
    ]


@router.get("/post-types", response_model=list[PostTypeResponse])
async def get_post_types(db: AsyncSession = Depends(get_db)):
    types = await order_service.get_post_types(db)
    return [
        PostTypeResponse(
            id=t.id, name=t.name, site=t.site,
            price=float(t.price) if t.price else None,
            post_vat=float(t.post_vat) if t.post_vat else None,
            post_vat_rate=float(t.post_vat_rate) if t.post_vat_rate else None,
            image_url=t.image_url, description=t.description,
        )
        for t in types
    ]


# ── Discounts ──

@router.post("/validate-discount", response_model=DiscountResponse)
async def validate_discount(
    request: ApplyDiscountRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    cart = order_service.get_cart(current_user.id)
    total = cart.total_price
    discount = await order_service.validate_discount_code(db, request.code, current_user.id, total)
    if discount is None:
        return DiscountResponse(
            id=uuid.uuid4(), code=request.code, is_valid=False, discount_value=0
        )
    value = order_service.calculate_discount_value(discount, total)
    return DiscountResponse(
        id=discount.id, code=discount.code, description=discount.description,
        amount=float(discount.amount) if discount.amount else None,
        percent=float(discount.percent) if discount.percent else None,
        discount_target=discount.discount_target,
        is_valid=True, discount_value=value,
    )


async def _cart_to_response(cart, db) -> CartResponse:
    await order_service.enrich_cart_with_products(db, cart)
    items = [
        {
            "id": item.id,
            "product_id": item.product_id,
            "product_name": item.product_name,
            "product_slug": item.product_slug,
            "product_image": item.product_image,
            "variety_id": item.variety_id,
            "variety_value": item.variety_value,
            "quantity": item.quantity,
            "unit_price": item.unit_price,
            "price_after_discount": item.price_after_discount,
            "total_price": item.total_price,
            "stock_quantity": item.stock_quantity,
        }
        for item in cart.items.values()
    ]
    return CartResponse(
        items=items,
        total_items=cart.total_items,
        total_price=cart.total_price,
    )