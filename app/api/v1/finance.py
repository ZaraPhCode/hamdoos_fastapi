"""Receipt & Currency API routes."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.dependencies import get_current_active_user, get_admin_user, require_any_role
from app.models.identity import User
from app.schemas.finance import (
    ReceiptCreate, ReceiptResponse, ReceiptConfirm, PaginatedResponse,
    CurrencyCreate, CurrencyResponse, CurrencyDetailCreate, CurrencyDetailResponse,
)
from app.services import finance_service

router = APIRouter(prefix="/finance", tags=["Finance"])


# ── Receipts ──

@router.post("/receipts", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_receipt(
    request: ReceiptCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    receipt = await finance_service.create_receipt(db, request, current_user.id)
    return finance_service.build_receipt_response(receipt)


@router.get("/receipts", response_model=PaginatedResponse)
async def get_user_receipts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    receipts, total = await finance_service.get_user_receipts(db, current_user.id, page, page_size)
    items = [finance_service.build_receipt_response(r) for r in receipts]
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size, total_pages=(total + page_size - 1) // page_size)


@router.get("/receipts/admin/all", response_model=PaginatedResponse)
async def get_all_receipts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None),
    current_user: User = Depends(require_any_role("Admin", "Financial Manager")),
    db: AsyncSession = Depends(get_db),
):
    receipts, total = await finance_service.get_all_receipts(db, page, page_size, status_filter)
    items = [finance_service.build_receipt_response(r) for r in receipts]
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size, total_pages=(total + page_size - 1) // page_size)


@router.put("/receipts/{receipt_id}/confirm", response_model=dict)
async def confirm_receipt(
    receipt_id: str,
    request: ReceiptConfirm,
    current_user: User = Depends(require_any_role("Admin", "Financial Manager")),
    db: AsyncSession = Depends(get_db),
):
    try:
        rid = uuid.UUID(receipt_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid receipt ID")
    receipt = await finance_service.confirm_receipt(db, rid, request.status)
    if not receipt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receipt not found")
    return finance_service.build_receipt_response(receipt)


# ── Currencies ──

@router.get("/currencies", response_model=list[CurrencyResponse])
async def get_currencies(db: AsyncSession = Depends(get_db)):
    currencies = await finance_service.get_all_currencies(db)
    result = []
    for c in currencies:
        last_price = getattr(c, '_last_price', None)
        result.append(CurrencyResponse(
            id=c.id,
            name=c.name,
            last_price=float(last_price.price) if last_price and last_price.price else None,
            last_price_date=last_price.date if last_price else None,
        ))
    return result


@router.post("/currencies", response_model=CurrencyResponse, status_code=status.HTTP_201_CREATED)
async def create_currency(
    name: str = Query(...),
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    currency = await finance_service.create_currency(db, name, current_user.id)
    return CurrencyResponse(id=currency.id, name=currency.name)


@router.post("/currencies/{currency_id}/price", response_model=CurrencyDetailResponse)
async def add_currency_price(
    currency_id: str,
    request: CurrencyDetailCreate,
    current_user: User = Depends(require_any_role("Admin", "Financial Manager")),
    db: AsyncSession = Depends(get_db),
):
    try:
        cid = uuid.UUID(currency_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid currency ID")
    detail = await finance_service.add_currency_price(db, cid, request.price, request.date)
    return CurrencyDetailResponse(
        id=detail.id, currency_id=detail.currency_id,
        price=float(detail.price) if detail.price else None,
        date=detail.date,
    )


@router.get("/currencies/{currency_id}/history", response_model=list[CurrencyDetailResponse])
async def get_currency_history(
    currency_id: str,
    limit: int = Query(30, le=100),
    db: AsyncSession = Depends(get_db),
):
    try:
        cid = uuid.UUID(currency_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid currency ID")
    details = await finance_service.get_currency_history(db, cid, limit)
    return [
        CurrencyDetailResponse(
            id=d.id, currency_id=d.currency_id,
            price=float(d.price) if d.price else None,
            date=d.date,
        )
        for d in details
    ]