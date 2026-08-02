"""Category API routes — tree, detail, products by category, CRUD."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.dependencies import get_admin_user, require_any_role
from app.models.identity import User
from app.schemas.product import (
    CategoryCreate, CategoryUpdate, CategoryResponse,
    ProductListResponse, PaginatedResponse,
)
from app.services import product_service

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.get("", response_model=list[CategoryResponse])
async def get_categories(db: AsyncSession = Depends(get_db)):
    categories = await product_service.get_category_tree(db)
    return _build_category_tree(categories)


@router.get("/flat", response_model=list[CategoryResponse])
async def get_categories_flat(db: AsyncSession = Depends(get_db)):
    categories = await product_service.get_all_categories_flat(db)
    return [CategoryResponse(
        id=c.id,
        title=c.title,
        en_title=c.en_title,
        description=c.description,
        slug=c.slug,
        keywords=c.keywords,
        meta_description=c.meta_description,
        is_disable=c.is_disable,
        priority=c.priority,
        poster_image_url=c.poster_image_url,
        no_display=c.no_display,
        parent_category_id=c.parent_category_id,
        product_count=c.product_count,
        insert_date=c.insert_date,
        children=[],
    ) for c in categories]


@router.get("/{category_id}", response_model=CategoryResponse)
async def get_category(category_id: str, db: AsyncSession = Depends(get_db)):
    try:
        cid = uuid.UUID(category_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid category ID")
    category = await product_service.get_category_by_id(db, cid)
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    return _single_category_response(category)


@router.get("/{category_id}/products", response_model=PaginatedResponse)
async def get_category_products(
    category_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    try:
        cid = uuid.UUID(category_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid category ID")
    products, total = await product_service.get_products_by_category(db, cid, page, page_size)
    items = [product_service._build_product_list_response(p) for p in products]
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


# ── Admin CRUD ──

@router.post("", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category(
    request: CategoryCreate,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    category = await product_service.create_category(db, request, current_user.id)
    return _single_category_response(category)


@router.put("/{category_id}", response_model=CategoryResponse)
async def update_category(
    category_id: str,
    request: CategoryUpdate,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    try:
        cid = uuid.UUID(category_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid category ID")
    category = await product_service.get_category_by_id(db, cid)
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    category = await product_service.update_category(db, category, request)
    return _single_category_response(category)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: str,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        cid = uuid.UUID(category_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid category ID")
    category = await product_service.get_category_by_id(db, cid)
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    await product_service.delete_category(db, category)


# ── Helpers ──

def _build_category_tree(categories: list) -> list[CategoryResponse]:
    return [
        CategoryResponse(
            id=c.id,
            title=c.title,
            en_title=c.en_title,
            description=c.description,
            slug=c.slug,
            keywords=c.keywords,
            meta_description=c.meta_description,
            is_disable=c.is_disable,
            priority=c.priority,
            poster_image_url=c.poster_image_url,
            no_display=c.no_display,
            parent_category_id=c.parent_category_id,
            product_count=c.product_count,
            insert_date=c.insert_date,
            children=_build_category_tree(c.children),
        )
        for c in categories
        if not c.is_removed and not c.no_display
    ]


def _single_category_response(c: object) -> CategoryResponse:
    return CategoryResponse(
        id=c.id,
        title=c.title,
        en_title=c.en_title,
        description=c.description,
        slug=c.slug,
        keywords=c.keywords,
        meta_description=c.meta_description,
        is_disable=c.is_disable,
        priority=c.priority,
        poster_image_url=c.poster_image_url,
        no_display=c.no_display,
        parent_category_id=c.parent_category_id,
        product_count=c.product_count,
        insert_date=c.insert_date,
        children=_build_category_tree(getattr(c, 'children', []) or []),
    )