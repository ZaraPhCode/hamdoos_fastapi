
import uuid
from typing import Optional
from datetime import datetime

from sqlalchemy import (
    Column, String, Boolean, DateTime, ForeignKey, Text, Integer, Numeric
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base, BaseEntityMixin


class CurrencyDetail(Base, BaseEntityMixin):
    __tablename__ = "currency_details"

    currency_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("currencies.id", ondelete="CASCADE"), nullable=False)
    price: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    currency: Mapped["Currency"] = relationship("Currency", back_populates="currency_details")


class PaymentRequest(Base, BaseEntityMixin):
    __tablename__ = "payment_requests"

    amount: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    is_pay: Mapped[bool] = mapped_column(Boolean, default=False)
    pay_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    authority: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    approval: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    card_pan: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    card_hash: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    wage: Mapped[int] = mapped_column(Integer, default=0)
    identifier_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    ref_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_paying: Mapped[bool] = mapped_column(Boolean, default=False)
    wage_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    result_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    mobile: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fee_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    order_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="SET NULL"), nullable=True)

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], back_populates="payment_requests")
    order: Mapped["OrderModel"] = relationship("OrderModel", back_populates="payment_requests")


class Receipt(Base, BaseEntityMixin):
    __tablename__ = "receipts"

    price: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    paya: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    deposit_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reference_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    destination_bank: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tab: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    order_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="SET NULL"), nullable=False)

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], back_populates="receipts")
    order: Mapped["OrderModel"] = relationship("OrderModel", back_populates="receipts")


class Transaction(Base, BaseEntityMixin):
    __tablename__ = "transactions"

    amount: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    customer_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id", ondelete="SET NULL"), nullable=True)


class Wallet(Base, BaseEntityMixin):
    __tablename__ = "wallets"

    amount: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    customer_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id", ondelete="SET NULL"), nullable=True)

    wallet_transfers: Mapped[list["WalletTransfer"]] = relationship("WalletTransfer", back_populates="wallet", lazy="selectin")


class WalletTransfer(Base, BaseEntityMixin):
    __tablename__ = "wallet_transfers"

    wallet_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("wallets.id", ondelete="CASCADE"), nullable=False)
    amount: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    wallet: Mapped[Wallet] = relationship("Wallet", back_populates="wallet_transfers")


class WarehouseMovement(Base, BaseEntityMixin):
    __tablename__ = "warehouse_movements"

    title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, default=0)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False)

    product: Mapped["Product"] = relationship("Product")