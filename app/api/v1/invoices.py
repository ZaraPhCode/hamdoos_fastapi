"""Invoice API routes — CRUD for invoices, invoice products, and suppliers."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.dependencies import get_admin_user, get_current_active_user, require_any_role
from app.models.identity import User
from app.schemas.invoice import (
    InvoiceCreate, InvoiceResponse, InvoiceListResponse,
    PaginatedResponse,
    SupplierCreate, SupplierResponse,
)
from app.services import invoice_service

router = APIRouter(prefix="/invoices", tags=["Invoices"])


# ── User Invoice Endpoints ──

@router.get("", response_model=PaginatedResponse)
async def get_user_invoices(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    invoices, total = await invoice_service.get_user_invoices(db, current_user.id, page, page_size)
    items = [invoice_service.build_invoice_response(inv) for inv in invoices]
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size, total_pages=(total + page_size - 1) // page_size)


@router.get("/{invoice_id}", response_model=dict)
async def get_invoice(
    invoice_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        iid = uuid.UUID(invoice_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid invoice ID")
    invoice = await invoice_service.get_invoice_by_id(db, iid)
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    if invoice.user_id != current_user.id and "Admin" not in {ur.role.name for ur in current_user.roles}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your invoice")
    return invoice_service.build_invoice_response(invoice)


# ── Admin Invoice Endpoints ──

@router.get("/admin/all", response_model=PaginatedResponse)
async def get_all_invoices(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    type_filter: Optional[str] = Query(None),
    current_user: User = Depends(require_any_role("Admin", "Financial Manager")),
    db: AsyncSession = Depends(get_db),
):
    invoices, total = await invoice_service.get_all_invoices(db, page, page_size, type_filter)
    items = [invoice_service.build_invoice_response(inv) for inv in invoices]
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size, total_pages=(total + page_size - 1) // page_size)


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_invoice(
    request: InvoiceCreate,
    current_user: User = Depends(require_any_role("Admin", "Financial Manager")),
    db: AsyncSession = Depends(get_db),
):
    try:
        invoice = await invoice_service.create_invoice(db, request, current_user.id)
        return invoice_service.build_invoice_response(invoice)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/from-order/{order_id}", response_model=dict)
async def create_invoice_from_order(
    order_id: str,
    current_user: User = Depends(require_any_role("Admin", "Financial Manager")),
    db: AsyncSession = Depends(get_db),
):
    try:
        oid = uuid.UUID(order_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid order ID")
    invoice = await invoice_service.create_invoice_from_order(db, oid)
    if not invoice:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Order not found or invoice already exists")
    return invoice_service.build_invoice_response(invoice)


# ── Supplier Endpoints ──

@router.get("/suppliers", response_model=list[SupplierResponse])
async def get_suppliers(
    current_user: User = Depends(require_any_role("Admin", "Financial Manager", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    suppliers = await invoice_service.get_all_suppliers(db)
    return [SupplierResponse(id=s.id, telephone=s.telephone, address=s.address, site=s.site, intermediary_name=s.intermediary_name) for s in suppliers]


@router.post("/suppliers", response_model=SupplierResponse, status_code=status.HTTP_201_CREATED)
async def create_supplier(
    request: SupplierCreate,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    supplier = await invoice_service.create_supplier(db, request, current_user.id)
    return SupplierResponse(id=supplier.id, telephone=supplier.telephone, address=supplier.address, site=supplier.site, intermediary_name=supplier.intermediary_name)