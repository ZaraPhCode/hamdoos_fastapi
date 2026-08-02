"""Pydantic schemas for finance (wallet, receipts, currency)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ── Currency ──

class CurrencyBase(BaseModel):
    name: str = Field(..., max_length=100)


class CurrencyCreate(CurrencyBase):
    pass


class CurrencyResponse(CurrencyBase):
    id: UUID
    last_price: Optional[float] = None
    last_price_date: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CurrencyDetailCreate(BaseModel):
    currency_id: UUID
    price: float
    date: Optional[datetime] = None


class CurrencyDetailResponse(BaseModel):
    id: UUID
    currency_id: UUID
    price: Optional[float] = None
    date: Optional[datetime] = None
    currency_name: Optional[str] = None

    model_config = {"from_attributes": True}


# ── Wallet ──

class WalletResponse(BaseModel):
    id: UUID
    amount: float = 0
    customer_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    insert_date: Optional[datetime] = None

    model_config = {"from_attributes": True}


class WalletTransferCreate(BaseModel):
    amount: float = Field(..., gt=0)
    description: Optional[str] = None


class WalletTransferResponse(BaseModel):
    id: UUID
    wallet_id: UUID
    amount: Optional[float] = None
    status: Optional[str] = None
    description: Optional[str] = None
    insert_date: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── Receipt ──

class ReceiptCreate(BaseModel):
    price: float = Field(..., gt=0)
    description: Optional[str] = None
    paya: Optional[str] = None
    deposit_date: Optional[datetime] = None
    reference_code: Optional[str] = None
    destination_bank: Optional[str] = None
    image_url: Optional[str] = None
    order_id: Optional[UUID] = None


class ReceiptResponse(BaseModel):
    id: UUID
    price: Optional[float] = None
    description: Optional[str] = None
    paya: Optional[str] = None
    deposit_date: Optional[datetime] = None
    reference_code: Optional[str] = None
    destination_bank: Optional[str] = None
    image_url: Optional[str] = None
    status: Optional[str] = None
    user_id: Optional[UUID] = None
    order_id: Optional[UUID] = None
    insert_date: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ReceiptConfirm(BaseModel):
    status: str = "Confirmed"


# ── Transaction ──

class TransactionResponse(BaseModel):
    id: UUID
    amount: Optional[float] = None
    description: Optional[str] = None
    customer_id: Optional[UUID] = None
    insert_date: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    page_size: int
    total_pages: int