"""Shop page routes — renders Jinja2 templates for the public storefront."""

from __future__ import annotations

import math
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.core.dependencies import get_current_active_user, get_optional_user_from_cookie
from app.models.identity import User, UserRole
from app.models.product import Product, Category, Brand, MenuDatasheet, Variety
from app.models.order import OrderModel as Order, PayMethod
from app.models.common import Address, BankInfo
from app.models.customer_content import Comment
from app.models.finance import Receipt
from app.models.order import OrderStatusRecord
from app.schemas.order import CartItemCreate, CreateOrderRequest, OrderAddressInput
from app.services import product_service, order_service, auth_service
from app.services.cart_cookie_service import (
    Cart, CartItem as CartCookieItem, parse_cart, save_cart_response, enrich_cart, cart_context,
)
from app.schemas.product import ProductSearchParams
from app.utils.persian_tools import normalize_image_url

templates = Jinja2Templates(directory="app/templates")
router = APIRouter(tags=["Shop Pages"])


def _normalize_media_url(url):
    """Convert a stored path like \\Media\\laser\\file.jpg to /media/laser/file.jpg.
    Only transforms paths that look like Media/... or \\Media\\...;
    leaves absolute URLs, full URLs, and None unchanged."""
    if not url:
        return url
    if url.startswith(("http://", "https://", "//", "/static/", "/media/")):
        return url
    normalized = url.replace("\\", "/").lstrip("/")
    if normalized.lower().startswith("media/"):
        normalized = normalized[len("media/"):]
    return "/media/" + normalized


templates.env.filters["media_url"] = _normalize_media_url

NET_ORDER_OPTIONS = ("Sale", "Id", "AlphabetAsc", "AlphabetDesc", "Cheapest", "Expensive")


async def _ensure_province_cities(db: AsyncSession, province: "ProvinceCity") -> list["ProvinceCity"]:
    """Ensure ProvinceCity city records exist for the given province (seeded from built-in data)."""
    from app.models.common import ProvinceCity as PC
    from sqlalchemy import select
    from datetime import datetime, timezone

    city_rows = await db.execute(
        select(PC).where(
            PC.province_id == province.int_id,
            PC.is_removed == False,
        ).order_by(PC.name)
    )
    cities = city_rows.scalars().all()
    if len(cities) >= 3:
        return cities
    for c in cities:
        c.is_removed = True
        c.update_date = datetime.now(timezone.utc)
    await db.flush()

    IRAN_CITIES = {
        "آذربایجان شرقی": ["تبریز", "مراغه", "مرند", "اهر", "میانه", "بناب", "سراب", "شبستر", "بستان‌آباد", "هریس", "اسکو", "عجب‌شیر", "ملکان", "آذرشهر", "جلفا", "خداآفرین", "چاراویماق", "ورزقان", "کلیبر", "هشترود"],
        "آذربایجان غربی": ["ارومیه", "خوی", "بوکان", "مهاباد", "سلماس", "نقده", "ماکو", "شاهین‌دژ", "پیرانشهر", "تکاب", "میاندوآب", "اشنویه", "چالدران", "پلدشت", "سردشت", "باروق", "چایپاره", "شوط", "چهاربرج"],
        "اردبیل": ["اردبیل", "پارس‌آباد", "مشگین‌شهر", "خلخال", "گرمی", "بیله‌سوار", "نمین", "نیر", "سرعین", "کوثر", "کیوی", "اردبیل"],
        "اصفهان": ["اصفهان", "کاشان", "خمینی‌شهر", "نجف‌آباد", "شاهین‌شهر", "شهرضا", "فلاورجان", "مبارکه", "لنجان", "نطنز", "آران و بیدگل", "تیران و کرون", "چادگان", "خمینی‌شهر", "دهاقان", "سمیرم", "فریدن", "فریدونشهر", "گلپایگان", "خوانسار", "نائین", "برخوار"],
        "البرز": ["کرج", "فردیس", "هشتگرد", "نظرآباد", "طالقان", "ساوجبلاغ", "اشتهارد", "چهارباغ", "ماهدشت", "مهرشهر", "گوهردشت"],
        "ایلام": ["ایلام", "مهران", "دهلران", "آبدانان", "دره‌شهر", "ایوان", "بدره", "چرداول", "ملکشاهی", "سیروان", "هلیلان"],
        "بوشهر": ["بوشهر", "برازجان", "کنگان", "گناوه", "دیر", "دیلم", "تنگستان", "جم", "عسلویه", "دشتی", "دشتستان"],
        "تهران": ["تهران", "ری", "شهریار", "اسلامشهر", "ورامین", "پاکدشت", "رباط کریم", "دماوند", "فیروزکوه", "شمیرانات", "ملارد", "قدس", "قرچک", "بهارستان", "پیشوا", "لواسان", "بومهن", "پرند", "چهاردانگه", "صالحیه", "گلستان", "اندیشه", "باغستان"],
        "چهارمحال و بختیاری": ["شهرکرد", "بروجن", "لردگان", "فارسان", "کیار", "کوهرنگ", "اردل", "سامان", "بازفت", "گندمان", "ناغان", "بن"],
        "خراسان جنوبی": ["بیرجند", "قائن", "فردوس", "طبس", "نهبندان", "سرایان", "سربیشه", "بشرویه", "درمیان", "خوسف", "زیرکوه"],
        "خراسان رضوی": ["مشهد", "نیشابور", "سبزوار", "تربت حیدریه", "قوچان", "کاشمر", "تربت جام", "چناران", "سرخس", "درگز", "فریمان", "خواف", "رشتخوار", "گناباد", "بردسکن", "باخرز", "تایباد", "فیروزه", "بینالود", "زبرخان", "جویبار", "کلات", "مه ولات"],
        "خراسان شمالی": ["بجنورد", "اسفراین", "شیروان", "مانه و سملقان", "گرمه", "راز و جرگلان", "فاروج", "جاجرم"],
        "خوزستان": ["اهواز", "آبادان", "دزفول", "بندرماهشهر", "مسجدسلیمان", "ایذه", "شوشتر", "بهبهان", "اندیمشک", "شادگان", "خرمشهر", "رامهرمز", "بندرامام خمینی", "شوش", "هفتکل", "هندیجان", "لالی", "گتوند", "باغ‌ملک", "دشت‌آزادگان", "کارون", "حمیدیه", "باوی", "آغاجاری", "امیدیه"],
        "زنجان": ["زنجان", "ابهر", "خدابنده", "خرمدره", "ایجرود", "طارم", "ماهنشان", "سلطانیه"],
        "سمنان": ["سمنان", "شاهرود", "دامغان", "گرمسار", "مهدی‌شهر", "میامی", "آرادان", "سرخه"],
        "سیستان و بلوچستان": ["زاهدان", "زابل", "ایرانشهر", "چابهار", "سراوان", "خاش", "نیک‌شهر", "کنارک", "زهک", "هیرمند", "نیمروز", "هامون", "مهرستان", "سیب و سوران", "دلگان", "فنوج", "قصرقند", "لاشار", "راسک", "گلشن", "تفتان"],
        "فارس": ["شیراز", "مرودشت", "جهرم", "فیروزآباد", "کازرون", "لارستان", "فسا", "اقلید", "داراب", "سپیدان", "ممسنی", "نی‌ریز", "استهبان", "خرامه", "بوانات", "خرم‌بید", "زریندشت", "پاسارگاد", "ارسنجان", "کوار", "سروستان", "قیر و کارزین", "فراشبند", "مهر", "لامرد", "گراش", "خنج", "رستم", "بیضا", "ششتمد"],
        "قزوین": ["قزوین", "تاکستان", "آبیک", "البرز", "بوئین‌زهرا", "آوج", "محمدیه", "شال", "اقبالیه", "ضیاءآباد"],
        "قم": ["قم", "جعفرآباد", "کهک", "سلفچگان", "قنوات", "قاهان", "دستجرد"],
        "کردستان": ["سنندج", "سقز", "مریوان", "بانه", "قروه", "بیجار", "کامیاران", "دیواندره", "دهگلان", "سروآباد", "چناره"],
        "کرمان": ["کرمان", "رفسنجان", "سیرجان", "بم", "جیرفت", "زرند", "بافت", "بردسیر", "شهربابک", "انار", "راور", "کوهبنان", "رودبار جنوب", "عنبرآباد", "قلعه‌گنج", "منوجان", "فهرج", "نرماشیر", "ریگان", "ارزوئیه", "کهنوج"],
        "کرمانشاه": ["کرمانشاه", "اسلام‌آباد غرب", "سرپل ذهاب", "کنگاور", "سنقر", "هرسین", "پاوه", "قصرشیرین", "جوانرود", "صحنه", "ثلاث باباجانی", "دالاهو", "روانسر", "گیلانغرب"],
        "کهگیلویه و بویراحمد": ["یاسوج", "گچساران", "دهدشت", "بهمئی", "بویراحمد", "چرام", "لنده", "کهگیلویه", "دنا", "باشت", "مارگون"],
        "گلستان": ["گرگان", "گنبد کاووس", "علی‌آباد", "آق‌قلا", "بندرترکمن", "کردکوی", "کلاله", "آزادشهر", "مینودشت", "گالیکش", "مراوه‌تپه", "رامیان", "نوکنده"],
        "گیلان": ["رشت", "انزلی", "لاهیجان", "رودسر", "آستانه اشرفیه", "صومعه‌سرا", "طوالش", "فومن", "رشت", "لنگرود", "املش", "رضوانشهر", "سیاهکل", "ماسال", "شفت", "بندر انزلی"],
        "لرستان": ["خرم‌آباد", "بروجرد", "الیگودرز", "دورود", "کوهدشت", "ازنا", "پلدختر", "نورآباد", "چگنی", "رومشکان", "سلسله"],
        "مازندران": ["ساری", "بابل", "آمل", "قائم‌شهر", "تنکابن", "نوشهر", "چالوس", "بهشهر", "نور", "رامسر", "بابلسر", "جویبار", "محمودآباد", "نکا", "فریدونکنار", "عباس‌آباد", "کلاردشت", "سوادکوه", "سیمرغ", "میاندورود", "گلوگاه"],
        "مرکزی": ["اراک", "ساوه", "خمین", "محلات", "دلیجان", "شازند", "زرندیه", "کمیجان", "تفرش", "فراهان", "آشتیان"],
        "هرمزگان": ["بندرعباس", "قشم", "کیش", "میناب", "بندرلنگه", "جاسک", "حاجی‌آباد", "رودان", "ابوموسی", "بستک", "خمیر", "سیریک", "پارسیان", "بشاگرد"],
        "همدان": ["همدان", "ملایر", "نهاوند", "تویسرکان", "اسدآباد", "کبودرآهنگ", "بهار", "رزن", "فامنین", "درگزین"],
        "یزد": ["یزد", "میبد", "اردکان", "مهریز", "بافق", "ابرکوه", "خاتم", "تفت", "اشکذر", "بهاباد", "طبس"],
    }

    province_name = province.name
    city_names = IRAN_CITIES.get(province_name, [])
    if not city_names:
        return []

    max_int = 0
    max_row = await db.execute(select(PC).order_by(PC.int_id.desc()).limit(1))
    max_obj = max_row.scalar_one_or_none()
    if max_obj:
        max_int = max_obj.int_id

    new_cities = []
    for cname in city_names:
        max_int += 1
        pc = PC(
            id=uuid.uuid4(),
            name=cname,
            int_id=max_int,
            province_id=province.int_id,
            insert_date=datetime.now(timezone.utc),
            update_date=datetime.now(timezone.utc),
        )
        db.add(pc)
        new_cities.append(pc)
    await db.flush()
    return new_cities


async def _get_category_hierarchy(db: AsyncSession, cat: Category) -> list[dict]:
    """Build breadcrumb hierarchy from root to current category (exclusive)."""
    hierarchy = []
    current = cat
    seen = set()
    while current and current.parent_category_id and current.parent_category_id not in seen:
        seen.add(current.parent_category_id)
        parent = await product_service.get_category_by_id(db, current.parent_category_id)
        if parent:
            hierarchy.insert(0, {"title": parent.title, "en_title": parent.en_title, "slug": parent.slug})
            current = parent
        else:
            break
    return hierarchy


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


def _cart_context_simple(request: Request) -> dict:
    """Cart context without DB enrichment — just cookie data for count/total."""
    from app.services.cart_cookie_service import parse_cart, cart_context
    cart = parse_cart(request)
    return cart_context(cart)

async def _get_cart(request: Request, db: AsyncSession) -> Cart:
    """Parse cart from cookie and enrich with product data."""
    cart = parse_cart(request)
    try:
        await enrich_cart(db, cart)
    except Exception:
        pass
    return cart


async def _get_cart_context(request: Request, db: AsyncSession) -> dict:
    """Return template context dict with cart_count, cart_total, cart_items."""
    cart = parse_cart(request)
    try:
        await enrich_cart(db, cart)
    except Exception:
        pass
    return cart_context(cart)


