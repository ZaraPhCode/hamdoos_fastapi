"""Warehouse API routes — inventory movements, stock management."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.dependencies import get_admin_user, require_any_role
from app.models.identity import User
from app.schemas.warehouse import (
    WarehouseMovementCreate, WarehouseMovementResponse,
    StockAlertResponse, ProductStockResponse, PaginatedResponse,
)
from app.services import warehouse_service

router = APIRouter(prefix="/warehouse", tags=["Warehouse"])


@router.post("/movements", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_movement(
    request: WarehouseMovementCreate,
    current_user: User = Depends(require_any_role("Admin", "Warehouse Keeper", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    """Record a warehouse movement (import/export). Positive quantity = Import, negative = Export."""
    try:
        movement = await warehouse_service.create_movement(db, request, current_user.id)
        return warehouse_service.build_movement_response(movement)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/movements", response_model=PaginatedResponse)
async def get_movements(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    product_id: Optional[str] = Query(None),
    current_user: User = Depends(require_any_role("Admin", "Warehouse Keeper", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    pid = uuid.UUID(product_id) if product_id else None
    movements, total = await warehouse_service.get_all_movements(db, page, page_size, pid)
    items = [warehouse_service.build_movement_response(m) for m in movements]
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size, total_pages=(total + page_size - 1) // page_size)


@router.get("/products/{product_id}/movements", response_model=PaginatedResponse)
async def get_product_movements(
    product_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_any_role("Admin", "Warehouse Keeper", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    try:
        pid = uuid.UUID(product_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid product ID")
    movements, total = await warehouse_service.get_product_movements(db, pid, page, page_size)
    items = [warehouse_service.build_movement_response(m) for m in movements]
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size, total_pages=(total + page_size - 1) // page_size)


@router.get("/products/{product_id}/stock", response_model=dict)
async def get_product_stock(
    product_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        pid = uuid.UUID(product_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid product ID")
    summary = await warehouse_service.get_product_stock_summary(db, pid)
    if not summary:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return summary


@router.get("/alerts/low-stock", response_model=list[dict])
async def get_low_stock_alerts(
    threshold: int = Query(5, ge=1),
    current_user: User = Depends(require_any_role("Admin", "Warehouse Keeper", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    alerts = await warehouse_service.get_low_stock_products(db, threshold)
    return alerts


@router.post("/import", response_model=dict, status_code=status.HTTP_201_CREATED)
async def import_stock(
    product_id: str = Query(...),
    quantity: int = Query(..., gt=0),
    title: Optional[str] = Query(None),
    note: Optional[str] = Query(None),
    current_user: User = Depends(require_any_role("Admin", "Warehouse Keeper")),
    db: AsyncSession = Depends(get_db),
):
    """Quick import stock (positive adjustment)."""
    from app.schemas.warehouse import WarehouseMovementCreate
    try:
        pid = uuid.UUID(product_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid product ID")
    request = WarehouseMovementCreate(product_id=pid, quantity=quantity, type="Import", title=title, note=note)
    movement = await warehouse_service.create_movement(db, request, current_user.id)
    return warehouse_service.build_movement_response(movement)


@router.post("/export", response_model=dict, status_code=status.HTTP_201_CREATED)
async def export_stock(
    product_id: str = Query(...),
    quantity: int = Query(..., gt=0),
    title: Optional[str] = Query(None),
    note: Optional[str] = Query(None),
    current_user: User = Depends(require_any_role("Admin", "Warehouse Keeper")),
    db: AsyncSession = Depends(get_db),
):
    """Quick export stock (negative adjustment)."""
    from app.schemas.warehouse import WarehouseMovementCreate
    try:
        pid = uuid.UUID(product_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid product ID")
    request = WarehouseMovementCreate(product_id=pid, quantity=-quantity, type="Export", title=title, note=note)
    movement = await warehouse_service.create_movement(db, request, current_user.id)
    return warehouse_service.build_movement_response(movement)