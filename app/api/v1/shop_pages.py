"""Public storefront page routes — renders Jinja2 templates for the shop."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.dependencies import get_optional_user, get_current_active_user
from app.models.identity import User
from app.services import product_service, order_service
from app.schemas.product import ProductSearchParams

templates = Jinja2Templates(directory="app/templates")
router = APIRouter(tags=["Shop Pages"])


async def _get_shop_context(request: Request, db: AsyncSession, current_user=None) -> dict:
    from app.services.order_service import get_cart, enrich_cart_with_products
    cart = get_cart(current_user.id) if current_user else None
    cart_count = cart.total_items if cart else 0
    return {
        "request": request,
        "current_user": current_user,
        "cart_count": cart_count,
    }


@router.get("/", response_class=HTMLResponse)
async def home_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    ctx = await _get_shop_context(request, db, current_user)
    try:
        featured = await product_service.get_featured_products(db, 8)
        new_p = await product_service.get_new_products(db, 8)
        best = await product_service.get_best_selling_products(db, 8)
        ctx["featured_products"] = [product_service._build_product_list_response(p) for p in featured]
        ctx["new_products"] = [product_service._build_product_list_response(p) for p in new_p]
        ctx["best_selling_products"] = [product_service._build_product_list_response(p) for p in best]
    except Exception:
        ctx["featured_products"] = ctx["new_products"] = ctx["best_selling_products"] = []
    return templates.TemplateResponse("shop/index.html", ctx)


@router.get("/products", response_class=HTMLResponse)
async def product_list_page(
    request: Request,
    query: str = Query(None),
    category_id: str = Query(None),
    brand_id: str = Query(None),
    sort_by: str = Query("insert_date"),
    sort_desc: bool = Query(True),
    page: int = Query(1),
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    import uuid
    ctx = await _get_shop_context(request, db, current_user)
    params = ProductSearchParams(
        query=query, page=page, page_size=20,
        sort_by=sort_by, sort_desc=sort_desc,
        category_id=uuid.UUID(category_id) if category_id else None,
        brand_id=uuid.UUID(brand_id) if brand_id else None,
    )
    try:
        products, total = await product_service.search_products(db, params)
        cats = await product_service.get_all_categories_flat(db)
        brands = await product_service.get_all_brands(db)
        ctx["products"] = [product_service._build_product_list_response(p) for p in products]
        ctx["categories"] = [{"id": str(c.id), "title": c.title} for c in cats]
        ctx["brands"] = [{"id": str(b.id), "name": b.name} for b in brands]
        ctx["total"] = total
        ctx["page"] = page
        ctx["page_size"] = 20
        ctx["total_pages"] = (total + 19) // 20
        ctx["query"] = query
        ctx["selected_category"] = category_id
        ctx["selected_brand"] = brand_id
        ctx["sort_by"] = sort_by
        ctx["sort_desc"] = sort_desc
    except Exception:
        ctx["products"] = []
        ctx["total"] = 0
    return templates.TemplateResponse("shop/product_list.html", ctx)


@router.get("/products/{slug}", response_class=HTMLResponse)
async def product_detail_page(
    request: Request,
    slug: str,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    import uuid
    ctx = await _get_shop_context(request, db, current_user)
    try:
        pid = uuid.UUID(slug)
        product = await product_service.get_product_by_id(db, pid)
    except ValueError:
        product = await product_service.get_product_by_slug(db, slug)
    if not product:
        return templates.TemplateResponse("shop/product_list.html", ctx)
    await product_service.increment_product_view(db, product)
    ctx["product"] = _build_detail_response(product)
    related = await product_service.get_related_products(db, product, 6)
    ctx["related_products"] = [product_service._build_product_list_response(p) for p in related]
    return templates.TemplateResponse("shop/product_detail.html", ctx)


@router.get("/cart", response_class=HTMLResponse)
async def cart_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    ctx = await _get_shop_context(request, db, current_user)
    if current_user:
        cart = order_service.get_cart(current_user.id)
        await order_service.enrich_cart_with_products(db, cart)
        items = [
            {
                "id": str(item.id),
                "product_id": str(item.product_id),
                "product_name": item.product_name,
                "product_slug": item.product_slug,
                "product_image": item.product_image,
                "variety_id": str(item.variety_id) if item.variety_id else None,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "price_after_discount": item.price_after_discount,
                "total_price": item.total_price,
                "stock_quantity": item.stock_quantity,
            }
            for item in cart.items.values()
        ]
        ctx["cart"] = {"items": items, "total_items": cart.total_items, "total_price": cart.total_price}
    else:
        ctx["cart"] = {"items": [], "total_items": 0, "total_price": 0}
    return templates.TemplateResponse("shop/cart.html", ctx)


@router.get("/checkout", response_class=HTMLResponse)
async def checkout_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    ctx = await _get_shop_context(request, db, current_user)
    pay_methods = await order_service.get_pay_methods(db)
    post_types = await order_service.get_post_types(db)
    ctx["pay_methods"] = [
        {"id": str(m.id), "name": m.name, "type": m.type, "description": m.description}
        for m in pay_methods
    ]
    ctx["post_types"] = [
        {"id": str(t.id), "name": t.name, "price": float(t.price) if t.price else 0, "description": t.description}
        for t in post_types
    ]
    return templates.TemplateResponse("shop/checkout.html", ctx)


@router.get("/profile", response_class=HTMLResponse)
async def profile_page(
    request: Request,
    current_user: User = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    ctx = await _get_shop_context(request, db, current_user)
    ctx["user"] = {
        "id": str(current_user.id),
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "email": current_user.email,
        "phone_number": current_user.phone_number,
        "gender": current_user.gender,
        "national_id": current_user.national_id,
    }
    return templates.TemplateResponse("shop/profile.html", ctx)


@router.get("/orders", response_class=HTMLResponse)
async def orders_page(
    request: Request,
    page: int = Query(1),
    current_user: User = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    ctx = await _get_shop_context(request, db, current_user)
    orders, total = await order_service.get_user_orders(db, current_user.id, page, 20)
    ctx["orders"] = [order_service.build_order_response(o) for o in orders]
    ctx["page"] = page
    ctx["total_pages"] = (total + 19) // 20
    return templates.TemplateResponse("shop/order_list.html", ctx)


@router.get("/orders/{order_id}", response_class=HTMLResponse)
async def order_detail_page(
    request: Request,
    order_id: str,
    current_user: User = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    import uuid
    ctx = await _get_shop_context(request, db, current_user)
    try:
        oid = uuid.UUID(order_id)
        order = await order_service.get_order_by_id(db, oid)
        if order and order.user_id == current_user.id:
            ctx["order"] = order_service.build_order_response(order)
    except ValueError:
        pass
    return templates.TemplateResponse("shop/order_detail.html", ctx)


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("shop/login.html", {"request": request})


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("shop/register.html", {"request": request})


@router.get("/search", response_class=HTMLResponse)
async def search_page(
    request: Request,
    q: str = Query(""),
    page: int = Query(1),
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    ctx = await _get_shop_context(request, db, current_user)
    params = ProductSearchParams(query=q, page=page, page_size=20)
    try:
        products, total = await product_service.search_products(db, params)
        ctx["products"] = [product_service._build_product_list_response(p) for p in products]
        ctx["query"] = q
        ctx["total"] = total
        ctx["page"] = page
        ctx["total_pages"] = (total + 19) // 20
    except Exception:
        ctx["products"] = []
    return templates.TemplateResponse("shop/product_list.html", ctx)


def _build_detail_response(product):
    base = product_service._build_product_list_response(product)
    return {
        **base.model_dump(),
        "introduction": product.introduction,
        "keywords": product.keywords,
        "meta_description": product.meta_description,
        "min_purchase": product.minimum_purchase,
        "max_purchases": product.max_number_of_purchases,
        "delivery_day": product.delivery_day,
        "vat_rate": float(product.vat_rate) if product.vat_rate else None,
        "varieties": [
            {
                "id": str(v.id),
                "part_number": v.part_number,
                "stock_quantity": v.stock_quantity,
                "price": float(v.price) if v.price else None,
                "price_after_discount": float(v.price_after_discount) if v.price_after_discount else None,
                "product_varieties": [
                    {"value": pv.value, "option_name": pv.category_option.name if pv.category_option else ""}
                    for pv in (v.product_varieties or [])
                ],
            }
            for v in (product.varieties or [])
        ],
        "images": [
            {
                "medium_image_url": img.medium_image_url,
                "large_image_url": img.large_image_url,
                "title": img.title,
                "display_photo": img.display_photo,
                "picture_order": img.picture_order,
            }
            for img in (product.product_images or [])
        ],
    }