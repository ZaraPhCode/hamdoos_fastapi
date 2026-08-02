"""Purchase Order API routes — CRUD for purchase orders."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.dependencies import get_admin_user, require_any_role
from app.models.identity import User
from app.schemas.invoice import PurchaseOrderCreate, PurchaseOrderResponse, PaginatedResponse
from app.services import invoice_service

router = APIRouter(prefix="/purchase-orders", tags=["Purchase Orders"])


@router.get("", response_model=PaginatedResponse)
async def get_purchase_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(require_any_role("Admin", "Financial Manager", "Warehouse Keeper")),
    db: AsyncSession = Depends(get_db),
):
    pos, total = await invoice_service.get_all_purchase_orders(db, page, page_size)
    items = [invoice_service.build_purchase_order_response(po) for po in pos]
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size, total_pages=(total + page_size - 1) // page_size)


@router.get("/{po_id}", response_model=dict)
async def get_purchase_order(
    po_id: str,
    current_user: User = Depends(require_any_role("Admin", "Financial Manager", "Warehouse Keeper")),
    db: AsyncSession = Depends(get_db),
):
    try:
        pid = uuid.UUID(po_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid purchase order ID")
    po = await invoice_service.get_purchase_order_by_id(db, pid)
    if not po:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Purchase order not found")
    return invoice_service.build_purchase_order_response(po)


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_purchase_order(
    request: PurchaseOrderCreate,
    current_user: User = Depends(require_any_role("Admin", "Financial Manager")),
    db: AsyncSession = Depends(get_db),
):
    try:
        po = await invoice_service.create_purchase_order(db, request, current_user.id)
        return invoice_service.build_purchase_order_response(po)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))