def _cart_preview_html(cart: Cart) -> str:
    """Render the cart dropdown HTML as a string (for AJAX refresh endpoint).
    Matches the .NET _CartPreview.cshtml output so ps_shoppingcart.js can parse it."""
    items_html = ""
    for it in cart.items:
        img = it.feature_image_url or "https://placehold.co/80x80"
        reg_price = ""
        if it.price and it.price != it.price_after_discount:
            reg_price = f'<span class="regular-price">{it.price:,.0f} ريال</span>'
        items_html += f"""<li class="cart-product-line">
                <a class="product-image" href="/products/{it.part_number or it.product_id}">
                    <img src="{img}" alt="{it.image_description or ''}" class="img-fluid">
                </a>
                <div class="product-infos">
                    <a class="product-name" href="/products/{it.part_number or it.product_id}">{it.name}</a>
                    <div class="product-attributes">{it.variety_values_str}</div>
                    <div class="product-price-quantity">
                        <div class="product-quantity-touchspin">
                            <input class="js-cart-line-product-quantity" type="number" value="{it.quantity}" name="product-sidebar-quantity-spin" min="1" data-item-id="{it.id}">
                        </div>
                        <div class="product-cart-price">
                            <div style="display: grid">
                                {reg_price}
                                <span class="product-price">{it.price_after_discount or it.price:,.0f} ريال</span>
                            </div>
                            <span class="x-character">x</span>
                            <span class="product-qty">{it.quantity}</span>
                        </div>
                    </div>
                </div>
                <a class="remove-from-cart icon-link" rel="nofollow" href="/cart/remove-ajax/{it.id}" data-link-action="delete-from-cart" data-item-id="{it.id}" title="حذف">
                    <i class="fa fa-trash-o" aria-hidden="true"></i>
                </a>
            </li>"""
    body = ""
    if cart.items:
        body = f"""<div class="cart-title h4">سبد خرید</div>
                <ul class="cart-items _allow-update-quantity">
                    {items_html}
                </ul>
                <div class="cart-bottom">
                    <p class="cart-products-count alert-info">{cart.count} کالا در سبد خرید شما</p>
                    <div class="cart-summary-subtotals">
                        <div class="cart-summary-line cart-subtotal-products">
                            <label>جمع محصولات</label>
                            <span class="price price-total">{cart.total_price_after_discount:,.0f} ريال</span>
                        </div>
                        <div class="cart-summary-line shipping-hook"></div>
                    </div>
                    <div class="cart-action">
                        <div class="text-center">
                            <a href="/checkout" class="btn btn-primary">مشاهده و پرداخت &nbsp;<i class="caret-right"></i></a>
                        </div>
                    </div>
                </div>"""
    else:
        body = """<div class="cart-title h4">سبد خرید</div>
                <div class="no-items">سبد خرید شما خالی است</div>"""
    full_html = f"""<div class="shopping-cart-module">
        <div class="blockcart cart-preview" data-refresh-url="/cart/refresh-preview" data-sidebar-cart-trigger>
            <ul class="cart-header">
                <li data-header-cart-source>
                    <a style="border-radius: 10px" rel="nofollow" href="/cart" class="cart-link btn-primary">
                        <span class="cart-design">
                            <i class="fa fa-shopping-basket" aria-hidden="true"></i>
                            <span class="cart-products-count js-cart-count">{cart.count}</span>
                        </span>
                        <span class="cart-total-value">{cart.total_price_after_discount:,.0f} ريال</span>
                    </a>
                </li>
            </ul>
            <div class="cart-dropdown" data-shopping-cart-source>
                <div class="cart-dropdown-wrapper">
                    {body}
                </div>
                <div class="js-cart-update-quantity page-loading-overlay cart-overview-loading">
                    <div class="page-loading-backdrop d-flex align-items-center justify-content-center">
                        <span class="uil-spin-css"><span><span></span></span><span><span></span></span><span><span></span></span><span><span></span></span><span><span></span></span><span><span></span></span><span><span></span></span><span><span></span></span></span>
                    </div>
                </div>
            </div>
        </div>
    </div>"""
    return full_html


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

    _map = lambda pl: [product_service._build_product_list_response(p) for p in pl]
    cc = await _get_cart_context(request, db)
    return templates.TemplateResponse("shop/index.html", {
        "request": request,
        "special_products": _map(special_products),
        "new_products": _map(new_products),
        "restocked_products": _map(restocked_products),
        "suggested_products": _map(suggested_products),
        "top_category": top_category,
        "top_category_title": top_category.title if top_category else None,
        "top_category_products": _map(top_category_products),
        "top_category_poster": top_category_poster,
        "middle_category": middle_category,
        "middle_category_title": middle_category.title if middle_category else None,
        "middle_category_products": _map(middle_category_products),
        "middle_category_poster": middle_category_poster,
        "mid_left_poster": mid_left_poster,
        "mid_right_poster": mid_right_poster,
        "bottom_category": bottom_category,
        "bottom_category_title": bottom_category.title if bottom_category else None,
        "bottom_category_products": _map(bottom_category_products),
        "bottom_category_poster": bottom_category_poster,
        "categories": categories,
        "header_categories": categories,
        "site_settings": site_settings,
        "current_user": current_user,
        **cc,
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
    current_user: Optional[User] = Depends(get_optional_user_from_cookie),
):
    if current_page and current_page > 0:
        page = current_page
    return await _render_product_list(
        request, db,
        category_id=category_id, category=category,
        branches=branches, brands=brands,
        min_value=min_value or min_price, max_value=max_value or max_price,
        order=order, query=query or q, page=page, page_size=page_size,
        current_user=current_user,
    )


@router.get("/search", response_class=HTMLResponse)
async def search_page(
    request: Request,
    q: Optional[str] = Query(None),
    query: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    order: str = Query("AlphabetAsc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(28, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user_from_cookie),
):
    search_term = query or q
    tags = [t.strip() for t in tag.split(",") if t.strip()] if tag else None
    tag_titles = {
        "new": "محصولات جدید",
        "special": "محصولات ویژه",
        "restocked": "تازه‌های رسیده",
        "suggested": "پیشنهاد آشا",
    }
    tags = [t for t in tags if t in tag_titles] if tags else None

    page_title = None
    if search_term:
        page_title = f'نتایج جستجو برای «{search_term}»'
    elif tags:
        page_title = "، ".join(tag_titles[t] for t in tags)

    return await _render_product_list(
        request, db,
        order=order, query=search_term, page=page, page_size=page_size,
        tags=tags, page_title=page_title, current_user=current_user,
    )


async def _render_product_list(
    request: Request, db: AsyncSession, *,
    category_id: Optional[str] = None, category: Optional[str] = None,
    branches: Optional[str] = None, brands: Optional[str] = None,
    min_value: Optional[float] = None, max_value: Optional[float] = None,
    order: str = "AlphabetAsc", query: Optional[str] = None,
    page: int = 1, page_size: int = 28,
    current_user: Optional[User] = None,
    tags: Optional[list[str]] = None,
    page_title: Optional[str] = None,
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
        order=order, query=query, page=page, page_size=page_size, tags=tags,
    )
    brand_facets = await product_service.get_brand_facets(db, category_id=cat_uuid, branch_ids=branch_ids or None)
    _, price_max = await product_service.get_category_price_range(db, category_id=cat_uuid, branch_ids=branch_ids or None)
    cats = await product_service.get_category_tree(db)

    from app.models.common import SiteSetting
    from sqlalchemy import select
    site_settings = (await db.execute(
        select(SiteSetting).where(SiteSetting.is_removed == False).limit(1)
    )).scalars().first()

    category_hierarchy = await _get_category_hierarchy(db, cat) if cat else []

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
    if tags:
        parts.append(f"tag={','.join(tags)}")
    filter_qs = "&".join(parts)

    cc = await _get_cart_context(request, db)
    return templates.TemplateResponse("shop/product_list.html", {
        "request": request,
        "category": cat,
        "categories": cats,
        "header_categories": cats,
        "children": list(cat.children) if cat and cat.children else [],
        "products": [product_service._build_product_list_response(p) for p in products],
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
        "category_hierarchy": category_hierarchy,
        "current_user": current_user,
        "page_title": page_title,
        **cc,
    })


@router.get("/products/{slug}", response_class=HTMLResponse)
async def product_detail_page(slug: str, request: Request, db: AsyncSession = Depends(get_db), current_user: Optional[User] = Depends(get_optional_user_from_cookie)):
    try:
        pid = uuid.UUID(slug)
        product = await product_service.get_product_by_id(db, pid)
    except ValueError:
        product = await product_service.get_product_by_slug(db, slug)

    if not product:
        return HTMLResponse("Product not found", status_code=404)

    await product_service.increment_product_view(db, product)
    detail = _build_shop_detail(product)
    related = await product_service.get_related_products(db, product, 12)
    similar = await product_service.get_similar_products(db, product, 12)
    category_hierarchy = await _get_category_hierarchy(db, product.category) if product.category else []
    cats = await product_service.get_category_tree(db)

    def _norm_list(plist):
        result = []
        for p in plist:
            r = product_service._build_product_list_response(p)
            d = r.model_dump()
            if d.get("medium_image_url"):
                d["medium_image_url"] = _normalize_media_url(d["medium_image_url"])
            if d.get("large_image_url"):
                d["large_image_url"] = _normalize_media_url(d["large_image_url"])
            result.append(d)
        return result

    cc = await _get_cart_context(request, db)
    return templates.TemplateResponse("shop/product_detail.html", {
        "request": request, "product": detail,
        "related_products": _norm_list(related),
        "similar_products": _norm_list(similar),
        "categories": cats, "header_categories": cats,
        "category_hierarchy": category_hierarchy,
        "current_user": current_user,
        **cc,
    })


@router.get("/cart", response_class=HTMLResponse)
async def cart_page(request: Request, db: AsyncSession = Depends(get_db), current_user: Optional[User] = Depends(get_optional_user_from_cookie)):
    cc = await _get_cart_context(request, db)
    cats = await product_service.get_category_tree(db)
    return templates.TemplateResponse("shop/cart.html", {**cc, "request": request, "categories": cats, "header_categories": cats, "current_user": current_user})


async def _checkout_context(request: Request, db: AsyncSession, user: User, order: Order, error: Optional[str] = None, site_settings=None):
    """Build the rendering context for the 4-step ordering page (mirrors .NET OrderingStep)."""
    from app.models.common import ProvinceCity

    identities = await order_service.get_user_identities(db, user.id)
    addresses = await order_service.get_user_addresses(db, user.id)
    post_types = await order_service.get_post_types(db)
    pay_methods = await order_service.get_pay_methods(db)

    provinces = {}
    prow = await db.execute(select(ProvinceCity).where(ProvinceCity.province_id.is_(None)))
    for p in prow.scalars().all():
        provinces[p.int_id] = p.name

    if site_settings is None:
        from app.models.common import SiteSetting
        ss_result = await db.execute(select(SiteSetting).where(SiteSetting.is_removed == False).limit(1))
        site_settings = ss_result.scalar_one_or_none()

    order_products = order.order_products or []
    step_identity = order.identity_information_id is not None
    step_address = order.address_id is not None
    step_post = order.post_type_id is not None
    if not step_identity:
        current_step = "identity"
    elif not step_address:
        current_step = "addresses"
    elif not step_post:
        current_step = "delivery"
    else:
        current_step = "pay"

    def step_class(step: str, done: bool) -> str:
        if step == current_step:
            return "checkout-step -current -reachable js-current-step"
        if done:
            return "checkout-step -reachable -complete"
        return "checkout-step -unreachable"

    cats = await product_service.get_category_tree(db)
    summary_items = []
    for op in order_products:
        product = op.product
        img = ""
        if product:
            img = normalize_image_url(product.medium_image_url or product.feature_image_url or product.image_url or "")
        summary_items.append({
            "name": product.name if product else "",
            "image": img,
            "variety_values": op.variety_values or "",
            "count": op.count or 1,
            "price_after_discount": float(op.price_after_discount or 0),
            "total": float(op.total_price_after_discount or 0),
            "slug": getattr(product, 'slug', ''),
        })
    return {
        "request": request,
        "order": order,
        "order_products": order_products,
        "summary_items": summary_items,
        "subtotal": float(order.total_price_after_discount or 0),
        "postage_fee": float(order.postage_fee or 0),
        "payable": float(order.payable or 0),
        "current_step": current_step,
        "steps": {
            "identity": step_class("identity", step_identity),
            "addresses": step_class("addresses", step_address),
            "delivery": step_class("delivery", step_post),
            "pay": step_class("pay", step_identity and step_address and step_post),
        },
        "identities": identities,
        "selected_identity_id": str(order.identity_information_id) if order.identity_information_id else None,
        "addresses": addresses,
        "selected_address_id": str(order.address_id) if order.address_id else None,
        "provinces": provinces,
        "post_types": post_types,
        "selected_post_type_id": str(order.post_type_id) if order.post_type_id else None,
        "pay_methods": pay_methods,
        "note": order.notes,
        "error": error,
        "categories": cats,
        "header_categories": cats,
        "cart_count": 0,
        "cart_total": 0,
        "site_settings": site_settings,
        "current_user": user,
    }


@router.get("/checkout", response_class=HTMLResponse)
async def checkout_ordering_step(
    request: Request,
    identity_id: Optional[str] = Query(None, alias="identityId"),
    address_id: Optional[str] = Query(None, alias="addressId"),
    PostTypeId: Optional[str] = Query(None, alias="PostTypeId"),
    note: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user_from_cookie),
):
    if current_user is None:
        return RedirectResponse(url="/login?returnUrl=/checkout", status_code=303)
    cart = parse_cart(request)
    order, consumed = await order_service.sync_ordering_order_from_cart(db, current_user, cart)
    if order is None or not (order.order_products or []):
        return RedirectResponse(url="/cart", status_code=303)
    from app.models.common import SiteSetting
    ss_result = await db.execute(select(SiteSetting).where(SiteSetting.is_removed == False).limit(1))
    site_settings = ss_result.scalar_one_or_none()
    # ── identityId: set identity, then show next unreached stage ──
    if identity_id:
        try:
            await order_service.set_ordering_identity(db, current_user, order, uuid.UUID(identity_id))
            await db.commit()
        except (ValueError, AttributeError):
            pass
        # Re-fetch order with updated state
        order = await order_service.get_ordering_order_full(db, current_user.id)
        # Redirect to checkout without identityId param to get proper step routing
        qs = []
        if address_id:
            qs.append(f"addressId={address_id}")
        if PostTypeId:
            qs.append(f"PostTypeId={PostTypeId}")
        q = f"?{'&'.join(qs)}" if qs else ""
        return RedirectResponse(url=f"/checkout{q}", status_code=303)
    # ── addressId: set address, then show next stage ──
    if address_id:
        try:
            await order_service.set_ordering_address(db, current_user, order, uuid.UUID(address_id))
            await db.commit()
        except ValueError:
            pass
        order = await order_service.get_ordering_order_full(db, current_user.id)
        qs = []
        if PostTypeId:
            qs.append(f"PostTypeId={PostTypeId}")
        q = f"?{'&'.join(qs)}" if qs else ""
        return RedirectResponse(url=f"/checkout{q}", status_code=303)
    # ── PostTypeId: set post type, then show payment stage ──
    if PostTypeId:
        try:
            await order_service.set_ordering_post(db, order, uuid.UUID(PostTypeId), note)
            await db.commit()
        except ValueError:
            pass
        return RedirectResponse(url="/checkout", status_code=303)
    # ── No params: route to correct stage ──
    if order.identity_information_id is None:
        identities = await order_service.get_user_identities(db, current_user.id)
        if not identities:
            resp = RedirectResponse(url="/identity-information/create?redirect=true", status_code=303)
            if consumed:
                save_cart_response(Cart(), resp)
            return resp
    ctx = await _checkout_context(request, db, current_user, order, site_settings=site_settings)
    resp = templates.TemplateResponse("shop/checkout.html", ctx)
    if consumed:
        save_cart_response(Cart(), resp)
    return resp


@router.post("/checkout", response_class=HTMLResponse)
async def checkout_ordering_submit(
    request: Request,
    address_id: Optional[str] = Form(None),
    PostTypeId: Optional[str] = Form(None),
    note: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user_from_cookie),
):
    if current_user is None:
        return RedirectResponse(url="/login?returnUrl=/checkout", status_code=303)
    cart = parse_cart(request)
    order, consumed = await order_service.sync_ordering_order_from_cart(db, current_user, cart)
    if order is None or not (order.order_products or []):
        return RedirectResponse(url="/cart", status_code=303)
    error = None
    if address_id:
        try:
            await order_service.set_ordering_address(db, current_user, order, uuid.UUID(address_id))
            await db.commit()
        except ValueError as e:
            error = str(e)
        if not error:
            return RedirectResponse(url="/checkout", status_code=303)
    if PostTypeId:
        try:
            await order_service.set_ordering_post(db, order, uuid.UUID(PostTypeId), note)
            await db.commit()
        except ValueError as e:
            error = error or str(e)
        if not error:
            return RedirectResponse(url="/checkout", status_code=303)
    ctx = await _checkout_context(request, db, current_user, order, error=error)
    resp = templates.TemplateResponse("shop/checkout.html", ctx)
    if consumed:
        save_cart_response(Cart(), resp)
    return resp


