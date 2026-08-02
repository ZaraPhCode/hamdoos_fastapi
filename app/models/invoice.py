
import uuid
from typing import Optional
from datetime import datetime

from sqlalchemy import (
    Column, String, Boolean, DateTime, ForeignKey, Text, Integer, Numeric, UniqueConstraint, Index
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base, BaseEntityMixin


class Supplier(Base, BaseEntityMixin):
    __tablename__ = "suppliers"

    telephone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    site: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    intermediary_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    supplier_products: Mapped[list["SupplierProduct"]] = relationship("SupplierProduct", back_populates="supplier", lazy="selectin")


class SupplierProduct(Base, BaseEntityMixin):
    __tablename__ = "supplier_products"

    supplier_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    link: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    supplier: Mapped[Supplier] = relationship("Supplier", back_populates="supplier_products")
    product: Mapped["Product"] = relationship("Product", back_populates="supplier_products")

    __table_args__ = (
        UniqueConstraint("product_id", "supplier_id", name="uq_supplier_product"),
    )


class PurchaseOrder(Base, BaseEntityMixin):
    __tablename__ = "purchase_orders"

    reference_code: Mapped[Optional[str]] = mapped_column(String(100), unique=True, nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    shipping_and_clearance_price: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)

    purchase_order_details: Mapped[list["PurchaseOrderDetail"]] = relationship(
        "PurchaseOrderDetail", back_populates="purchase_order", lazy="selectin", cascade="all, delete-orphan"
    )


class PurchaseOrderDetail(Base, BaseEntityMixin):
    __tablename__ = "purchase_order_details"

    purchase_order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="NO ACTION"), nullable=False)
    variety_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    count: Mapped[int] = mapped_column(Integer, default=0)
    currency_price: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    weight_percent: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    currency_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("currencies.id", ondelete="SET NULL"), nullable=True)
    supplier_product_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("supplier_products.id", ondelete="SET NULL"), nullable=True)

    purchase_order: Mapped[PurchaseOrder] = relationship("PurchaseOrder", back_populates="purchase_order_details")
    product: Mapped["Product"] = relationship("Product")

    __table_args__ = (
        UniqueConstraint("product_id", "variety_id", name="uq_po_product_variety"),
    )


class Invoice(Base, BaseEntityMixin):
    __tablename__ = "invoices"

    reference_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    easy_invoice_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tracking_number: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    weight: Mapped[Optional[float]] = mapped_column(Numeric(10, 3), nullable=True)
    is_cash: Mapped[bool] = mapped_column(Boolean, default=False)
    pay_method: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    count: Mapped[int] = mapped_column(Integer, default=0)

    total_price: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    total_discount_price: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    total_price_after_discount: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    total_price_plus_taxes: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    total_taxes_and_duties: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    payable: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    vat: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    packaging_cost: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    packaging_vat: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    packaging_vat_rate: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    postage_fee: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    post_vat: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    post_vat_rate: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)

    # Denormalized identity info
    identity_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    identity_postal_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    economic_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    identity_name: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    national_code_or_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    identity_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    identity_country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    identity_province: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    identity_city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    identity_phone_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    final_consumer: Mapped[bool] = mapped_column(Boolean, default=False)

    # Denormalized address
    post_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    post_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    order_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="SET NULL"), nullable=True)
    purchase_order_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("purchase_orders.id", ondelete="SET NULL"), nullable=True)
    reference_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("invoice_references.id", ondelete="NO ACTION"), nullable=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    identity_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)

    order: Mapped[Optional["OrderModel"]] = relationship("OrderModel")
    purchase_order: Mapped[Optional[PurchaseOrder]] = relationship("PurchaseOrder")
    reference: Mapped[Optional["InvoiceReference"]] = relationship("InvoiceReference", back_populates="invoices", foreign_keys=[reference_id])
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], back_populates="invoices")
    invoice_products: Mapped[list["InvoiceProduct"]] = relationship("InvoiceProduct", back_populates="invoice", lazy="selectin", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("purchase_order_id", name="uq_invoice_purchase_order"),
        UniqueConstraint("order_id", name="uq_invoice_order"),
        Index("ix_invoice_refcode_type", "reference_code", "type", unique=True),
    )


class InvoiceProduct(Base, BaseEntityMixin):
    __tablename__ = "invoice_products"

    invoice_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    variety_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    supplier_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    supplier_product_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    part_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    reference_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    en_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    count: Mapped[int] = mapped_column(Integer, default=1)
    product_unit: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    product_unit_tax_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    tax_unique_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    unit_price: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    total_price: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    discount_amount: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    price_after_discount: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    total_price_after_discount: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    taxes_and_duties: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    vat_rate: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    total_amount_plus_taxes: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    currency_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    currency_price: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    currency_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    variety_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    supplier_link: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    invoice: Mapped[Invoice] = relationship("Invoice", back_populates="invoice_products")


class InvoiceReference(Base, BaseEntityMixin):
    __tablename__ = "invoice_references"

    invoices: Mapped[list[Invoice]] = relationship("Invoice", back_populates="reference", foreign_keys="Invoice.reference_id", lazy="selectin")