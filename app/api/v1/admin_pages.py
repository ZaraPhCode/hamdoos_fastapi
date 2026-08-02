"""Admin page routes — renders Jinja2 templates for the admin panel."""

from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.core.dependencies import get_admin_user, require_any_role
from app.models.identity import User, Role, IdentityInformation, RoleClaim, UserRole
from app.models.product import Product, Category, Brand, ProductType, ProductUnit, Currency, Tag, CategoryOption, PriceHistory, ProductTag, RelatedProduct, SimilarProduct
from app.models.product_features import TechnicalFeature, TechnicalTable, CategoryTechnicalFeature, TechnicalTableProduct, TechnicalFeatureEnum
from app.models.order import OrderModel as Order, PayMethod, PostType, Discount
from app.models.invoice import Invoice, Supplier, PurchaseOrder
from app.models.finance import Receipt, Wallet, CurrencyDetail, WarehouseMovement
from app.models.customer_content import Comment, Media, NotifiedProduct
from app.models.support import Ticket, Chat
from app.models.common import Log, AdminParameter
from app.models.manufacturer import Manufacturer
from app.schemas.product import CategoryCreate, CategoryUpdate
from app.utils.common_works import generate_slug
from app.services import admin_service, product_service, order_service, invoice_service, warehouse_service, finance_service, support_service

templates = Jinja2Templates(directory="app/templates")
router = APIRouter(prefix="/administration", tags=["Admin Pages"])


# ── Admin Login ──

@router.get("/login", response_class=HTMLResponse)
async def admin_login_page(request: Request):
    next_url = request.query_params.get("next", "/administration")
    return templates.TemplateResponse("admin/login.html", {
        "request": request, "next": next_url,
    })


@router.post("/login", response_class=HTMLResponse)
async def admin_login_submit(request: Request, db: AsyncSession = Depends(get_db)):
    from app.schemas.auth import LoginRequest
    from app.services.auth_service import authenticate_user, create_token_response
    from fastapi.responses import RedirectResponse
    form = await request.form()
    username = form.get("username", "")
    password = form.get("password", "")
    next_url = form.get("next", "/administration")
    try:
        user = await authenticate_user(db, LoginRequest(username=username, password=password))
        if not user:
            return templates.TemplateResponse("admin/login.html", {
                "request": request, "error": "نام کاربری یا رمز عبور اشتباه است", "next": next_url,
            })
        user_role_names = {ur.role.name for ur in user.roles}
        if not user_role_names.intersection({"Admin", "Product Manager", "Orders Manager", "Financial Manager", "Warehouse Keeper"}):
            return templates.TemplateResponse("admin/login.html", {
                "request": request, "error": "شما دسترسی به پنل مدیریت ندارید", "next": next_url,
            })
        response = RedirectResponse(url=next_url, status_code=303)
        token = await create_token_response(user)
        response.set_cookie(key="access_token", value=token.access_token, httponly=True, max_age=7200)
        return response
    except Exception:
        return templates.TemplateResponse("admin/login.html", {
            "request": request, "error": "خطا در ورود به سیستم", "next": next_url,
        })


# ── Dashboard ──

