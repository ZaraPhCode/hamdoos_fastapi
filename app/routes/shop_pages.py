"""Shop page routes — renders Jinja2 templates for the public storefront."""

from __future__ import annotations

import math
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.core.dependencies import get_current_active_user, get_optional_user_from_cookie
from app.models.identity import User, UserRole
from app.models.product import Product, Category, Brand
from app.models.order import OrderModel as Order
from app.models.common import Address, BankInfo
from app.models.customer_content import Comment
from app.schemas.order import CartItemCreate, CreateOrderRequest, OrderAddressInput
from app.services import product_service, order_service, auth_service
from app.schemas.product import ProductSearchParams

templates = Jinja2Templates(directory="app/templates")
router = APIRouter(tags=["Shop Pages"])

NET_ORDER_OPTIONS = ("Sale", "Id", "AlphabetAsc", "AlphabetDesc", "Cheapest", "Expensive")


def _parse_uuids(value: Optional[str]) -> list[uuid.UUID]:
    """Parse a comma-separated list of UUIDs (.NET `branches` / `brands` params)."""
    if not value:
        return []
    result = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            result.append(uuid.UUID(part))
        except ValueError:
            pass
    return result


async def _resolve_category(db: AsyncSession, category_id: Optional[str], category: Optional[str]) -> Optional[Category]:
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    def _query() -> select:
        return (
            select(Category)
            .options(
                selectinload(Category.children),
                selectinload(Category.medias),
            )
            .where(Category.is_removed == False)
        )

    if category_id:
        try:
            result = await db.execute(_query().where(Category.id == uuid.UUID(category_id)))
            return result.unique().scalar_one_or_none()
        except ValueError:
            return None
    if category:
        cat = (await db.execute(_query().where(Category.en_title == category))).unique().scalar_one_or_none()
        if not cat:
            cat = (await db.execute(_query().where(Category.slug == category))).unique().scalar_one_or_none()
        if not cat:
            try:
                cat = (await db.execute(_query().where(Category.id == uuid.UUID(category)))).unique().scalar_one_or_none()
            except ValueError:
                pass
        return cat
    return None


@router.get("/home", response_class=HTMLResponse)
async def home_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user_from_cookie),
):
    from app.models.common import SiteSetting

    # Defaults (empty lists/None) mirror .NET nullable view-model props
    special_products = new_products = restocked_products = suggested_products = []
    categories = []
    site_settings = None
    top_category = middle_category = bottom_category = None
    top_category_products = middle_category_products = bottom_category_products = []
    top_category_poster = mid_left_poster = mid_right_poster = middle_category_poster = bottom_category_poster = None

    try:
        special_products = await product_service.get_special_products(db, 12)
        new_products = await product_service.get_new_products(db, 12)
        restocked_products = await product_service.get_restocked_products(db, 12)
        suggested_products = await product_service.get_suggested_products(db, 12)
        categories = await product_service.get_category_tree(db)
        stmt = select(SiteSetting).where(SiteSetting.is_removed == False)
        result = await db.execute(stmt)
        site_settings = result.scalars().first()
    except Exception:
        pass

    if site_settings:
        ref_ids = {
            site_settings.top_category_id,
            site_settings.middle_category_id,
            site_settings.bottom_category_id,
            site_settings.top_poster_category_id,
            site_settings.mid_left_poster_category_id,
            site_settings.mid_right_poster_category_id,
            site_settings.middle_poster_category_id,
            site_settings.bottom_poster_category_id,
        }
        ref_ids.discard(None)
        cats_map = {}
        if ref_ids:
            cat_stmt = (
                select(Category)
                .options(selectinload(Category.children))
                .where(Category.id.in_(ref_ids), Category.is_removed == False)
            )
            cat_res = await db.execute(cat_stmt)
            cats_map = {c.id: c for c in cat_res.unique().scalars().all()}

        top_category = cats_map.get(site_settings.top_category_id)
        middle_category = cats_map.get(site_settings.middle_category_id)
        bottom_category = cats_map.get(site_settings.bottom_category_id)
        top_category_poster = cats_map.get(site_settings.top_poster_category_id)
        mid_left_poster = cats_map.get(site_settings.mid_left_poster_category_id)
        mid_right_poster = cats_map.get(site_settings.mid_right_poster_category_id)
        middle_category_poster = cats_map.get(site_settings.middle_poster_category_id)
        bottom_category_poster = cats_map.get(site_settings.bottom_poster_category_id)

        try:
            if top_category:
                top_category_products = await product_service.get_home_products_by_category(db, top_category.id)
            if middle_category:
                middle_category_products = await product_service.get_home_products_by_category(db, middle_category.id)
            if bottom_category:
                bottom_category_products = await product_service.get_home_products_by_category(db, bottom_category.id)
        except Exception:
            pass

    return templates.TemplateResponse("shop/index.html", {
        "request": request,
        "special_products": special_products,
        "new_products": new_products,
        "restocked_products": restocked_products,
        "suggested_products": suggested_products,
        "top_category": top_category,
        "top_category_title": top_category.title if top_category else None,
        "top_category_products": top_category_products,
        "top_category_poster": top_category_poster,
        "middle_category": middle_category,
        "middle_category_title": middle_category.title if middle_category else None,
        "middle_category_products": middle_category_products,
        "middle_category_poster": middle_category_poster,
        "mid_left_poster": mid_left_poster,
        "mid_right_poster": mid_right_poster,
        "bottom_category": bottom_category,
        "bottom_category_title": bottom_category.title if bottom_category else None,
        "bottom_category_products": bottom_category_products,
        "bottom_category_poster": bottom_category_poster,
        "categories": categories,
        "header_categories": categories,
        "site_settings": site_settings,
        "current_user": current_user,
    })


