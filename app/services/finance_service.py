"""Finance business logic — wallets, receipts, currency, transactions."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.finance import (
    Wallet, WalletTransfer, Receipt, Transaction,
    CurrencyDetail,
)
from app.models.product import Currency
from app.models.identity import User


# ── Currency ──

async def get_all_currencies(db: AsyncSession) -> list[Currency]:
    stmt = select(Currency).where(Currency.is_removed == False).order_by(Currency.name)
    result = await db.execute(stmt)
    currencies = result.scalars().all()
    # Load latest price for each
    for c in currencies:
        detail_stmt = (
            select(CurrencyDetail)
            .where(CurrencyDetail.currency_id == c.id, CurrencyDetail.is_removed == False)
            .order_by(CurrencyDetail.insert_date.desc())
            .limit(1)
        )
        detail_result = await db.execute(detail_stmt)
        detail = detail_result.scalar_one_or_none()
        c._last_price = detail
    return list(currencies)


async def create_currency(db: AsyncSession, name: str, user_id: uuid.UUID) -> Currency:
    currency = Currency(
        id=uuid.uuid4(),
        name=name,
        insert_date=datetime.now(timezone.utc),
        update_date=datetime.now(timezone.utc),
    )
    db.add(currency)
    await db.flush()
    return currency


async def add_currency_price(db: AsyncSession, currency_id: uuid.UUID, price: float, date: Optional[datetime] = None) -> CurrencyDetail:
    detail = CurrencyDetail(
        id=uuid.uuid4(),
        currency_id=currency_id,
        price=price,
        date=date or datetime.now(timezone.utc),
        insert_date=datetime.now(timezone.utc),
        update_date=datetime.now(timezone.utc),
    )
    db.add(detail)
    await db.flush()
    return detail


async def get_currency_history(db: AsyncSession, currency_id: uuid.UUID, limit: int = 30) -> list[CurrencyDetail]:
    stmt = (
        select(CurrencyDetail)
        .where(CurrencyDetail.currency_id == currency_id, CurrencyDetail.is_removed == False)
        .order_by(CurrencyDetail.insert_date.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


# ── Wallet ──

async def get_or_create_wallet(db: AsyncSession, user_id: uuid.UUID) -> Wallet:
    stmt = select(Wallet).where(Wallet.customer_id == user_id, Wallet.is_removed == False)
    result = await db.execute(stmt)
    wallet = result.scalar_one_or_none()
    if not wallet:
        wallet = Wallet(
            id=uuid.uuid4(),
            amount=0,
            customer_id=user_id,
            insert_date=datetime.now(timezone.utc),
            update_date=datetime.now(timezone.utc),
        )
        db.add(wallet)
        await db.flush()
    return wallet


async def get_wallet_balance(db: AsyncSession, user_id: uuid.UUID) -> Wallet:
    return await get_or_create_wallet(db, user_id)


async def credit_wallet(db: AsyncSession, user_id: uuid.UUID, amount: float, description: str = "") -> Wallet:
    wallet = await get_or_create_wallet(db, user_id)
    wallet.amount = (wallet.amount or 0) + amount
    wallet.update_date = datetime.now(timezone.utc)

    transfer = WalletTransfer(
        id=uuid.uuid4(),
        wallet_id=wallet.id,
        amount=amount,
        status="Confirmed",
        insert_date=datetime.now(timezone.utc),
        update_date=datetime.now(timezone.utc),
    )
    db.add(transfer)
    await db.flush()
    return wallet


async def debit_wallet(db: AsyncSession, user_id: uuid.UUID, amount: float, description: str = "") -> Wallet:
    wallet = await get_or_create_wallet(db, user_id)
    if (wallet.amount or 0) < amount:
        raise ValueError("Insufficient wallet balance")
    wallet.amount = (wallet.amount or 0) - amount
    wallet.update_date = datetime.now(timezone.utc)

    transfer = WalletTransfer(
        id=uuid.uuid4(),
        wallet_id=wallet.id,
        amount=-amount,
        status="Confirmed",
        insert_date=datetime.now(timezone.utc),
        update_date=datetime.now(timezone.utc),
    )
    db.add(transfer)
    await db.flush()
    return wallet


async def get_wallet_transfers(
    db: AsyncSession, user_id: uuid.UUID, page: int = 1, page_size: int = 20
) -> tuple[list[WalletTransfer], int]:
    wallet = await get_or_create_wallet(db, user_id)
    count_stmt = select(func.count(WalletTransfer.id)).where(
        WalletTransfer.wallet_id == wallet.id, WalletTransfer.is_removed == False
    )
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    stmt = (
        select(WalletTransfer)
        .where(WalletTransfer.wallet_id == wallet.id, WalletTransfer.is_removed == False)
        .order_by(WalletTransfer.insert_date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all()), total


# ── Receipts ──

async def create_receipt(db: AsyncSession, request, user_id: uuid.UUID) -> Receipt:
    receipt = Receipt(
        id=uuid.uuid4(),
        price=request.price,
        description=request.description,
        paya=request.paya,
        deposit_date=request.deposit_date,
        reference_code=request.reference_code,
        destination_bank=request.destination_bank,
        image_url=request.image_url,
        order_id=request.order_id,
        user_id=user_id,
        status="AwaitingConfirmation",
        insert_date=datetime.now(timezone.utc),
        update_date=datetime.now(timezone.utc),
    )
    db.add(receipt)
    await db.flush()
    return receipt


async def get_user_receipts(
    db: AsyncSession, user_id: uuid.UUID, page: int = 1, page_size: int = 20
) -> tuple[list[Receipt], int]:
    count_stmt = select(func.count(Receipt.id)).where(
        Receipt.user_id == user_id, Receipt.is_removed == False
    )
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    stmt = (
        select(Receipt)
        .where(Receipt.user_id == user_id, Receipt.is_removed == False)
        .order_by(Receipt.insert_date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all()), total


async def get_all_receipts(
    db: AsyncSession, page: int = 1, page_size: int = 20, status_filter: Optional[str] = None
) -> tuple[list[Receipt], int]:
    conditions = [Receipt.is_removed == False]
    if status_filter:
        conditions.append(Receipt.status == status_filter)

    count_stmt = select(func.count(Receipt.id)).where(*conditions)
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    stmt = (
        select(Receipt)
        .where(*conditions)
        .order_by(Receipt.insert_date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all()), total


async def confirm_receipt(db: AsyncSession, receipt_id: uuid.UUID, status: str) -> Optional[Receipt]:
    stmt = select(Receipt).where(Receipt.id == receipt_id, Receipt.is_removed == False)
    result = await db.execute(stmt)
    receipt = result.scalar_one_or_none()
    if not receipt:
        return None
    receipt.status = status
    receipt.update_date = datetime.now(timezone.utc)

    # If confirmed, credit the user's wallet
    if status == "Confirmed" and receipt.user_id and receipt.price:
        try:
            await credit_wallet(db, receipt.user_id, float(receipt.price), f"Receipt: {receipt.reference_code or receipt.id}")
        except ValueError:
            pass

    await db.flush()
    return receipt


# ── Transactions ──

async def get_transactions(
    db: AsyncSession, page: int = 1, page_size: int = 20
) -> tuple[list[Transaction], int]:
    count_stmt = select(func.count(Transaction.id)).where(Transaction.is_removed == False)
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    stmt = (
        select(Transaction)
        .where(Transaction.is_removed == False)
        .order_by(Transaction.insert_date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all()), total


def build_wallet_response(wallet: Wallet) -> dict:
    return {
        "id": wallet.id,
        "amount": float(wallet.amount or 0),
        "customer_id": wallet.customer_id,
        "insert_date": wallet.insert_date,
        "transfers": [],
    }


def build_receipt_response(receipt: Receipt) -> dict:
    return {
        "id": receipt.id,
        "price": float(receipt.price) if receipt.price else None,
        "description": receipt.description,
        "paya": receipt.paya,
        "deposit_date": receipt.deposit_date,
        "reference_code": receipt.reference_code,
        "destination_bank": receipt.destination_bank,
        "image_url": receipt.image_url,
        "status": receipt.status,
        "user_id": receipt.user_id,
        "order_id": receipt.order_id,
        "insert_date": receipt.insert_date,
    }