"""Pydantic schemas for cart and orders."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ── Cart ──

class CartItemCreate(BaseModel):
    product_id: UUID
    variety_id: Optional[UUID] = None
    quantity: int = Field(default=1, ge=1)


class CartItemUpdate(BaseModel):
    quantity: int = Field(..., ge=0)


class CartItemResponse(BaseModel):
    id: UUID
    product_id: UUID
    product_name: str = ""
    product_slug: str = ""
    product_image: Optional[str] = None
    variety_id: Optional[UUID] = None
    variety_value: Optional[str] = None
    quantity: int
    unit_price: Optional[float] = None
    price_after_discount: Optional[float] = None
    total_price: float = 0
    stock_quantity: int = 0

    model_config = {"from_attributes": True}


class CartResponse(BaseModel):
    items: list[CartItemResponse] = []
    total_items: int = 0
    total_price: float = 0
    total_discount: float = 0
    total_price_after_discount: float = 0


# ── Pay Method & Post Type ──

class PayMethodResponse(BaseModel):
    id: UUID
    name: Optional[str] = None
    enable: bool = True
    type: Optional[str] = None
    description: Optional[str] = None

    model_config = {"from_attributes": True}


class PostTypeResponse(BaseModel):
    id: UUID
    name: Optional[str] = None
    site: Optional[str] = None
    price: Optional[float] = None
    post_vat: Optional[float] = None
    post_vat_rate: Optional[float] = None
    image_url: Optional[str] = None
    description: Optional[str] = None

    model_config = {"from_attributes": True}


# ── Discount ──

class ApplyDiscountRequest(BaseModel):
    code: str = Field(..., min_length=1)


class DiscountResponse(BaseModel):
    id: UUID
    code: Optional[str] = None
    description: Optional[str] = None
    amount: Optional[float] = None
    percent: Optional[float] = None
    discount_target: Optional[str] = None
    is_valid: bool = True
    discount_value: float = 0

    model_config = {"from_attributes": True}


# ── Order ──

class OrderAddressInput(BaseModel):
    first_name: str = Field(..., max_length=100)
    last_name: str = Field(..., max_length=100)
    phone_number: str = Field(..., pattern=r"^09\d{9}$")
    telephone: Optional[str] = None
    address_description: str = Field(..., min_length=1)
    postal_code: str = Field(..., min_length=1)
    country: Optional[str] = "Iran"
    province: Optional[str] = None
    city: Optional[str] = None


class CreateOrderRequest(BaseModel):
    address: OrderAddressInput
    pay_method_id: UUID
    post_type_id: UUID
    notes: Optional[str] = None
    discount_code: Optional[str] = None


class OrderProductResponse(BaseModel):
    id: UUID
    product_id: UUID
    product_name: str = ""
    product_image: Optional[str] = None
    variety_id: Optional[UUID] = None
    variety_value: Optional[str] = None
    part_number: Optional[str] = None
    count: int
    unit_price: Optional[float] = None
    discount: Optional[float] = None
    price_after_discount: Optional[float] = None
    total_price: Optional[float] = None
    total_price_after_discount: Optional[float] = None
    vat_rate: Optional[float] = None

    model_config = {"from_attributes": True}


class OrderStatusRecordResponse(BaseModel):
    id: UUID
    status: Optional[str] = None
    comment: Optional[str] = None
    tracking_number: Optional[str] = None
    insert_date: Optional[datetime] = None

    model_config = {"from_attributes": True}


class OrderResponse(BaseModel):
    id: UUID
    reference_code: Optional[int] = None
    tracking_number: Optional[str] = None
    order_status: Optional[str] = None
    count: int = 0
    notes: Optional[str] = None
    date: Optional[datetime] = None
    email: Optional[str] = None

    total_price: Optional[float] = None
    total_discount_price: Optional[float] = None
    discount_price: Optional[float] = None
    total_price_after_discount: Optional[float] = None
    total_taxes_and_duties: Optional[float] = None
    payable: Optional[float] = None
    vat: Optional[float] = None
    postage_fee: Optional[float] = None
    post_vat: Optional[float] = None
    packaging_cost: Optional[float] = None
    packaging_vat: Optional[float] = None

    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None
    address_description: Optional[str] = None
    postal_code: Optional[str] = None
    province: Optional[str] = None
    city: Optional[str] = None

    user_id: Optional[UUID] = None
    pay_method_id: Optional[UUID] = None
    post_type_id: Optional[UUID] = None

    order_products: list[OrderProductResponse] = []
    order_status_records: list[OrderStatusRecordResponse] = []
    insert_date: Optional[datetime] = None

    model_config = {"from_attributes": True}


class OrderStatusUpdate(BaseModel):
    status: str
    comment: Optional[str] = None
    tracking_number: Optional[str] = None


class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    page_size: int
    total_pages: int