@router.post("/checkout/payment", response_class=RedirectResponse)
async def checkout_payment_submit(
    request: Request,
    pay_method_id: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user_from_cookie),
):
    if current_user is None:
        return RedirectResponse(url="/login?returnUrl=/checkout", status_code=303)
    order = await order_service.get_ordering_order_full(db, current_user.id)
    if order is None or not (order.order_products or []):
        return RedirectResponse(url="/cart", status_code=303)
    try:
        await order_service.pay_ordering_order(db, order, uuid.UUID(pay_method_id))
    except ValueError as e:
        ctx = await _checkout_context(request, db, current_user, order, error=str(e))
        # Can't return template from RedirectResponse route; fallback redirect with error in session
        return RedirectResponse(url="/checkout?error=" + str(e), status_code=303)
    return RedirectResponse(url=f"/orders/{order.id}", status_code=303)


@router.post("/checkout/paper-invoice")
async def checkout_paper_invoice(
    invoice_required: str = Form("false"),
    db: AsyncSession = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user_from_cookie),
):
    if current_user is None:
        return JSONResponse({"ok": False})
    order = await order_service.get_ordering_order_full(db, current_user.id)
    if order is None:
        return JSONResponse({"ok": False})
    order.paper_invoice = invoice_required in ("true", "1", "on")
    await db.flush()
    await db.commit()
    return JSONResponse({"invoice_required": 1 if order.paper_invoice else 0})


# ── ProformaInvoice (printable preview, mirrors .NET OrderController.ProformaInvoice) ──

