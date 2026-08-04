import uuid
from typing import Optional
from datetime import datetime

from sqlalchemy import (
    String, Boolean, DateTime, ForeignKey, Text, Integer, Numeric, UniqueConstraint, Index
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base, BaseEntityMixin
from app.models.enum_types import (
    InvoiceTypeEnum, InvoiceStatusEnum, InvoiceProductTypeEnum,
    PurchaseOrderStatusEnum, IdentityTypeEnum,
)


class Supplier(Base, BaseEntityMixin):
    __tablename__ = "Suppliers"

    telephone: Mapped[Optional[str]] = mapped_column("Telephone", Text, nullable=True)
    address: Mapped[str] = mapped_column("Address", Text, nullable=False)
    site: Mapped[Optional[str]] = mapped_column("Site", Text, nullable=True)
    intermediary_name: Mapped[Optional[str]] = mapped_column("IntermediaryName", Text, nullable=True)

    supplier_products: Mapped[list["SupplierProduct"]] = relationship("SupplierProduct", back_populates="supplier", lazy="selectin")


class SupplierProduct(Base, BaseEntityMixin):
    __tablename__ = "SupplierProducts"

    supplier_id: Mapped[uuid.UUID] = mapped_column("SupplierId", UUID(as_uuid=True), ForeignKey("Suppliers.Id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column("ProductId", UUID(as_uuid=True), ForeignKey("Products.Id", ondelete="CASCADE"), nullable=False)
    link: Mapped[Optional[str]] = mapped_column("Link", Text, nullable=True)

    supplier: Mapped[Supplier] = relationship("Supplier", back_populates="supplier_products")
    product: Mapped["Product"] = relationship("Product", back_populates="supplier_products")

    __table_args__ = (
        UniqueConstraint("ProductId", "SupplierId", name="uq_supplier_product"),
    )


class PurchaseOrder(Base, BaseEntityMixin):
    __tablename__ = "PurchaseOrders"

    reference_code: Mapped[int] = mapped_column("ReferenceCode", Integer, unique=True, nullable=False)
    status: Mapped[str] = mapped_column("Status", PurchaseOrderStatusEnum, nullable=False, default="InTransit")
    date: Mapped[datetime] = mapped_column("Date", DateTime(timezone=True), nullable=False)
    shipping_and_clearance_price: Mapped[float] = mapped_column("ShippingAndClearancePrice", Numeric(14, 2), nullable=False)

    purchase_order_details: Mapped[list["PurchaseOrderDetail"]] = relationship(
        "PurchaseOrderDetail", back_populates="purchase_order", lazy="selectin", cascade="all, delete-orphan"
    )


class PurchaseOrderDetail(Base, BaseEntityMixin):
    __tablename__ = "PurchaseOrderDetails"

    purchase_order_id: Mapped[uuid.UUID] = mapped_column("PurchaseOrderId", UUID(as_uuid=True), ForeignKey("PurchaseOrders.Id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[uuid.UUID] = mapped_column("ProductId", UUID(as_uuid=True), ForeignKey("Products.Id", ondelete="NO ACTION"), nullable=False)
    variety_id: Mapped[uuid.UUID] = mapped_column("VarietyId", UUID(as_uuid=True), nullable=False)
    count: Mapped[int] = mapped_column("Count", Integer, nullable=False, default=0)
    currency_price: Mapped[float] = mapped_column("CurrencyPrice", Numeric(14, 2), nullable=False)
    weight_percent: Mapped[float] = mapped_column("WeightPercent", Numeric(14, 2), nullable=False)
    currency_id: Mapped[uuid.UUID] = mapped_column("CurrencyId", UUID(as_uuid=True), ForeignKey("Currencies.Id", ondelete="SET NULL"), nullable=False)
    supplier_product_id: Mapped[Optional[uuid.UUID]] = mapped_column("SupplierProductId", UUID(as_uuid=True), ForeignKey("SupplierProducts.Id", ondelete="SET NULL"), nullable=True)

    purchase_order: Mapped[PurchaseOrder] = relationship("PurchaseOrder", back_populates="purchase_order_details")
    product: Mapped["Product"] = relationship("Product")

    __table_args__ = (
        UniqueConstraint("ProductId", "VarietyId", name="uq_po_product_variety"),
    )


class Invoice(Base, BaseEntityMixin):
    __tablename__ = "Invoices"

    reference_code: Mapped[Optional[int]] = mapped_column("ReferenceCode", Integer, nullable=True)
    easy_invoice_id: Mapped[Optional[uuid.UUID]] = mapped_column("EasyInvoiceId", UUID(as_uuid=True), nullable=True)
    type: Mapped[str] = mapped_column("Type", InvoiceTypeEnum, nullable=False, default="Sale")
    status: Mapped[str] = mapped_column("Status", InvoiceStatusEnum, nullable=False, default="Shopping")
    date: Mapped[datetime] = mapped_column("Date", DateTime(timezone=True), nullable=False)
    description: Mapped[Optional[str]] = mapped_column("Description", Text, nullable=True)
    tracking_number: Mapped[Optional[str]] = mapped_column("TrackingNumber", Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column("Notes", Text, nullable=True)
    weight: Mapped[Optional[str]] = mapped_column("Weight", Text, nullable=True)
    is_cash: Mapped[bool] = mapped_column("IsCash", Boolean, nullable=False, default=False)
    pay_method: Mapped[Optional[str]] = mapped_column("PayMethod", Text, nullable=True)
    count: Mapped[int] = mapped_column("Count", Integer, nullable=False, default=0)

    total_price: Mapped[float] = mapped_column("TotalPrice", Numeric(14, 2), nullable=False)
    total_discount_price: Mapped[float] = mapped_column("TotalDiscountPrice", Numeric(14, 2), nullable=False)
    total_price_after_discount: Mapped[float] = mapped_column("TotalPriceAfterDiscount", Numeric(14, 2), nullable=False)
    total_price_plus_taxes: Mapped[float] = mapped_column("TotalPricePlusTaxesAndDuties", Numeric(14, 2), nullable=False)
    total_taxes_and_duties: Mapped[float] = mapped_column("TotalTaxesAndDuties", Numeric(14, 2), nullable=False)
    payable: Mapped[float] = mapped_column("Payable", Numeric(14, 2), nullable=False)
    vat: Mapped[float] = mapped_column("VAT", Numeric(14, 2), nullable=False)
    packaging_cost: Mapped[float] = mapped_column("PackagingCost", Numeric(14, 2), nullable=False)
    packaging_vat: Mapped[float] = mapped_column("PackagingVAT", Numeric(14, 2), nullable=False)
    packaging_vat_rate: Mapped[float] = mapped_column("PackagingVATRate", Numeric(14, 2), nullable=False)
    postage_fee: Mapped[float] = mapped_column("PostageFee", Numeric(14, 2), nullable=False)
    post_vat: Mapped[float] = mapped_column("PostVAT", Numeric(14, 2), nullable=False)
    post_vat_rate: Mapped[float] = mapped_column("PostVATRate", Numeric(14, 2), nullable=False)

    # Denormalized identity info
    identity_type: Mapped[Optional[str]] = mapped_column("IdentityType", IdentityTypeEnum, nullable=True)
    identity_postal_code: Mapped[Optional[str]] = mapped_column("IdentityPostalCode", Text, nullable=True)
    economic_code: Mapped[Optional[str]] = mapped_column("EconomicCode", Text, nullable=True)
    identity_name: Mapped[Optional[str]] = mapped_column("IdentityName", Text, nullable=True)
    national_code_or_id: Mapped[Optional[str]] = mapped_column("NationalCodeOrId", Text, nullable=True)
    identity_address: Mapped[Optional[str]] = mapped_column("IdentityAddress", Text, nullable=True)
    identity_country: Mapped[Optional[str]] = mapped_column("IdentityCountry", Text, nullable=True)
    identity_province: Mapped[Optional[str]] = mapped_column("IdentityProvince", Text, nullable=True)
    identity_city: Mapped[Optional[str]] = mapped_column("IdentityCity", Text, nullable=True)
    identity_phone_number: Mapped[Optional[str]] = mapped_column("IdentityPhoneNumber", Text, nullable=True)
    final_consumer: Mapped[Optional[bool]] = mapped_column("FinalCounsumer", Boolean, nullable=True)

    # Denormalized address
    post_date: Mapped[datetime] = mapped_column("PostDate", DateTime(timezone=True), nullable=False)
    post_type: Mapped[Optional[str]] = mapped_column("PostType", Text, nullable=True)

    address_description: Mapped[Optional[str]] = mapped_column("AddressDescription", Text, nullable=True)
    alias: Mapped[Optional[str]] = mapped_column("Alias", Text, nullable=True)
    city: Mapped[Optional[str]] = mapped_column("City", Text, nullable=True)
    country: Mapped[Optional[str]] = mapped_column("Country", Text, nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column("FirstName", Text, nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column("LastName", Text, nullable=True)
    phone_number: Mapped[Optional[str]] = mapped_column("PhoneNumber", Text, nullable=True)
    postal_code: Mapped[Optional[str]] = mapped_column("PostalCode", Text, nullable=True)
    province: Mapped[Optional[str]] = mapped_column("Province", Text, nullable=True)
    telephone: Mapped[Optional[str]] = mapped_column("Telephone", Text, nullable=True)
    invoice_id: Mapped[Optional[uuid.UUID]] = mapped_column("InvoiceId", UUID(as_uuid=True), nullable=True)

    order_id: Mapped[Optional[uuid.UUID]] = mapped_column("OrderId", UUID(as_uuid=True), ForeignKey("Orders.Id", ondelete="SET NULL"), nullable=True)
    purchase_order_id: Mapped[Optional[uuid.UUID]] = mapped_column("PurchaseOrderId", UUID(as_uuid=True), ForeignKey("PurchaseOrders.Id", ondelete="SET NULL"), nullable=True)
    reference_id: Mapped[Optional[uuid.UUID]] = mapped_column("ReferenceId", UUID(as_uuid=True), ForeignKey("InvoiceReferences.Id", ondelete="NO ACTION"), nullable=True)
    user_id: Mapped[uuid.UUID] = mapped_column("UserId", UUID(as_uuid=True), ForeignKey("Users.Id", ondelete="SET NULL"), nullable=False)
    identity_user_id: Mapped[Optional[uuid.UUID]] = mapped_column("IdentityUserId", UUID(as_uuid=True), nullable=True)

    order: Mapped[Optional["OrderModel"]] = relationship("OrderModel")
    purchase_order: Mapped[Optional[PurchaseOrder]] = relationship("PurchaseOrder")
    reference: Mapped[Optional["InvoiceReference"]] = relationship("InvoiceReference", back_populates="invoices", foreign_keys=[reference_id])
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], back_populates="invoices")
    invoice_products: Mapped[list["InvoiceProduct"]] = relationship("InvoiceProduct", back_populates="invoice", lazy="selectin", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("PurchaseOrderId", name="uq_invoice_purchase_order"),
        UniqueConstraint("OrderId", name="uq_invoice_order"),
        Index("ix_invoice_refcode_type", "ReferenceCode", "Type", unique=True),
    )


class InvoiceProduct(Base, BaseEntityMixin):
    __tablename__ = "InvoiceProducts"

    invoice_id: Mapped[uuid.UUID] = mapped_column("InvoiceId", UUID(as_uuid=True), ForeignKey("Invoices.Id", ondelete="CASCADE"), nullable=False)
    product_id: Mapped[Optional[uuid.UUID]] = mapped_column("ProductId", UUID(as_uuid=True), nullable=True)
    variety_id: Mapped[Optional[uuid.UUID]] = mapped_column("VarietyId", UUID(as_uuid=True), nullable=True)
    supplier_id: Mapped[Optional[uuid.UUID]] = mapped_column("SupplierId", UUID(as_uuid=True), nullable=True)
    supplier_product_id: Mapped[Optional[uuid.UUID]] = mapped_column("SupplierProductId", UUID(as_uuid=True), nullable=True)
    part_number: Mapped[Optional[str]] = mapped_column("PartNumber", Text, nullable=True)
    reference_code: Mapped[Optional[int]] = mapped_column("ReferenceCode", Integer, nullable=True)
    name: Mapped[Optional[str]] = mapped_column("Name", Text, nullable=True)
    model: Mapped[Optional[str]] = mapped_column("Model", Text, nullable=True)
    en_name: Mapped[Optional[str]] = mapped_column("EnName", String(250), nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column("ImageUrl", Text, nullable=True)
    count: Mapped[int] = mapped_column("Count", Integer, nullable=False, default=1)
    product_unit: Mapped[Optional[str]] = mapped_column("ProductUnit", Text, nullable=True)
    product_unit_tax_id: Mapped[Optional[str]] = mapped_column("ProductUnitTaxId", Text, nullable=True)
    tax_unique_id: Mapped[Optional[str]] = mapped_column("TaxUniqueId", String(13), nullable=True)
    unit_price: Mapped[float] = mapped_column("UnitPrice", Numeric(14, 2), nullable=False)
    total_price: Mapped[float] = mapped_column("TotalPrice", Numeric(14, 2), nullable=False)
    discount_amount: Mapped[float] = mapped_column("DiscountAmount", Numeric(14, 2), nullable=False)
    price_after_discount: Mapped[float] = mapped_column("PriceAfterDiscount", Numeric(14, 2), nullable=False)
    total_price_after_discount: Mapped[float] = mapped_column("TotalPriceAfterDiscount", Numeric(14, 2), nullable=False)
    taxes_and_duties: Mapped[float] = mapped_column("TaxesAndDuties", Numeric(14, 2), nullable=False)
    vat_rate: Mapped[float] = mapped_column("VATRate", Numeric(14, 2), nullable=False)
    total_amount_plus_taxes: Mapped[float] = mapped_column("TotalAmountPlusTaxesAndDuties", Numeric(14, 2), nullable=False)
    type: Mapped[str] = mapped_column("Type", InvoiceProductTypeEnum, nullable=False, default="Product")
    currency_id: Mapped[Optional[uuid.UUID]] = mapped_column("CurrencyId", UUID(as_uuid=True), nullable=True)
    currency_price: Mapped[float] = mapped_column("CurrencyPrice", Numeric(14, 2), nullable=False)
    currency_name: Mapped[Optional[str]] = mapped_column("CurrencyName", Text, nullable=True)
    variety_value: Mapped[Optional[str]] = mapped_column("VarietyValue", Text, nullable=True)
    supplier_link: Mapped[Optional[str]] = mapped_column("SupplierLink", Text, nullable=True)

    invoice: Mapped[Invoice] = relationship("Invoice", back_populates="invoice_products")


class InvoiceReference(Base, BaseEntityMixin):
    __tablename__ = "InvoiceReferences"

    invoices: Mapped[list[Invoice]] = relationship("Invoice", back_populates="reference", foreign_keys="Invoice.reference_id", lazy="selectin")