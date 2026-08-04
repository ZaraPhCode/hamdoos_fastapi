import uuid
from typing import Optional
from datetime import datetime

from sqlalchemy import (
    String, Boolean, DateTime, ForeignKey, Text, Integer, BigInteger, Numeric
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base, BaseEntityMixin
from app.models.enum_types import (
    PaymentRequestStatusEnum, PaymentWageEnum, ReceiptStatusEnum, TabEnum, BankEnum,
    TransferStatusEnum, InventoryOperationEnum,
)


class CurrencyDetail(Base, BaseEntityMixin):
    __tablename__ = "CurrencyDetails"

    currency_id: Mapped[uuid.UUID] = mapped_column("CurrencyId", UUID(as_uuid=True), ForeignKey("Currencies.Id", ondelete="CASCADE"), nullable=False)
    price: Mapped[float] = mapped_column("Price", Numeric(14, 2), nullable=False)
    date: Mapped[datetime] = mapped_column("Date", DateTime(timezone=True), nullable=False)

    currency: Mapped["Currency"] = relationship("Currency", back_populates="currency_details")


class PaymentRequest(Base, BaseEntityMixin):
    __tablename__ = "PaymentRequests"

    amount: Mapped[float] = mapped_column("Amount", Numeric(14, 2), nullable=False)
    is_pay: Mapped[bool] = mapped_column("IsPay", Boolean, nullable=False, default=False)
    pay_date: Mapped[datetime] = mapped_column("PayDate", DateTime(timezone=True), nullable=False)
    authority: Mapped[str] = mapped_column("Authority", Text, nullable=False)
    approval: Mapped[datetime] = mapped_column("Approval", DateTime(timezone=True), nullable=False)
    card_pan: Mapped[Optional[str]] = mapped_column("CardPan", Text, nullable=True)
    card_hash: Mapped[Optional[str]] = mapped_column("CardHash", Text, nullable=True)
    wage: Mapped[int] = mapped_column("Wage", Integer, nullable=False, default=0)
    identifier_id: Mapped[uuid.UUID] = mapped_column("IdentifierId", UUID(as_uuid=True), nullable=False)
    ref_id: Mapped[int] = mapped_column("RefId", BigInteger, nullable=False)
    is_paying: Mapped[bool] = mapped_column("IsPaying", Boolean, nullable=False, default=False)
    wage_type: Mapped[str] = mapped_column("WageType", PaymentWageEnum, nullable=False, default="Unknown")
    result_code: Mapped[str] = mapped_column("ResultCode", Text, nullable=False)
    status: Mapped[str] = mapped_column("Status", PaymentRequestStatusEnum, nullable=False, default="Paying")
    email: Mapped[Optional[str]] = mapped_column("Email", Text, nullable=True)
    mobile: Mapped[Optional[str]] = mapped_column("Mobile", Text, nullable=True)
    message: Mapped[Optional[str]] = mapped_column("Message", Text, nullable=True)
    fee_type: Mapped[Optional[str]] = mapped_column("FeeType", Text, nullable=True)

    user_id: Mapped[uuid.UUID] = mapped_column("UserId", UUID(as_uuid=True), ForeignKey("Users.Id", ondelete="SET NULL"), nullable=False)
    order_id: Mapped[uuid.UUID] = mapped_column("OrderId", UUID(as_uuid=True), ForeignKey("Orders.Id", ondelete="SET NULL"), nullable=False)

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], back_populates="payment_requests")
    order: Mapped["OrderModel"] = relationship("OrderModel", back_populates="payment_requests")


class Receipt(Base, BaseEntityMixin):
    __tablename__ = "Receipts"

    price: Mapped[float] = mapped_column("Price", Numeric(14, 2), nullable=False)
    description: Mapped[Optional[str]] = mapped_column("Description", Text, nullable=True)
    paya: Mapped[Optional[bool]] = mapped_column("PAYA", Boolean, nullable=True)
    deposit_date: Mapped[Optional[datetime]] = mapped_column("DepositDate", DateTime(timezone=True), nullable=True)
    reference_code: Mapped[int] = mapped_column("ReferenceCode", Integer, nullable=False)
    destination_bank: Mapped[Optional[str]] = mapped_column("DestinationBank", BankEnum, nullable=True)
    tab: Mapped[str] = mapped_column("Tab", TabEnum, nullable=False, default="loadImage")
    image_url: Mapped[Optional[str]] = mapped_column("ImageUrl", Text, nullable=True)
    status: Mapped[str] = mapped_column("Status", ReceiptStatusEnum, nullable=False, default="AwaitingConfirmation")

    user_id: Mapped[uuid.UUID] = mapped_column("UserId", UUID(as_uuid=True), ForeignKey("Users.Id", ondelete="SET NULL"), nullable=False)
    order_id: Mapped[uuid.UUID] = mapped_column("OrderId", UUID(as_uuid=True), ForeignKey("Orders.Id", ondelete="SET NULL"), nullable=False)

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], back_populates="receipts")
    order: Mapped["OrderModel"] = relationship("OrderModel", back_populates="receipts")


class Transaction(Base, BaseEntityMixin):
    __tablename__ = "Transactions"

    amount: Mapped[Optional[float]] = mapped_column("Amount", Numeric(14, 2), nullable=True)
    description: Mapped[Optional[str]] = mapped_column("Description", Text, nullable=True)
    customer_id: Mapped[Optional[uuid.UUID]] = mapped_column("CustomerId", UUID(as_uuid=True), ForeignKey("Customers.Id", ondelete="SET NULL"), nullable=True)


class Wallet(Base, BaseEntityMixin):
    __tablename__ = "Wallets"

    amount: Mapped[Optional[float]] = mapped_column("Amount", Numeric(14, 2), nullable=True)
    customer_id: Mapped[Optional[uuid.UUID]] = mapped_column("CustomerId", UUID(as_uuid=True), ForeignKey("Customers.Id", ondelete="SET NULL"), nullable=True)

    wallet_transfers: Mapped[list["WalletTransfer"]] = relationship("WalletTransfer", back_populates="wallet", lazy="selectin")


class WalletTransfer(Base, BaseEntityMixin):
    __tablename__ = "WalletTransfers"

    wallet_id: Mapped[uuid.UUID] = mapped_column("WalletId", UUID(as_uuid=True), ForeignKey("Wallets.Id", ondelete="CASCADE"), nullable=False)
    amount: Mapped[Optional[float]] = mapped_column("Amount", Numeric(14, 2), nullable=True)
    status: Mapped[Optional[str]] = mapped_column("Status", TransferStatusEnum, nullable=True)

    wallet: Mapped[Wallet] = relationship("Wallet", back_populates="wallet_transfers")


class WarehouseMovement(Base, BaseEntityMixin):
    __tablename__ = "WarehouseMovements"

    title: Mapped[Optional[str]] = mapped_column("Title", String(200), nullable=True)
    date: Mapped[Optional[datetime]] = mapped_column("Date", DateTime(timezone=True), nullable=True)
    type: Mapped[Optional[str]] = mapped_column("Type", InventoryOperationEnum, nullable=True)
    note: Mapped[Optional[str]] = mapped_column("Note", Text, nullable=True)
    quantity: Mapped[int] = mapped_column("Quantity", Integer, default=0)
    product_id: Mapped[uuid.UUID] = mapped_column("ProductId", UUID(as_uuid=True), ForeignKey("Products.Id", ondelete="CASCADE"), nullable=False)

    product: Mapped["Product"] = relationship("Product")