@router.get("/products", response_class=HTMLResponse)
async def product_list_page(
    request: Request,
    category_id: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    branches: Optional[str] = Query(None),
    brands: Optional[str] = Query(None),
    min_value: Optional[float] = Query(None),
    max_value: Optional[float] = Query(None),
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
    order: str = Query("AlphabetAsc"),
    query: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    current_page: Optional[int] = Query(None),
    page_size: int = Query(28, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    if current_page and current_page > 0:
        page = current_page
    return await _render_product_list(
        request, db,
        category_id=category_id, category=category,
        branches=branches, brands=brands,
        min_value=min_value or min_price, max_value=max_value or max_price,
        order=order, query=query or q, page=page, page_size=page_size,
    )


async def _render_product_list(
    request: Request, db: AsyncSession, *,
    category_id: Optional[str] = None, category: Optional[str] = None,
    branches: Optional[str] = None, brands: Optional[str] = None,
    min_value: Optional[float] = None, max_value: Optional[float] = None,
    order: str = "AlphabetAsc", query: Optional[str] = None,
    page: int = 1, page_size: int = 28,
) -> HTMLResponse:
    cat = await _resolve_category(db, category_id, category)
    if order not in NET_ORDER_OPTIONS:
        order = "AlphabetAsc"

    branch_ids = _parse_uuids(branches)
    brand_ids = _parse_uuids(brands)
    cat_uuid = cat.id if cat else None

    products, total = await product_service.search_products_net(
        db, category_id=cat_uuid, branch_ids=branch_ids or None,
        brand_ids=brand_ids or None, min_price=min_value, max_price=max_value,
        order=order, query=query, page=page, page_size=page_size,
    )
    brand_facets = await product_service.get_brand_facets(db, category_id=cat_uuid, branch_ids=branch_ids or None)
    _, price_max = await product_service.get_category_price_range(db, category_id=cat_uuid, branch_ids=branch_ids or None)
    cats = await product_service.get_category_tree(db)

    from app.models.common import SiteSetting
    from sqlalchemy import select
    site_settings = (await db.execute(
        select(SiteSetting).where(SiteSetting.is_removed == False).limit(1)
    )).scalars().first()

    total_pages = max(1, math.ceil(total / page_size))

    parts = []
    if cat:
        parts.append(f"category={cat.en_title or cat.slug}")
    elif category_id:
        parts.append(f"category_id={category_id}")
    if branches:
        parts.append(f"branches={branches}")
    if brands:
        parts.append(f"brands={brands}")
    if min_value is not None:
        parts.append(f"min_value={min_value}")
    if max_value is not None:
        parts.append(f"max_value={max_value}")
    if query:
        parts.append(f"query={query}")
    filter_qs = "&".join(parts)

    return templates.TemplateResponse("shop/product_list.html", {
        "request": request,
        "category": cat,
        "categories": cats,
        "header_categories": cats,
        "children": list(cat.children) if cat and cat.children else [],
        "products": products,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "order": order,
        "query": query,
        "min_value": min_value,
        "max_value": max_value,
        "branch_ids": {str(b) for b in branch_ids},
        "brand_ids": {str(b) for b in brand_ids},
        "brand_facets": brand_facets,
        "price_max": price_max,
        "filter_qs": filter_qs,
        "site_settings": site_settings,
    })


@router.get("/products/{slug}", response_class=HTMLResponse)
async def product_detail_page(slug: str, request: Request, db: AsyncSession = Depends(get_db)):
    try:
        pid = uuid.UUID(slug)
        product = await product_service.get_product_by_id(db, pid)
    except ValueError:
        product = await product_service.get_product_by_slug(db, slug)

    if not product:
        return HTMLResponse("Product not found", status_code=404)

    await product_service.increment_product_view(db, product)
    detail = _build_shop_detail(product)
    related = await product_service.get_related_products(db, product, 6)
    cats = await product_service.get_category_tree(db)
    return templates.TemplateResponse("shop/product_detail.html", {
        "request": request, "product": detail,
        "related_products": [product_service._build_product_list_response(p) for p in related],
        "categories": cats, "header_categories": cats,
    })


@router.get("/cart", response_class=HTMLResponse)
async def cart_page(request: Request, current_user: Optional[User] = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    cart_data = {"items": [], "total_items": 0, "total_price": 0}
    if current_user:
        cart = order_service.get_cart(current_user.id)
        await order_service.enrich_cart_with_products(db, cart)
        cart_data = cart.to_dict()
    cats = await product_service.get_category_tree(db)
    return templates.TemplateResponse("shop/cart.html", {"request": request, "cart": cart_data, "categories": cats, "header_categories": cats})


@router.get("/checkout", response_class=HTMLResponse)
async def checkout_page(request: Request, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    cart = order_service.get_cart(current_user.id)
    await order_service.enrich_cart_with_products(db, cart)
    pay_methods = await order_service.get_pay_methods(db)
    post_types = await order_service.get_post_types(db)
    cats = await product_service.get_category_tree(db)
    return templates.TemplateResponse("shop/checkout.html", {
        "request": request, "cart": cart.to_dict(),
        "pay_methods": pay_methods, "post_types": post_types,
        "categories": cats, "header_categories": cats,
    })


@router.post("/checkout", response_class=HTMLResponse)
async def checkout_submit(
    request: Request,
    first_name: str = Form(...), last_name: str = Form(...),
    phone_number: str = Form(...), telephone: Optional[str] = Form(""),
    address_description: str = Form(...), postal_code: str = Form(...),
    province: Optional[str] = Form(""), city: Optional[str] = Form(""),
    pay_method_id: str = Form(...), post_type_id: str = Form(...),
    discount_code: Optional[str] = Form(""),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    cart = order_service.get_cart(current_user.id)
    if not cart.items:
        return templates.TemplateResponse("shop/cart.html", {
            "request": request, "cart": cart.to_dict(), "error": "سبد خرید خالی است"
        })
    try:
        addr = OrderAddressInput(
            first_name=first_name, last_name=last_name, phone_number=phone_number,
            telephone=telephone, address_description=address_description,
            postal_code=postal_code, province=province, city=city,
        )
        order_req = CreateOrderRequest(
            address=addr,
            pay_method_id=uuid.UUID(pay_method_id),
            post_type_id=uuid.UUID(post_type_id),
            discount_code=discount_code or None,
        )
        order = await order_service.create_order(db, current_user, order_req, cart)
        return RedirectResponse(url=f"/orders/{order.id}", status_code=303)
    except ValueError as e:
        return templates.TemplateResponse("shop/checkout.html", {
            "request": request, "cart": cart.to_dict(), "error": str(e)
        })


# ── Orders ──

@router.get("/orders", response_class=HTMLResponse)
async def orders_page(request: Request, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    orders_list, _ = await order_service.get_user_orders(db, current_user.id, 1, 50)
    return templates.TemplateResponse("shop/order_list.html", {"request": request, "orders": [order_service.build_order_response(o) for o in orders_list]})


@router.get("/orders/{order_id}", response_class=HTMLResponse)
async def order_detail_page(order_id: str, request: Request, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    try:
        oid = uuid.UUID(order_id)
        order = await order_service.get_order_by_id(db, oid)
    except ValueError:
        return HTMLResponse("Order not found", status_code=404)
    if not order or (order.user_id != current_user.id and "Admin" not in {ur.role.name for ur in current_user.roles}):
        return HTMLResponse("Order not found", status_code=404)
    return templates.TemplateResponse("shop/order_detail.html", {
        "request": request, "order": order_service.build_order_response(order)
    })


# ── Profile Pages ──

@router.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request, current_user: User = Depends(get_current_active_user)):
    return templates.TemplateResponse("shop/profile.html", {"request": request, "current_user": current_user, "section": "profile"})


@router.post("/profile/update", response_class=RedirectResponse)
async def profile_update(
    request: Request, first_name: Optional[str] = Form(None), last_name: Optional[str] = Form(None),
    email: Optional[str] = Form(None), current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    from app.schemas.auth import UserProfileUpdate
    req = UserProfileUpdate(first_name=first_name, last_name=last_name, email=email)
    await auth_service.update_user_profile(current_user, db, req)
    return RedirectResponse(url="/profile", status_code=303)


@router.get("/profile/addresses", response_class=HTMLResponse)
async def profile_addresses(request: Request, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select
    from app.models.common import Address
    stmt = select(Address).where(Address.user_id == current_user.id, Address.is_removed == False)
    result = await db.execute(stmt)
    addresses = result.scalars().all()
    return templates.TemplateResponse("shop/addresses.html", {"request": request, "current_user": current_user, "addresses": addresses})


@router.post("/profile/addresses/add", response_class=RedirectResponse)
async def profile_address_add(
    request: Request, first_name: str = Form(...), last_name: str = Form(...),
    phone_number: str = Form(...), address_description: str = Form(...),
    postal_code: str = Form(...), province: str = Form(""), city: str = Form(""),
    current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db),
):
    from app.models.common import Address
    from datetime import datetime, timezone
    addr = Address(
        id=uuid.uuid4(), user_id=current_user.id,
        first_name=first_name, last_name=last_name, phone_number=phone_number,
        address_description=address_description, postal_code=postal_code,
        province_id=None, country="Iran",
        insert_date=datetime.now(timezone.utc), update_date=datetime.now(timezone.utc),
    )
    db.add(addr); await db.flush()
    return RedirectResponse(url="/profile/addresses", status_code=303)


@router.post("/profile/addresses/{addr_id}/delete", response_class=RedirectResponse)
async def profile_address_delete(addr_id: str, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    from app.models.common import Address
    try:
        addr = await db.get(Address, uuid.UUID(addr_id))
        if addr and addr.user_id == current_user.id:
            addr.is_removed = True
            await db.flush()
    except ValueError:
        pass
    return RedirectResponse(url="/profile/addresses", status_code=303)


@router.get("/profile/bank-info", response_class=HTMLResponse)
async def profile_bank_info(request: Request, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    from app.models.common import BankInfo
    from sqlalchemy import select
    stmt = select(BankInfo).where(BankInfo.user_id == current_user.id, BankInfo.is_removed == False)
    result = await db.execute(stmt)
    bank_infos = result.scalars().all()
    return templates.TemplateResponse("shop/bank_info.html", {"request": request, "current_user": current_user, "bank_infos": bank_infos})


@router.post("/profile/bank-info/add", response_class=RedirectResponse)
async def profile_bank_info_add(
    request: Request, account_owner: str = Form(...), card_number: str = Form(""),
    sheba_number: str = Form(""), bank_name: str = Form(""),
    current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db),
):
    from app.models.common import BankInfo
    from datetime import datetime, timezone
    bi = BankInfo(id=uuid.uuid4(), user_id=current_user.id, account_owner=account_owner,
                  card_number=card_number, sheba_number=sheba_number, bank_name=bank_name,
                  insert_date=datetime.now(timezone.utc), update_date=datetime.now(timezone.utc))
    db.add(bi); await db.flush()
    return RedirectResponse(url="/profile/bank-info", status_code=303)


@router.get("/profile/favorites", response_class=HTMLResponse)
async def profile_favorites(request: Request, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    from app.models.product import FavoriteProductList, FavoriteListItem
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    stmt = select(FavoriteProductList).where(
        FavoriteProductList.user_id == current_user.id, FavoriteProductList.is_removed == False
    ).options(selectinload(FavoriteProductList.favorite_list_items).selectinload(FavoriteListItem.product))
    result = await db.execute(stmt)
    lists = result.unique().scalars().all()
    return templates.TemplateResponse("shop/favorites.html", {"request": request, "current_user": current_user, "favorite_lists": lists})


@router.get("/profile/identity", response_class=HTMLResponse)
async def profile_identity(request: Request, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    from app.models.identity import IdentityInformation
    from sqlalchemy import select
    stmt = select(IdentityInformation).where(IdentityInformation.user_id == current_user.id, IdentityInformation.is_removed == False)
    result = await db.execute(stmt)
    identities = result.scalars().all()
    return templates.TemplateResponse("shop/identity.html", {"request": request, "current_user": current_user, "identities": identities})


@router.post("/profile/identity/add", response_class=RedirectResponse)
async def profile_identity_add(
    request: Request, name: str = Form(...), national_code_or_id: str = Form(""),
    economic_code: str = Form(""), postal_code: str = Form(""), address: str = Form(""),
    identity_type: str = Form("Real"),
    current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db),
):
    from app.models.identity import IdentityInformation
    from datetime import datetime, timezone
    info = IdentityInformation(
        id=uuid.uuid4(), user_id=current_user.id, name=name,
        national_code_or_id=national_code_or_id, economic_code=economic_code,
        postal_code=postal_code, address=address, type=identity_type,
        insert_date=datetime.now(timezone.utc), update_date=datetime.now(timezone.utc),
    )
    db.add(info); await db.flush()
    return RedirectResponse(url="/profile/identity", status_code=303)


@router.get("/profile/change-password", response_class=HTMLResponse)
async def profile_change_password_page(request: Request, current_user: User = Depends(get_current_active_user)):
    return templates.TemplateResponse("shop/change_password.html", {"request": request, "current_user": current_user})


@router.post("/profile/change-password", response_class=HTMLResponse)
async def profile_change_password_submit(
    request: Request, current_password: str = Form(...), new_password: str = Form(...),
    current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db),
):
    from app.schemas.auth import ChangePasswordRequest
    try:
        req = ChangePasswordRequest(current_password=current_password, new_password=new_password)
        await auth_service.change_user_password(current_user, db, req)
        return templates.TemplateResponse("shop/change_password.html", {
            "request": request, "current_user": current_user, "success": "رمز عبور با موفقیت تغییر کرد"
        })
    except ValueError as e:
        return templates.TemplateResponse("shop/change_password.html", {
            "request": request, "current_user": current_user, "error": str(e)
        })


# ── Static Pages ──

@router.get("/about", response_class=HTMLResponse)
async def about_page(request: Request):
    return templates.TemplateResponse("shop/about.html", {"request": request})


@router.get("/contact", response_class=HTMLResponse)
async def contact_page(request: Request):
    return templates.TemplateResponse("shop/contact.html", {"request": request})


@router.get("/faq", response_class=HTMLResponse)
async def faq_page(request: Request):
    return templates.TemplateResponse("shop/faq.html", {"request": request})


@router.get("/brands", response_class=HTMLResponse)
async def brand_list_page(request: Request, db: AsyncSession = Depends(get_db)):
    brands = await product_service.get_all_brands(db)
    return templates.TemplateResponse("shop/brands.html", {"request": request, "brands": brands})


@router.get("/brands/{brand_id}", response_class=HTMLResponse)
async def brand_detail_page(brand_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    try:
        bid = uuid.UUID(brand_id)
        brand = await product_service.get_brand_by_id(db, bid)
    except ValueError:
        return HTMLResponse("Brand not found", status_code=404)
    if not brand:
        return HTMLResponse("Brand not found", status_code=404)
    return templates.TemplateResponse("shop/brand_detail.html", {"request": request, "brand": brand})


# ── Helpers ──

def _build_shop_detail(product):
    base = product_service._build_product_list_response(product)
    import uuid
    return {
        **base.model_dump(),
        "introduction": product.introduction,
        "keywords": product.keywords,
        "meta_description": product.meta_description,
        "stock_quantity": product.stock_quantity,
        "minimum_purchase": product.minimum_purchase,
        "max_number_of_purchases": product.max_number_of_purchases,
        "delivery_day": product.delivery_day,
        "vat_rate": float(product.vat_rate) if product.vat_rate else None,
        "images": [{"id": str(img.id), "medium_image_url": img.medium_image_url, "large_image_url": img.large_image_url}
                   for img in (product.product_images or [])] if hasattr(product, 'product_images') else [],
        "varieties": [{"id": str(v.id), "part_number": v.part_number, "price": float(v.price or 0),
                       "price_after_discount": float(v.price_after_discount or v.price or 0),
                       "stock_quantity": v.stock_quantity,
                       "product_varieties": [{"category_option_name": pv.category_option.name if pv.category_option else None, "value": pv.value}
                                             for pv in (v.product_varieties or [])] if hasattr(v, 'product_varieties') else []}
                      for v in (product.varieties or [])] if hasattr(product, 'varieties') else [],
        "technical_features": [],
        "related_products": [],
    }


# ── Categories Page ──

@router.get("/categories", response_class=HTMLResponse)
async def shop_categories(request: Request, db: AsyncSession = Depends(get_db)):
    categories = await product_service.get_category_tree(db)
    return templates.TemplateResponse("shop/categories.html", {"request": request, "categories": categories})


@router.get("/category/{slug}", response_class=HTMLResponse)
async def shop_category(slug: str, request: Request, db: AsyncSession = Depends(get_db)):
    return await _render_category_page(slug, request, db)


@router.get("/Shop/Category/Index/{slug}", response_class=HTMLResponse)
async def shop_category_dotnet(slug: str, request: Request, db: AsyncSession = Depends(get_db)):
    return await _render_category_page(slug, request, db)


async def _render_category_page(slug: str, request: Request, db: AsyncSession) -> HTMLResponse:
    cat = await _resolve_category(db, None, slug)
    if not cat:
        return HTMLResponse("دسته‌بندی یافت نشد", status_code=404)
    branches = request.query_params.get("branches")
    brands = request.query_params.get("brands")
    try:
        min_value = float(request.query_params.get("min_value") or request.query_params.get("minValue")) if request.query_params.get("min_value") or request.query_params.get("minValue") else None
    except (ValueError, TypeError):
        min_value = None
    try:
        max_value = float(request.query_params.get("max_value") or request.query_params.get("maxValue")) if request.query_params.get("max_value") or request.query_params.get("maxValue") else None
    except (ValueError, TypeError):
        max_value = None
    order = request.query_params.get("order", "AlphabetAsc")
    query = request.query_params.get("query") or request.query_params.get("q")
    try:
        page = int(request.query_params.get("currentPage") or request.query_params.get("page") or 1)
    except (ValueError, TypeError):
        page = 1
    try:
        page_size = int(request.query_params.get("pageSize") or request.query_params.get("page_size") or 28)
    except (ValueError, TypeError):
        page_size = 28
    return await _render_product_list(
        request, db,
        category_id=str(cat.id), category=slug,
        branches=branches, brands=brands,
        min_value=min_value, max_value=max_value,
        order=order, query=query, page=page, page_size=page_size,
    )