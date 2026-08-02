"""Product API routes — list, detail, search, filter, sort, CRUD."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.dependencies import get_current_active_user, get_admin_user, require_any_role
from app.models.identity import User
from app.schemas.product import (
    ProductCreate, ProductUpdate, ProductSearchParams,
    ProductListResponse, ProductDetailResponse, PaginatedResponse,
)
from app.services import product_service

router = APIRouter(prefix="/products", tags=["Products"])


@router.get("", response_model=PaginatedResponse)
async def list_products(
    query: Optional[str] = Query(None),
    category_id: Optional[str] = Query(None),
    brand_id: Optional[str] = Query(None),
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
    on_sale: Optional[bool] = Query(None),
    is_new: Optional[bool] = Query(None),
    is_special: Optional[bool] = Query(None),
    status: Optional[str] = Query(None),
    sort_by: Optional[str] = Query("insert_date"),
    sort_desc: bool = Query(True),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    params = ProductSearchParams(
        query=query,
        category_id=uuid.UUID(category_id) if category_id else None,
        brand_id=uuid.UUID(brand_id) if brand_id else None,
        min_price=min_price,
        max_price=max_price,
        on_sale=on_sale,
        is_new=is_new,
        is_special=is_special,
        status=status,
        sort_by=sort_by,
        sort_desc=sort_desc,
        page=page,
        page_size=page_size,
    )
    products, total = await product_service.search_products(db, params)
    items = [product_service._build_product_list_response(p) for p in products]
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/featured", response_model=list[ProductListResponse])
async def featured_products(
    limit: int = Query(10, le=50),
    db: AsyncSession = Depends(get_db),
):
    products = await product_service.get_featured_products(db, limit)
    return [product_service._build_product_list_response(p) for p in products]


@router.get("/new", response_model=list[ProductListResponse])
async def new_products(
    limit: int = Query(10, le=50),
    db: AsyncSession = Depends(get_db),
):
    products = await product_service.get_new_products(db, limit)
    return [product_service._build_product_list_response(p) for p in products]


@router.get("/best-selling", response_model=list[ProductListResponse])
async def best_selling_products(
    limit: int = Query(10, le=50),
    db: AsyncSession = Depends(get_db),
):
    products = await product_service.get_best_selling_products(db, limit)
    return [product_service._build_product_list_response(p) for p in products]


@router.get("/{product_id}", response_model=ProductDetailResponse)
async def get_product(product_id: str, db: AsyncSession = Depends(get_db)):
    try:
        pid = uuid.UUID(product_id)
    except ValueError:
        # Try slug lookup
        product = await product_service.get_product_by_slug(db, product_id)
        if product is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
        await product_service.increment_product_view(db, product)
        return _build_detail_response(product)

    product = await product_service.get_product_by_id(db, pid)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    await product_service.increment_product_view(db, product)
    return _build_detail_response(product)


@router.get("/{product_id}/related", response_model=list[ProductListResponse])
async def get_related_products(
    product_id: str,
    limit: int = Query(6, le=20),
    db: AsyncSession = Depends(get_db),
):
    try:
        pid = uuid.UUID(product_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid product ID")
    product = await product_service.get_product_by_id(db, pid)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    related = await product_service.get_related_products(db, product, limit)
    return [product_service._build_product_list_response(p) for p in related]


# ── Admin CRUD ──

@router.post("", response_model=ProductDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    request: ProductCreate,
    current_user: User = Depends(require_any_role("Admin", "Product Manager", "Product Officer")),
    db: AsyncSession = Depends(get_db),
):
    product = await product_service.create_product(db, request, current_user.id)
    return _build_detail_response(product)


@router.put("/{product_id}", response_model=ProductDetailResponse)
async def update_product(
    product_id: str,
    request: ProductUpdate,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    try:
        pid = uuid.UUID(product_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid product ID")
    product = await product_service.get_product_by_id(db, pid)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    product = await product_service.update_product(db, product, request)
    return _build_detail_response(product)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: str,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        pid = uuid.UUID(product_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid product ID")
    product = await product_service.get_product_by_id(db, pid)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    await product_service.delete_product(db, product)


def _build_detail_response(product) -> ProductDetailResponse:
    base = product_service._build_product_list_response(product)
    detail = ProductDetailResponse(
        **base.model_dump(),
        introduction=product.introduction,
        keywords=product.keywords,
        meta_description=product.meta_description,
        concatenated=product.concatenated,
        en_concatenated=product.en_concatenated,
        min_purchase=product.minimum_purchase,
        max_purchases=product.max_number_of_purchases,
        delivery_day=product.delivery_day,
        release_date=product.release_date,
        tax_unique_id=product.tax_unique_id,
        vat_rate=float(product.vat_rate) if product.vat_rate else None,
        taxes_and_duties=float(product.taxes_and_duties) if product.taxes_and_duties else None,
        total_amount_plus_taxes=float(product.total_amount_plus_taxes) if product.total_amount_plus_taxes else None,
        currency_price=float(product.currency_price) if product.currency_price else None,
        profit_rate=float(product.profit_rate) if product.profit_rate else None,
        max_price=float(product.max_price) if product.max_price else None,
        product_type_id=product.product_type_id,
        product_unit_id=product.product_unit_id,
        currency_id=product.currency_id,
        no_display=product.no_display,
        images=[
            {
                "id": img.id,
                "medium_image_url": img.medium_image_url,
                "small_image_url": img.small_image_url,
                "large_image_url": img.large_image_url,
                "title": img.title,
                "display_photo": img.display_photo,
                "picture_order": img.picture_order,
            }
            for img in (product.product_images or [])
        ] if hasattr(product, 'product_images') else [],
        varieties=[
            {
                "id": v.id,
                "part_number": v.part_number,
                "stock_quantity": v.stock_quantity,
                "price": float(v.price) if v.price else None,
                "price_after_discount": float(v.price_after_discount) if v.price_after_discount else None,
                "discount_amount": float(v.discount_amount) if v.discount_amount else None,
                "currency_price": float(v.currency_price) if v.currency_price else None,
                "minimum_purchase": v.minimum_purchase,
                "place": v.place,
                "product_varieties": [
                    {
                        "id": pv.id,
                        "category_option_id": pv.category_option_id,
                        "value": pv.value,
                        "category_option_name": pv.category_option.name if pv.category_option else None,
                    }
                    for pv in (v.product_varieties or [])
                ] if hasattr(v, 'product_varieties') else [],
            }
            for v in (product.varieties or [])
        ] if hasattr(product, 'varieties') else [],
        related_products=[
            product_service._build_product_list_response(rp.relate_product)
            for rp in (product.related_products or [])
            if hasattr(rp, 'relate_product') and rp.relate_product and not rp.is_removed
        ] if hasattr(product, 'related_products') else [],
        similar_products=[
            product_service._build_product_list_response(sp.similar)
            for sp in (product.similar_products or [])
            if hasattr(sp, 'similar') and sp.similar and not sp.is_removed
        ] if hasattr(product, 'similar_products') else [],
        technical_features=[],
    )
    return detail