@router.get("/checkout/proforma-invoice/{order_id}", response_class=HTMLResponse)
async def proforma_invoice(
    order_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    try:
        oid = uuid.UUID(order_id)
    except ValueError:
        return HTMLResponse("Order not found", status_code=404)
    order = await order_service.get_admin_order_detail(db, oid)
    if not order or order.user_id != current_user.id:
        return HTMLResponse("Order not found", status_code=404)
    # Build a proforma invoice dict from the order
    inv = await order_service.build_proforma_invoice(db, order)
    return templates.TemplateResponse("shop/proforma_invoice.html", {"request": request, "invoice": inv})


# ── Orders ──

@router.get("/orders", response_class=HTMLResponse)
async def orders_page(request: Request, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    orders_list, _ = await order_service.get_user_orders(db, current_user.id, 1, 50)
    cc = await _get_cart_context(request, db)
    return templates.TemplateResponse("shop/order_list.html", {"request": request, "orders": [order_service.build_order_response(o) for o in orders_list], **cc})


@router.get("/orders/unpaid", response_class=HTMLResponse)
async def orders_unpaid_page(request: Request, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    orders_list, _ = await order_service.get_user_orders(db, current_user.id, 1, 50)
    unpaid = [order_service.build_order_response(o) for o in orders_list if o.order_status in ("AwaitingPayment", "Ordering")]
    cc = await _get_cart_context(request, db)
    return templates.TemplateResponse("shop/unpaid_orders.html", {
        "request": request, "current_user": current_user, "orders": unpaid, **cc,
    })


@router.get("/orders/history", response_class=HTMLResponse)
async def orders_history_page(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.invoice import Invoice
    from app.models.order import OrderProduct
    from sqlalchemy import select, func
    exclude = ("Ordering", "NextOrder", "NeedsToBeChecked")
    stmt = (
        select(Order)
        .options(
            selectinload(Order.order_products).selectinload(OrderProduct.product),
            selectinload(Order.order_status_records),
        )
        .where(
            Order.user_id == current_user.id,
            Order.is_removed == False,
            Order.order_status.notin_(exclude),
        )
        .order_by(Order.date.desc())
    )
    result = await db.execute(stmt)
    orders = result.unique().scalars().all()
    # Check invoice existence for each order
    order_ids = [o.id for o in orders]
    inv_stmt = select(Invoice.order_id).where(
        Invoice.order_id.in_(order_ids),
        Invoice.status == "Confirmed",
        Invoice.type == "Sale",
        Invoice.is_removed == False,
    )
    inv_result = await db.execute(inv_stmt)
    invoice_order_ids = {r[0] for r in inv_result.all()}
    order_list = []
    for o in orders:
        resp = order_service.build_order_response(o)
        resp["has_invoice"] = o.id in invoice_order_ids
        order_list.append(resp)
    cc = await _get_cart_context(request, db)
    return templates.TemplateResponse("shop/order_history.html", {
        "request": request, "current_user": current_user, "orders": order_list, **cc,
    })


@router.get("/orders/{order_id}", response_class=HTMLResponse)
async def order_detail_page(order_id: str, request: Request, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    try:
        oid = uuid.UUID(order_id)
        order = await order_service.get_admin_order_detail(db, oid)
    except ValueError:
        return HTMLResponse("Order not found", status_code=404)
    if not order or (order.user_id != current_user.id and "Admin" not in {ur.role.name for ur in current_user.roles}):
        return HTMLResponse("Order not found", status_code=404)
    cc = await _get_cart_context(request, db)
    detail = order_service.build_admin_order_response(order)
    # Precompute product totals matching .NET _orderDetail.cshtml footer math
    detail["products_total"] = sum(op.get("price_after_discount") or 0 for op in detail["order_products"])
    detail["products_vat"] = sum(
        (op.get("vat_rate") or 0) * (op.get("price_after_discount") or 0) / 100
        for op in detail["order_products"]
    )
    detail["payable_total"] = (detail["payable"] or 0)
    return templates.TemplateResponse("shop/order_detail.html", {
        "request": request, "order": detail, "current_user": current_user, **cc,
    })


# ── Profile Pages ──

@router.get("/profile", response_class=HTMLResponse)
async def profile_page(
    request: Request,
    notification: Optional[str] = Query(None),
    em_message: Optional[str] = Query(None),
    em_message_er: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    first_name: Optional[str] = Query(None),
    last_name: Optional[str] = Query(None),
    email: Optional[str] = Query(None),
    gender: Optional[str] = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    cc = await _get_cart_context(request, db)
    form_data = {
        "first_name": first_name or current_user.first_name or "",
        "last_name": last_name or current_user.last_name or "",
        "email": email or current_user.email or "",
        "gender": gender or current_user.gender or "Unknown",
    }
    return templates.TemplateResponse("shop/profile.html", {
        "request": request, "current_user": current_user, "section": "profile",
        "notification": notification, "em_message": em_message, "em_message_er": em_message_er,
        "error": error, "form": form_data, **cc,
    })


@router.post("/profile", response_class=RedirectResponse)
async def profile_update(
    request: Request,
    first_name: str = Form(...),
    last_name: str = Form(...),
    email: str = Form(...),
    gender: str = Form("Unknown"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select
    from app.models.identity import User as UserModel

    # Check email uniqueness
    if email != current_user.email:
        stmt = select(UserModel).where(UserModel.email == email, UserModel.is_removed == False, UserModel.id != current_user.id)
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing:
            params = f"?error=کاربر دیگری با این ایمیل قبلا ثبت نام کرده&first_name={first_name}&last_name={last_name}&email={email}&gender={gender}"
            return RedirectResponse(url=f"/profile{params}", status_code=303)

    current_user.first_name = first_name
    current_user.last_name = last_name
    current_user.gender = gender

    if email != current_user.email:
        current_user.email = email
        current_user.email_confirmed = False

    current_user.update_date = datetime.now(timezone.utc)
    await db.flush()

    return RedirectResponse(url="/profile?notification=اطلاعات شما با موفقیت بروزرسانی شد", status_code=303)


@router.get("/profile/send-confirm-email", response_class=JSONResponse)
async def profile_send_confirm_email(
    request: Request,
    current_user: User = Depends(get_current_active_user),
):
    from app.services.auth_flow import create_email_confirm_token
    from app.services.email_service import EmailSender
    if not current_user.email:
        return JSONResponse({"isSucceded": False, "message": "ایمیل ثبت نشده است"})
    try:
        token = create_email_confirm_token(current_user.id)
        base = str(request.base_url).rstrip("/")
        callback = f"{base}/profile/confirm-email?token={token}"
        await EmailSender().send_view_email(current_user.email, "همدوس - تأیید ایمیل", "email/confirm_email.html", {"callback_url": callback})
        return JSONResponse({"isSucceded": True, "message": "ایمیل با موفقیت ارسال شد"})
    except Exception:
        return JSONResponse({"isSucceded": False, "message": "خطا در عملیات"})


@router.get("/profile/confirm-email", response_class=RedirectResponse)
async def profile_confirm_email(
    request: Request,
    token: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    from app.services.auth_flow import decode_auth_token
    if not token:
        return RedirectResponse(url="/profile?em_message_er=خطا در تایید ایمیل", status_code=303)
    user_id = decode_auth_token(token, "email_confirm")
    if user_id and user_id == current_user.id and not current_user.email_confirmed:
        current_user.email_confirmed = True
        current_user.update_date = datetime.now(timezone.utc)
        await db.flush()
        return RedirectResponse(url="/profile?em_message=ایمیل با موفقیت تایید شد", status_code=303)
    return RedirectResponse(url="/profile?em_message_er=خطا در تایید ایمیل", status_code=303)


@router.get("/profile/phone-numbers", response_class=HTMLResponse)
async def profile_phone_numbers(
    request: Request,
    notification: Optional[str] = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select
    from app.models.common import Address
    stmt = (
        select(Address)
        .where(Address.user_id == current_user.id, Address.is_removed == False)
    )
    result = await db.execute(stmt)
    addresses = result.scalars().all()
    primary = current_user.phone_number
    confirmed_nums = {primary} | {a.phone_number for a in addresses if a.phone_number_confirmed}
    confirmed = [a for a in addresses if a.phone_number_confirmed and a.phone_number != primary]
    unconfirmed = [a for a in addresses if not a.phone_number_confirmed and a.phone_number not in confirmed_nums]
    cc = await _get_cart_context(request, db)
    return templates.TemplateResponse("shop/profile_phone_numbers.html", {
        "request": request, "current_user": current_user,
        "confirmed_addresses": confirmed, "unconfirmed_addresses": unconfirmed,
        "notification": notification, **cc,
    })


@router.post("/profile/phone-numbers/verify")
async def profile_phone_numbers_verify(
    request: Request,
    phone_number: str = Form(...),
    address_id: str = Form(""),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select
    from app.models.common import Address
    from app.services.auth_flow import send_verification_sms
    from uuid import UUID

    query = select(Address).where(
        Address.phone_number == phone_number,
        Address.user_id == current_user.id,
        Address.phone_number_confirmed == False,
        Address.is_removed == False,
    )
    if address_id:
        query = query.where(Address.id == UUID(address_id))
    result = await db.execute(query)
    address = result.scalar_one_or_none()
    if not address:
        return JSONResponse({"hasError": True, "error": "آدرس یافت نشد"}, status_code=404)

    res = await send_verification_sms(db, phone_number, current_user)
    return JSONResponse({
        "redirectURL": str(request.url_for("profile_phone_send_sms_code").include_query_params(
            phone_number=phone_number, address_id=address.id,
        )),
        "hasError": False,
        "redirect": True,
    })


@router.get("/profile/phone-numbers/send-sms-code", response_class=HTMLResponse)
async def profile_phone_send_sms_code(
    request: Request,
    phone_number: str = Query(...),
    address_id: str = Query(...),
    code_error: Optional[str] = Query(None),
    timer: Optional[str] = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    from uuid import UUID
    from sqlalchemy import select
    from app.models.common import Address
    from app.services.auth_flow import check_sms_status

    result = await db.execute(
        select(Address).where(
            Address.id == UUID(address_id),
            Address.user_id == current_user.id,
            Address.is_removed == False,
        )
    )
    address = result.scalar_one_or_none()
    if not address:
        return HTMLResponse("آدرس یافت نشد", status_code=404)

    sms_status = await check_sms_status(db, phone_number, current_user.id)
    display_timer = timer or sms_status["timer"]

    cc = await _get_cart_context(request, db)
    return templates.TemplateResponse("shop/phone_sms_verify.html", {
        "request": request, "current_user": current_user,
        "phone_number": phone_number, "address_id": address_id,
        "timer": display_timer, "code_error": code_error, **cc,
    })


@router.post("/profile/phone-numbers/send-sms-code", response_class=HTMLResponse)
async def profile_phone_send_sms_code_post(
    request: Request,
    code: str = Form(""),
    phone_number: str = Form(""),
    address_id: str = Form(""),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    from uuid import UUID
    from sqlalchemy import select
    from app.models.common import Address
    from app.services.auth_flow import verify_sms_code, check_sms_status

    address = await db.get(Address, UUID(address_id))
    if not address or address.user_id != current_user.id or address.is_removed:
        return HTMLResponse("آدرس یافت نشد", status_code=404)

    sms_status = await check_sms_status(db, phone_number, current_user.id)
    display_timer = sms_status["timer"]

    if not code or len(code) != 6:
        cc = await _get_cart_context(request, db)
        return templates.TemplateResponse("shop/phone_sms_verify.html", {
            "request": request, "current_user": current_user,
            "phone_number": phone_number, "address_id": address_id,
            "timer": display_timer,
            "code_error": "کد تایید باید 6 رقم باشد", **cc,
        })

    result = await verify_sms_code(db, current_user, phone_number, code)
    if not result["ok"]:
        cc = await _get_cart_context(request, db)
        return templates.TemplateResponse("shop/phone_sms_verify.html", {
            "request": request, "current_user": current_user,
            "phone_number": phone_number, "address_id": address_id,
            "timer": result.get("timer", display_timer),
            "code_error": result["error"], **cc,
        })

    address.phone_number_confirmed = True
    await db.flush()
    return RedirectResponse(
        url="/profile/phone-numbers?notification=شماره موبایل با موفقیت تایید شد",
        status_code=303,
    )


@router.get("/profile/phone-numbers/resend-code", response_class=RedirectResponse)
async def profile_phone_resend_code(
    request: Request,
    phone_number: str = Query(...),
    address_id: str = Query(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    from uuid import UUID
    from sqlalchemy import select
    from app.models.common import Address
    from app.services.auth_flow import send_verification_sms, check_sms_status

    address = await db.get(Address, UUID(address_id))
    if not address or address.user_id != current_user.id:
        return RedirectResponse(url="/profile/phone-numbers", status_code=303)

    await send_verification_sms(db, phone_number, current_user)
    return RedirectResponse(
        url=request.url_for("profile_phone_send_sms_code").include_query_params(
            phone_number=phone_number, address_id=address_id,
        ),
        status_code=303,
    )


@router.get("/profile/addresses", response_class=HTMLResponse)
async def profile_addresses(
    request: Request,
    notification: Optional[str] = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models.common import Address
    stmt = (
        select(Address)
        .options(selectinload(Address.province_city))
        .where(Address.user_id == current_user.id, Address.is_removed == False)
        .order_by(Address.insert_date.desc())
    )
    result = await db.execute(stmt)
    addresses = result.unique().scalars().all()
    cc = await _get_cart_context(request, db)
    return templates.TemplateResponse("shop/addresses.html", {
        "request": request, "current_user": current_user,
        "addresses": addresses, "notification": notification, **cc,
    })


@router.get("/profile/addresses/create", response_class=HTMLResponse)
async def profile_address_create_form(
    request: Request,
    back_to_order: Optional[str] = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.common import ProvinceCity
    from sqlalchemy import select
    prow = await db.execute(select(ProvinceCity).where(ProvinceCity.province_id.is_(None)).order_by(ProvinceCity.name))
    provinces = prow.scalars().all()
    selected_province_id = None
    cities = []
    for p in provinces:
        if p.name == "تهران":
            selected_province_id = str(p.id)
            cities = await _ensure_province_cities(db, p)
            break
    cc = await _get_cart_context(request, db)
    return templates.TemplateResponse("shop/address_create.html", {
        "request": request, "current_user": current_user,
        "provinces": provinces, "cities": cities,
        "selected_province_id": selected_province_id,
        "form": {}, "errors": {},
        "back_to_order": back_to_order == "true", **cc,
    })


@router.post("/profile/addresses/create", response_class=HTMLResponse)
async def profile_address_create_submit(
    request: Request,
    alias: str = Form(""),
    first_name: str = Form(...),
    last_name: str = Form(...),
    country: str = Form("Iran"),
    province_id: str = Form(""),
    province_city_id: str = Form(""),
    address_description: str = Form(...),
    telephone: str = Form(""),
    phone_number: str = Form(...),
    postal_code: str = Form(...),
    back_to_order: Optional[str] = Form(None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.common import Address, ProvinceCity
    from sqlalchemy import select
    from datetime import datetime, timezone
    import re

    errors = {}
    if not phone_number:
        errors["phone_number"] = "شماره موبایل الزامی است"
    elif not re.match(r"^09\d{9}$", phone_number):
        errors["phone_number"] = "شماره موبایل باید با 09 شروع شده و 11 رقم باشد"
    if not postal_code:
        errors["postal_code"] = "کد پستی الزامی است"
    elif not re.match(r"^\d{10}$", postal_code):
        errors["postal_code"] = "کد پستی باید 10 رقم باشد"
    if not province_city_id:
        errors["province_city_id"] = "شهر باید وارد شود"
    if not first_name:
        errors["first_name"] = "نام الزامی است"
    if not last_name:
        errors["last_name"] = "نام خانوادگی الزامی است"
    if not address_description:
        errors["address_description"] = "آدرس الزامی است"

    if errors:
        prow = await db.execute(select(ProvinceCity).where(ProvinceCity.province_id.is_(None)).order_by(ProvinceCity.name))
        provinces = prow.scalars().all()
        selected_province_id = province_id if province_id else None
        cities = []
        if province_id:
            try:
                prov_obj = await db.get(ProvinceCity, uuid.UUID(province_id))
                if prov_obj:
                    cities = await _ensure_province_cities(db, prov_obj)
            except ValueError:
                pass
        cc = await _get_cart_context(request, db)
        return templates.TemplateResponse("shop/address_create.html", {
            "request": request, "current_user": current_user,
            "provinces": provinces, "cities": cities,
            "selected_province_id": selected_province_id,
            "form": {
                "alias": alias, "first_name": first_name, "last_name": last_name,
                "address_description": address_description, "telephone": telephone,
                "phone_number": phone_number, "postal_code": postal_code,
            },
            "errors": errors,
            "back_to_order": back_to_order == "true", **cc,
        })

    try:
        pc_id = uuid.UUID(province_city_id)
    except ValueError:
        prow = await db.execute(select(ProvinceCity).where(ProvinceCity.province_id.is_(None)).order_by(ProvinceCity.name))
        provinces = prow.scalars().all()
        selected_province_id = province_id if province_id else None
        cities = []
        if province_id:
            try:
                prov_obj = await db.get(ProvinceCity, uuid.UUID(province_id))
                if prov_obj:
                    cities = await _ensure_province_cities(db, prov_obj)
            except ValueError:
                pass
        cc = await _get_cart_context(request, db)
        return templates.TemplateResponse("shop/address_create.html", {
            "request": request, "current_user": current_user,
            "provinces": provinces, "cities": cities,
            "selected_province_id": selected_province_id,
            "errors": {"province_city_id": "شهر انتخاب شده معتبر نیست"},
            "form": {
                "alias": alias, "first_name": first_name, "last_name": last_name,
                "address_description": address_description, "telephone": telephone,
                "phone_number": phone_number, "postal_code": postal_code,
            },
            "back_to_order": back_to_order == "true", **cc,
        })

    try:
        pv_id = int(province_id) if province_id else None
    except ValueError:
        pv_id = None

    addr = Address(
        id=uuid.uuid4(), user_id=current_user.id,
        first_name=first_name, last_name=last_name,
        phone_number=phone_number, telephone=telephone or None,
        alias=alias or None,
        address_description=address_description,
        postal_code=postal_code, country=country,
        province_city_id=pc_id, province_id=pv_id,
        insert_date=datetime.now(timezone.utc), update_date=datetime.now(timezone.utc),
    )
    db.add(addr)
    await db.flush()
    if back_to_order == "true":
        return RedirectResponse(url="/checkout", status_code=303)
    return RedirectResponse(url="/profile/addresses?notification=آدرس با موفقیت اضافه شد", status_code=303)


@router.get("/profile/addresses/edit/{addr_id}", response_class=HTMLResponse)
async def profile_address_edit_form(
    addr_id: str, request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.common import Address, ProvinceCity
    from sqlalchemy import select
    try:
        address = await db.get(Address, uuid.UUID(addr_id))
    except ValueError:
        return HTMLResponse("آدرس یافت نشد", status_code=404)
    if not address or address.user_id != current_user.id:
        return HTMLResponse("آدرس یافت نشد", status_code=404)

    prow = await db.execute(select(ProvinceCity).where(ProvinceCity.province_id.is_(None)).order_by(ProvinceCity.name))
    provinces = prow.scalars().all()

    selected_province_id = None
    cities = []
    if address.province_city_id:
        city_rec = await db.get(ProvinceCity, address.province_city_id)
        if city_rec and city_rec.province_id is not None:
            prov_stmt = select(ProvinceCity).where(
                ProvinceCity.int_id == city_rec.province_id,
                ProvinceCity.province_id.is_(None),
            )
            prov = (await db.execute(prov_stmt)).scalar_one_or_none()
            if prov:
                selected_province_id = str(prov.id)
                cities = await _ensure_province_cities(db, prov)
        elif city_rec:
            selected_province_id = str(city_rec.id)
            cities = await _ensure_province_cities(db, city_rec)

    cc = await _get_cart_context(request, db)
    return templates.TemplateResponse("shop/address_edit.html", {
        "request": request, "current_user": current_user,
        "address": address, "provinces": provinces,
        "cities": cities, "selected_province_id": selected_province_id, **cc,
    })


@router.post("/profile/addresses/edit/{addr_id}", response_class=HTMLResponse)
async def profile_address_edit_submit(
    addr_id: str, request: Request,
    alias: str = Form(""),
    first_name: str = Form(...),
    last_name: str = Form(...),
    country: str = Form("Iran"),
    province_id: str = Form(""),
    province_city_id: str = Form(""),
    address_description: str = Form(...),
    telephone: str = Form(""),
    phone_number: str = Form(...),
    postal_code: str = Form(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.common import Address, ProvinceCity
    from sqlalchemy import select
    from datetime import datetime, timezone
    import re
    try:
        address = await db.get(Address, uuid.UUID(addr_id))
    except ValueError:
        return HTMLResponse("آدرس یافت نشد", status_code=404)
    if not address or address.user_id != current_user.id:
        return HTMLResponse("آدرس یافت نشد", status_code=404)

    errors = {}
    if not phone_number:
        errors["phone_number"] = "شماره موبایل الزامی است"
    elif not re.match(r"^09\d{9}$", phone_number):
        errors["phone_number"] = "شماره موبایل باید با 09 شروع شده و 11 رقم باشد"
    if not postal_code:
        errors["postal_code"] = "کد پستی الزامی است"
    elif not re.match(r"^\d{10}$", postal_code):
        errors["postal_code"] = "کد پستی باید 10 رقم باشد"
    if not province_city_id:
        errors["province_city_id"] = "شهر باید وارد شود"
    if not first_name:
        errors["first_name"] = "نام الزامی است"
    if not last_name:
        errors["last_name"] = "نام خانوادگی الزامی است"
    if not address_description:
        errors["address_description"] = "آدرس الزامی است"

    if errors:
        prow = await db.execute(select(ProvinceCity).where(ProvinceCity.province_id.is_(None)).order_by(ProvinceCity.name))
        provinces = prow.scalars().all()
        selected_province_id = province_id if province_id else None
        cities = []
        if province_id:
            try:
                prov_obj = await db.get(ProvinceCity, uuid.UUID(province_id))
                if prov_obj:
                    cities = await _ensure_province_cities(db, prov_obj)
            except ValueError:
                pass
        cc = await _get_cart_context(request, db)
        return templates.TemplateResponse("shop/address_edit.html", {
            "request": request, "current_user": current_user,
            "address": address, "provinces": provinces,
            "cities": cities, "selected_province_id": selected_province_id,
            "errors": errors, **cc,
        })

    try:
        pc_id = uuid.UUID(province_city_id)
    except ValueError:
        prow = await db.execute(select(ProvinceCity).where(ProvinceCity.province_id.is_(None)).order_by(ProvinceCity.name))
        provinces = prow.scalars().all()
        selected_province_id = province_id if province_id else None
        cities = []
        if province_id:
            try:
                prov_obj = await db.get(ProvinceCity, uuid.UUID(province_id))
                if prov_obj:
                    cities = await _ensure_province_cities(db, prov_obj)
            except ValueError:
                pass
        cc = await _get_cart_context(request, db)
        return templates.TemplateResponse("shop/address_edit.html", {
            "request": request, "current_user": current_user,
            "address": address, "provinces": provinces,
            "cities": cities, "selected_province_id": selected_province_id,
            "errors": {"province_city_id": "شهر انتخاب شده معتبر نیست"}, **cc,
        })

    try:
        pv_id = int(province_id) if province_id else None
    except ValueError:
        pv_id = None

    if phone_number != address.phone_number:
        address.phone_number_confirmed = False
    address.alias = alias or None
    address.first_name = first_name
    address.last_name = last_name
    address.country = country
    address.province_id = pv_id
    address.province_city_id = pc_id
    address.address_description = address_description
    address.telephone = telephone or None
    address.phone_number = phone_number
    address.postal_code = postal_code
    address.update_date = datetime.now(timezone.utc)

    await db.flush()
    return RedirectResponse(url="/profile/addresses?notification=آدرس با موفقیت ویرایش شد", status_code=303)


@router.get("/profile/addresses/delete/{addr_id}", response_class=RedirectResponse)
async def profile_address_delete(
    addr_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.common import Address
    try:
        addr = await db.get(Address, uuid.UUID(addr_id))
        if addr and addr.user_id == current_user.id:
            addr.is_removed = True
            addr.update_date = datetime.now(timezone.utc)
            await db.flush()
    except ValueError:
        pass
    return RedirectResponse(url="/profile/addresses?notification=آدرس با موفقیت حذف شد", status_code=303)


@router.get("/profile/addresses/cities/{province_id}", response_class=JSONResponse)
async def profile_address_cities(
    province_id: str,
    db: AsyncSession = Depends(get_db),
):
    from app.models.common import ProvinceCity
    from sqlalchemy import select
    from datetime import datetime, timezone
    try:
        pid = uuid.UUID(province_id)
    except ValueError:
        return JSONResponse({"succeded": False})
    province = await db.get(ProvinceCity, pid)
    if not province:
        return JSONResponse({"succeded": False})
    city_rows = await db.execute(
        select(ProvinceCity).where(
            ProvinceCity.province_id == province.int_id,
            ProvinceCity.is_removed == False,
        ).order_by(ProvinceCity.name)
    )
    cities = city_rows.scalars().all()

    if not cities:
        city_data_rows = await db.execute(
            select(City).where(
                City.province_id == province.int_id,
                City.is_removed == False,
            ).order_by(City.name)
        )
        city_data = city_data_rows.scalars().all()
        if city_data:
            max_int = 0
            max_row = await db.execute(select(ProvinceCity).order_by(ProvinceCity.int_id.desc()).limit(1))
            max_obj = max_row.scalar_one_or_none()
            if max_obj:
                max_int = max_obj.int_id
            new_cities = []
            for cd in city_data:
                max_int += 1
                pc = ProvinceCity(
                    id=uuid.uuid4(),
                    name=cd.name,
                    int_id=max_int,
                    province_id=province.int_id,
                    insert_date=datetime.now(timezone.utc),
                    update_date=datetime.now(timezone.utc),
                )
                db.add(pc)
                new_cities.append(pc)
            await db.flush()
            cities = new_cities

    return JSONResponse({
        "succeded": True,
        "cities": [
            {"value": str(c.id), "text": c.name, "selected": False}
            for c in cities
        ],
    })


@router.get("/profile/bank-info", response_class=HTMLResponse)
async def profile_bank_info(
    request: Request,
    notification: Optional[str] = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.common import BankInfo
    from sqlalchemy import select
    stmt = select(BankInfo).where(BankInfo.user_id == current_user.id, BankInfo.is_removed == False)
    result = await db.execute(stmt)
    bank_infos = result.scalars().all()
    cc = await _get_cart_context(request, db)
    return templates.TemplateResponse("shop/bank_info.html", {
        "request": request, "current_user": current_user,
        "bank_infos": bank_infos, "notification": notification, **cc,
    })


@router.get("/profile/bank-info/create", response_class=HTMLResponse)
async def profile_bank_info_create_form(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    cc = await _get_cart_context(request, db)
    return templates.TemplateResponse("shop/bank_info_create.html", {
        "request": request, "current_user": current_user,
        "form": {}, "errors": {}, **cc,
    })


@router.post("/profile/bank-info/create", response_class=HTMLResponse)
async def profile_bank_info_create_submit(
    request: Request,
    bank_name: str = Form(""), account_owner: str = Form(...),
    sheba_number: str = Form(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.common import BankInfo
    from sqlalchemy import select
    from datetime import datetime, timezone

    form = {"bank_name": bank_name, "account_owner": account_owner, "sheba_number": sheba_number}
    errors = {}

    sheba = sheba_number.strip()
    if not sheba.startswith("IR"):
        errors["sheba_number"] = "شماره شبا صحیح نیست"
    else:
        rest = sheba[2:]
        modified = rest[2:] + "1827" + rest[:2]
        try:
            if int(modified) % 97 != 1:
                errors["sheba_number"] = "شماره شبا صحیح نیست"
        except (ValueError, IndexError):
            errors["sheba_number"] = "شماره شبا صحیح نیست"

    if not account_owner.strip():
        errors["account_owner"] = "نام صاحب حساب را وارد کنید"
    if not bank_name.strip():
        errors["bank_name"] = "نام بانک را وارد کنید"

    if not errors:
        existing = await db.execute(
            select(BankInfo).where(
                BankInfo.user_id == current_user.id,
                BankInfo.sheba_number == sheba,
                BankInfo.is_removed == False,
            )
        )
        if existing.scalar_one_or_none():
            errors["sheba_number"] = "شماره شبا قبلاً ثبت شده است"

    if errors:
        cc = await _get_cart_context(request, db)
        return templates.TemplateResponse("shop/bank_info_create.html", {
            "request": request, "current_user": current_user,
            "form": form, "errors": errors, **cc,
        }, status_code=422)

    bi = BankInfo(
        id=uuid.uuid4(), user_id=current_user.id,
        account_owner=account_owner.strip(), sheba_number=sheba,
        bank_name=bank_name.strip(),
        insert_date=datetime.now(timezone.utc), update_date=datetime.now(timezone.utc),
    )
    db.add(bi)
    await db.flush()
    return RedirectResponse(
        url="/profile/bank-info?notification=اطلاعات حساب بانکی با موفقیت افزوده شد",
        status_code=303,
    )


@router.get("/profile/bank-info/edit/{bi_id}", response_class=HTMLResponse)
async def profile_bank_info_edit_form(
    bi_id: str, request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.common import BankInfo
    bank_info = await db.get(BankInfo, uuid.UUID(bi_id))
    if not bank_info or bank_info.user_id != current_user.id or bank_info.is_removed:
        return HTMLResponse("اطلاعات بانکی یافت نشد", status_code=404)
    cc = await _get_cart_context(request, db)
    return templates.TemplateResponse("shop/bank_info_edit.html", {
        "request": request, "current_user": current_user,
        "bank_info": bank_info, "errors": {}, **cc,
    })


@router.post("/profile/bank-info/edit/{bi_id}", response_class=HTMLResponse)
async def profile_bank_info_edit_submit(
    bi_id: str, request: Request,
    bank_name: str = Form(""), account_owner: str = Form(...),
    sheba_number: str = Form(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.common import BankInfo
    from sqlalchemy import select
    from datetime import datetime, timezone

    bank_info = await db.get(BankInfo, uuid.UUID(bi_id))
    if not bank_info or bank_info.user_id != current_user.id or bank_info.is_removed:
        return HTMLResponse("اطلاعات بانکی یافت نشد", status_code=404)

    errors = {}
    sheba = sheba_number.strip()
    if not sheba.startswith("IR"):
        errors["sheba_number"] = "شماره شبا صحیح نیست"
    else:
        rest = sheba[2:]
        modified = rest[2:] + "1827" + rest[:2]
        try:
            if int(modified) % 97 != 1:
                errors["sheba_number"] = "شماره شبا صحیح نیست"
        except (ValueError, IndexError):
            errors["sheba_number"] = "شماره شبا صحیح نیست"

    if not account_owner.strip():
        errors["account_owner"] = "نام صاحب حساب را وارد کنید"
    if not bank_name.strip():
        errors["bank_name"] = "نام بانک را وارد کنید"

    if not errors and sheba != bank_info.sheba_number:
        existing = await db.execute(
            select(BankInfo).where(
                BankInfo.user_id == current_user.id,
                BankInfo.sheba_number == sheba,
                BankInfo.is_removed == False,
                BankInfo.id != bank_info.id,
            )
        )
        if existing.scalar_one_or_none():
            errors["sheba_number"] = "شماره شبا قبلاً ثبت شده است"

    if errors:
        bank_info.bank_name = bank_name
        bank_info.account_owner = account_owner
        bank_info.sheba_number = sheba_number
        cc = await _get_cart_context(request, db)
        return templates.TemplateResponse("shop/bank_info_edit.html", {
            "request": request, "current_user": current_user,
            "bank_info": bank_info, "errors": errors, **cc,
        }, status_code=422)

    bank_info.bank_name = bank_name.strip()
    bank_info.account_owner = account_owner.strip()
    bank_info.sheba_number = sheba
    bank_info.update_date = datetime.now(timezone.utc)
    await db.flush()
    return RedirectResponse(
        url="/profile/bank-info?notification=اطلاعات حساب بانکی با موفقیت ویرایش شد",
        status_code=303,
    )


@router.get("/profile/bank-info/delete/{bi_id}", response_class=RedirectResponse)
async def profile_bank_info_delete(
    bi_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.common import BankInfo
    from datetime import datetime, timezone
    bank_info = await db.get(BankInfo, uuid.UUID(bi_id))
    if bank_info and bank_info.user_id == current_user.id and not bank_info.is_removed:
        bank_info.is_removed = True
        bank_info.update_date = datetime.now(timezone.utc)
        await db.flush()
    return RedirectResponse(
        url="/profile/bank-info?notification=اطلاعات حساب بانکی با موفقیت حذف شد",
        status_code=303,
    )


@router.get("/profile/favorites", response_class=HTMLResponse)
async def profile_favorites(request: Request, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    cc = await _get_cart_context(request, db)
    return templates.TemplateResponse("shop/favorites.html", {
        "request": request, "current_user": current_user, **cc,
    })


@router.get("/profile/favorites/lists", response_class=JSONResponse)
async def profile_favorites_lists(request: Request, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    from app.models.product import FavoriteProductList, FavoriteListItem
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    stmt = select(FavoriteProductList).where(
        FavoriteProductList.user_id == current_user.id, FavoriteProductList.is_removed == False
    ).options(selectinload(FavoriteProductList.favorite_list_items))
    result = await db.execute(stmt)
    lists = result.unique().scalars().all()
    domain = f"{request.url.scheme}://{request.url.hostname}"
    if request.url.port and request.url.port not in (80, 443):
        domain += f":{request.url.port}"
    wishlists = []
    for fl in lists:
        wishlists.append({
            "id_wishlist": str(fl.int_id),
            "nbProducts": str(len(fl.favorite_list_items or [])),
            "name": fl.name,
            "default": "1" if fl.is_default else "0",
            "shareUrl": f"{domain}/shared-favorites/{fl.token}",
            "listUrl": f"/profile/favorites/list/{fl.id}",
        })
    return JSONResponse({"wishlists": wishlists})


@router.post("/api/v1/favorites/list/create")
async def profile_favorites_list_create(request: Request, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    from app.models.product import FavoriteProductList
    from sqlalchemy import select, func
    form = await request.form()
    name = form.get("params[name]", "")
    if not name or not name.strip():
        return JSONResponse({"success": False, "message": "نام نمی تواند خالی باشد"})
    max_int = await db.execute(select(func.max(FavoriteProductList.int_id)))
    max_val = max_int.scalar() or 0
    fl = FavoriteProductList(
        id=uuid.uuid4(), user_id=current_user.id, name=name.strip(),
        count=0, token=uuid.uuid4(), is_default=False,
        int_id=max_val + 1,
        insert_date=datetime.now(timezone.utc), update_date=datetime.now(timezone.utc),
    )
    db.add(fl)
    await db.flush()
    return JSONResponse({"success": True, "message": "لیست با موفقیت ایجاد شد", "id_wishlist": str(fl.int_id)})


@router.post("/api/v1/favorites/list/rename")
async def profile_favorites_list_rename(request: Request, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    from app.models.product import FavoriteProductList
    from sqlalchemy import select
    form = await request.form()
    name = form.get("params[name]", "")
    id_str = form.get("params[idWishList]", "")
    if not name or not name.strip() or not id_str:
        return JSONResponse({"success": False, "message": "خطا در عملیات"})
    try:
        int_id = int(id_str)
    except ValueError:
        return JSONResponse({"success": False, "message": "خطا در عملیات"})
    stmt = select(FavoriteProductList).where(FavoriteProductList.int_id == int_id, FavoriteProductList.user_id == current_user.id, FavoriteProductList.is_removed == False)
    fl = (await db.execute(stmt)).scalar_one_or_none()
    if not fl:
        return JSONResponse({"success": False, "message": "خطا در عملیات"})
    fl.name = name.strip()
    fl.update_date = datetime.now(timezone.utc)
    await db.flush()
    return JSONResponse({"success": True, "message": "نام لیست تغییر داده شد"})


@router.post("/api/v1/favorites/list/delete")
async def profile_favorites_list_delete(request: Request, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    from app.models.product import FavoriteProductList
    from sqlalchemy import select
    form = await request.form()
    id_str = form.get("params[idWishList]", "")
    if not id_str:
        return JSONResponse({"success": False, "message": "خطا در عملیات"})
    try:
        int_id = int(id_str)
    except ValueError:
        return JSONResponse({"success": False, "message": "خطا در عملیات"})
    stmt = select(FavoriteProductList).where(FavoriteProductList.int_id == int_id, FavoriteProductList.user_id == current_user.id, FavoriteProductList.is_removed == False)
    fl = (await db.execute(stmt)).scalar_one_or_none()
    if not fl:
        return JSONResponse({"success": False, "message": "خطا در عملیات"})
    fl.is_removed = True
    fl.update_date = datetime.now(timezone.utc)
    await db.flush()
    return JSONResponse({"success": True, "message": "با موفقیت حذف شد"})


@router.post("/api/v1/favorites/item/add")
async def profile_favorites_item_add(request: Request, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    from app.models.product import FavoriteProductList, FavoriteListItem, Product
    from sqlalchemy import select
    form = await request.form()
    favorite_list_id = form.get("params[idWishList]", "")
    p_id = form.get("params[id_product]", "")
    quantity = form.get("params[quantity]", "1")
    if not favorite_list_id or not p_id:
        return JSONResponse({"success": False, "message": "خطا در عملیات"})
    try:
        fav_int_id = int(favorite_list_id)
        p_int_id = int(p_id)
        qty = int(quantity)
    except ValueError:
        return JSONResponse({"success": False, "message": "خطا در عملیات"})
    fav_stmt = select(FavoriteProductList).where(FavoriteProductList.int_id == fav_int_id, FavoriteProductList.is_removed == False)
    fav_list = (await db.execute(fav_stmt)).scalar_one_or_none()
    if not fav_list:
        return JSONResponse({"success": False, "message": "خطا در عملیات"})
    prod_stmt = select(Product).where(Product.int_id == p_int_id, Product.is_removed == False)
    product = (await db.execute(prod_stmt)).scalar_one_or_none()
    if not product:
        return JSONResponse({"success": False, "message": "خطا در عملیات"})
    existing_stmt = select(FavoriteListItem).where(
        FavoriteListItem.favorite_product_list_id == fav_list.id,
        FavoriteListItem.product_id == product.id,
        FavoriteListItem.is_removed == False,
    )
    existing = (await db.execute(existing_stmt)).scalar_one_or_none()
    if existing:
        return JSONResponse({"success": True, "message": "این محصول از قبل در لیست مورد نظر است"})
    item = FavoriteListItem(
        id=uuid.uuid4(), product_id=product.id,
        favorite_product_list_id=fav_list.id, quantity=qty,
        insert_date=datetime.now(timezone.utc),
    )
    db.add(item)
    fav_list.count = len(fav_list.favorite_list_items or []) + 1
    fav_list.update_date = datetime.now(timezone.utc)
    await db.flush()
    return JSONResponse({"success": True, "message": "محصول به علاقه مندی ها اضافه شد"})


@router.post("/api/v1/favorites/item/remove-all")
async def profile_favorites_item_remove_all(request: Request, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    from app.models.product import FavoriteProductList, FavoriteListItem, Product
    from sqlalchemy import select
    form = await request.form()
    p_id = form.get("params[id_product]", "")
    if not p_id:
        return JSONResponse({"success": False, "message": "خطا در عملیات"})
    try:
        p_int_id = int(p_id)
    except ValueError:
        return JSONResponse({"success": False, "message": "خطا در عملیات"})
    prod_stmt = select(Product).where(Product.int_id == p_int_id, Product.is_removed == False)
    product = (await db.execute(prod_stmt)).scalar_one_or_none()
    if not product:
        return JSONResponse({"success": False, "message": "خطا در عملیات"})
    stmt = (
        select(FavoriteListItem, FavoriteProductList)
        .join(FavoriteProductList, FavoriteListItem.favorite_product_list_id == FavoriteProductList.id)
        .where(
            FavoriteListItem.product_id == product.id,
            FavoriteListItem.is_removed == False,
            FavoriteProductList.user_id == current_user.id,
            FavoriteProductList.is_removed == False,
        )
    )
    rows = (await db.execute(stmt)).all()
    now = datetime.now(timezone.utc)
    for item, fav_list in rows:
        item.is_removed = True
        fav_list.count = max(0, (fav_list.count or 1) - 1)
        fav_list.update_date = now
    await db.flush()
    return JSONResponse({"success": True, "message": "محصول از علاقه مندی ها حذف شد"})


@router.get("/api/v1/favorites/item/delete")
async def profile_favorites_item_delete(request: Request, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    from app.models.product import FavoriteProductList, FavoriteListItem, Product
    from sqlalchemy import select
    favorite_list_id = request.query_params.get("params[idWishList]", "")
    p_id = request.query_params.get("params[id_product]", "")
    if not favorite_list_id or not p_id:
        return JSONResponse({"success": False, "message": "خطا در عملیات"})
    try:
        fav_int_id = int(favorite_list_id)
        p_int_id = int(p_id)
    except ValueError:
        return JSONResponse({"success": False, "message": "خطا در عملیات"})
    fav_stmt = select(FavoriteProductList).where(FavoriteProductList.int_id == fav_int_id, FavoriteProductList.user_id == current_user.id, FavoriteProductList.is_removed == False)
    fav_list = (await db.execute(fav_stmt)).scalar_one_or_none()
    if not fav_list:
        return JSONResponse({"success": False, "message": "خطا در عملیات"})
    prod_stmt = select(Product).where(Product.int_id == p_int_id, Product.is_removed == False)
    product = (await db.execute(prod_stmt)).scalar_one_or_none()
    if not product:
        return JSONResponse({"success": False, "message": "خطا در عملیات"})
    item_stmt = select(FavoriteListItem).where(
        FavoriteListItem.product_id == product.id,
        FavoriteListItem.favorite_product_list_id == fav_list.id,
        FavoriteListItem.is_removed == False,
    )
    item = (await db.execute(item_stmt)).scalar_one_or_none()
    if not item:
        return JSONResponse({"success": False, "message": "خطا در عملیات"})
    item.is_removed = True
    fav_list.count = max(0, (fav_list.count or 1) - 1)
    fav_list.update_date = datetime.now(timezone.utc)
    await db.flush()
    return JSONResponse({"success": True, "message": "محصول از لیست حذف شد"})


@router.get("/api/v1/favorites/check/{product_int_id}")
async def profile_favorites_check(product_int_id: int, request: Request, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    from app.models.product import FavoriteProductList, FavoriteListItem, Product
    from sqlalchemy import select
    prod_stmt = select(Product).where(Product.int_id == product_int_id, Product.is_removed == False)
    product = (await db.execute(prod_stmt)).scalar_one_or_none()
    if not product:
        return JSONResponse({"checked": False})
    item_stmt = select(FavoriteListItem).join(FavoriteProductList).where(
        FavoriteListItem.product_id == product.id,
        FavoriteListItem.is_removed == False,
        FavoriteProductList.user_id == current_user.id,
        FavoriteProductList.is_removed == False,
    ).limit(1)
    item = (await db.execute(item_stmt)).scalar_one_or_none()
    return JSONResponse({"checked": item is not None})


@router.get("/profile/favorites/list/{list_id}", response_class=HTMLResponse)
async def profile_favorites_list_products(list_id: str, request: Request, current_user: User = Depends(get_current_active_user), db: AsyncSession = Depends(get_db)):
    from app.models.product import FavoriteProductList, FavoriteListItem, Product
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    try:
        lid = uuid.UUID(list_id)
    except ValueError:
        return HTMLResponse("Not found", status_code=404)
    stmt = select(FavoriteProductList).where(
        FavoriteProductList.id == lid,
        FavoriteProductList.user_id == current_user.id,
        FavoriteProductList.is_removed == False,
    ).options(selectinload(FavoriteProductList.favorite_list_items).selectinload(FavoriteListItem.product).selectinload(Product.varieties))
    fl = (await db.execute(stmt)).unique().scalar_one_or_none()
    if not fl:
        return HTMLResponse("Not found", status_code=404)
    # Normalize product image URLs
    for item in (fl.favorite_list_items or []):
        if item.product:
            item.product.medium_image_url = _normalize_media_url(item.product.medium_image_url)
            item.product.feature_image_url = _normalize_media_url(item.product.feature_image_url)
            item.product.large_image_url = _normalize_media_url(item.product.large_image_url)
    cc = await _get_cart_context(request, db)
    return templates.TemplateResponse("shop/favorite_list_products.html", {
        "request": request, "current_user": current_user, "favorite_list": fl, **cc,
    })


@router.get("/shared-favorites/{token}", response_class=HTMLResponse)
async def profile_favorites_shared(token: str, request: Request, db: AsyncSession = Depends(get_db)):
    from app.models.product import FavoriteProductList, FavoriteListItem, Product
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    try:
        tok = uuid.UUID(token)
    except ValueError:
        return HTMLResponse("Not found", status_code=404)
    stmt = select(FavoriteProductList).where(
        FavoriteProductList.token == tok,
        FavoriteProductList.is_removed == False,
    ).options(selectinload(FavoriteProductList.favorite_list_items).selectinload(FavoriteListItem.product).selectinload(Product.varieties))
    fl = (await db.execute(stmt)).unique().scalar_one_or_none()
    if not fl:
        return HTMLResponse("Not found", status_code=404)
    for item in (fl.favorite_list_items or []):
        if item.product:
            item.product.medium_image_url = _normalize_media_url(item.product.medium_image_url)
            item.product.feature_image_url = _normalize_media_url(item.product.feature_image_url)
            item.product.large_image_url = _normalize_media_url(item.product.large_image_url)
    cc = await _get_cart_context(request, db)
    return templates.TemplateResponse("shop/favorite_list_shared.html", {
        "request": request, "favorite_list": fl, **cc,
    })


# ── Profile Identity Information (mirrors .NET IdentityInformationUserController) ──

@router.get("/profile/identity", response_class=HTMLResponse)
async def profile_identity(
    request: Request,
    identity_notif: Optional[str] = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.identity import IdentityInformation
    from sqlalchemy import select
    stmt = select(IdentityInformation).where(
        IdentityInformation.user_id == current_user.id,
        IdentityInformation.is_removed == False,
        IdentityInformation.status != "PendingDeletion",
    )
    result = await db.execute(stmt)
    identities = result.scalars().all()
    cc = await _get_cart_context(request, db)
    return templates.TemplateResponse("shop/identity.html", {
        "request": request, "current_user": current_user, "identities": identities,
        "identity_notif": identity_notif, **cc,
    })


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
    return RedirectResponse(url="/profile/identity?identity_notif=اطلاعات با موفقیت ثبت شد", status_code=303)


@router.get("/profile/identity/delete/{identity_id}", response_class=RedirectResponse)
async def profile_identity_delete(
    identity_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.identity import IdentityInformation
    try:
        info = await db.get(IdentityInformation, uuid.UUID(identity_id))
        if info and info.user_id == current_user.id and info.status != "PendingDeletion":
            info.status = "PendingDeletion"
            info.update_date = datetime.now(timezone.utc)
            await db.flush()
    except ValueError:
        pass
    return RedirectResponse(url="/profile/identity?identity_notif=اطلاعات با موفقیت حذف شد", status_code=303)


@router.get("/profile/identity/edit/{identity_id}", response_class=HTMLResponse)
async def profile_identity_edit_page(
    identity_id: str,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.identity import IdentityInformation
    from app.models.common import ProvinceCity
    try:
        info = await db.get(IdentityInformation, uuid.UUID(identity_id))
    except ValueError:
        return HTMLResponse("Not found", status_code=404)
    if not info or info.user_id != current_user.id or info.status == "PendingDeletion":
        return HTMLResponse("Not found", status_code=404)
    prow = await db.execute(select(ProvinceCity).where(ProvinceCity.province_id.is_(None)))
    provinces = prow.scalars().all()
    city_rows = await db.execute(select(ProvinceCity).where(ProvinceCity.province_id.is_not(None)))
    cities = city_rows.scalars().all()
    selected_province_id = None
    selected_city_id = None
    if info.province:
        for p in provinces:
            if p.name == info.province:
                selected_province_id = str(p.id)
                break
    if info.city and selected_province_id:
        for c in cities:
            if c.name == info.city:
                selected_city_id = str(c.id)
                break
    cc = _cart_context_simple(request)
    return templates.TemplateResponse("shop/identity_edit.html", {
        "request": request, "current_user": current_user,
        "info": info, "provinces": provinces, "cities": cities,
        "selected_province_id": selected_province_id,
        "selected_city_id": selected_city_id, **cc,
    })


@router.post("/profile/identity/edit/{identity_id}", response_class=HTMLResponse)
async def profile_identity_edit_submit(
    identity_id: str,
    request: Request,
    name: str = Form(...),
    identity_type: str = Form("Real"),
    national_code_or_id: str = Form(""),
    economic_code: Optional[str] = Form(""),
    postal_code: str = Form(""),
    phone_number: str = Form(""),
    province: str = Form(""),
    city: str = Form(""),
    country: str = Form("Iran"),
    address: str = Form(""),
    final_consumer: str = Form(""),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.common import ProvinceCity
    from app.models.identity import IdentityInformation
    from datetime import datetime, timezone
    try:
        info = await db.get(IdentityInformation, uuid.UUID(identity_id))
    except ValueError:
        info = None
    if not info or info.user_id != current_user.id or info.status == "PendingDeletion":
        return HTMLResponse("Not found", status_code=404)
    try:
        is_final_consumer = final_consumer == "on"
        if not name or not national_code_or_id:
            raise ValueError("نام و کد ملی/شناسه ملی الزامی است")
        if identity_type == "Real":
            if not is_final_consumer and len(economic_code or "") != 14:
                raise ValueError("کد اقتصادی باید ۱۴ رقم باشد")
            if len(national_code_or_id) != 10:
                raise ValueError("کد ملی باید ۱۰ رقم باشد")
        elif identity_type in ("Legal", "CivicParticipation", "Non_IranianNationals"):
            if len(economic_code or "") != 11:
                raise ValueError("کد اقتصادی باید ۱۱ رقم باشد")
            if identity_type == "Legal" and len(national_code_or_id) != 11:
                raise ValueError("شناسه ملی باید ۱۱ رقم باشد")
            if identity_type in ("CivicParticipation", "Non_IranianNationals") and len(national_code_or_id) != 12:
                raise ValueError("شناسه باید ۱۲ رقم باشد")
            if is_final_consumer:
                raise ValueError("مصرف‌کننده نهایی فقط برای اشخاص حقیقی مجاز است")
        if is_final_consumer and identity_type == "Real":
            economic_code = None
        info.name = name
        info.type = identity_type
        info.national_code_or_id = national_code_or_id
        info.economic_code = economic_code
        info.postal_code = postal_code
        info.phone_number = phone_number
        info.country = country
        info.address = address
        info.final_consumer = is_final_consumer
        if province:
            province_row = await db.get(ProvinceCity, uuid.UUID(province))
            if province_row:
                info.province = province_row.name
        if city:
            city_row = await db.get(ProvinceCity, uuid.UUID(city))
            if city_row:
                info.city = city_row.name
        info.status = "AwaitingConfirmation"
        info.update_date = datetime.now(timezone.utc)
        await db.flush()
        return RedirectResponse(url="/profile/identity?identity_notif=اطلاعات با موفقیت ویرایش شد", status_code=303)
    except ValueError as e:
        prow = await db.execute(select(ProvinceCity).where(ProvinceCity.province_id.is_(None)))
        provinces = prow.scalars().all()
        city_rows = await db.execute(select(ProvinceCity).where(ProvinceCity.province_id.is_not(None)))
        cities = city_rows.scalars().all()
        selected_province_id = province if province else None
        selected_city_id = city if city else None
        cc = _cart_context_simple(request)
        return templates.TemplateResponse("shop/identity_edit.html", {
            "request": request, "current_user": current_user,
            "info": info, "provinces": provinces, "cities": cities, "error": str(e),
            "selected_province_id": selected_province_id,
            "selected_city_id": selected_city_id, **cc,
        })


@router.get("/identity-information/create", response_class=HTMLResponse)
async def identity_create_page(
    request: Request,
    redirect: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    from app.models.common import ProvinceCity
    prow = await db.execute(select(ProvinceCity).where(ProvinceCity.province_id.is_(None)))
    provinces = prow.scalars().all()
    city_rows = await db.execute(select(ProvinceCity).where(ProvinceCity.province_id.is_not(None)))
    cities = city_rows.scalars().all()
    cc = _cart_context_simple(request)
    return templates.TemplateResponse("shop/identity_create.html", {
        "request": request, "current_user": current_user,
        "provinces": provinces, "cities": cities, "redirect": redirect,
        **cc,
    })


@router.post("/identity-information/create", response_class=HTMLResponse)
async def identity_create_submit(
    request: Request,
    name: str = Form(...),
    identity_type: str = Form("Real"),
    national_code_or_id: str = Form(""),
    economic_code: Optional[str] = Form(""),
    postal_code: str = Form(""),
    phone_number: str = Form(""),
    province: str = Form(""),
    city: str = Form(""),
    country: str = Form("Iran"),
    address: str = Form(""),
    final_consumer: str = Form(""),
    redirect: Optional[str] = Form(None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.common import ProvinceCity
    from app.models.identity import IdentityInformation
    from datetime import datetime, timezone
    try:
        is_final_consumer = final_consumer == "on"
        if not name or not national_code_or_id:
            raise ValueError("نام و کد ملی/شناسه ملی الزامی است")
        if not province or not city:
            raise ValueError("استان و شهر را انتخاب کنید")
        if identity_type == "Real":
            if not is_final_consumer and len(economic_code or "") != 14:
                raise ValueError("کد اقتصادی باید ۱۴ رقم باشد")
            if len(national_code_or_id) != 10:
                raise ValueError("کد ملی باید ۱۰ رقم باشد")
        elif identity_type in ("Legal", "CivicParticipation", "Non_IranianNationals"):
            if len(economic_code or "") != 11:
                raise ValueError("کد اقتصادی باید ۱۱ رقم باشد")
            if identity_type == "Legal" and len(national_code_or_id) != 11:
                raise ValueError("شناسه ملی باید ۱۱ رقم باشد")
            if identity_type in ("CivicParticipation", "Non_IranianNationals") and len(national_code_or_id) != 12:
                raise ValueError("شناسه باید ۱۲ رقم باشد")
            if is_final_consumer:
                raise ValueError("مصرف‌کننده نهایی فقط برای اشخاص حقیقی مجاز است")
        else:
            raise ValueError("نوع اطلاعات هویتی نامعتبر است")
        province_row = await db.get(ProvinceCity, uuid.UUID(province))
        city_row = await db.get(ProvinceCity, uuid.UUID(city))
        if province_row is None or city_row is None or city_row.province_id != province_row.int_id:
            raise ValueError("استان یا شهر انتخابی نامعتبر است")
        if is_final_consumer and identity_type == "Real":
            economic_code = None
        info = IdentityInformation(
            id=uuid.uuid4(), user_id=current_user.id, name=name,
            national_code_or_id=national_code_or_id, economic_code=economic_code,
            postal_code=postal_code, phone_number=phone_number, address=address,
            province=province_row.name, city=city_row.name, country=country,
            type=identity_type, status="AwaitingConfirmation",
            final_consumer=is_final_consumer,
            insert_date=datetime.now(timezone.utc), update_date=datetime.now(timezone.utc),
        )
        db.add(info)
        await db.flush()
        if redirect == "true":
            return RedirectResponse(url=f"/checkout?identityId={info.id}", status_code=303)
        return RedirectResponse(url="/profile/identity", status_code=303)
    except ValueError as e:
        prow = await db.execute(select(ProvinceCity).where(ProvinceCity.province_id.is_(None)))
        provinces = prow.scalars().all()
        city_rows = await db.execute(select(ProvinceCity).where(ProvinceCity.province_id.is_not(None)))
        cities = city_rows.scalars().all()
        cc = _cart_context_simple(request)
        return templates.TemplateResponse("shop/identity_create.html", {
            "request": request, "current_user": current_user,
            "provinces": provinces, "cities": cities, "error": str(e), "redirect": redirect, **cc,
        })


@router.get("/addresses/create", response_class=HTMLResponse)
async def address_create_page(
    request: Request,
    back_to_order: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    from app.models.common import ProvinceCity
    prow = await db.execute(select(ProvinceCity).where(ProvinceCity.province_id.is_(None)))
    provinces = prow.scalars().all()
    cc = _cart_context_simple(request)
    return templates.TemplateResponse("shop/address_create.html", {
        "request": request, "current_user": current_user,
        "provinces": provinces, "back_to_order": back_to_order,
        **cc,
    })


@router.get("/addresses/cities", response_class=JSONResponse)
async def address_cities(province_id: int = Query(...), db: AsyncSession = Depends(get_db)):
    from app.models.common import ProvinceCity
    rows = await db.execute(select(ProvinceCity).where(ProvinceCity.province_id == province_id))
    return JSONResponse({
        "cities": [{"id": str(c.id), "name": c.name} for c in rows.scalars().all()],
    })


@router.post("/addresses/create", response_class=HTMLResponse)
async def address_create_submit(
    request: Request,
    first_name: str = Form(...),
    last_name: str = Form(...),
    phone_number: str = Form(...),
    telephone: Optional[str] = Form(""),
    address_description: str = Form(...),
    postal_code: str = Form(...),
    province: str = Form(""),
    city: str = Form(""),
    back_to_order: Optional[str] = Form(None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.common import ProvinceCity
    from app.models.common import Address as AddressModel
    from datetime import datetime, timezone
    from uuid import UUID
    try:
        if not province or not city:
            raise ValueError("استان و شهر را انتخاب کنید")
        city_row = await db.get(ProvinceCity, UUID(city))
        if city_row is None or city_row.province_id != int(province):
            raise ValueError("شهر انتخابی نامعتبر است")
        addr = AddressModel(
            id=uuid.uuid4(), user_id=current_user.id,
            first_name=first_name, last_name=last_name, phone_number=phone_number,
            telephone=telephone or None, address_description=address_description,
            postal_code=postal_code, province_id=int(province),
            province_city_id=city_row.id, country="Iran",
            insert_date=datetime.now(timezone.utc), update_date=datetime.now(timezone.utc),
        )
        db.add(addr)
        await db.flush()
        if back_to_order == "true":
            return RedirectResponse(url="/checkout", status_code=303)
        return RedirectResponse(url="/profile/addresses", status_code=303)
    except (ValueError, AttributeError) as e:
        from app.models.common import ProvinceCity as PC
        prow = await db.execute(select(PC).where(PC.province_id.is_(None)))
        provinces = prow.scalars().all()
        cc = _cart_context_simple(request)
        return templates.TemplateResponse("shop/address_create.html", {
            "request": request, "current_user": current_user,
            "provinces": provinces, "error": str(e), "back_to_order": back_to_order, **cc,
        })


@router.get("/profile/change-password", response_class=HTMLResponse)
async def profile_change_password_page(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    cc = await _get_cart_context(request, db)
    return templates.TemplateResponse("shop/change_password.html", {
        "request": request, "current_user": current_user,
        "succeeded": None, "errors": {}, "form": {}, **cc,
    })


@router.post("/profile/change-password", response_class=HTMLResponse)
async def profile_change_password_submit(
    request: Request,
    current_password: str = Form(""), new_password: str = Form(""),
    confirm_password: str = Form(""),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.auth_service import change_user_password
    from app.schemas.auth import ChangePasswordRequest
    from pydantic import ValidationError

    errors = {}
    form = {
        "current_password": current_password,
        "new_password": new_password,
        "confirm_password": confirm_password,
    }

    if not current_password.strip():
        errors["current_password"] = "رمز عبور فعلی را وارد کنید"
    if not new_password.strip():
        errors["new_password"] = "رمز عبور جدید را وارد کنید"
    if not confirm_password.strip():
        errors["confirm_password"] = "تائید رمز عبور را وارد کنید"

    if new_password and new_password != confirm_password:
        errors["confirm_password"] = "گذرواژه و تایید آن باید یکسان باشند"

    if not errors and new_password:
        if len(new_password) < 6:
            errors["new_password"] = "پسورد باید حداقل دارای 6 کارکتر باشد"
        elif not any(c.isdigit() for c in new_password):
            errors["new_password"] = "پسورد باید حداقل دارای یک عدد ('0'-'9') باشد"
        elif not any(c.islower() for c in new_password):
            errors["new_password"] = "پسورد باید حداقل دارای یک حرف کوچک ('a'-'z') باشد"
        elif not any(c.isupper() for c in new_password):
            errors["new_password"] = "پسورد باید حداقل دارای یک حرف بزرگ ('A'-'Z') باشد"
        elif not any(not c.isalnum() for c in new_password):
            errors["new_password"] = "پسورد باید حداقل دارای یک نشانه باشد"

    if not errors:
        try:
            req = ChangePasswordRequest(current_password=current_password, new_password=new_password)
            await change_user_password(current_user, db, req)
        except ValueError:
            errors["current_password"] = "رمز عبور فعلی صحیح نیست"

    cc = await _get_cart_context(request, db)
    return templates.TemplateResponse("shop/change_password.html", {
        "request": request, "current_user": current_user,
        "succeeded": not errors, "errors": errors, "form": form, **cc,
    })


@router.get("/profile/register-receipt", response_class=HTMLResponse)
async def profile_register_receipt_page(
    request: Request,
    id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(PayMethod).where(PayMethod.type == "BankReceipt", PayMethod.is_removed == False)
    pay_method = (await db.execute(stmt)).scalar_one_or_none()
    orders = []
    if pay_method:
        stmt = (
            select(Order)
            .where(
                Order.user_id == current_user.id,
                Order.pay_method_id == pay_method.id,
                Order.order_status == "AwaitingPayment",
                Order.is_removed == False,
            )
            .order_by(Order.reference_code.desc())
        )
        orders = (await db.execute(stmt)).scalars().all()
    selected_order_id = id if id and id != "00000000-0000-0000-0000-000000000000" else None
    cc = await _get_cart_context(request, db)
    return templates.TemplateResponse("shop/profile_register_receipt.html", {
        "request": request, "current_user": current_user,
        "receipt_orders": orders, "selected_order_id": selected_order_id, **cc,
    })


@router.post("/profile/register-receipt")
async def profile_register_receipt_submit(
    request: Request,
    order_id: str = Form(...),
    price: float = Form(0),
    description: str = Form(""),
    destination_bank: Optional[str] = Form(None),
    deposit_date: Optional[str] = Form(None),
    paya: Optional[str] = Form(None),
    tab: str = Form("paymentInfo"),
    img: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    import aiofiles
    import os
    from uuid import UUID
    from datetime import datetime

    try:
        oid = UUID(order_id) if order_id else None
    except ValueError:
        oid = None
    order = None
    if oid:
        stmt = select(Order).where(Order.id == oid, Order.user_id == current_user.id, Order.is_removed == False)
        order = (await db.execute(stmt)).scalar_one_or_none()
    if not order:
        return JSONResponse({"errors": ["خطا در عملیات"], "success": []})

    if price <= 0:
        return JSONResponse({"errors": ["خطا در عملیات"], "success": []})

    receipt = Receipt(
        price=price,
        description=description or None,
        paya=True if paya == "true" else (False if paya == "false" else None),
        deposit_date=None,
        reference_code=order.reference_code,
        destination_bank=destination_bank,
        tab=tab,
        status="AwaitingConfirmation",
        user_id=current_user.id,
        order_id=order.id,
    )

    if tab == "loadImage":
        if not img or not img.filename or not img.content_type.lower().startswith("image/"):
            return JSONResponse({"errors": ["خطا در عملیات"], "success": []})
        upload_dir = "app/static/uploads/receipts"
        os.makedirs(upload_dir, exist_ok=True)
        ext = img.filename.split(".")[-1] if "." in img.filename else "jpg"
        fname = f"receipt_{current_user.id.hex[:8]}_{uuid.uuid4().hex[:8]}.{ext}"
        file_path = os.path.join(upload_dir, fname)
        content = await img.read()
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)
        receipt.image_url = f"/static/uploads/receipts/{fname}"
        receipt.paya = None
        receipt.deposit_date = None
        receipt.destination_bank = None
    else:
        if deposit_date:
            try:
                receipt.deposit_date = datetime.strptime(deposit_date, "%Y/%m/%d")
            except ValueError:
                pass

    receipt.created_by_user_id = current_user.id
    receipt.insert_date = datetime.now(timezone.utc)
    receipt.update_date = datetime.now(timezone.utc)
    db.add(receipt)

    receipts_stmt = select(Receipt).where(
        Receipt.order_id == order.id,
        Receipt.status.in_(["Confirmed", "AwaitingConfirmation"]),
        Receipt.is_removed == False,
        Receipt.id != receipt.id,
    )
    all_receipts = (await db.execute(receipts_stmt)).scalars().all()
    receipts_sum = sum(float(r.price or 0) for r in all_receipts)

    from app.models.finance import PaymentRequest
    payments_stmt = select(PaymentRequest).where(
        PaymentRequest.order_id == order.id,
        PaymentRequest.status == "Success",
        PaymentRequest.is_removed == False,
    )
    all_payments = (await db.execute(payments_stmt)).scalars().all()
    payments_sum = sum(float(p.amount or 0) for p in all_payments)

    total_paid = float(receipt.price) + receipts_sum + payments_sum
    payable = float(order.payable or 0)

    if total_paid == payable:
        order.order_status = "Paid"
        db.add(OrderStatusRecord(
            order_id=order.id, status="Paid",
            comment="Accept payment",
        ))
    elif total_paid > payable:
        order.order_status = "NeedsToBeChecked"
        db.add(OrderStatusRecord(
            order_id=order.id, status="NeedsToBeChecked",
            comment="Need to be checked",
        ))

    await db.commit()

    return JSONResponse({"success": ["با موفقیت ثبت شد"], "errors": []})


# ── Static Pages ──

@router.get("/about", response_class=HTMLResponse)
async def about_page(request: Request, current_user: Optional[User] = Depends(get_optional_user_from_cookie)):
    cc = _cart_context_simple(request)
    return templates.TemplateResponse("shop/about.html", {"request": request, "current_user": current_user, **cc})


@router.get("/contact", response_class=HTMLResponse)
async def contact_page(request: Request, current_user: Optional[User] = Depends(get_optional_user_from_cookie)):
    cc = _cart_context_simple(request)
    return templates.TemplateResponse("shop/contact.html", {"request": request, "current_user": current_user, **cc})


@router.get("/faq", response_class=HTMLResponse)
async def faq_page(request: Request, current_user: Optional[User] = Depends(get_optional_user_from_cookie)):
    cc = _cart_context_simple(request)
    return templates.TemplateResponse("shop/faq.html", {"request": request, "current_user": current_user, **cc})


# ── AJAX Cart Endpoints (cookie-based) ──

@router.post("/cart/add-ajax")
async def cart_add_ajax(
    request: Request,
    db: AsyncSession = Depends(get_db),
    product_id: str = Form(...),
    count: int = Form(1),
    variety_id: str = Form(""),
    variety_values: str = Form(""),
):
    cart = parse_cart(request)
    existing = cart.find_item(product_id, variety_id)
    if existing:
        existing.quantity += count
    else:
        cart.items.append(CartCookieItem(
            product_id=product_id,
            variety_id=variety_id,
            quantity=count,
            variety_values_str=variety_values,
        ))
    cart.refresh()
    await enrich_cart(db, cart)
    resp = {"success": True, "count": cart.count, "total": cart.total_price_after_discount}
    response_obj = JSONResponse(content=resp)
    save_cart_response(cart, response_obj)
    return response_obj


@router.get("/cart/remove-ajax/{item_id}")
async def cart_remove_ajax(item_id: str, request: Request):
    cart = parse_cart(request)
    cart.remove_item(item_id)
    cart.refresh()
    resp = {"success": True, "count": cart.count, "total": cart.total_price_after_discount}
    response_obj = JSONResponse(content=resp)
    save_cart_response(cart, response_obj)
    return response_obj


@router.post("/cart/update-ajax/{item_id}")
async def cart_update_ajax(item_id: str, request: Request, quantity: int = Form(1)):
    cart = parse_cart(request)
    item = cart.find_item_by_id(item_id)
    if item:
        if quantity <= 0:
            cart.remove_item(item_id)
        else:
            item.quantity = quantity
    cart.refresh()
    resp = {"success": True, "count": cart.count, "total": cart.total_price_after_discount}
    response_obj = JSONResponse(content=resp)
    save_cart_response(cart, response_obj)
    return response_obj


@router.get("/cart/refresh-preview")
async def cart_refresh_preview(request: Request, db: AsyncSession = Depends(get_db)):
    """Return JSON with HTML preview — matches .NET RefreshShoppingCart endpoint."""
    cart = await _get_cart(request, db)
    preview = _cart_preview_html(cart)
    return {"preview": preview}


@router.get("/brands", response_class=HTMLResponse)
async def brand_list_page(request: Request, db: AsyncSession = Depends(get_db), current_user: Optional[User] = Depends(get_optional_user_from_cookie)):
    brands = await product_service.get_all_brands(db)
    cc = await _get_cart_context(request, db)
    return templates.TemplateResponse("shop/brands.html", {"request": request, "brands": brands, "current_user": current_user, **cc})


@router.get("/brands/{brand_id}", response_class=HTMLResponse)
async def brand_detail_page(brand_id: str, request: Request, db: AsyncSession = Depends(get_db), current_user: Optional[User] = Depends(get_optional_user_from_cookie)):
    try:
        bid = uuid.UUID(brand_id)
        brand = await product_service.get_brand_by_id(db, bid)
    except ValueError:
        return HTMLResponse("Brand not found", status_code=404)
    if not brand:
        return HTMLResponse("Brand not found", status_code=404)
    cc = await _get_cart_context(request, db)
    return templates.TemplateResponse("shop/brand_detail.html", {"request": request, "brand": brand, "current_user": current_user, **cc})


# ── Datasheet Download ──

@router.get("/products/{product_id}/datasheet/{datasheet_id}")
async def product_datasheet_download(
    product_id: str,
    datasheet_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    try:
        ds = (await db.execute(
            select(MenuDatasheet).where(
                MenuDatasheet.id == uuid.UUID(datasheet_id),
                MenuDatasheet.is_removed == False,
            )
        )).scalar_one_or_none()
    except ValueError:
        return HTMLResponse("Invalid ID", status_code=400)

    if not ds or not ds.file_url:
        return HTMLResponse("Datasheet not found", status_code=404)

    # Resolve path from the mounted .NET wwwroot/Media directory (or bundled copy)
    rel = ds.file_url.replace("\\", "/").lstrip("/")
    # Strip the "Media/" prefix if present (it's the root of the mount)
    if rel.lower().startswith("media/"):
        rel = rel[len("media/"):]
    file_path = None
    for root in ("/app/media", "app/static/Media"):
        candidate = os.path.join(root, rel)
        if os.path.exists(candidate):
            file_path = candidate
            break
    if not file_path:
        return HTMLResponse("File not found", status_code=404)

    filename = os.path.basename(file_path)
    return FileResponse(file_path, media_type="application/pdf", filename=filename)


# ── Helpers ──

def _fmt_tech_num(n):
    """Replicate .NET double→string with no decimal for integers."""
    if n is None:
        return "-"
    return str(int(n)) if n == int(n) else f"{n:.15g}"


def _format_tech_value(value, format_str):
    """Replicate .NET TechnicalFeatureValue.Value(displayFormat)."""
    if not format_str:
        return ""
    te = value.technical_feature_enum
    te1 = value.technical_feature_enum1
    args = [
        _fmt_tech_num(value.d_value),  # {0} DValue
        value.unit,                     # {1} Unit
        value.s_value,                  # {2} SValue
        te.persian_name if te else None,  # {3} EValue
        value.b_value,                  # {4} BValue
        _fmt_tech_num(value.min_value),  # {5} MinValue
        value.min_unit,                 # {6} MinUnit
        _fmt_tech_num(value.max_value),  # {7} MaxValue
        value.max_unit,                 # {8} MaxUnit
        _fmt_tech_num(value.x_value),   # {9} XValue
        value.x_unit,                   # {10} XUnit
        _fmt_tech_num(value.y_value),   # {11} YValue
        value.y_unit,                   # {12} YUnit
        _fmt_tech_num(value.z_value),   # {13} ZValue
        value.z_unit,                   # {14} ZUnit
        te1.persian_name if te1 else None,  # {15} EValue1
    ]
    try:
        return format_str.format(*args)
    except (IndexError, ValueError):
        return format_str


def _build_technical_tables(product):
    """Build structured technical table data matching .NET Details.cshtml."""
    tables = []
    for ttp in (product.technical_table_products or []):
        if ttp.is_removed:
            continue
        if not ttp.technical_feature_values:
            continue
        table = ttp.technical_table
        headers = [h for h in (table.header or "").split(";") if h.strip()]
        column_values = []
        linear_values = []
        specs = []
        for value in sorted(
            [v for v in ttp.technical_feature_values if v.technical_feature and v.technical_feature.columns == table.columns],
            key=lambda v: (v.technical_feature.priority, v.technical_feature.name),
        ):
            vh = [h for h in (value.technical_feature.display_format or "").split(";") if h.strip()]
            hc = len(vh)
            if hc < table.columns:
                vh += [" "] * (table.columns - hc)
            elif hc > table.columns:
                vh = vh[:max(0, hc - table.columns)]
            column_values.append({
                "name": value.technical_feature.name,
                "cells": [_format_tech_value(value, f) for f in vh],
            })
        for value in sorted(
            [v for v in ttp.technical_feature_values if v.technical_feature and v.technical_feature.columns != table.columns],
            key=lambda v: (v.technical_feature.priority, v.technical_feature.name),
        ):
            linear_values.append({
                "name": value.technical_feature.name,
                "value": _format_tech_value(value, value.technical_feature.display_format),
                "colspan": table.columns - value.technical_feature.columns + 1,
                "extra_cells": value.technical_feature.columns - 1,
            })
        # specifications list (linear display features)
        for value in sorted(
            [v for v in ttp.technical_feature_values if v.technical_feature and v.technical_feature.linear_display],
            key=lambda v: (v.technical_feature.priority, v.technical_feature.name),
        ):
            specs.append({
                "fa_name": value.technical_feature.fa_name,
                "name": value.technical_feature.name,
                "value": _format_tech_value(value, value.technical_feature.linear_display),
            })
        tables.append({
            "en_title": table.en_title,
            "columns": table.columns,
            "headers": headers,
            "column_values": column_values,
            "linear_values": linear_values,
            "specifications": specs,
        })
    return tables


def _build_shop_detail(product):
    base = product_service._build_product_list_response(product)
    from collections import OrderedDict
    _DEFAULT_OPTION = "پیش فرض"
    variety_values = OrderedDict()
    for v in (product.varieties or []):
        for pv in (v.product_varieties or []):
            if not pv.category_option or pv.category_option.name == _DEFAULT_OPTION:
                continue
            key = pv.category_option.name
            if key not in variety_values:
                variety_values[key] = []
            if pv.value not in variety_values[key]:
                variety_values[key].append(pv.value)
    variety_values_list = [{"category_name": k, "vals": v} for k, v in variety_values.items()]
    technical_tables = _build_technical_tables(product)
    specifications = []
    for tt in technical_tables:
        specifications.extend(tt["specifications"])
    return {
        **base.model_dump(),
        "medium_image_url": _normalize_media_url(product.medium_image_url),
        "large_image_url": _normalize_media_url(product.large_image_url),
        "feature_image_url": _normalize_media_url(product.feature_image_url),
        "introduction": product.introduction,
        "keywords": product.keywords,
        "meta_description": product.meta_description,
        "stock_quantity": product.stock_quantity,
        "minimum_purchase": product.minimum_purchase,
        "max_number_of_purchases": product.max_number_of_purchases,
        "delivery_day": product.delivery_day,
        "vat_rate": float(product.vat_rate) if product.vat_rate else None,
        "images": [{"id": str(img.id),
             "small_image_url": _normalize_media_url(img.small_image_url),
             "medium_image_url": _normalize_media_url(img.medium_image_url),
             "large_image_url": _normalize_media_url(img.large_image_url)}
                   for img in (product.product_images or [])] if hasattr(product, 'product_images') else [],
        "varieties": [{"id": str(v.id), "part_number": v.part_number, "price": float(v.price or 0),
                       "price_after_discount": float(v.price_after_discount or v.price or 0),
                       "stock_quantity": v.stock_quantity,
                       "product_varieties": [{"category_option_name": pv.category_option.name if pv.category_option else None, "value": pv.value}
                                             for pv in (v.product_varieties or [])
                                             if pv.category_option and pv.category_option.name != _DEFAULT_OPTION] if hasattr(v, 'product_varieties') else []}
                      for v in (product.varieties or [])] if hasattr(product, 'varieties') else [],
        "menu_datasheets": [{"id": str(ds.id), "type": ds.type, "file_url": ds.file_url, "complete_file_url": ds.complete_file_url}
                            for ds in (product.menu_datasheets or []) if not ds.is_removed],
        "technical_tables": technical_tables,
        "specifications": specifications,
        "variety_values": variety_values_list,
        "category_en_title": product.category.en_title if product.category else None,
        "brand_name": product.brand.name if product.brand else None,
        "brand_id": str(product.brand_id) if product.brand_id else None,
        "category_id": str(product.category_id) if product.category_id else None,
    }


# ── Categories Page ──

@router.get("/categories", response_class=HTMLResponse)
async def shop_categories(request: Request, db: AsyncSession = Depends(get_db), current_user: Optional[User] = Depends(get_optional_user_from_cookie)):
    categories = await product_service.get_category_tree(db)
    cc = await _get_cart_context(request, db)
    return templates.TemplateResponse("shop/categories.html", {"request": request, "categories": categories, "current_user": current_user, **cc})


@router.get("/category/{slug}", response_class=HTMLResponse)
async def shop_category(slug: str, request: Request, db: AsyncSession = Depends(get_db), current_user: Optional[User] = Depends(get_optional_user_from_cookie)):
    return await _render_category_page(slug, request, db, current_user=current_user)


@router.get("/Shop/Category/Index/{slug}", response_class=HTMLResponse)
async def shop_category_dotnet(slug: str, request: Request, db: AsyncSession = Depends(get_db), current_user: Optional[User] = Depends(get_optional_user_from_cookie)):
    return await _render_category_page(slug, request, db, current_user=current_user)


async def _render_category_page(slug: str, request: Request, db: AsyncSession, current_user: Optional[User] = None) -> HTMLResponse:
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
        current_user=current_user,
    )