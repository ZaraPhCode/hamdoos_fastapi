"""Wallet API routes — balance, transfers, admin management."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.dependencies import get_current_active_user, get_admin_user, require_any_role
from app.models.identity import User
from app.schemas.finance import (
    WalletResponse, WalletTransferCreate, WalletTransferResponse, PaginatedResponse,
)
from app.services import finance_service

router = APIRouter(prefix="/wallet", tags=["Wallet"])


@router.get("", response_model=dict)
async def get_wallet(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    wallet = await finance_service.get_wallet_balance(db, current_user.id)
    return finance_service.build_wallet_response(wallet)


@router.get("/transfers", response_model=PaginatedResponse)
async def get_transfers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    transfers, total = await finance_service.get_wallet_transfers(db, current_user.id, page, page_size)
    items = [
        {
            "id": str(t.id),
            "wallet_id": str(t.wallet_id),
            "amount": float(t.amount or 0),
            "status": t.status,
            "insert_date": t.insert_date,
        }
        for t in transfers
    ]
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size, total_pages=(total + page_size - 1) // page_size)


@router.post("/credit", response_model=dict)
async def credit_wallet(
    amount: float = Query(..., gt=0),
    description: str = Query(""),
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    wallet = await finance_service.credit_wallet(db, current_user.id, amount, description)
    return finance_service.build_wallet_response(wallet)


@router.post("/debit", response_model=dict)
async def debit_wallet(
    amount: float = Query(..., gt=0),
    description: str = Query(""),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        wallet = await finance_service.debit_wallet(db, current_user.id, amount, description)
        return finance_service.build_wallet_response(wallet)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))