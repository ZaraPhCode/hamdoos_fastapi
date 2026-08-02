"""Pydantic schemas for warehouse (inventory movements)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class WarehouseMovementCreate(BaseModel):
    product_id: UUID
    quantity: int = Field(..., description="Positive = import, Negative = export")
    type: Optional[str] = "Import"
    title: Optional[str] = None
    note: Optional[str] = None
    date: Optional[datetime] = None


class WarehouseMovementResponse(BaseModel):
    id: UUID
    product_id: UUID
    product_name: Optional[str] = None
    part_number: Optional[str] = None
    title: Optional[str] = None
    type: Optional[str] = None
    note: Optional[str] = None
    quantity: int = 0
    date: Optional[datetime] = None
    insert_date: Optional[datetime] = None

    model_config = {"from_attributes": True}


class StockAlertResponse(BaseModel):
    product_id: UUID
    product_name: str
    part_number: Optional[str] = None
    current_stock: int = 0
    threshold: int = 5
    status: str = "Low Stock"


class ProductStockResponse(BaseModel):
    product_id: UUID
    product_name: str
    part_number: Optional[str] = None
    current_stock: int = 0
    total_imported: int = 0
    total_exported: int = 0
    last_movement_date: Optional[datetime] = None


class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    page_size: int
    total_pages: int