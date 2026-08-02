"""Pydantic schemas for invoices, purchase orders, and suppliers."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ── Supplier ──

class SupplierBase(BaseModel):
    telephone: Optional[str] = None
    address: Optional[str] = None
    site: Optional[str] = None
    intermediary_name: Optional[str] = None


class SupplierCreate(SupplierBase):
    pass


class SupplierResponse(SupplierBase):
    id: UUID

    model_config = {"from_attributes": True}


# ── Supplier Product ──

class SupplierProductResponse(BaseModel):
    id: UUID
    supplier_id: UUID
    product_id: UUID
    link: Optional[str] = None
    product_name: Optional[str] = None

    model_config = {"from_attributes": True}


# ── Invoice Product ──

class InvoiceProductBase(BaseModel):
    product_id: Optional[UUID] = None
    variety_id: Optional[UUID] = None
    part_number: Optional[str] = None
    name: Optional[str] = None
    model: Optional[str] = None
    en_name: Optional[str] = None
    image_url: Optional[str] = None
    count: int = 1
    unit_price: Optional[float] = None
    discount_amount: Optional[float] = None
    vat_rate: Optional[float] = None
    type: Optional[str] = "Product"
    currency_id: Optional[UUID] = None
    currency_price: Optional[float] = None
    supplier_id: Optional[UUID] = None


class InvoiceProductResponse(InvoiceProductBase):
    id: UUID
    invoice_id: UUID
    total_price: Optional[float] = None
    price_after_discount: Optional[float] = None
    total_price_after_discount: Optional[float] = None
    taxes_and_duties: Optional[float] = None
    total_amount_plus_taxes: Optional[float] = None

    model_config = {"from_attributes": True}


# ── Invoice ──

class InvoiceBase(BaseModel):
    type: Optional[str] = "Sale"
    status: Optional[str] = "Bought"
    description: Optional[str] = None
    tracking_number: Optional[str] = None
    notes: Optional[str] = None
    weight: Optional[float] = None
    is_cash: bool = False
    pay_method: Optional[str] = None

    # Identity information
    identity_type: Optional[str] = None
    identity_name: Optional[str] = None
    national_code_or_id: Optional[str] = None
    economic_code: Optional[str] = None
    identity_postal_code: Optional[str] = None
    identity_address: Optional[str] = None
    identity_country: Optional[str] = None
    identity_province: Optional[str] = None
    identity_city: Optional[str] = None
    identity_phone_number: Optional[str] = None
    final_consumer: bool = True

    # Post
    post_type: Optional[str] = None
    postage_fee: Optional[float] = None
    post_vat: Optional[float] = None
    post_vat_rate: Optional[float] = None
    packaging_cost: Optional[float] = None
    packaging_vat: Optional[float] = None
    packaging_vat_rate: Optional[float] = None


class InvoiceCreate(InvoiceBase):
    order_id: Optional[UUID] = None
    user_id: UUID
    invoice_products: list[InvoiceProductBase] = []


class InvoiceResponse(InvoiceBase):
    id: UUID
    reference_code: Optional[str] = None
    easy_invoice_id: Optional[str] = None
    order_id: Optional[UUID] = None
    purchase_order_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    date: Optional[datetime] = None
    count: int = 0

    total_price: Optional[float] = None
    total_discount_price: Optional[float] = None
    total_price_after_discount: Optional[float] = None
    total_price_plus_taxes: Optional[float] = None
    total_taxes_and_duties: Optional[float] = None
    payable: Optional[float] = None
    vat: Optional[float] = None

    invoice_products: list[InvoiceProductResponse] = []
    insert_date: Optional[datetime] = None

    model_config = {"from_attributes": True}


class InvoiceListResponse(BaseModel):
    id: UUID
    reference_code: Optional[str] = None
    type: Optional[str] = None
    status: Optional[str] = None
    date: Optional[datetime] = None
    total_price: Optional[float] = None
    payable: Optional[float] = None
    identity_name: Optional[str] = None
    count: int = 0
    insert_date: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── Purchase Order ──

class PurchaseOrderDetailBase(BaseModel):
    product_id: UUID
    variety_id: Optional[UUID] = None
    count: int = 0
    currency_price: Optional[float] = None
    weight_percent: Optional[float] = None
    currency_id: Optional[UUID] = None
    supplier_product_id: Optional[UUID] = None


class PurchaseOrderDetailResponse(PurchaseOrderDetailBase):
    id: UUID
    purchase_order_id: UUID
    product_name: Optional[str] = None

    model_config = {"from_attributes": True}


class PurchaseOrderBase(BaseModel):
    status: Optional[str] = "Ordered"
    shipping_and_clearance_price: Optional[float] = None


class PurchaseOrderCreate(PurchaseOrderBase):
    details: list[PurchaseOrderDetailBase] = []


class PurchaseOrderResponse(PurchaseOrderBase):
    id: UUID
    reference_code: Optional[str] = None
    date: Optional[datetime] = None
    details: list[PurchaseOrderDetailResponse] = []

    model_config = {"from_attributes": True}


# ── Paginated ──

class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    page_size: int
    total_pages: int