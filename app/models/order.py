
import uuid
from typing import Optional
from datetime import datetime

from sqlalchemy import (
    Column, String, Boolean, DateTime, ForeignKey, Text, Integer, Numeric, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base, BaseEntityMixin


class PayMethod(Base, BaseEntityMixin):
    __tablename__ = "pay_methods"

    name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    enable: Mapped[bool] = mapped_column(Boolean, default=True)
    type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class PostType(Base, BaseEntityMixin):
    __tablename__ = "post_types"

    name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    site: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    post_vat: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    post_vat_rate: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    price: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class Discount(Base, BaseEntityMixin):
    __tablename__ = "discounts"

    code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    amount: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    percent: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    minimum_purchase: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    max_percent_amount: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    start_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    discount_target: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_enable: Mapped[bool] = mapped_column(Boolean, default=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    category_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    product_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL"), nullable=True)


class OrderModel(Base, BaseEntityMixin):
    __tablename__ = "orders"

    reference_code: Mapped[Optional[int]] = mapped_column(Integer, unique=True, nullable=True)
    tracking_number: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    order_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    count: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    weight: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    postage_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    paper_invoice: Mapped[bool] = mapped_column(Boolean, default=False)
    email: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    total_price: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    total_price_plus_taxes: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    total_taxes_and_duties: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    total_price_after_discount: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    total_discount_price: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    discount_price: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    payable: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    vat: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    packaging_cost: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    packaging_vat: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    packaging_vat_rate: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    postage_fee: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    post_vat: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    post_vat_rate: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)

    # Denormalized address fields
    address_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    postal_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    phone_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    telephone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    alias: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    province: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    address_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("addresses.id", ondelete="SET NULL"), nullable=True)
    pay_method_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("pay_methods.id", ondelete="SET NULL"), nullable=True)
    post_type_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("post_types.id", ondelete="SET NULL"), nullable=True)
    identity_information_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("identity_informations.id", ondelete="NO ACTION"), nullable=True)

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], back_populates="orders")
    pay_method: Mapped[Optional["PayMethod"]] = relationship("PayMethod", foreign_keys=[pay_method_id])
    post_type: Mapped[Optional["PostType"]] = relationship("PostType", foreign_keys=[post_type_id])
    order_products: Mapped[list["OrderProduct"]] = relationship("OrderProduct", back_populates="order", lazy="selectin", cascade="all, delete-orphan")
    order_status_records: Mapped[list["OrderStatusRecord"]] = relationship("OrderStatusRecord", back_populates="order", lazy="selectin", cascade="all, delete-orphan")
    receipts: Mapped[list["Receipt"]] = relationship("Receipt", back_populates="order", lazy="selectin")
    payment_requests: Mapped[list["PaymentRequest"]] = relationship("PaymentRequest", back_populates="order", lazy="selectin")
    identity_information: Mapped[Optional["IdentityInformation"]] = relationship("IdentityInformation")


class OrderProduct(Base, BaseEntityMixin):
    __tablename__ = "order_products"

    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="NO ACTION"), nullable=False)
    variety_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("varieties.id", ondelete="NO ACTION"), nullable=True)
    count: Mapped[int] = mapped_column(Integer, default=1)
    unit_price: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    total_price: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    discount: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    price_after_discount: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    total_price_after_discount: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    product_unit: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    vat_rate: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    mood: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    variety_values: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    order: Mapped[OrderModel] = relationship("OrderModel", back_populates="order_products")
    product: Mapped["Product"] = relationship("Product")
    variety: Mapped[Optional["Variety"]] = relationship("Variety")

    __table_args__ = (
        UniqueConstraint("order_id", "product_id", "variety_id", name="uq_order_product_variety"),
    )


class OrderStatusRecord(Base, BaseEntityMixin):
    __tablename__ = "order_status_records"

    order_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tracking_number: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    order: Mapped[OrderModel] = relationship("OrderModel", back_populates="order_status_records")