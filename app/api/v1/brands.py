"""Brand API routes — list, CRUD."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.dependencies import get_admin_user, require_any_role
from app.models.identity import User
from app.schemas.product import BrandCreate, BrandResponse
from app.services import product_service

router = APIRouter(prefix="/brands", tags=["Brands"])


@router.get("", response_model=list[BrandResponse])
async def get_brands(db: AsyncSession = Depends(get_db)):
    brands = await product_service.get_all_brands(db)
    return [
        BrandResponse(id=b.id, name=b.name, count=b.count)
        for b in brands
    ]


@router.get("/{brand_id}", response_model=BrandResponse)
async def get_brand(brand_id: str, db: AsyncSession = Depends(get_db)):
    try:
        bid = uuid.UUID(brand_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid brand ID")
    brand = await product_service.get_brand_by_id(db, bid)
    if brand is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found")
    return BrandResponse(id=brand.id, name=brand.name, count=brand.count)


@router.post("", response_model=BrandResponse, status_code=status.HTTP_201_CREATED)
async def create_brand(
    request: BrandCreate,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    brand = await product_service.create_brand(db, request, current_user.id)
    return BrandResponse(id=brand.id, name=brand.name, count=brand.count)


@router.delete("/{brand_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_brand(
    brand_id: str,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        bid = uuid.UUID(brand_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid brand ID")
    brand = await product_service.get_brand_by_id(db, bid)
    if brand is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found")
    brand.is_removed = True