"""SEO API routes — JSON-LD structured data, sitemap, meta tags."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.product import Product, Category, Brand
from app.models.identity import User
from app.services.seo_service import (
    ProductSchema, Offer, Brand as BrandSchema, AggregateRating,
    OrganizationSchema, WebsiteSchema, SearchAction,
    StoreSchema, PostalAddress, ContactPoint,
    BreadcrumbSchema, breadcrumb_item,
    CollectionPageSchema,
)

router = APIRouter(tags=["SEO"])


@router.get("/seo/product/{product_id}", response_model=dict)
async def get_product_schema(
    product_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Generate JSON-LD structured data for a product page."""
    try:
        pid = uuid.UUID(product_id)
    except ValueError:
        return PlainTextResponse("Invalid product ID", status_code=404)

    stmt = (
        select(Product)
        .options(selectinload(Product.category), selectinload(Product.brand))
        .where(Product.id == pid, Product.is_removed == False)
    )
    result = await db.execute(stmt)
    product = result.unique().scalar_one_or_none()
    if not product:
        return PlainTextResponse("Product not found", status_code=404)

    base_url = str(request.base_url).rstrip("/")
    product_url = f"{base_url}/products/{product.slug or product.id}"

    schema = ProductSchema(
        name=product.name,
        description=product.short_description or product.introduction,
        sku=product.part_number,
        image=product.medium_image_url or product.large_image_url,
        url=product_url,
        model=product.model,
        brand=BrandSchema(name=product.brand.name) if product.brand else None,
        category=product.category.title if product.category else None,
        offers=Offer(
            price=float(product.price_after_discount or product.price or 0),
            price_currency="IRR",
            url=product_url,
            availability="https://schema.org/InStock" if (product.stock_quantity or 0) > 0 else "https://schema.org/OutOfStock",
        ),
        aggregate_rating=AggregateRating(
            rating_value=float(product.rate or 0),
            review_count=0,
        ) if product.rate and product.rate > 0 else None,
    )
    return schema.to_dict()


@router.get("/seo/organization", response_model=dict)
async def get_organization_schema(request: Request):
    """Generate JSON-LD structured data for the organization."""
    base_url = str(request.base_url).rstrip("/")
    schema = OrganizationSchema(
        name="آشا شاپ",
        url=base_url,
        logo=f"{base_url}/static/img/logo.png",
        contact_point=ContactPoint(
            telephone="+9821-12345678",
            contact_type="customer service",
        ),
        same_as=[
            "https://www.instagram.com/asha.shop",
            "https://t.me/asha_shop",
        ],
    )
    return schema.to_dict()


@router.get("/seo/website", response_model=dict)
async def get_website_schema(request: Request):
    """Generate JSON-LD structured data for the website."""
    base_url = str(request.base_url).rstrip("/")
    schema = WebsiteSchema(
        name="آشا شاپ",
        url=base_url,
        search_action=SearchAction(
            target=f"{base_url}/search?q={{search_term_string}}",
        ),
    )
    return schema.to_dict()


@router.get("/seo/breadcrumb", response_model=dict)
async def get_breadcrumb_schema(
    category_id: Optional[str] = Query(None),
    product_id: Optional[str] = Query(None),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """Generate JSON-LD BreadcrumbList."""
    base_url = str(request.base_url).rstrip("/")
    items = [breadcrumb_item(1, "خانه", base_url)]

    position = 2
    if category_id:
        try:
            cid = uuid.UUID(category_id)
            stmt = select(Category).where(Category.id == cid)
            result = await db.execute(stmt)
            category = result.scalar_one_or_none()
            if category:
                items.append(breadcrumb_item(position, category.title or "", f"{base_url}/categories/{category.slug or category.id}"))
                position += 1
        except ValueError:
            pass

    if product_id:
        try:
            pid = uuid.UUID(product_id)
            stmt = select(Product).where(Product.id == pid)
            result = await db.execute(stmt)
            product = result.scalar_one_or_none()
            if product:
                items.append(breadcrumb_item(position, product.name, f"{base_url}/products/{product.slug or product.id}"))
        except ValueError:
            pass

    schema = BreadcrumbSchema(item_list_element=items)
    return schema.to_dict()


@router.get("/seo/category/{category_id}", response_model=dict)
async def get_category_schema(
    category_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Generate JSON-LD for a category page."""
    try:
        cid = uuid.UUID(category_id)
    except ValueError:
        return PlainTextResponse("Invalid category ID", status_code=404)

    stmt = select(Category).where(Category.id == cid, Category.is_removed == False)
    result = await db.execute(stmt)
    category = result.scalar_one_or_none()
    if not category:
        return PlainTextResponse("Category not found", status_code=404)

    base_url = str(request.base_url).rstrip("/")
    schema = CollectionPageSchema(
        name=category.title or "",
        description=category.description,
        url=f"{base_url}/categories/{category.slug or category.id}",
    )
    return schema.to_dict()


@router.get("/sitemap.xml", response_class=PlainTextResponse)
async def get_sitemap(request: Request, db: AsyncSession = Depends(get_db)):
    """Generate XML sitemap."""
    base_url = str(request.base_url).rstrip("/")
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
        f"  <url><loc>{base_url}/</loc><priority>1.0</priority></url>",
    ]
    stmt = select(Product.id, Product.slug, Product.update_date).where(
        Product.is_removed == False, Product.no_display == False
    )
    result = await db.execute(stmt)
    products = result.all()
    for p in products:
        slug = p.slug or str(p.id)
        lastmod = p.update_date.strftime("%Y-%m-%d") if p.update_date else ""
        lines.append(f'  <url><loc>{base_url}/products/{slug}</loc><lastmod>{lastmod}</lastmod><priority>0.8</priority></url>')

    # Categories
    cat_stmt = select(Category.id, Category.slug, Category.update_date).where(
        Category.is_removed == False, Category.no_display == False
    )
    cat_result = await db.execute(cat_stmt)
    categories = cat_result.all()
    for c in categories:
        slug = c.slug or str(c.id)
        lines.append(f'  <url><loc>{base_url}/categories/{slug}</loc><priority>0.6</priority></url>')

    lines.append("</urlset>")
    return PlainTextResponse("\n".join(lines), media_type="application/xml")


@router.get("/robots.txt", response_class=PlainTextResponse)
async def get_robots(request: Request):
    """Generate robots.txt."""
    base_url = str(request.base_url).rstrip("/")
    content = f"""User-agent: *
Allow: /
Disallow: /administration/
Disallow: /api/
Disallow: /cart/
Disallow: /account/

Sitemap: {base_url}/sitemap.xml
"""
    return PlainTextResponse(content, media_type="text/plain")