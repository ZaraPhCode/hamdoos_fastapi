import uuid
from typing import Optional
from datetime import datetime

from sqlalchemy import (
    String, Boolean, DateTime, ForeignKey, Text, Integer, Numeric, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base, BaseEntityMixin
from app.models.enum_types import (
    OrderStatusEnum, PaymentStatusEnum, PayMethodEnum, PostTypeEnum_,
    DiscountTargetEnum, DiscountTypeEnum,
)


class PayMethod(Base, BaseEntityMixin):
    __tablename__ = "PayMethods"

    name: Mapped[str] = mapped_column("Name", Text, nullable=False)
    enable: Mapped[bool] = mapped_column("Enable", Boolean, nullable=False, default=True)
    type: Mapped[str] = mapped_column("Type", PayMethodEnum, nullable=False, default="Zarinpal")
    description: Mapped[str] = mapped_column("Description", Text, nullable=False)


class PostType(Base, BaseEntityMixin):
    __tablename__ = "PostTypes"

    name: Mapped[str] = mapped_column("Name", Text, nullable=False)
    site: Mapped[Optional[str]] = mapped_column("Site", Text, nullable=True)
    post_vat: Mapped[Optional[float]] = mapped_column("PostVat", Numeric(14, 2), nullable=True)
    post_vat_rate: Mapped[float] = mapped_column("PostVATRate", Numeric(14, 2), nullable=False)
    image_url: Mapped[Optional[str]] = mapped_column("ImageUrl", Text, nullable=True)
    price: Mapped[float] = mapped_column("Price", Numeric(14, 2), nullable=False)
    description: Mapped[str] = mapped_column("Description", Text, nullable=False)
    post_type: Mapped[Optional[str]] = mapped_column("PostType", PostTypeEnum_, nullable=True)


class Discount(Base, BaseEntityMixin):
    __tablename__ = "Discounts"

    code: Mapped[Optional[str]] = mapped_column("Code", String(100), nullable=True)
    description: Mapped[Optional[str]] = mapped_column("Description", Text, nullable=True)
    amount: Mapped[Optional[float]] = mapped_column("Amount", Numeric(14, 2), nullable=True)
    percent: Mapped[Optional[float]] = mapped_column("Percent", Numeric(5, 2), nullable=True)
    minimum_purchase: Mapped[Optional[float]] = mapped_column("MinimumPurchase", Numeric(14, 2), nullable=True)
    max_percent_amount: Mapped[Optional[float]] = mapped_column("MaxPercentAmount", Numeric(14, 2), nullable=True)
    end_date: Mapped[Optional[datetime]] = mapped_column("EndDate", DateTime(timezone=True), nullable=True)
    start_date: Mapped[Optional[datetime]] = mapped_column("StartDate", DateTime(timezone=True), nullable=True)
    discount_target: Mapped[Optional[str]] = mapped_column("DiscountTarget", DiscountTargetEnum, nullable=True)
    discount_type: Mapped[Optional[str]] = mapped_column("DiscountType", DiscountTypeEnum, nullable=True)
    is_enable: Mapped[bool] = mapped_column("IsEnable", Boolean, default=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column("UserId", UUID(as_uuid=True), ForeignKey("Users.Id", ondelete="SET NULL"), nullable=True)
    category_id: Mapped[Optional[uuid.UUID]] = mapped_column("CategoryId", UUID(as_uuid=True), ForeignKey("Categories.Id", ondelete="SET NULL"), nullable=True)
    product_id: Mapped[Optional[uuid.UUID]] = mapped_column("ProductId", UUID(as_uuid=True), ForeignKey("Products.Id", ondelete="SET NULL"), nullable=True)


class OrderModel(Base, BaseEntityMixin):
    __tablename__ = "Orders"

    reference_code: Mapped[int] = mapped_column("ReferenceCode", Integer, unique=True, nullable=False)
    tracking_number: Mapped[Optional[str]] = mapped_column("TrackingNumber", Text, nullable=True)
    order_status: Mapped[str] = mapped_column("OrderStatus", OrderStatusEnum, nullable=False, default="Ordering")
    payment_status: Mapped[Optional[str]] = mapped_column("PaymentStatus", PaymentStatusEnum, nullable=True)
    count: Mapped[int] = mapped_column("Count", Integer, nullable=False, default=0)
    notes: Mapped[Optional[str]] = mapped_column("Notes", Text, nullable=True)
    weight: Mapped[Optional[str]] = mapped_column("Weight", Text, nullable=True)
    postage_date: Mapped[Optional[datetime]] = mapped_column("PostageDate", DateTime(timezone=True), nullable=True)
    date: Mapped[datetime] = mapped_column("Date", DateTime(timezone=True), nullable=False)
    paper_invoice: Mapped[bool] = mapped_column("PaperInvoice", Boolean, nullable=False, default=False)
    email: Mapped[str] = mapped_column("Email", Text, nullable=False)
    pay_date: Mapped[datetime] = mapped_column("PayDate", DateTime(timezone=True), nullable=False)
    pay_method_name: Mapped[Optional[str]] = mapped_column("PayMethodName", Text, nullable=True)
    post_type_name: Mapped[Optional[str]] = mapped_column("PostTypeName", Text, nullable=True)

    total_price: Mapped[float] = mapped_column("TotalPrice", Numeric(14, 2), nullable=False)
    total_price_plus_taxes: Mapped[float] = mapped_column("TotalPricePlusTaxesAndDuties", Numeric(14, 2), nullable=False)
    total_taxes_and_duties: Mapped[float] = mapped_column("TotalTaxesAndDuties", Numeric(14, 2), nullable=False)
    total_price_after_discount: Mapped[float] = mapped_column("TotalPriceAfterDiscount", Numeric(14, 2), nullable=False)
    total_discount_price: Mapped[float] = mapped_column("TotalDiscountPrice", Numeric(14, 2), nullable=False)
    discount_price: Mapped[float] = mapped_column("DiscountPrice", Numeric(14, 2), nullable=False)
    payable: Mapped[float] = mapped_column("Payable", Numeric(14, 2), nullable=False)
    vat: Mapped[float] = mapped_column("VAT", Numeric(14, 2), nullable=False)
    packaging_cost: Mapped[float] = mapped_column("PackagingCost", Numeric(14, 2), nullable=False)
    packaging_vat: Mapped[float] = mapped_column("PackagingVAT", Numeric(14, 2), nullable=False)
    packaging_vat_rate: Mapped[float] = mapped_column("PackagingVATRate", Numeric(14, 2), nullable=False)
    postage_fee: Mapped[float] = mapped_column("PostageFee", Numeric(14, 2), nullable=False)
    post_vat: Mapped[float] = mapped_column("PostVAT", Numeric(14, 2), nullable=False)
    post_vat_rate: Mapped[float] = mapped_column("PostVATRate", Numeric(14, 2), nullable=False)

    # Denormalized address fields
    address_description: Mapped[Optional[str]] = mapped_column("AddressDescription", Text, nullable=True)
    postal_code: Mapped[Optional[str]] = mapped_column("PostalCode", Text, nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column("FirstName", Text, nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column("LastName", Text, nullable=True)
    phone_number: Mapped[Optional[str]] = mapped_column("PhoneNumber", Text, nullable=True)
    telephone: Mapped[Optional[str]] = mapped_column("Telephone", Text, nullable=True)
    alias: Mapped[Optional[str]] = mapped_column("Alias", Text, nullable=True)
    country: Mapped[Optional[str]] = mapped_column("Country", Text, nullable=True)
    province: Mapped[Optional[str]] = mapped_column("Province", Text, nullable=True)
    city: Mapped[Optional[str]] = mapped_column("City", Text, nullable=True)

    user_id: Mapped[Optional[uuid.UUID]] = mapped_column("UserId", UUID(as_uuid=True), ForeignKey("Users.Id", ondelete="SET NULL"), nullable=True)
    address_id: Mapped[Optional[uuid.UUID]] = mapped_column("AddressId", UUID(as_uuid=True), ForeignKey("Addresses.Id", ondelete="SET NULL"), nullable=True)
    pay_method_id: Mapped[Optional[uuid.UUID]] = mapped_column("PayMethodId", UUID(as_uuid=True), ForeignKey("PayMethods.Id", ondelete="SET NULL"), nullable=True)
    post_type_id: Mapped[Optional[uuid.UUID]] = mapped_column("PostTypeId", UUID(as_uuid=True), ForeignKey("PostTypes.Id", ondelete="SET NULL"), nullable=True)
    identity_information_id: Mapped[Optional[uuid.UUID]] = mapped_column("IdentityInformationId", UUID(as_uuid=True), ForeignKey("IdentityInformations.Id", ondelete="NO ACTION"), nullable=True)

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], back_populates="orders")
    pay_method: Mapped[Optional["PayMethod"]] = relationship("PayMethod", foreign_keys=[pay_method_id])
    post_type: Mapped[Optional["PostType"]] = relationship("PostType", foreign_keys=[post_type_id])
    order_products: Mapped[list["OrderProduct"]] = relationship("OrderProduct", back_populates="order", lazy="selectin", cascade="all, delete-orphan")
    order_status_records: Mapped[list["OrderStatusRecord"]] = relationship("OrderStatusRecord", back_populates="order", lazy="selectin", cascade="all, delete-orphan")
    receipts: Mapped[list["Receipt"]] = relationship("Receipt", back_populates="order", lazy="selectin")
    payment_requests: Mapped[list["PaymentRequest"]] = relationship("PaymentRequest", back_populates="order", lazy="selectin")
    identity_information: Mapped[Optional["IdentityInformation"]] = relationship("IdentityInformation")


class OrderProduct(Base, BaseEntityMixin):
    __tablename__ = "OrderProducts"

    order_id: Mapped[uuid.UUID] = mapped_column("OrderId", UUID(as_uuid=True), ForeignKey("Orders.Id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column("ProductId", UUID(as_uuid=True), ForeignKey("Products.Id", ondelete="NO ACTION"), nullable=False)
    variety_id: Mapped[Optional[uuid.UUID]] = mapped_column("VarietyId", UUID(as_uuid=True), ForeignKey("Varieties.Id", ondelete="NO ACTION"), nullable=True)
    count: Mapped[int] = mapped_column("Count", Integer, nullable=False, default=1)
    unit_price: Mapped[float] = mapped_column("UnitPrice", Numeric(14, 2), nullable=False)
    total_price: Mapped[float] = mapped_column("TotalPrice", Numeric(14, 2), nullable=False)
    discount: Mapped[float] = mapped_column("Discount", Numeric(14, 2), nullable=False)
    price_after_discount: Mapped[float] = mapped_column("PriceAfterDiscount", Numeric(14, 2), nullable=False)
    total_price_after_discount: Mapped[float] = mapped_column("TotalPriceAfterDiscount", Numeric(14, 2), nullable=False)
    product_unit: Mapped[Optional[str]] = mapped_column("ProductUnit", Text, nullable=True)
    vat_rate: Mapped[float] = mapped_column("VATRate", Numeric(14, 2), nullable=False)
    mood: Mapped[Optional[str]] = mapped_column("Mood", String(20), nullable=True)
    variety_values: Mapped[Optional[str]] = mapped_column("VarietyValues", Text, nullable=True)

    order: Mapped[OrderModel] = relationship("OrderModel", back_populates="order_products")
    product: Mapped["Product"] = relationship("Product")
    variety: Mapped[Optional["Variety"]] = relationship("Variety")

    __table_args__ = (
        UniqueConstraint("OrderId", "ProductId", "VarietyId", name="uq_order_product_variety"),
    )


class OrderStatusRecord(Base, BaseEntityMixin):
    __tablename__ = "OrderStatusRecords"

    order_id: Mapped[uuid.UUID] = mapped_column("OrderId", UUID(as_uuid=True), ForeignKey("Orders.Id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column("Status", OrderStatusEnum, nullable=False, default="Ordering")
    comment: Mapped[Optional[str]] = mapped_column("Comment", Text, nullable=True)
    tracking_number: Mapped[Optional[str]] = mapped_column("TrackingNumber", Text, nullable=True)

    order: Mapped[OrderModel] = relationship("OrderModel", back_populates="order_status_records")