@router.get("", response_class=HTMLResponse)
@router.get("/dashboard", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    stats = await admin_service.get_dashboard_stats(db)
    order_distribution = await admin_service.get_order_status_distribution(db)
    recent_orders = await admin_service.get_recent_orders(db, 10)
    low_stock = await admin_service.get_low_stock_products(db, 5, 10)
    return templates.TemplateResponse(
        "admin/dashboard.html",
        {
            "request": request,
            "current_user": current_user,
            "stats": stats,
            "order_distribution": order_distribution,
            "recent_orders": recent_orders,
            "low_stock_products": low_stock,
        },
    )


# ── Products ──

@router.get("/products", response_class=HTMLResponse)
async def admin_products(
    request: Request,
    page: int = Query(1),
    q: str = Query(None),
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    from app.schemas.product import ProductSearchParams
    params = ProductSearchParams(query=q, page=page, page_size=20)
    products, total = await product_service.search_products(db, params)
    # Load admin users for filter dropdown
    users_result = await db.execute(
        select(User).where(User.is_removed == False).order_by(User.first_name)
    )
    users = users_result.scalars().all()
    tree = await product_service.get_admin_category_tree(db)
    options = _flatten_category_options(tree)
    return templates.TemplateResponse("admin/products.html", {
        "request": request,
        "current_user": current_user,
        "products": [product_service._build_product_list_response(p) for p in products],
        "total": total, "page": page, "total_pages": (total + 19) // 20, "query": q,
        "users": users, "categories": options,
    })


@router.get("/products/new", response_class=HTMLResponse)
async def admin_product_create(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    tree = await product_service.get_admin_category_tree(db)
    options = _flatten_category_options(tree)
    brands = await product_service.get_all_brands(db)
    types = (await db.execute(select(ProductType).where(ProductType.is_removed == False))).scalars().all()
    units = (await db.execute(select(ProductUnit).where(ProductUnit.is_removed == False))).scalars().all()
    currencies = (await db.execute(select(Currency).where(Currency.is_removed == False))).scalars().all()
    suppliers = (await db.execute(select(Supplier).where(Supplier.is_removed == False))).scalars().all()
    return templates.TemplateResponse("admin/product_form.html", {
        "request": request, "current_user": current_user,
        "product": None, "categories_tree": options,
        "brands": brands, "product_types": types,
        "product_units": units, "currencies": currencies, "suppliers": suppliers,
    })


@router.post("/products/new", response_class=HTMLResponse)
async def admin_product_create_submit(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    from app.schemas.product import ProductCreate
    from app.services.product_service import create_product
    import jdatetime

    purchase_date_str = form.get("purchase_date") or ""
    purchase_date = None
    if purchase_date_str:
        try:
            parts = purchase_date_str.replace("/", "-").split("-")
            purchase_date = jdatetime.date(int(parts[0]), int(parts[1]), int(parts[2])).togregorian()
        except:
            pass

    data = ProductCreate(
        name=(form.get("name") or "").strip(),
        en_name=(form.get("en_name") or "").strip() or None,
        slug=(form.get("slug") or "").strip() or None,
        en_slug=(form.get("en_slug") or "").strip() or None,
        part_number=(form.get("part_number") or "").strip() or None,
        model=(form.get("model") or "").strip() or None,
        short_description=form.get("short_description") or None,
        introduction=form.get("introduction") or None,
        keywords=(form.get("keywords") or "").strip() or None,
        meta_description=form.get("meta_description") or None,
        status=form.get("status") or "OutOfStock",
        type=form.get("type") or "Product",
        delivery_day=int(form.get("delivery_day") or 0) or None,
        tax_unique_id=(form.get("tax_unique_id") or "").strip() or None,
        taobao_choice_id=(form.get("taobao_choice_id") or "").strip() or None,
        vat_rate=float(form.get("vat_rate") or 0) or None,
        profit_rate=float(form.get("profit_rate") or 0) or None,
        points_from_purchases=int(form.get("points_from_purchases") or 0),
        max_number_of_purchases=int(form.get("max_number_of_purchases") or 0) or None,
        default_variation=(form.get("default_variation") or "").strip() or None,
        purchase_date=purchase_date,
        price=float(form.get("price") or 0) or None,
        stock_quantity=int(form.get("stock_quantity") or 0),
        minimum_purchase=int(form.get("minimum_purchase") or 1),
        category_id=uuid.UUID(form.get("category_id")) if form.get("category_id") else None,
        brand_id=uuid.UUID(form.get("brand_id")) if form.get("brand_id") else None,
        product_type_id=uuid.UUID(form.get("product_type_id")) if form.get("product_type_id") else None,
        product_unit_id=uuid.UUID(form.get("product_unit_id")) if form.get("product_unit_id") else None,
        currency_id=uuid.UUID(form.get("currency_id")) if form.get("currency_id") else None,
        is_new=form.get("is_new") in ("1", "true", "on"),
        is_special=form.get("is_special") in ("1", "true", "on"),
        on_sale=form.get("on_sale") in ("1", "true", "on"),
        suggested=form.get("suggested") in ("1", "true", "on"),
        no_display=form.get("no_display") in ("1", "true", "on"),
        is_bundle=form.get("is_bundle") in ("1", "true", "on"),
        is_calibrated=form.get("is_calibrated") in ("1", "true", "on"),
        restocked=form.get("restocked") in ("1", "true", "on"),
    )
    if not data.slug and data.name:
        from app.utils.common_works import generate_slug
        data.slug = generate_slug(data.name)
    if not data.en_slug and data.en_name:
        docstring = """<implementation of generate_slug>"""
        from app.utils.common_works import generate_slug
        data.en_slug = generate_slug(data.en_name)

    product = await create_product(db, data, current_user.id)
    log_text = form.get("log") or f"ایجاد محصول: {product.name}"
    db.add(Log(
        record_id=product.id, table_name="products",
        description=log_text, created_by_user_id=current_user.id,
        type="Create",
    ))
    await db.commit()
    return RedirectResponse(url="/administration/products", status_code=303)


@router.get("/products/{product_id}/edit", response_class=HTMLResponse)
async def admin_product_edit(
    request: Request,
    product_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    import uuid
    pid = uuid.UUID(product_id)
    product = await product_service.get_product_by_id(db, pid)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    categories = await product_service.get_all_categories_flat(db)
    brands = await product_service.get_all_brands(db)
    return templates.TemplateResponse("admin/product_form.html", {
        "request": request, "current_user": current_user,
        "product": product, "categories": categories, "brands": brands,
    })


# ── Categories ──

def _flatten_category_options(categories: list[Category], depth: int = 0) -> list[dict]:
    """Flatten the category list into (id, title, depth) options for the parent picker.

    Builds the hierarchy in memory from parent_category_id to avoid async lazy-loading.
    """
    by_parent: dict[str, list[Category]] = {}
    id_to_cat: dict[str, Category] = {}
    for cat in categories:
        id_to_cat[str(cat.id)] = cat
        key = str(cat.parent_category_id) if cat.parent_category_id is not None else ""
        by_parent.setdefault(key, []).append(cat)

    options: list[dict] = []

    def _walk(parent_key: str, depth: int) -> None:
        for cat in by_parent.get(parent_key, []):
            options.append({"id": str(cat.id), "title": cat.title, "depth": depth})
            _walk(str(cat.id), depth + 1)

    _walk("", 0)
    return options


async def _get_descendant_ids(db: AsyncSession, category_id: uuid.UUID) -> set[str]:
    """Collect ids of the category and all its descendants (to exclude from the parent picker)."""
    ids = {str(category_id)}
    stack = [category_id]
    while stack:
        current = stack.pop()
        stmt = select(Category.id).where(
            Category.parent_category_id == current, Category.is_removed == False
        )
        child_ids = [row[0] for row in (await db.execute(stmt)).all()]
        for child_id in child_ids:
            sid = str(child_id)
            if sid not in ids:
                ids.add(sid)
                stack.append(child_id)
    return ids


@router.get("/categories", response_class=HTMLResponse)
async def admin_categories(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    cats = await product_service.get_admin_categories(db)
    return templates.TemplateResponse("admin/categories.html", {
        "request": request, "current_user": current_user, "categories": cats,
    })


@router.get("/categories/new", response_class=HTMLResponse)
async def admin_category_create(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    parent: str | None = request.query_params.get("parent")
    tree = await product_service.get_admin_category_tree(db)
    options = _flatten_category_options(tree)
    return templates.TemplateResponse("admin/category_form.html", {
        "request": request, "current_user": current_user,
        "categories": options, "category": None, "parent_id": parent,
        "exclude_ids": set(),
    })


@router.post("/categories/new", response_class=HTMLResponse)
async def admin_category_create_submit(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    parent_raw = form.get("parent_category_id")
    data = {
        "title": (form.get("title") or "").strip(),
        "en_title": (form.get("en_title") or "").strip(),
        "slug": (form.get("slug") or "").strip(),
        "keywords": (form.get("keywords") or "").strip(),
        "description": form.get("description") or "",
        "meta_description": form.get("meta_description") or "",
        "place": (form.get("place") or "").strip(),
        "priority": int(form.get("priority") or 0),
        "no_display": form.get("no_display") in ("1", "true", "on"),
        "is_disable": form.get("is_disable") in ("1", "true", "on"),
        "parent_category_id": uuid.UUID(parent_raw) if parent_raw else None,
    }
    if data["en_title"]:
        data["en_title"] = generate_slug(data["en_title"])
    if not data["slug"] and data["title"]:
        data["slug"] = generate_slug(data["title"])

    category = await product_service.create_category(db, CategoryCreate(**data), current_user.id)
    log_text = form.get("log") or ""
    db.add(Log(
        record_id=category.id,
        table_name="categories",
        description=log_text,
        created_by_user_id=current_user.id,
    ))
    return RedirectResponse(url="/administration/categories", status_code=303)


@router.get("/categories/{category_id}/edit", response_class=HTMLResponse)
async def admin_category_edit(
    request: Request,
    category_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    cid = uuid.UUID(category_id)
    category = await product_service.get_category_by_id(db, cid)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    tree = await product_service.get_admin_category_tree(db)
    options = _flatten_category_options(tree)
    exclude_ids = await _get_descendant_ids(db, cid)
    return templates.TemplateResponse("admin/category_form.html", {
        "request": request, "current_user": current_user,
        "category": category, "categories": options, "parent_id": None,
        "exclude_ids": exclude_ids,
    })


@router.post("/categories/{category_id}/edit", response_class=HTMLResponse)
async def admin_category_edit_submit(
    request: Request,
    category_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    cid = uuid.UUID(category_id)
    category = await product_service.get_category_by_id(db, cid)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")

    form = await request.form()
    parent_raw = form.get("parent_category_id")
    data = {
        "title": (form.get("title") or "").strip(),
        "en_title": (form.get("en_title") or "").strip(),
        "slug": (form.get("slug") or "").strip(),
        "keywords": (form.get("keywords") or "").strip(),
        "description": form.get("description") or "",
        "meta_description": form.get("meta_description") or "",
        "place": (form.get("place") or "").strip(),
        "priority": int(form.get("priority") or 0),
        "no_display": form.get("no_display") in ("1", "true", "on"),
        "is_disable": form.get("is_disable") in ("1", "true", "on"),
        "parent_category_id": uuid.UUID(parent_raw) if parent_raw else None,
    }
    if data["en_title"]:
        data["en_title"] = generate_slug(data["en_title"])
    if not data["slug"] and data["title"]:
        data["slug"] = generate_slug(data["title"])

    await product_service.update_category(db, category, CategoryUpdate(**data))

    if category.no_display:
        await _hide_category_children(db, category)

    log_text = form.get("log") or ""
    if log_text:
        db.add(Log(
            record_id=category.id,
            table_name="categories",
            description=log_text,
            created_by_user_id=current_user.id,
        ))
    return RedirectResponse(url="/administration/categories", status_code=303)


@router.get("/categories/{category_id}/details", response_class=HTMLResponse)
async def admin_category_details(
    request: Request,
    category_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    cid = uuid.UUID(category_id)
    stmt = (
        select(Category)
        .options(
            selectinload(Category.parent),
            selectinload(Category.medias),
            selectinload(Category.products).selectinload(Product.category),
        )
        .where(Category.id == cid, Category.is_removed == False)
    )
    result = await db.execute(stmt)
    category = result.unique().scalar_one_or_none()
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    child_stmt = (
        select(Category)
        .options(selectinload(Category.parent), selectinload(Category.medias))
        .where(Category.parent_category_id == cid, Category.is_removed == False)
        .order_by(Category.title)
    )
    child_result = await db.execute(child_stmt)
    children = child_result.unique().scalars().all()
    # Get products for the category (including child categories, with pagination support)
    products, total_products = await product_service.get_products_by_category(db, cid, 1, 100)
    return templates.TemplateResponse("admin/category_detail.html", {
        "request": request, "current_user": current_user,
        "category": category, "children": children,
        "products": products, "total_products": total_products,
        "medias": category.medias,
    })


@router.get("/categories/{category_id}/delete", response_class=HTMLResponse)
async def admin_category_delete(
    request: Request,
    category_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    cid = uuid.UUID(category_id)
    category = await product_service.get_category_by_id(db, cid)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    return templates.TemplateResponse("admin/category_delete.html", {
        "request": request, "current_user": current_user, "category": category,
    })


@router.post("/categories/{category_id}/delete", response_class=HTMLResponse)
async def admin_category_delete_confirm(
    request: Request,
    category_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    cid = uuid.UUID(category_id)
    category = await product_service.get_category_by_id(db, cid)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found")
    title = category.title
    await product_service.delete_category(db, category)
    db.add(Log(
        record_id=cid,
        table_name="categories",
        description=f"حذف دسته بندی: {title}",
        created_by_user_id=current_user.id,
    ))
    return RedirectResponse(url="/administration/categories", status_code=303)


async def _hide_category_children(db: AsyncSession, category: Category) -> None:
    """Mirrors .NET HideChildrenAsync — sets no_display True on all descendants."""
    stack = [category]
    while stack:
        current = stack.pop()
        child_stmt = (
            select(Category)
            .options(selectinload(Category.children))
            .where(Category.parent_category_id == current.id, Category.is_removed == False)
        )
        child_result = await db.execute(child_stmt)
        children = child_result.unique().scalars().all()
        for child in children:
            child.no_display = True
            stack.append(child)


# ── Brands ──

@router.get("/brands", response_class=HTMLResponse)
async def admin_brands(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    brands = await product_service.get_all_brands(db)
    return templates.TemplateResponse("admin/brands.html", {
        "request": request, "current_user": current_user, "brands": brands,
    })


@router.get("/brands/new", response_class=HTMLResponse)
async def admin_brand_create(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    return templates.TemplateResponse("admin/brand_form.html", {
        "request": request, "current_user": current_user,
    })


# ── Orders ──

@router.get("/orders", response_class=HTMLResponse)
async def admin_orders(
    request: Request,
    page: int = Query(1),
    status_filter: str = Query(None),
    current_user: User = Depends(require_any_role("Admin", "Orders Manager")),
    db: AsyncSession = Depends(get_db),
):
    orders, total = await order_service.get_all_orders(db, page, 20, status_filter)
    return templates.TemplateResponse("admin/orders.html", {
        "request": request, "current_user": current_user,
        "orders": [order_service.build_order_response(o) for o in orders],
        "total": total, "page": page, "total_pages": (total + 19) // 20,
        "status_filter": status_filter,
    })


@router.get("/orders/{order_id}", response_class=HTMLResponse)
async def admin_order_detail(
    request: Request,
    order_id: str,
    current_user: User = Depends(require_any_role("Admin", "Orders Manager")),
    db: AsyncSession = Depends(get_db),
):
    import uuid
    oid = uuid.UUID(order_id)
    order = await order_service.get_order_by_id(db, oid)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return templates.TemplateResponse("admin/order_detail.html", {
        "request": request, "current_user": current_user,
        "order": order_service.build_order_response(order),
        "order_statuses": [
            "Ordering", "AwaitingPayment", "Paid", "ConfirmedPayment",
            "Processing", "Collecting", "Packing", "Sending", "Posted", "Canceled",
        ],
    })


# ── Users ──

@router.get("/users", response_class=HTMLResponse)
async def admin_users(
    request: Request,
    page: int = Query(1),
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select, func
    from app.models.identity import User
    total = (await db.execute(select(func.count(User.id)).where(User.is_removed == False))).scalar() or 0
    users = (await db.execute(
        select(User).where(User.is_removed == False).order_by(User.insert_date.desc()).offset((page-1)*20).limit(20)
    )).scalars().all()
    return templates.TemplateResponse("admin/users.html", {
        "request": request, "current_user": current_user,
        "users": users, "total": total, "page": page, "total_pages": (total + 19) // 20,
    })


@router.get("/users/{user_id}", response_class=HTMLResponse)
async def admin_user_detail(
    request: Request,
    user_id: str,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    import uuid
    uid = uuid.UUID(user_id)
    from app.services.auth_service import get_user_by_id
    user = await get_user_by_id(db, uid)
    roles = (await db.execute(select(Role).where(Role.is_removed == False))).scalars().all()
    return templates.TemplateResponse("admin/user_detail.html", {
        "request": request, "current_user": current_user,
        "user": user, "roles": roles,
    })


# ── Roles ──

@router.get("/roles", response_class=HTMLResponse)
async def admin_roles(
    request: Request,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    roles = (await db.execute(select(Role).where(Role.is_removed == False))).scalars().all()
    return templates.TemplateResponse("admin/roles.html", {
        "request": request, "current_user": current_user, "roles": roles,
    })


@router.get("/roles/new", response_class=HTMLResponse)
async def admin_role_create(
    request: Request,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    return templates.TemplateResponse("admin/role_form.html", {
        "request": request, "current_user": current_user,
    })


# ── Comments ──

@router.get("/comments", response_class=HTMLResponse)
async def admin_comments(
    request: Request,
    pending_only: bool = Query(False),
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Comment).where(Comment.is_removed == False).order_by(Comment.insert_date.desc()).limit(50)
    if pending_only:
        stmt = stmt.where(Comment.is_confirmed == False)
    comments = (await db.execute(stmt)).scalars().all()
    return templates.TemplateResponse("admin/comments.html", {
        "request": request, "current_user": current_user, "comments": comments,
    })


# ── Settings ──

@router.get("/settings", response_class=HTMLResponse)
async def admin_settings(
    request: Request,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.common import SiteSetting
    settings = (await db.execute(select(SiteSetting).where(SiteSetting.is_removed == False).limit(1))).scalar_one_or_none()
    return templates.TemplateResponse("admin/settings.html", {
        "request": request, "current_user": current_user, "settings": settings,
    })


# ── Invoices ──

@router.get("/invoices", response_class=HTMLResponse)
async def admin_invoices(
    request: Request,
    page: int = Query(1),
    current_user: User = Depends(require_any_role("Admin", "Financial Manager")),
    db: AsyncSession = Depends(get_db),
):
    invoices, total = await invoice_service.get_all_invoices(db, page, 20)
    return templates.TemplateResponse("admin/invoices.html", {
        "request": request, "current_user": current_user,
        "invoices": [invoice_service.build_invoice_response(inv) for inv in invoices],
        "total": total, "page": page, "total_pages": (total + 19) // 20,
    })


@router.get("/invoices/{invoice_id}", response_class=HTMLResponse)
async def admin_invoice_detail(
    request: Request,
    invoice_id: str,
    current_user: User = Depends(require_any_role("Admin", "Financial Manager")),
    db: AsyncSession = Depends(get_db),
):
    import uuid
    iid = uuid.UUID(invoice_id)
    invoice = await invoice_service.get_invoice_by_id(db, iid)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return templates.TemplateResponse("admin/invoice_detail.html", {
        "request": request, "current_user": current_user,
        "invoice": invoice_service.build_invoice_response(invoice),
    })


# ── Purchase Orders ──

@router.get("/purchase-orders", response_class=HTMLResponse)
async def admin_purchase_orders(
    request: Request,
    page: int = Query(1),
    current_user: User = Depends(require_any_role("Admin", "Financial Manager")),
    db: AsyncSession = Depends(get_db),
):
    pos, total = await invoice_service.get_all_purchase_orders(db, page, 20)
    return templates.TemplateResponse("admin/purchase_orders.html", {
        "request": request, "current_user": current_user,
        "purchase_orders": [invoice_service.build_purchase_order_response(po) for po in pos],
        "total": total, "page": page, "total_pages": (total + 19) // 20,
    })


@router.get("/purchase-orders/new", response_class=HTMLResponse)
async def admin_purchase_order_create(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Financial Manager")),
    db: AsyncSession = Depends(get_db),
):
    products = (await db.execute(select(Product).where(Product.is_removed == False, Product.no_display == False).limit(100))).scalars().all()
    suppliers = (await db.execute(select(Supplier).where(Supplier.is_removed == False))).scalars().all()
    currencies = (await db.execute(select(Currency).where(Currency.is_removed == False))).scalars().all()
    return templates.TemplateResponse("admin/purchase_order_form.html", {
        "request": request, "current_user": current_user,
        "products": products, "suppliers": suppliers, "currencies": currencies,
    })


# ── Suppliers ──

@router.get("/suppliers", response_class=HTMLResponse)
async def admin_suppliers(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Financial Manager")),
    db: AsyncSession = Depends(get_db),
):
    suppliers = await invoice_service.get_all_suppliers(db)
    return templates.TemplateResponse("admin/suppliers.html", {
        "request": request, "current_user": current_user, "suppliers": suppliers,
    })


@router.get("/suppliers/new", response_class=HTMLResponse)
async def admin_supplier_create(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Financial Manager")),
    db: AsyncSession = Depends(get_db),
):
    return templates.TemplateResponse("admin/supplier_form.html", {
        "request": request, "current_user": current_user,
    })


# ── Receipts ──

@router.get("/receipts", response_class=HTMLResponse)
async def admin_receipts(
    request: Request,
    page: int = Query(1),
    status_filter: str = Query(None),
    current_user: User = Depends(require_any_role("Admin", "Financial Manager")),
    db: AsyncSession = Depends(get_db),
):
    receipts, total = await finance_service.get_all_receipts(db, page, 20, status_filter)
    return templates.TemplateResponse("admin/receipt_list.html", {
        "request": request, "current_user": current_user,
        "receipts": [finance_service.build_receipt_response(r) for r in receipts],
        "total": total, "page": page, "total_pages": (total + 19) // 20,
        "status_filter": status_filter,
    })


# ── Currency ──

@router.get("/currency", response_class=HTMLResponse)
async def admin_currency(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Financial Manager")),
    db: AsyncSession = Depends(get_db),
):
    currencies = await finance_service.get_all_currencies(db)
    return templates.TemplateResponse("admin/currency_list.html", {
        "request": request, "current_user": current_user, "currencies": currencies,
    })


# ── Warehouse ──

@router.get("/warehouse", response_class=HTMLResponse)
async def admin_warehouse(
    request: Request,
    page: int = Query(1),
    current_user: User = Depends(require_any_role("Admin", "Warehouse Keeper")),
    db: AsyncSession = Depends(get_db),
):
    movements, total = await warehouse_service.get_all_movements(db, page, 20)
    low_stock = await warehouse_service.get_low_stock_products(db, 5)
    return templates.TemplateResponse("admin/warehouse_movements.html", {
        "request": request, "current_user": current_user,
        "movements": [warehouse_service.build_movement_response(m) for m in movements],
        "low_stock_products": low_stock,
        "total": total, "page": page, "total_pages": (total + 19) // 20,
    })


# ── Tickets ──

@router.get("/tickets", response_class=HTMLResponse)
async def admin_tickets(
    request: Request,
    page: int = Query(1),
    status_filter: str = Query(None),
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    tickets, total = await support_service.get_all_tickets(db, page, 20, status_filter)
    return templates.TemplateResponse("admin/tickets.html", {
        "request": request, "current_user": current_user,
        "tickets": [support_service.build_ticket_response(t) for t in tickets],
        "total": total, "page": page, "total_pages": (total + 19) // 20,
    })


@router.get("/tickets/{ticket_id}", response_class=HTMLResponse)
async def admin_ticket_detail(
    request: Request,
    ticket_id: str,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    import uuid
    tid = uuid.UUID(ticket_id)
    ticket = await support_service.get_ticket_by_id(db, tid)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return templates.TemplateResponse("admin/ticket_detail.html", {
        "request": request, "current_user": current_user,
        "ticket": support_service.build_ticket_response(ticket),
    })


# ── Product Types ──

@router.get("/product-types", response_class=HTMLResponse)
async def admin_product_types(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    items = (await db.execute(
        select(ProductType).where(ProductType.is_removed == False).order_by(ProductType.insert_date.desc())
    )).scalars().all()
    return templates.TemplateResponse("admin/product_types.html", {
        "request": request, "current_user": current_user, "items": items,
    })


@router.get("/product-types/new", response_class=HTMLResponse)
async def admin_product_type_create(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    return templates.TemplateResponse("admin/product_type_form.html", {
        "request": request, "current_user": current_user, "product_type": None,
    })


@router.post("/product-types/new", response_class=HTMLResponse)
async def admin_product_type_create_submit(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    fa_name = (form.get("fa_name") or "").strip()
    en_name = (form.get("en_name") or "").strip()

    pt = ProductType(fa_name=fa_name or None, en_name=en_name or None, created_by_user_id=current_user.id)
    db.add(pt)
    await db.flush()

    log_text = form.get("log") or ""
    if log_text:
        db.add(Log(
            record_id=pt.id,
            table_name="product_types",
            description=log_text,
            created_by_user_id=current_user.id,
        ))
    return RedirectResponse(url="/administration/product-types", status_code=303)


@router.get("/product-types/{product_type_id}/edit", response_class=HTMLResponse)
async def admin_product_type_edit(
    request: Request,
    product_type_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    pt = await db.get(ProductType, uuid.UUID(product_type_id))
    if pt is None or pt.is_removed:
        raise HTTPException(status_code=404, detail="Product type not found")
    return templates.TemplateResponse("admin/product_type_form.html", {
        "request": request, "current_user": current_user, "product_type": pt,
    })


@router.post("/product-types/{product_type_id}/edit", response_class=HTMLResponse)
async def admin_product_type_edit_submit(
    request: Request,
    product_type_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    pt = await db.get(ProductType, uuid.UUID(product_type_id))
    if pt is None or pt.is_removed:
        raise HTTPException(status_code=404, detail="Product type not found")

    form = await request.form()
    pt.fa_name = (form.get("fa_name") or "").strip() or None
    pt.en_name = (form.get("en_name") or "").strip() or None
    await db.flush()

    log_text = form.get("log") or ""
    if log_text:
        db.add(Log(
            record_id=pt.id,
            table_name="product_types",
            description=log_text,
            created_by_user_id=current_user.id,
        ))
    return RedirectResponse(url="/administration/product-types", status_code=303)


@router.get("/product-types/{product_type_id}", response_class=HTMLResponse)
async def admin_product_type_detail(
    request: Request,
    product_type_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    pt = await db.get(ProductType, uuid.UUID(product_type_id))
    if pt is None or pt.is_removed:
        raise HTTPException(status_code=404, detail="Product type not found")
    return templates.TemplateResponse("admin/product_type_detail.html", {
        "request": request, "current_user": current_user, "product_type": pt,
    })


@router.post("/product-types/{product_type_id}/delete", response_class=HTMLResponse)
async def admin_product_type_delete(
    request: Request,
    product_type_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    pt = await db.get(ProductType, uuid.UUID(product_type_id))
    if pt is None or pt.is_removed:
        raise HTTPException(status_code=404, detail="Product type not found")
    name = pt.fa_name or pt.en_name or ""
    pt.is_removed = True
    await db.flush()
    db.add(Log(
        record_id=pt.id,
        table_name="product_types",
        description=f"حذف نوع محصول: {name}",
        created_by_user_id=current_user.id,
    ))
    return RedirectResponse(url="/administration/product-types", status_code=303)


# ── Product Units ──

@router.get("/product-units", response_class=HTMLResponse)
async def admin_product_units(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    items = (await db.execute(
        select(ProductUnit).where(ProductUnit.is_removed == False).order_by(ProductUnit.insert_date.desc()).limit(100)
    )).scalars().all()
    return templates.TemplateResponse("admin/generic_list.html", {
        "request": request, "current_user": current_user,
        "title": "واحدهای محصول", "items": items,
        "columns": [
            {"key": "name", "label": "نام"},
            {"key": "abbreviation", "label": "مخفف"},
        ],
    })


# ── Tags ──

@router.get("/tags", response_class=HTMLResponse)
async def admin_tags(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    items = (await db.execute(
        select(Tag).where(Tag.is_removed == False).order_by(Tag.insert_date.desc()).limit(100)
    )).scalars().all()
    return templates.TemplateResponse("admin/generic_list.html", {
        "request": request, "current_user": current_user,
        "title": "برچسب‌ها", "items": items,
        "columns": [{"key": "name", "label": "نام"}],
        "create_url": "/administration/tags/new", "create_label": "برچسب جدید",
        "edit_url": "/administration/tags",
    })


@router.get("/tags/new", response_class=HTMLResponse)
async def admin_tag_create(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    return templates.TemplateResponse("admin/generic_form.html", {
        "request": request, "current_user": current_user,
        "title": "برچسب جدید",
        "fields": [
            {"name": "name", "label": "نام برچسب", "type": "text", "required": True},
        ],
    })


# ── Discounts ──

@router.get("/discounts", response_class=HTMLResponse)
async def admin_discounts(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Orders Manager")),
    db: AsyncSession = Depends(get_db),
):
    items = (await db.execute(
        select(Discount).where(Discount.is_removed == False).order_by(Discount.insert_date.desc()).limit(100)
    )).scalars().all()
    return templates.TemplateResponse("admin/generic_list.html", {
        "request": request, "current_user": current_user,
        "title": "تخفیف‌ها", "items": items,
        "columns": [
            {"key": "code", "label": "کد تخفیف"},
            {"key": "percent", "label": "درصد"},
            {"key": "amount", "label": "مبلغ"},
            {"key": "is_enable", "label": "فعال"},
        ],
        "create_url": "/administration/discounts/new", "create_label": "تخفیف جدید",
        "edit_url": "/administration/discounts",
    })


@router.get("/discounts/new", response_class=HTMLResponse)
async def admin_discount_create(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Orders Manager")),
    db: AsyncSession = Depends(get_db),
):
    return templates.TemplateResponse("admin/generic_form.html", {
        "request": request, "current_user": current_user,
        "title": "تخفیف جدید",
        "fields": [
            {"name": "code", "label": "کد تخفیف", "type": "text", "required": True},
            {"name": "percent", "label": "درصد تخفیف", "type": "number"},
            {"name": "amount", "label": "مبلغ تخفیف", "type": "number"},
            {"name": "is_enable", "label": "فعال", "type": "checkbox"},
        ],
    })


# ── Pay Methods ──

@router.get("/pay-methods", response_class=HTMLResponse)
async def admin_pay_methods(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Orders Manager")),
    db: AsyncSession = Depends(get_db),
):
    items = (await db.execute(
        select(PayMethod).where(PayMethod.is_removed == False).order_by(PayMethod.insert_date.desc()).limit(100)
    )).scalars().all()
    return templates.TemplateResponse("admin/generic_list.html", {
        "request": request, "current_user": current_user,
        "title": "روش‌های پرداخت", "items": items,
        "columns": [
            {"key": "name", "label": "نام"},
            {"key": "type", "label": "نوع"},
            {"key": "enable", "label": "فعال"},
        ],
    })


# ── Post Types ──

@router.get("/post-types", response_class=HTMLResponse)
async def admin_post_types(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Orders Manager")),
    db: AsyncSession = Depends(get_db),
):
    items = (await db.execute(
        select(PostType).where(PostType.is_removed == False).order_by(PostType.insert_date.desc()).limit(100)
    )).scalars().all()
    return templates.TemplateResponse("admin/generic_list.html", {
        "request": request, "current_user": current_user,
        "title": "روش‌های ارسال", "items": items,
        "columns": [
            {"key": "name", "label": "نام"},
            {"key": "site", "label": "سایت"},
            {"key": "price", "label": "هزینه"},
        ],
    })


# ── Technical Features ──

@router.get("/technical-features", response_class=HTMLResponse)
async def admin_technical_features(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    items = (await db.execute(
        select(TechnicalFeature).where(TechnicalFeature.is_removed == False).order_by(TechnicalFeature.insert_date.desc()).limit(100)
    )).scalars().all()
    return templates.TemplateResponse("admin/generic_list.html", {
        "request": request, "current_user": current_user,
        "title": "ویژگی‌های فنی", "items": items,
        "columns": [
            {"key": "name", "label": "نام"},
            {"key": "fa_name", "label": "نام فارسی"},
            {"key": "priority", "label": "اولویت"},
        ],
    })


# ── Technical Tables ──

@router.get("/technical-tables", response_class=HTMLResponse)
async def admin_technical_tables(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    items = (await db.execute(
        select(TechnicalTable).where(TechnicalTable.is_removed == False).order_by(TechnicalTable.insert_date.desc()).limit(100)
    )).scalars().all()
    return templates.TemplateResponse("admin/generic_list.html", {
        "request": request, "current_user": current_user,
        "title": "جدول‌های فنی", "items": items,
        "columns": [
            {"key": "title", "label": "عنوان"},
            {"key": "en_title", "label": "عنوان انگلیسی"},
            {"key": "columns", "label": "ستون‌ها"},
        ],
    })


# ── Category Options ──

@router.get("/category-options", response_class=HTMLResponse)
async def admin_category_options(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    items = (await db.execute(
        select(CategoryOption).where(CategoryOption.is_removed == False).order_by(CategoryOption.insert_date.desc()).limit(100)
    )).scalars().all()
    return templates.TemplateResponse("admin/generic_list.html", {
        "request": request, "current_user": current_user,
        "title": "گزینه‌های دسته‌بندی", "items": items,
        "columns": [{"key": "name", "label": "نام"}],
    })


# ── Media ──

@router.get("/media", response_class=HTMLResponse)
async def admin_media(
    request: Request,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    items = (await db.execute(
        select(Media).where(Media.is_removed == False).order_by(Media.insert_date.desc()).limit(100)
    )).scalars().all()
    return templates.TemplateResponse("admin/generic_list.html", {
        "request": request, "current_user": current_user,
        "title": "رسانه‌ها", "items": items,
        "columns": [
            {"key": "title", "label": "عنوان"},
            {"key": "type", "label": "نوع"},
        ],
    })


# ── Manufacturers ──

@router.get("/manufacturers", response_class=HTMLResponse)
async def admin_manufacturers(
    request: Request,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    items = (await db.execute(
        select(Manufacturer).where(Manufacturer.is_removed == False).order_by(Manufacturer.insert_date.desc()).limit(100)
    )).scalars().all()
    return templates.TemplateResponse("admin/generic_list.html", {
        "request": request, "current_user": current_user,
        "title": "تولیدکنندگان", "items": items,
        "columns": [
            {"key": "name", "label": "نام"},
            {"key": "telephone", "label": "تلفن"},
            {"key": "email", "label": "ایمیل"},
        ],
    })


# ── Admin Parameters ──

@router.get("/admin-parameters", response_class=HTMLResponse)
async def admin_parameters_page(
    request: Request,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    params = (await db.execute(
        select(AdminParameter).where(AdminParameter.is_removed == False).limit(10)
    )).scalars().all()
    return templates.TemplateResponse("admin/generic_list.html", {
        "request": request, "current_user": current_user,
        "title": "پارامترهای مدیریت", "items": params,
        "columns": [
            {"key": "confirm_order_pn", "label": "تلفن تأیید سفارش"},
            {"key": "confirm_order_em", "label": "ایمیل تأیید سفارش"},
        ],
    })


# ── Logs ──

@router.get("/logs", response_class=HTMLResponse)
async def admin_logs(
    request: Request,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    items = (await db.execute(
        select(Log).where(Log.is_removed == False).order_by(Log.insert_date.desc()).limit(200)
    )).scalars().all()
    return templates.TemplateResponse("admin/generic_list.html", {
        "request": request, "current_user": current_user,
        "title": "لاگ‌ها", "items": items,
        "columns": [
            {"key": "table_name", "label": "جدول"},
            {"key": "type", "label": "نوع"},
            {"key": "desc", "label": "توضیحات"},
            {"key": "insert_date", "label": "تاریخ"},
        ],
    })


# ── Logger (سوابق) dedicated page matching .NET ──

@router.get("/logs/{record_id}", response_class=HTMLResponse)
async def admin_logger(
    request: Request,
    record_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    from app.models.common import Log
    from app.models.identity import User

    # Build the base query
    filters = [Log.is_removed == False]

    # Record ID filter (route param)
    cid = uuid.UUID(record_id)
    filters.append(Log.record_id == cid)

    # Optional query filters
    uid = request.query_params.get("uId") or request.query_params.get("user_id") or ""
    log_type = request.query_params.get("log_type") or request.query_params.get("type") or ""
    table_name = "categories"

    try:
        if uid and uid != "all":
            filters.append(Log.created_by_user_id == uuid.UUID(uid))
    except (ValueError, AttributeError):
        pass

    if log_type and log_type != "all":
        filters.append(Log.type == log_type)

    # Fetch logs
    stmt = (
        select(Log)
        .where(*filters)
        .order_by(Log.insert_date.desc())
    )
    result = await db.execute(stmt)
    logs = result.unique().scalars().all()

    # Fetch all users for the filter dropdown
    users_result = await db.execute(
        select(User).where(User.is_removed == False).order_by(User.first_name)
    )
    users = users_result.scalars().all()

    # Get the record type from the first log entry
    if logs:
        table_name = logs[0].table_name or "categories"

    # Fetch the related user who created the record
    record_user = None
    for log in logs:
        if log.created_by_user_id:
            record_user = next((u for u in users if u.id == log.created_by_user_id), None)
            if record_user:
                break

    return templates.TemplateResponse("admin/logger.html", {
        "request": request, "current_user": current_user,
        "logs": logs, "users": users,
        "record_id": record_id,
        "table_name": table_name,
        "filter_user_id": uid,
        "filter_log_type": log_type,
        "record_user": record_user,
        "user_map": {str(u.id): u.full_name or u.username or "" for u in users},
    })


# ── Notified Products ──

@router.get("/notified-products", response_class=HTMLResponse)
async def admin_notified_products(
    request: Request,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    items = (await db.execute(
        select(NotifiedProduct).where(NotifiedProduct.is_removed == False).order_by(NotifiedProduct.insert_date.desc()).limit(100)
    )).scalars().all()
    return templates.TemplateResponse("admin/generic_list.html", {
        "request": request, "current_user": current_user,
        "title": "محصولات اطلاع‌رسانی شده", "items": items,
        "columns": [
            {"key": "variety_id", "label": "شناسه تنوع"},
            {"key": "sms_response_date", "label": "تاریخ پیامک"},
            {"key": "email_response_date", "label": "تاریخ ایمیل"},
        ],
    })


# ── Price History ──

@router.get("/price-history", response_class=HTMLResponse)
async def admin_price_history(
    request: Request,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    items = (await db.execute(
        select(PriceHistory).where(PriceHistory.is_removed == False).order_by(PriceHistory.insert_date.desc()).limit(200)
    )).scalars().all()
    return templates.TemplateResponse("admin/generic_list.html", {
        "request": request, "current_user": current_user,
        "title": "تاریخچه قیمت", "items": items,
        "columns": [
            {"key": "product_id", "label": "شناسه محصول"},
            {"key": "price", "label": "قیمت"},
            {"key": "insert_date", "label": "تاریخ"},
        ],
    })


# ── Chats (Admin) ──

@router.get("/chats", response_class=HTMLResponse)
async def admin_chats(
    request: Request,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    items = (await db.execute(
        select(Chat).where(Chat.is_removed == False).order_by(Chat.insert_date.desc()).limit(100)
    )).scalars().all()
    return templates.TemplateResponse("admin/generic_list.html", {
        "request": request, "current_user": current_user,
        "title": "چت‌ها", "items": items,
        "columns": [
            {"key": "title", "label": "عنوان"},
            {"key": "subject", "label": "موضوع"},
        ],
    })


# ── Identity Information ──

@router.get("/identity-informations", response_class=HTMLResponse)
async def admin_identity_informations(
    request: Request,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    items = (await db.execute(
        select(IdentityInformation).where(IdentityInformation.is_removed == False).order_by(IdentityInformation.insert_date.desc()).limit(100)
    )).scalars().all()
    return templates.TemplateResponse("admin/generic_list.html", {
        "request": request, "current_user": current_user,
        "title": "اطلاعات هویتی", "items": items,
        "columns": [
            {"key": "name", "label": "نام"},
            {"key": "national_code_or_id", "label": "کد ملی"},
            {"key": "type", "label": "نوع"},
            {"key": "status", "label": "وضعیت"},
        ],
    })


# ── Similar Products ──

@router.get("/similar-products", response_class=HTMLResponse)
async def admin_similar_products(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    items = (await db.execute(
        select(SimilarProduct).where(SimilarProduct.is_removed == False).order_by(SimilarProduct.insert_date.desc()).limit(100)
    )).scalars().all()
    return templates.TemplateResponse("admin/generic_list.html", {
        "request": request, "current_user": current_user,
        "title": "محصولات مشابه", "items": items,
        "columns": [
            {"key": "product_id", "label": "شناسه محصول"},
            {"key": "similar_product_id", "label": "شناسه محصول مشابه"},
        ],
    })


# ── Related Products ──

@router.get("/related-products", response_class=HTMLResponse)
async def admin_related_products(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    items = (await db.execute(
        select(RelatedProduct).where(RelatedProduct.is_removed == False).order_by(RelatedProduct.insert_date.desc()).limit(100)
    )).scalars().all()
    return templates.TemplateResponse("admin/generic_list.html", {
        "request": request, "current_user": current_user,
        "title": "محصولات مرتبط", "items": items,
        "columns": [
            {"key": "product_id", "label": "شناسه محصول"},
            {"key": "relate_product_id", "label": "شناسه محصول مرتبط"},
        ],
    })


# ── Product Tags ──

@router.get("/product-tags", response_class=HTMLResponse)
async def admin_product_tags(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    items = (await db.execute(
        select(ProductTag).where(ProductTag.is_removed == False).order_by(ProductTag.insert_date.desc()).limit(100)
    )).scalars().all()
    return templates.TemplateResponse("admin/generic_list.html", {
        "request": request, "current_user": current_user,
        "title": "برچسب محصولات", "items": items,
        "columns": [
            {"key": "product_id", "label": "شناسه محصول"},
            {"key": "tag_id", "label": "شناسه برچسب"},
        ],
    })


# ── Technical Table Products ──

@router.get("/technical-table-products", response_class=HTMLResponse)
async def admin_technical_table_products(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    items = (await db.execute(
        select(TechnicalTableProduct).where(TechnicalTableProduct.is_removed == False).order_by(TechnicalTableProduct.insert_date.desc()).limit(100)
    )).scalars().all()
    return templates.TemplateResponse("admin/generic_list.html", {
        "request": request, "current_user": current_user,
        "title": "جدول‌های فنی محصول", "items": items,
        "columns": [
            {"key": "product_id", "label": "شناسه محصول"},
            {"key": "technical_table_id", "label": "شناسه جدول فنی"},
        ],
    })


# ── Category Technical Features ──

@router.get("/category-technical-features", response_class=HTMLResponse)
async def admin_category_technical_features(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    items = (await db.execute(
        select(CategoryTechnicalFeature).where(CategoryTechnicalFeature.is_removed == False).order_by(CategoryTechnicalFeature.insert_date.desc()).limit(100)
    )).scalars().all()
    return templates.TemplateResponse("admin/generic_list.html", {
        "request": request, "current_user": current_user,
        "title": "دسته‌بندی ویژگی فنی", "items": items,
        "columns": [
            {"key": "category_id", "label": "شناسه دسته‌بندی"},
            {"key": "technical_feature_id", "label": "شناسه ویژگی فنی"},
        ],
    })


# ── Technical Feature Enums ──

@router.get("/technical-feature-enums", response_class=HTMLResponse)
async def admin_technical_feature_enums(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    items = (await db.execute(
        select(TechnicalFeatureEnum).where(TechnicalFeatureEnum.is_removed == False).order_by(TechnicalFeatureEnum.insert_date.desc()).limit(100)
    )).scalars().all()
    return templates.TemplateResponse("admin/generic_list.html", {
        "request": request, "current_user": current_user,
        "title": "انوم ویژگی فنی", "items": items,
        "columns": [
            {"key": "name", "label": "نام"},
            {"key": "persian_name", "label": "نام فارسی"},
        ],
    })


# ── Role Claims ──

@router.get("/role-claims", response_class=HTMLResponse)
async def admin_role_claims(
    request: Request,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    items = (await db.execute(
        select(RoleClaim).where(RoleClaim.is_removed == False).order_by(RoleClaim.insert_date.desc()).limit(100)
    )).scalars().all()
    return templates.TemplateResponse("admin/generic_list.html", {
        "request": request, "current_user": current_user,
        "title": "دسترسی‌ها", "items": items,
        "columns": [
            {"key": "role_id", "label": "شناسه نقش"},
            {"key": "operation_name", "label": "عملیات"},
        ],
    })


# ── User Roles ──

@router.get("/user-roles", response_class=HTMLResponse)
async def admin_user_roles(
    request: Request,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    items = (await db.execute(
        select(UserRole).where(UserRole.is_removed == False).order_by(UserRole.insert_date.desc()).limit(100)
    )).scalars().all()
    return templates.TemplateResponse("admin/generic_list.html", {
        "request": request, "current_user": current_user,
        "title": "نقش کاربران", "items": items,
        "columns": [
            {"key": "user_id", "label": "شناسه کاربر"},
            {"key": "role_id", "label": "شناسه نقش"},
        ],
    })