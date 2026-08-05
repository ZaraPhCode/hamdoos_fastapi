"""Pydantic schemas for products, categories, brands, varieties, and features."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ── Category ──

class CategoryBase(BaseModel):
    title: Optional[str] = None
    en_title: Optional[str] = None
    description: Optional[str] = None
    slug: Optional[str] = None
    keywords: Optional[str] = None
    meta_description: Optional[str] = None
    is_disable: bool = False
    priority: int = 0
    poster_image_url: Optional[str] = None
    place: Optional[str] = None
    no_display: bool = False


class CategoryCreate(CategoryBase):
    parent_category_id: Optional[UUID] = None


class CategoryUpdate(CategoryBase):
    pass


class CategoryResponse(CategoryBase):
    id: UUID
    parent_category_id: Optional[UUID] = None
    product_count: int = 0
    insert_date: Optional[datetime] = None
    children: list[CategoryResponse] = []

    model_config = {"from_attributes": True}


# ── Brand ──

class BrandBase(BaseModel):
    name: str = Field(..., max_length=200)


class BrandCreate(BrandBase):
    pass


class BrandResponse(BrandBase):
    id: UUID
    count: int = 0

    model_config = {"from_attributes": True}


# ── Product Type ──

class ProductTypeResponse(BaseModel):
    id: UUID
    fa_name: Optional[str] = None
    en_name: Optional[str] = None

    model_config = {"from_attributes": True}


# ── Product Unit ──

class ProductUnitResponse(BaseModel):
    id: UUID
    name: Optional[str] = None
    abbreviation: Optional[str] = None

    model_config = {"from_attributes": True}


# ── Product Image ──

class ProductImageResponse(BaseModel):
    id: UUID
    medium_image_url: Optional[str] = None
    small_image_url: Optional[str] = None
    large_image_url: Optional[str] = None
    title: Optional[str] = None
    display_photo: bool = False
    picture_order: int = 0

    model_config = {"from_attributes": True}


# ── Variety ──

class VarietyResponse(BaseModel):
    id: UUID
    part_number: Optional[str] = None
    stock_quantity: int = 0
    price: Optional[float] = None
    price_after_discount: Optional[float] = None
    discount_amount: Optional[float] = None
    currency_price: Optional[float] = None
    minimum_purchase: int = 1
    place: Optional[int] = None
    product_varieties: list[ProductVarietyResponse] = []

    model_config = {"from_attributes": True}


class ProductVarietyResponse(BaseModel):
    id: UUID
    category_option_id: UUID
    value: Optional[str] = None
    category_option_name: Optional[str] = None

    model_config = {"from_attributes": True}


# ── Technical Feature ──

class TechnicalFeatureValueResponse(BaseModel):
    id: UUID
    s_value: Optional[str] = None
    e_value: Optional[str] = None
    e_value1: Optional[str] = None
    b_value: Optional[bool] = None
    d_value: Optional[str] = None
    unit: Optional[str] = None
    min_value: Optional[str] = None
    max_value: Optional[str] = None
    x_value: Optional[str] = None
    x_unit: Optional[str] = None
    y_value: Optional[str] = None
    y_unit: Optional[str] = None
    z_value: Optional[str] = None
    z_unit: Optional[str] = None

    model_config = {"from_attributes": True}


class TechnicalFeatureResponse(BaseModel):
    id: UUID
    name: Optional[str] = None
    fa_name: Optional[str] = None
    description: Optional[str] = None
    display_format: Optional[str] = None
    priority: int = 0
    unit: Optional[str] = None
    s_value: Optional[str] = None
    e_value: Optional[str] = None
    columns: int = 1
    values: list[TechnicalFeatureValueResponse] = []

    model_config = {"from_attributes": True}


# ── Product ──

class ProductListResponse(BaseModel):
    id: UUID
    name: str
    en_name: Optional[str] = None
    slug: Optional[str] = None
    part_number: Optional[str] = None
    model: Optional[str] = None
    short_description: Optional[str] = None
    price: Optional[float] = None
    price_after_discount: Optional[float] = None
    discount_amount: Optional[float] = None
    discount_percentage: Optional[float] = None
    stock_quantity: int = 0
    rate: float = 0
    views: int = 0
    sale: int = 0
    is_new: bool = False
    is_special: bool = False
    on_sale: bool = False
    status: Optional[str] = None
    category_id: Optional[UUID] = None
    brand_id: Optional[UUID] = None
    medium_image_url: Optional[str] = None
    large_image_url: Optional[str] = None
    feature_image_url: Optional[str] = None
    insert_date: Optional[datetime] = None
    update_date: Optional[datetime] = None
    category_title: Optional[str] = None
    brand_name: Optional[str] = None
    created_by_user_name: Optional[str] = None

    model_config = {"from_attributes": True}


class ProductDetailResponse(ProductListResponse):
    introduction: Optional[str] = None
    keywords: Optional[str] = None
    meta_description: Optional[str] = None
    concatenated: Optional[str] = None
    en_concatenated: Optional[str] = None
    min_purchase: int = 1
    max_purchases: Optional[int] = None
    delivery_day: Optional[int] = None
    release_date: Optional[datetime] = None
    tax_unique_id: Optional[str] = None
    vat_rate: Optional[float] = None
    taxes_and_duties: Optional[float] = None
    total_amount_plus_taxes: Optional[float] = None
    currency_price: Optional[float] = None
    profit_rate: Optional[float] = None
    max_price: Optional[float] = None
    product_type_id: Optional[UUID] = None
    product_unit_id: Optional[UUID] = None
    currency_id: Optional[UUID] = None
    no_display: bool = False
    images: list[ProductImageResponse] = []
    varieties: list[VarietyResponse] = []
    related_products: list[ProductListResponse] = []
    similar_products: list[ProductListResponse] = []
    technical_features: list[TechnicalFeatureResponse] = []

    model_config = {"from_attributes": True}


class ProductCreate(BaseModel):
    name: str = Field(..., max_length=500)
    en_name: Optional[str] = None
    slug: Optional[str] = None
    en_slug: Optional[str] = None
    part_number: Optional[str] = None
    model: Optional[str] = None
    short_name: Optional[str] = None
    introduction: Optional[str] = None
    short_description: Optional[str] = None
    keywords: Optional[str] = None
    meta_description: Optional[str] = None
    price: Optional[float] = None
    max_price: Optional[float] = None
    discount_amount: Optional[float] = None
    discount_percentage: Optional[float] = None
    currency_price: Optional[float] = None
    profit_rate: Optional[float] = None
    taxes_and_duties: Optional[float] = None
    vat_rate: Optional[float] = None
    stock_quantity: int = 0
    minimum_purchase: int = 1
    max_number_of_purchases: Optional[int] = None
    delivery_day: Optional[int] = None
    points_from_purchases: int = 0
    status: Optional[str] = "OutOfStock"
    type: Optional[str] = "Product"
    default_variation: Optional[str] = None
    taobao_choice_id: Optional[str] = None
    tax_unique_id: Optional[str] = None
    purchase_date: Optional[str] = None
    is_new: bool = False
    is_special: bool = False
    on_sale: bool = False
    suggested: bool = False
    no_display: bool = False
    is_bundle: bool = False
    is_calibrated: bool = False
    restocked: bool = False
    category_id: Optional[UUID] = None
    brand_id: Optional[UUID] = None
    product_type_id: Optional[UUID] = None
    product_unit_id: Optional[UUID] = None
    currency_id: Optional[UUID] = None


class ProductUpdate(ProductCreate):
    pass


class ProductSearchParams(BaseModel):
    query: Optional[str] = None
    category_id: Optional[UUID] = None
    brand_id: Optional[UUID] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    on_sale: Optional[bool] = None
    is_new: Optional[bool] = None
    is_special: Optional[bool] = None
    status: Optional[str] = None
    sort_by: Optional[str] = "insert_date"
    sort_desc: bool = True
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    page_size: int
    total_pages: int