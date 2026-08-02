"""Warehouse business logic — inventory movements, stock tracking."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.finance import WarehouseMovement
from app.models.product import Product


async def create_movement(
    db: AsyncSession, request, user_id: uuid.UUID
) -> WarehouseMovement:
    """Record a warehouse movement (import/export)."""
    # Verify product exists
    product = await db.get(Product, request.product_id)
    if not product or product.is_removed:
        raise ValueError("Product not found")

    movement = WarehouseMovement(
        id=uuid.uuid4(),
        product_id=request.product_id,
        quantity=request.quantity,
        type=request.type or ("Import" if request.quantity > 0 else "Export"),
        title=request.title,
        note=request.note,
        date=request.date or datetime.now(timezone.utc),
        insert_date=datetime.now(timezone.utc),
        update_date=datetime.now(timezone.utc),
    )
    db.add(movement)

    # Update product stock quantity
    product.stock_quantity = (product.stock_quantity or 0) + request.quantity
    product.update_date = datetime.now(timezone.utc)

    await db.flush()
    return movement


async def get_product_movements(
    db: AsyncSession, product_id: uuid.UUID, page: int = 1, page_size: int = 20
) -> tuple[list[WarehouseMovement], int]:
    count_stmt = select(func.count(WarehouseMovement.id)).where(
        WarehouseMovement.product_id == product_id,
        WarehouseMovement.is_removed == False,
    )
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    stmt = (
        select(WarehouseMovement)
        .where(
            WarehouseMovement.product_id == product_id,
            WarehouseMovement.is_removed == False,
        )
        .order_by(WarehouseMovement.date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all()), total


async def get_all_movements(
    db: AsyncSession, page: int = 1, page_size: int = 20, product_id: Optional[uuid.UUID] = None
) -> tuple[list[WarehouseMovement], int]:
    conditions = [WarehouseMovement.is_removed == False]
    if product_id:
        conditions.append(WarehouseMovement.product_id == product_id)

    count_stmt = select(func.count(WarehouseMovement.id)).where(*conditions)
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    stmt = (
        select(WarehouseMovement)
        .options(selectinload(WarehouseMovement.product))
        .where(*conditions)
        .order_by(WarehouseMovement.date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all()), total


async def get_low_stock_products(
    db: AsyncSession, threshold: int = 5
) -> list[dict]:
    """Get products with stock below threshold."""
    stmt = (
        select(Product)
        .where(
            Product.stock_quantity <= threshold,
            Product.is_removed == False,
            Product.no_display == False,
        )
        .order_by(Product.stock_quantity)
        .limit(50)
    )
    result = await db.execute(stmt)
    products = result.scalars().all()
    return [
        {
            "product_id": p.id,
            "product_name": p.name,
            "part_number": p.part_number,
            "current_stock": p.stock_quantity,
            "threshold": threshold,
            "status": "Out of Stock" if p.stock_quantity <= 0 else "Low Stock",
        }
        for p in products
    ]


async def get_product_stock_summary(db: AsyncSession, product_id: uuid.UUID) -> Optional[dict]:
    """Get stock summary for a single product."""
    product = await db.get(Product, product_id)
    if not product or product.is_removed:
        return None

    import_stmt = select(func.coalesce(func.sum(WarehouseMovement.quantity), 0)).where(
        WarehouseMovement.product_id == product_id,
        WarehouseMovement.quantity > 0,
        WarehouseMovement.is_removed == False,
    )
    export_stmt = select(func.coalesce(func.sum(WarehouseMovement.quantity), 0)).where(
        WarehouseMovement.product_id == product_id,
        WarehouseMovement.quantity < 0,
        WarehouseMovement.is_removed == False,
    )

    imported = (await db.execute(import_stmt)).scalar() or 0
    exported = abs((await db.execute(export_stmt)).scalar() or 0)

    last_mvmt = (
        await db.execute(
            select(WarehouseMovement.date)
            .where(WarehouseMovement.product_id == product_id, WarehouseMovement.is_removed == False)
            .order_by(WarehouseMovement.date.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    return {
        "product_id": product.id,
        "product_name": product.name,
        "part_number": product.part_number,
        "current_stock": product.stock_quantity or 0,
        "total_imported": int(imported),
        "total_exported": int(exported),
        "last_movement_date": last_mvmt,
    }


def build_movement_response(movement: WarehouseMovement) -> dict:
    return {
        "id": movement.id,
        "product_id": movement.product_id,
        "product_name": movement.product.name if hasattr(movement, 'product') and movement.product else None,
        "part_number": movement.product.part_number if hasattr(movement, 'product') and movement.product else None,
        "title": movement.title,
        "type": movement.type,
        "note": movement.note,
        "quantity": movement.quantity,
        "date": movement.date,
        "insert_date": movement.insert_date,
    }