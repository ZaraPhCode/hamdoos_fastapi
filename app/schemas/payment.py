"""Pydantic schemas for payment (ZarinPal)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class PaymentRequestCreate(BaseModel):
    order_id: UUID
    description: Optional[str] = None


class PaymentRequestResponse(BaseModel):
    id: UUID
    order_id: UUID
    amount: float
    authority: Optional[str] = None
    ref_id: Optional[int] = None
    status: Optional[str] = None
    is_paying: bool = False
    gateway_url: Optional[str] = None
    message: Optional[str] = None

    model_config = {"from_attributes": True}


class PaymentVerifyResponse(BaseModel):
    success: bool
    ref_id: Optional[int] = None
    card_pan: Optional[str] = None
    message: str = ""
    order_id: Optional[UUID] = None
    order_status: Optional[str] = None


class PaymentCallbackRequest(BaseModel):
    Authority: str
    Status: str


class PaymentStatusResponse(BaseModel):
    id: UUID
    order_id: UUID
    amount: float
    authority: Optional[str] = None
    ref_id: Optional[int] = None
    status: str
    is_paying: bool
    result_code: Optional[str] = None
    card_pan: Optional[str] = None
    wage: int = 0
    pay_date: Optional[datetime] = None

    model_config = {"from_attributes": True}