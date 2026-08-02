"""Order API routes — list, detail, status tracking, admin management."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.dependencies import get_current_active_user, get_admin_user, require_any_role
from app.models.identity import User
from app.schemas.order import OrderResponse, OrderStatusUpdate, PaginatedResponse
from app.services import order_service

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.get("", response_model=PaginatedResponse)
async def get_user_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    orders, total = await order_service.get_user_orders(db, current_user.id, page, page_size)
    items = [order_service.build_order_response(o) for o in orders]
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        oid = uuid.UUID(order_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid order ID")
    order = await order_service.get_order_by_id(db, oid)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if order.user_id != current_user.id and "Admin" not in {ur.role.name for ur in current_user.roles}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your order")
    return order_service.build_order_response(order)


# ── Admin endpoints ──

@router.get("/admin/all", response_model=PaginatedResponse)
async def get_all_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None),
    current_user: User = Depends(require_any_role("Admin", "Orders Manager", "Orders Officer")),
    db: AsyncSession = Depends(get_db),
):
    orders, total = await order_service.get_all_orders(db, page, page_size, status_filter)
    items = [order_service.build_order_response(o) for o in orders]
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.put("/{order_id}/status", response_model=OrderResponse)
async def update_order_status(
    order_id: str,
    request: OrderStatusUpdate,
    current_user: User = Depends(require_any_role("Admin", "Orders Manager")),
    db: AsyncSession = Depends(get_db),
):
    try:
        oid = uuid.UUID(order_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid order ID")
    order = await order_service.get_order_by_id(db, oid)
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    order = await order_service.update_order_status(db, order, request)
    return order_service.build_order_response(order)