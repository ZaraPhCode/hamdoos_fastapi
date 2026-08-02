"""Admin page routes — renders Jinja2 templates for the admin panel."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.core.dependencies import get_admin_user, require_any_role
from app.models.identity import User, Role, IdentityInformation, RoleClaim, UserRole
from app.models.product import Product, Category, Brand, ProductType, ProductUnit, Currency, Tag, CategoryOption, PriceHistory, ProductTag, RelatedProduct, SimilarProduct, ProductImage, MenuDatasheet
from app.models.product_features import TechnicalFeature, TechnicalTable, CategoryTechnicalFeature, TechnicalTableProduct, TechnicalFeatureEnum, TechnicalFeatureValue
from app.models.order import OrderModel as Order, PayMethod, PostType, Discount
from app.models.invoice import Invoice, Supplier, SupplierProduct, PurchaseOrder
from app.models.finance import Receipt, Wallet, CurrencyDetail, WarehouseMovement
from app.models.customer_content import Comment, Media, NotifiedProduct
from app.models.support import Ticket, Chat
from app.models.common import Log, AdminParameter, SmsCode, MobileNumber, BankInfo
from app.models.manufacturer import Manufacturer
from app.schemas.product import CategoryCreate, CategoryUpdate
from app.utils.common_works import generate_slug
from app.services import admin_service, product_service, order_service, invoice_service, warehouse_service, finance_service, support_service, identity_service

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
    import jdatetime
    pid = uuid.UUID(product_id)
    product = await product_service.get_product_by_id(db, pid)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    tree = await product_service.get_admin_category_tree(db)
    options = _flatten_category_options(tree)
    brands = await product_service.get_all_brands(db)
    types = (await db.execute(select(ProductType).where(ProductType.is_removed == False))).scalars().all()
    units = (await db.execute(select(ProductUnit).where(ProductUnit.is_removed == False))).scalars().all()
    currencies = (await db.execute(select(Currency).where(Currency.is_removed == False))).scalars().all()
    suppliers = (await db.execute(select(Supplier).where(Supplier.is_removed == False))).scalars().all()
    purchase_date_str = ""
    if product.purchase_date:
        try:
            dt = product.purchase_date
            if dt.tzinfo is not None:
                dt = dt.replace(tzinfo=None)
            purchase_date_str = jdatetime.datetime.fromgregorian(datetime=dt).strftime("%Y/%m/%d")
        except Exception:
            purchase_date_str = product.purchase_date.strftime("%Y/%m/%d")
    return templates.TemplateResponse("admin/product_form.html", {
        "request": request, "current_user": current_user,
        "product": product, "categories_tree": options,
        "brands": brands, "product_types": types,
        "product_units": units, "currencies": currencies, "suppliers": suppliers,
        "purchase_date_str": purchase_date_str,
    })


@router.post("/products/{product_id}/edit", response_class=HTMLResponse)
async def admin_product_edit_submit(
    request: Request,
    product_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    import uuid
    import jdatetime
    from app.schemas.product import ProductUpdate
    from app.services.product_service import update_product

    pid = uuid.UUID(product_id)
    product = await product_service.get_product_by_id(db, pid)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    form = await request.form()

    purchase_date_str = form.get("purchase_date") or ""
    purchase_date = product.purchase_date
    if purchase_date_str:
        try:
            parts = purchase_date_str.replace("/", "-").split("-")
            purchase_date = jdatetime.date(int(parts[0]), int(parts[1]), int(parts[2])).togregorian()
        except Exception:
            purchase_date = product.purchase_date

    data = ProductUpdate(
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
        from app.utils.common_works import generate_slug
        data.en_slug = generate_slug(data.en_name)

    product = await update_product(db, product, data)
    log_text = form.get("log") or f"ویرایش محصول: {product.name}"
    db.add(Log(
        record_id=product.id, table_name="products",
        description=log_text, created_by_user_id=current_user.id,
        type="Update",
    ))
    await db.commit()
    return RedirectResponse(url="/administration/products", status_code=303)


@router.get("/products/{product_id}/details", response_class=HTMLResponse)
async def admin_product_details(
    request: Request,
    product_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    import uuid
    pid = uuid.UUID(product_id)
    product = await product_service.get_product_full_details(db, pid)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    tech_feature_ids = {
        value.technical_feature_id
        for table_product in product.technical_table_products
        for value in table_product.technical_feature_values
    }

    general_features = []
    if product.category_id:
        ctf_stmt = (
            select(CategoryTechnicalFeature)
            .options(selectinload(CategoryTechnicalFeature.technical_feature))
            .where(
                CategoryTechnicalFeature.category_id == product.category_id,
                CategoryTechnicalFeature.is_removed == False,
            )
            .order_by(CategoryTechnicalFeature.insert_date)
        )
        ctf_rows = (await db.execute(ctf_stmt)).scalars().all()
        for ctf in ctf_rows:
            if ctf.technical_feature_id in tech_feature_ids:
                continue
            general_features.append({
                "id": str(ctf.technical_feature_id),
                "text": ctf.technical_feature.fa_name or ctf.technical_feature.name or "",
            })

    special_features = []
    sp_stmt = (
        select(TechnicalFeature)
        .where(TechnicalFeature.is_removed == False)
        .order_by(TechnicalFeature.fa_name)
    )
    sp_rows = (await db.execute(sp_stmt)).scalars().all()
    for feat in sp_rows:
        if feat.id in tech_feature_ids:
            continue
        special_features.append({
            "id": str(feat.id),
            "text": feat.fa_name or feat.name or "",
        })

    tecnical_tables = []
    for table_product in product.technical_table_products:
        if table_product.technical_table:
            tecnical_tables.append({
                "id": str(table_product.id),
                "title": table_product.technical_table.title or "",
            })

    suppliers = (await db.execute(select(Supplier).where(Supplier.is_removed == False).order_by(Supplier.intermediary_name))).scalars().all()

    technical_products = []
    for table_product in product.technical_table_products:
        headers = []
        if table_product.technical_table and table_product.technical_table.header:
            headers = [h for h in table_product.technical_table.header.split(";") if h.strip()]
        column_count = table_product.technical_table.columns if table_product.technical_table else len(headers)
        rows = []
        for value in table_product.technical_feature_values:
            fmt_headers = []
            if value.technical_feature and value.technical_feature.display_format:
                fmt_headers = [h for h in value.technical_feature.display_format.split(";") if h.strip()]
            if column_count and len(fmt_headers) < column_count:
                fmt_headers.extend([""] * (column_count - len(fmt_headers)))
            elif column_count and len(fmt_headers) > column_count:
                fmt_headers = fmt_headers[:column_count]
            rows.append({
                "value": value,
                "feature": value.technical_feature,
                "value_headers": fmt_headers,
                "cells": [_format_tfv(value, f) for f in fmt_headers],
            })
        technical_products.append({
            "table_product": table_product,
            "technical_table": table_product.technical_table,
            "headers": headers,
            "rows": rows,
        })

    return templates.TemplateResponse("admin/product_details.html", {
        "request": request, "current_user": current_user,
        "product": product,
        "general_features": general_features,
        "special_features": special_features,
        "tecnical_tables": tecnical_tables,
        "technical_products": technical_products,
        "suppliers": suppliers,
        "insert_date_fa": _to_fa_datetime(product.insert_date),
        "update_date_fa": _to_fa_datetime(product.update_date),
        "purchase_date_fa": _to_fa_date(product.purchase_date),
        "product_images": sorted(product.product_images, key=lambda i: i.picture_order or 0),
    })


# ── Product sub-resources (details page) ──

@router.post("/products/{product_id}/images/new", response_class=HTMLResponse)
async def admin_product_image_create(
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
    form = await request.form()
    image = ProductImage(
        id=uuid.uuid4(),
        product_id=pid,
        title=form.get("title") or None,
        medium_image_url=form.get("medium_image_url") or None,
        small_image_url=form.get("medium_image_url") or None,
        large_image_url=form.get("medium_image_url") or None,
        display_photo=form.get("display_photo") in ("1", "true", "on"),
        picture_order=int(form.get("picture_order") or 0),
        created_by_user_id=current_user.id,
        insert_date=datetime.now(timezone.utc),
        update_date=datetime.now(timezone.utc),
    )
    db.add(image)
    db.add(Log(
        record_id=image.id, table_name="product_images",
        description=f"افزودن عکس به محصول: {product.name}",
        created_by_user_id=current_user.id, type="Create",
    ))
    await db.commit()
    return RedirectResponse(url=f"/administration/products/{product_id}/details", status_code=303)


@router.post("/products/{product_id}/images/{image_id}/delete", response_class=HTMLResponse)
async def admin_product_image_delete(
    request: Request,
    product_id: str,
    image_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    import uuid
    image = (await db.execute(
        select(ProductImage).where(ProductImage.id == uuid.UUID(image_id), ProductImage.is_removed == False)
    )).scalar_one_or_none()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    image.is_removed = True
    image.update_date = datetime.now(timezone.utc)
    await db.commit()
    return RedirectResponse(url=f"/administration/products/{product_id}/details", status_code=303)


@router.post("/products/{product_id}/datasheets/new", response_class=HTMLResponse)
async def admin_product_datasheet_create(
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
    form = await request.form()
    datasheet = MenuDatasheet(
        id=uuid.uuid4(),
        product_id=pid,
        type=form.get("type") or None,
        file_url=form.get("file_url") or None,
        complete_file_url=form.get("file_url") or None,
        created_by_user_id=current_user.id,
        insert_date=datetime.now(timezone.utc),
        update_date=datetime.now(timezone.utc),
    )
    db.add(datasheet)
    db.add(Log(
        record_id=datasheet.id, table_name="menu_datasheets",
        description=f"افزودن برگه اطلاعات به محصول: {product.name}",
        created_by_user_id=current_user.id, type="Create",
    ))
    await db.commit()
    return RedirectResponse(url=f"/administration/products/{product_id}/details", status_code=303)


@router.post("/products/{product_id}/datasheets/{datasheet_id}/delete", response_class=HTMLResponse)
async def admin_product_datasheet_delete(
    request: Request,
    product_id: str,
    datasheet_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    import uuid
    datasheet = (await db.execute(
        select(MenuDatasheet).where(MenuDatasheet.id == uuid.UUID(datasheet_id), MenuDatasheet.is_removed == False)
    )).scalar_one_or_none()
    if not datasheet:
        raise HTTPException(status_code=404, detail="Datasheet not found")
    datasheet.is_removed = True
    datasheet.update_date = datetime.now(timezone.utc)
    await db.commit()
    return RedirectResponse(url=f"/administration/products/{product_id}/details", status_code=303)


@router.post("/products/{product_id}/supplier-products/new", response_class=HTMLResponse)
async def admin_product_supplier_create(
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
    form = await request.form()
    supplier_id = form.get("supplier_id")
    link = form.get("link")
    if not supplier_id:
        raise HTTPException(status_code=400, detail="Supplier is required")
    supplier_product = SupplierProduct(
        id=uuid.uuid4(),
        product_id=pid,
        supplier_id=uuid.UUID(supplier_id) if supplier_id else None,
        link=link or None,
        created_by_user_id=current_user.id,
        insert_date=datetime.now(timezone.utc),
        update_date=datetime.now(timezone.utc),
    )
    db.add(supplier_product)
    db.add(Log(
        record_id=supplier_product.id, table_name="supplier_products",
        description=f"افزودن تامین‌کننده به محصول: {product.name}",
        created_by_user_id=current_user.id, type="Create",
    ))
    await db.commit()
    return RedirectResponse(url=f"/administration/products/{product_id}/details", status_code=303)


@router.post("/products/{product_id}/supplier-products/{sp_id}/delete", response_class=HTMLResponse)
async def admin_product_supplier_delete(
    request: Request,
    product_id: str,
    sp_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    import uuid
    sp = (await db.execute(
        select(SupplierProduct).where(SupplierProduct.id == uuid.UUID(sp_id), SupplierProduct.is_removed == False)
    )).scalar_one_or_none()
    if not sp:
        raise HTTPException(status_code=404, detail="Supplier product not found")
    sp.is_removed = True
    sp.update_date = datetime.now(timezone.utc)
    await db.commit()
    return RedirectResponse(url=f"/administration/products/{product_id}/details", status_code=303)


@router.post("/products/{product_id}/technical-values/set", response_class=HTMLResponse)
async def admin_product_technical_value_set(
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
    form = await request.form()
    feature_id = form.get("technical_feature_id")
    table_product_id = form.get("table_product_id")
    if not feature_id or not table_product_id:
        raise HTTPException(status_code=400, detail="Feature and table are required")

    table_product = (await db.execute(
        select(TechnicalTableProduct).where(
            TechnicalTableProduct.id == uuid.UUID(table_product_id),
            TechnicalTableProduct.product_id == pid,
            TechnicalTableProduct.is_removed == False,
        )
    )).scalar_one_or_none()
    if not table_product:
        raise HTTPException(status_code=404, detail="Technical table product not found")

    existing = (await db.execute(
        select(TechnicalFeatureValue).where(
            TechnicalFeatureValue.technical_table_product_id == table_product.id,
            TechnicalFeatureValue.technical_feature_id == uuid.UUID(feature_id),
            TechnicalFeatureValue.is_removed == False,
        )
    )).scalar_one_or_none()

    def _num(key):
        val = form.get(key)
        if val is None or val == "":
            return None
        try:
            return str(float(val))
        except Exception:
            return None

    payload = dict(
        technical_feature_id=uuid.UUID(feature_id),
        technical_table_product_id=table_product.id,
        min_value=_num("min_value"),
        max_value=_num("max_value"),
        min_unit=form.get("min_unit") or None,
        max_unit=form.get("max_unit") or None,
        d_value=_num("d_value"),
        unit=form.get("unit") or None,
        s_value=form.get("s_value") or None,
        b_value=form.get("b_value") in ("1", "true", "on"),
        x_value=_num("x_value"),
        x_unit=form.get("x_unit") or None,
        y_value=_num("y_value"),
        y_unit=form.get("y_unit") or None,
        z_value=_num("z_value"),
        z_unit=form.get("z_unit") or None,
        general_feature=form.get("general_feature") in ("1", "true", "on"),
        created_by_user_id=current_user.id,
    )
    if existing:
        for key, value in payload.items():
            setattr(existing, key, value)
        existing.update_date = datetime.now(timezone.utc)
        db.add(Log(
            record_id=existing.id, table_name="technical_feature_values",
            description=f"به‌روزرسانی ویژگی فنی محصول: {product.name}",
            created_by_user_id=current_user.id, type="Update",
        ))
    else:
        new_value = TechnicalFeatureValue(id=uuid.uuid4(), **payload)
        db.add(new_value)
        db.add(Log(
            record_id=new_value.id, table_name="technical_feature_values",
            description=f"افزودن ویژگی فنی به محصول: {product.name}",
            created_by_user_id=current_user.id, type="Create",
        ))
    await db.commit()
    return RedirectResponse(url=f"/administration/products/{product_id}/details", status_code=303)


@router.post("/products/{product_id}/technical-values/{value_id}/delete", response_class=HTMLResponse)
async def admin_product_technical_value_delete(
    request: Request,
    product_id: str,
    value_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    import uuid
    value = (await db.execute(
        select(TechnicalFeatureValue).where(TechnicalFeatureValue.id == uuid.UUID(value_id), TechnicalFeatureValue.is_removed == False)
    )).scalar_one_or_none()
    if not value:
        raise HTTPException(status_code=404, detail="Feature value not found")
    value.is_removed = True
    value.update_date = datetime.now(timezone.utc)
    await db.commit()
    return RedirectResponse(url=f"/administration/products/{product_id}/details", status_code=303)


@router.get("/products/{product_id}/delete", response_class=HTMLResponse)
async def admin_product_delete(
    request: Request,
    product_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    pid = uuid.UUID(product_id)
    product = await product_service.get_product_by_id(db, pid)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return templates.TemplateResponse("admin/product_delete.html", {
        "request": request, "current_user": current_user, "product": product,
    })


@router.post("/products/{product_id}/delete", response_class=HTMLResponse)
async def admin_product_delete_confirm(
    request: Request,
    product_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    pid = uuid.UUID(product_id)
    product = await product_service.get_product_by_id(db, pid)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    name = product.name
    category = product.category
    await product_service.delete_product(db, product)
    if category is not None:
        category.product_count = max((category.product_count or 0) - 1, 0)
    db.add(Log(
        record_id=pid,
        table_name="products",
        description=f"حذف محصول: {name}",
        created_by_user_id=current_user.id,
    ))
    await db.commit()
    return RedirectResponse(url="/administration/products", status_code=303)


def _format_tfv(value: TechnicalFeatureValue, display_format: str) -> str:
    """Render a technical feature value cell — mirrors the .NET
    TechnicalFeatureValue.Value(displayFormat) string.Format call."""
    if not display_format:
        return ""
    def _enum_name(enum):
        return enum.persian_name if enum else None
    args = (
        value.d_value if value.d_value is not None else "-",
        value.unit or "",
        value.s_value or "",
        _enum_name(value.technical_feature_enum) or value.e_value or "",
        str(value.b_value) if value.b_value is not None else "",
        value.min_value if value.min_value is not None else "-",
        value.min_unit or "",
        value.max_value if value.max_value is not None else "-",
        value.max_unit or "",
        value.x_value if value.x_value is not None else "-",
        value.x_unit or "",
        value.y_value if value.y_value is not None else "-",
        value.y_unit or "",
        value.z_value if value.z_value is not None else "-",
        value.z_unit or "",
        _enum_name(value.technical_feature_enum1) or value.e_value1 or "",
    )
    try:
        return display_format.format(*args)
    except Exception:
        return display_format


def _to_fa_datetime(value):
    """Convert an aware/naive datetime to a Persian (jalali) datetime string."""
    import jdatetime
    if not value:
        return "—"
    try:
        dt = value
        if dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)
        return jdatetime.datetime.fromgregorian(datetime=dt).strftime("%Y/%m/%d - %H:%M")
    except Exception:
        return "—"


def _to_fa_date(value):
    """Convert an aware/naive date to a Persian (jalali) date string."""
    import jdatetime
    if not value:
        return "—"
    try:
        dt = value
        if dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)
        return jdatetime.datetime.fromgregorian(datetime=dt).strftime("%Y/%m/%d")
    except Exception:
        return "—"


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
    stmt = (
        select(Brand)
        .options(selectinload(Brand.products))
        .where(Brand.is_removed == False)
        .order_by(Brand.insert_date.desc())
    )
    brands = (await db.execute(stmt)).unique().scalars().all()
    return templates.TemplateResponse("admin/brands.html", {
        "request": request, "current_user": current_user, "items": brands,
    })


@router.get("/brands/new", response_class=HTMLResponse)
async def admin_brand_create(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    return templates.TemplateResponse("admin/brand_form.html", {
        "request": request, "current_user": current_user, "brand": None,
    })


@router.post("/brands/new", response_class=HTMLResponse)
async def admin_brand_create_submit(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    name = (form.get("name") or "").strip()

    brand = Brand(name=name, created_by_user_id=current_user.id)
    db.add(brand)
    await db.flush()

    log_text = form.get("log") or ""
    if log_text:
        db.add(Log(
            record_id=brand.id,
            table_name="brands",
            description=log_text,
            created_by_user_id=current_user.id,
        ))
    return RedirectResponse(url="/administration/brands", status_code=303)


@router.get("/brands/{brand_id}/edit", response_class=HTMLResponse)
async def admin_brand_edit(
    request: Request,
    brand_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    brand = await db.get(Brand, uuid.UUID(brand_id))
    if brand is None or brand.is_removed:
        raise HTTPException(status_code=404, detail="Brand not found")
    return templates.TemplateResponse("admin/brand_form.html", {
        "request": request, "current_user": current_user, "brand": brand,
    })


@router.post("/brands/{brand_id}/edit", response_class=HTMLResponse)
async def admin_brand_edit_submit(
    request: Request,
    brand_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    brand = await db.get(Brand, uuid.UUID(brand_id))
    if brand is None or brand.is_removed:
        raise HTTPException(status_code=404, detail="Brand not found")

    form = await request.form()
    brand.name = (form.get("name") or "").strip()
    await db.flush()

    log_text = form.get("log") or ""
    if log_text:
        db.add(Log(
            record_id=brand.id,
            table_name="brands",
            description=log_text,
            created_by_user_id=current_user.id,
        ))
    return RedirectResponse(url="/administration/brands", status_code=303)


@router.get("/brands/{brand_id}", response_class=HTMLResponse)
async def admin_brand_detail(
    request: Request,
    brand_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    brand = await db.get(Brand, uuid.UUID(brand_id))
    if brand is None or brand.is_removed:
        raise HTTPException(status_code=404, detail="Brand not found")
    return templates.TemplateResponse("admin/brand_detail.html", {
        "request": request, "current_user": current_user, "brand": brand,
    })


@router.post("/brands/{brand_id}/delete", response_class=HTMLResponse)
async def admin_brand_delete(
    request: Request,
    brand_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    brand = await db.get(Brand, uuid.UUID(brand_id))
    if brand is None or brand.is_removed:
        raise HTTPException(status_code=404, detail="Brand not found")
    name = brand.name
    brand.is_removed = True
    await db.flush()
    db.add(Log(
        record_id=brand.id,
        table_name="brands",
        description=f"حذف برند: {name}",
        created_by_user_id=current_user.id,
    ))
    return RedirectResponse(url="/administration/brands", status_code=303)


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
    search: str = Query(""),
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    users, total = await identity_service.get_users_paginated(db, page, 20, search)
    roles = (await db.execute(select(Role).where(Role.is_removed == False))).scalars().all()
    return templates.TemplateResponse("admin/users.html", {
        "request": request, "current_user": current_user,
        "users": users, "total": total, "page": page, "total_pages": (total + 19) // 20,
        "search": search, "roles": roles,
    })


@router.get("/users/new", response_class=HTMLResponse)
async def admin_user_create(
    request: Request,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    return templates.TemplateResponse("admin/user_form.html", {
        "request": request, "current_user": current_user, "user": None,
    })


@router.post("/users/new", response_class=HTMLResponse)
async def admin_user_create_submit(
    request: Request,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    try:
        user = await identity_service.create_user(db, dict(form), current_user.id)
        return RedirectResponse(url="/administration/users", status_code=303)
    except ValueError as e:
        return templates.TemplateResponse("admin/user_form.html", {
            "request": request, "current_user": current_user, "user": None, "error": str(e),
        })


@router.get("/users/{user_id}/edit", response_class=HTMLResponse)
async def admin_user_edit(
    request: Request,
    user_id: str,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    uid = uuid.UUID(user_id)
    user = await identity_service.get_user_by_id(db, uid)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return templates.TemplateResponse("admin/user_form.html", {
        "request": request, "current_user": current_user, "user": user,
    })


@router.post("/users/{user_id}/edit", response_class=HTMLResponse)
async def admin_user_edit_submit(
    request: Request,
    user_id: str,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    uid = uuid.UUID(user_id)
    user = await identity_service.get_user_by_id(db, uid)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    form = await request.form()
    try:
        await identity_service.update_user(db, user, dict(form), current_user.id)
        return RedirectResponse(url="/administration/users", status_code=303)
    except ValueError as e:
        return templates.TemplateResponse("admin/user_form.html", {
            "request": request, "current_user": current_user, "user": user, "error": str(e),
        })


@router.get("/users/{user_id}", response_class=HTMLResponse)
async def admin_user_detail(
    request: Request,
    user_id: str,
    page: int = Query(1),
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.common import Address, BankInfo
    from app.models.order import OrderModel as Order
    uid = uuid.UUID(user_id)
    user = await identity_service.get_user_by_id(db, uid)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Load addresses
    addr_page = address_page = page
    addr_stmt = (
        select(Address)
        .options(selectinload(Address.province_city))
        .where(Address.user_id == uid, Address.is_removed == False)
        .order_by(Address.insert_date.desc())
    )
    addr_count = (await db.execute(select(func.count(Address.id)).where(Address.user_id == uid, Address.is_removed == False))).scalar() or 0
    addresses = (await db.execute(addr_stmt.offset(0).limit(100))).unique().scalars().all()

    # Load bank infos
    bank_stmt = (
        select(BankInfo)
        .where(BankInfo.user_id == uid, BankInfo.is_removed == False)
        .order_by(BankInfo.insert_date.desc())
    )
    bank_count = (await db.execute(select(func.count(BankInfo.id)).where(BankInfo.user_id == uid, BankInfo.is_removed == False))).scalar() or 0
    bank_infos = (await db.execute(bank_stmt.offset(0).limit(100))).scalars().all()

    # Load orders
    order_stmt = (
        select(Order)
        .where(Order.user_id == uid, Order.is_removed == False)
        .order_by(Order.insert_date.desc())
    )
    order_count = (await db.execute(select(func.count(Order.id)).where(Order.user_id == uid, Order.is_removed == False))).scalar() or 0
    orders = (await db.execute(order_stmt.offset(0).limit(100))).scalars().all()

    roles = (await db.execute(select(Role).where(Role.is_removed == False))).scalars().all()
    return templates.TemplateResponse("admin/user_detail.html", {
        "request": request, "current_user": current_user,
        "user": user, "roles": roles,
        "addresses": addresses, "addr_count": addr_count, "addr_page": 1, "addr_total_pages": (addr_count + 99) // 100,
        "bank_infos": bank_infos, "bank_count": bank_count, "bank_page": 1, "bank_total_pages": (bank_count + 99) // 100,
        "orders": orders, "order_count": order_count, "order_page": 1, "order_total_pages": (order_count + 99) // 100,
    })


@router.post("/users/{user_id}/delete", response_class=HTMLResponse)
async def admin_user_delete(
    request: Request,
    user_id: str,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    uid = uuid.UUID(user_id)
    user = await identity_service.get_user_by_id(db, uid)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await identity_service.soft_delete_user(db, user, current_user.id)
    return RedirectResponse(url="/administration/users", status_code=303)


@router.post("/users/{user_id}/roles", response_class=HTMLResponse)
async def admin_user_assign_role(
    request: Request,
    user_id: str,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    role_name = form.get("role_name", "")
    try:
        await identity_service.assign_role_to_user(db, uuid.UUID(user_id), role_name, current_user.id)
    except ValueError as e:
        return RedirectResponse(url=f"/administration/users/{user_id}", status_code=303)
    return RedirectResponse(url=f"/administration/users/{user_id}", status_code=303)


# ── Roles ──

@router.get("/roles", response_class=HTMLResponse)
async def admin_roles(
    request: Request,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    items = await identity_service.get_roles_with_counts(db)
    return templates.TemplateResponse("admin/roles.html", {
        "request": request, "current_user": current_user, "roles": items,
    })


@router.get("/roles/create", response_class=HTMLResponse)
async def admin_role_create(
    request: Request,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    return templates.TemplateResponse("admin/role_form.html", {
        "request": request, "current_user": current_user, "role": None,
    })


@router.post("/roles/create", response_class=HTMLResponse)
async def admin_role_create_submit(
    request: Request,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    try:
        role = await identity_service.create_role(db, dict(form), current_user.id)
        return RedirectResponse(url="/administration/roles", status_code=303)
    except ValueError as e:
        return templates.TemplateResponse("admin/role_form.html", {
            "request": request, "current_user": current_user, "role": None, "error": str(e),
        })


@router.get("/roles/{role_id}/edit", response_class=HTMLResponse)
async def admin_role_edit(
    request: Request,
    role_id: str,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    role = await identity_service.get_role_by_id(db, uuid.UUID(role_id))
    if not role or role.is_removed:
        raise HTTPException(status_code=404, detail="Role not found")
    return templates.TemplateResponse("admin/role_form.html", {
        "request": request, "current_user": current_user, "role": role,
    })


@router.post("/roles/{role_id}/edit", response_class=HTMLResponse)
async def admin_role_edit_submit(
    request: Request,
    role_id: str,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    role = await identity_service.get_role_by_id(db, uuid.UUID(role_id))
    if not role or role.is_removed:
        raise HTTPException(status_code=404, detail="Role not found")
    form = await request.form()
    try:
        await identity_service.update_role(db, role, dict(form), current_user.id)
        return RedirectResponse(url="/administration/roles", status_code=303)
    except ValueError as e:
        return templates.TemplateResponse("admin/role_form.html", {
            "request": request, "current_user": current_user, "role": role, "error": str(e),
        })


@router.get("/roles/{role_id}", response_class=HTMLResponse)
async def admin_role_detail(
    request: Request,
    role_id: str,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    role = await identity_service.get_role_by_id(db, uuid.UUID(role_id))
    if not role or role.is_removed:
        raise HTTPException(status_code=404, detail="Role not found")
    return templates.TemplateResponse("admin/role_detail.html", {
        "request": request, "current_user": current_user, "role": role,
    })


@router.post("/roles/{role_id}/delete", response_class=HTMLResponse)
async def admin_role_delete(
    request: Request,
    role_id: str,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    role = await identity_service.get_role_by_id(db, uuid.UUID(role_id))
    if not role or role.is_removed:
        raise HTTPException(status_code=404, detail="Role not found")
    await identity_service.soft_delete_role(db, role, current_user.id)
    return RedirectResponse(url="/administration/roles", status_code=303)


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
        select(ProductUnit).where(ProductUnit.is_removed == False).order_by(ProductUnit.insert_date.desc())
    )).scalars().all()
    return templates.TemplateResponse("admin/product_units.html", {
        "request": request, "current_user": current_user, "items": items,
    })


@router.get("/product-units/new", response_class=HTMLResponse)
async def admin_product_unit_create(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    return templates.TemplateResponse("admin/product_unit_form.html", {
        "request": request, "current_user": current_user, "product_unit": None,
    })


@router.post("/product-units/new", response_class=HTMLResponse)
async def admin_product_unit_create_submit(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    name = (form.get("name") or "").strip()
    abbreviation = (form.get("abbreviation") or "").strip()
    product_unit_tax_id = (form.get("product_unit_tax_id") or "").strip()

    pu = ProductUnit(
        name=name or None,
        abbreviation=abbreviation or None,
        product_unit_tax_id=product_unit_tax_id or None,
        created_by_user_id=current_user.id,
    )
    db.add(pu)
    await db.flush()

    log_text = form.get("log") or ""
    if log_text:
        db.add(Log(
            record_id=pu.id,
            table_name="product_units",
            description=log_text,
            created_by_user_id=current_user.id,
        ))
    return RedirectResponse(url="/administration/product-units", status_code=303)


@router.get("/product-units/{product_unit_id}/edit", response_class=HTMLResponse)
async def admin_product_unit_edit(
    request: Request,
    product_unit_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    pu = await db.get(ProductUnit, uuid.UUID(product_unit_id))
    if pu is None or pu.is_removed:
        raise HTTPException(status_code=404, detail="Product unit not found")
    return templates.TemplateResponse("admin/product_unit_form.html", {
        "request": request, "current_user": current_user, "product_unit": pu,
    })


@router.post("/product-units/{product_unit_id}/edit", response_class=HTMLResponse)
async def admin_product_unit_edit_submit(
    request: Request,
    product_unit_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    pu = await db.get(ProductUnit, uuid.UUID(product_unit_id))
    if pu is None or pu.is_removed:
        raise HTTPException(status_code=404, detail="Product unit not found")

    form = await request.form()
    pu.name = (form.get("name") or "").strip() or None
    pu.abbreviation = (form.get("abbreviation") or "").strip() or None
    pu.product_unit_tax_id = (form.get("product_unit_tax_id") or "").strip() or None
    await db.flush()

    log_text = form.get("log") or ""
    if log_text:
        db.add(Log(
            record_id=pu.id,
            table_name="product_units",
            description=log_text,
            created_by_user_id=current_user.id,
        ))
    return RedirectResponse(url="/administration/product-units", status_code=303)


@router.get("/product-units/{product_unit_id}", response_class=HTMLResponse)
async def admin_product_unit_detail(
    request: Request,
    product_unit_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    pu = await db.get(ProductUnit, uuid.UUID(product_unit_id))
    if pu is None or pu.is_removed:
        raise HTTPException(status_code=404, detail="Product unit not found")
    return templates.TemplateResponse("admin/product_unit_detail.html", {
        "request": request, "current_user": current_user, "product_unit": pu,
    })


@router.post("/product-units/{product_unit_id}/delete", response_class=HTMLResponse)
async def admin_product_unit_delete(
    request: Request,
    product_unit_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    pu = await db.get(ProductUnit, uuid.UUID(product_unit_id))
    if pu is None or pu.is_removed:
        raise HTTPException(status_code=404, detail="Product unit not found")
    name = pu.name or pu.abbreviation or ""
    pu.is_removed = True
    await db.flush()
    db.add(Log(
        record_id=pu.id,
        table_name="product_units",
        description=f"حذف واحد اندازه‌گیری: {name}",
        created_by_user_id=current_user.id,
    ))
    return RedirectResponse(url="/administration/product-units", status_code=303)


# ── Tags ──

@router.get("/tags", response_class=HTMLResponse)
async def admin_tags(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Tag)
        .options(selectinload(Tag.product_tags))
        .where(Tag.is_removed == False)
        .order_by(Tag.insert_date.desc())
    )
    items = (await db.execute(stmt)).unique().scalars().all()
    return templates.TemplateResponse("admin/tags.html", {
        "request": request, "current_user": current_user, "items": items,
    })


@router.get("/tags/new", response_class=HTMLResponse)
async def admin_tag_create(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    return templates.TemplateResponse("admin/tag_form.html", {
        "request": request, "current_user": current_user, "tag": None,
    })


@router.post("/tags/new", response_class=HTMLResponse)
async def admin_tag_create_submit(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    name = (form.get("name") or "").strip()

    tag = Tag(name=name, created_by_user_id=current_user.id)
    db.add(tag)
    await db.flush()

    log_text = form.get("log") or ""
    if log_text:
        db.add(Log(
            record_id=tag.id,
            table_name="tags",
            description=log_text,
            created_by_user_id=current_user.id,
        ))
    return RedirectResponse(url="/administration/tags", status_code=303)


@router.get("/tags/{tag_id}/edit", response_class=HTMLResponse)
async def admin_tag_edit(
    request: Request,
    tag_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    tag = await db.get(Tag, uuid.UUID(tag_id))
    if tag is None or tag.is_removed:
        raise HTTPException(status_code=404, detail="Tag not found")
    return templates.TemplateResponse("admin/tag_form.html", {
        "request": request, "current_user": current_user, "tag": tag,
    })


@router.post("/tags/{tag_id}/edit", response_class=HTMLResponse)
async def admin_tag_edit_submit(
    request: Request,
    tag_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    tag = await db.get(Tag, uuid.UUID(tag_id))
    if tag is None or tag.is_removed:
        raise HTTPException(status_code=404, detail="Tag not found")

    form = await request.form()
    tag.name = (form.get("name") or "").strip()
    await db.flush()

    log_text = form.get("log") or ""
    if log_text:
        db.add(Log(
            record_id=tag.id,
            table_name="tags",
            description=log_text,
            created_by_user_id=current_user.id,
        ))
    return RedirectResponse(url="/administration/tags", status_code=303)


@router.get("/tags/{tag_id}", response_class=HTMLResponse)
async def admin_tag_detail(
    request: Request,
    tag_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    tag = await db.get(Tag, uuid.UUID(tag_id))
    if tag is None or tag.is_removed:
        raise HTTPException(status_code=404, detail="Tag not found")
    return templates.TemplateResponse("admin/tag_detail.html", {
        "request": request, "current_user": current_user, "tag": tag,
    })


@router.post("/tags/{tag_id}/delete", response_class=HTMLResponse)
async def admin_tag_delete(
    request: Request,
    tag_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    tag = await db.get(Tag, uuid.UUID(tag_id))
    if tag is None or tag.is_removed:
        raise HTTPException(status_code=404, detail="Tag not found")
    name = tag.name
    tag.is_removed = True
    await db.flush()
    db.add(Log(
        record_id=tag.id,
        table_name="tags",
        description=f"حذف برچسب: {name}",
        created_by_user_id=current_user.id,
    ))
    return RedirectResponse(url="/administration/tags", status_code=303)


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
    page: int = Query(1),
    type_filter: str = Query(""),
    status_filter: str = Query(""),
    user_filter: str = Query(""),
    national_code_filter: str = Query(""),
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.enums import IdentityType, IdentityStatus
    items, total = await identity_service.get_identity_infos_with_user(
        db, page, 20, type_filter, status_filter, user_filter, national_code_filter
    )
    users = (await db.execute(select(User).where(User.is_removed == False).order_by(User.first_name))).scalars().all()
    return templates.TemplateResponse("admin/identity_informations.html", {
        "request": request, "current_user": current_user,
        "items": items, "total": total, "page": page, "total_pages": (total + 19) // 20,
        "type_filter": type_filter, "status_filter": status_filter,
        "user_filter": user_filter, "national_code_filter": national_code_filter,
        "users": users, "identity_types": list(IdentityType), "identity_statuses": list(IdentityStatus),
    })


@router.get("/identity-informations/new", response_class=HTMLResponse)
async def admin_identity_information_create(
    request: Request,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    users = (await db.execute(select(User).where(User.is_removed == False).order_by(User.first_name))).scalars().all()
    return templates.TemplateResponse("admin/identity_information_form.html", {
        "request": request, "current_user": current_user,
        "info": None, "users": users,
    })


@router.post("/identity-informations/new", response_class=HTMLResponse)
async def admin_identity_information_create_submit(
    request: Request,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    users = (await db.execute(select(User).where(User.is_removed == False).order_by(User.first_name))).scalars().all()
    try:
        info = await identity_service.create_identity_info(db, dict(form), current_user.id)
        return RedirectResponse(url="/administration/identity-informations", status_code=303)
    except ValueError as e:
        return templates.TemplateResponse("admin/identity_information_form.html", {
            "request": request, "current_user": current_user,
            "info": None, "users": users, "error": str(e), "form_data": dict(form),
        })


@router.get("/identity-informations/{info_id}/edit", response_class=HTMLResponse)
async def admin_identity_information_edit(
    request: Request,
    info_id: str,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    info = await identity_service.get_identity_info_by_id(db, uuid.UUID(info_id))
    if not info:
        raise HTTPException(status_code=404, detail="Identity information not found")
    users = (await db.execute(select(User).where(User.is_removed == False).order_by(User.first_name))).scalars().all()
    return templates.TemplateResponse("admin/identity_information_form.html", {
        "request": request, "current_user": current_user,
        "info": info, "users": users,
    })


@router.post("/identity-informations/{info_id}/edit", response_class=HTMLResponse)
async def admin_identity_information_edit_submit(
    request: Request,
    info_id: str,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    info = await identity_service.get_identity_info_by_id(db, uuid.UUID(info_id))
    if not info:
        raise HTTPException(status_code=404, detail="Identity information not found")
    form = await request.form()
    users = (await db.execute(select(User).where(User.is_removed == False).order_by(User.first_name))).scalars().all()
    try:
        await identity_service.update_identity_info(db, info, dict(form), current_user.id)
        return RedirectResponse(url="/administration/identity-informations", status_code=303)
    except ValueError as e:
        return templates.TemplateResponse("admin/identity_information_form.html", {
            "request": request, "current_user": current_user,
            "info": info, "users": users, "error": str(e), "form_data": dict(form),
        })


@router.get("/identity-informations/{info_id}", response_class=HTMLResponse)
async def admin_identity_information_detail(
    request: Request,
    info_id: str,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    info = await identity_service.get_identity_info_by_id(db, uuid.UUID(info_id))
    if not info:
        raise HTTPException(status_code=404, detail="Identity information not found")
    return templates.TemplateResponse("admin/identity_information_detail.html", {
        "request": request, "current_user": current_user, "info": info,
    })


@router.post("/identity-informations/{info_id}/accept", response_class=HTMLResponse)
async def admin_identity_information_accept(
    request: Request,
    info_id: str,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    info = await identity_service.get_identity_info_by_id(db, uuid.UUID(info_id))
    if not info:
        raise HTTPException(status_code=404, detail="Identity information not found")
    try:
        await identity_service.accept_identity_info(db, info, current_user.id)
    except ValueError as e:
        pass
    return RedirectResponse(url="/administration/identity-informations", status_code=303)


@router.post("/identity-informations/{info_id}/reject", response_class=HTMLResponse)
async def admin_identity_information_reject(
    request: Request,
    info_id: str,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    info = await identity_service.get_identity_info_by_id(db, uuid.UUID(info_id))
    if not info:
        raise HTTPException(status_code=404, detail="Identity information not found")
    try:
        await identity_service.reject_identity_info(db, info, current_user.id)
    except ValueError as e:
        pass
    return RedirectResponse(url="/administration/identity-informations", status_code=303)


@router.post("/identity-informations/{info_id}/delete", response_class=HTMLResponse)
async def admin_identity_information_delete(
    request: Request,
    info_id: str,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    info = await identity_service.get_identity_info_by_id(db, uuid.UUID(info_id))
    if not info:
        raise HTTPException(status_code=404, detail="Identity information not found")
    await identity_service.soft_delete_identity_info(db, info, current_user.id)
    return RedirectResponse(url="/administration/identity-informations", status_code=303)


# ── Similar Products ──

@router.get("/similar-products", response_class=HTMLResponse)
async def admin_similar_products(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(SimilarProduct)
        .options(selectinload(SimilarProduct.product), selectinload(SimilarProduct.similar))
        .where(SimilarProduct.is_removed == False)
        .order_by(SimilarProduct.insert_date.desc())
    )
    items = (await db.execute(stmt)).unique().scalars().all()
    return templates.TemplateResponse("admin/similar_products.html", {
        "request": request, "current_user": current_user, "items": items,
    })


@router.get("/similar-products/new", response_class=HTMLResponse)
async def admin_similar_product_create(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    products = (await db.execute(
        select(Product).where(Product.is_removed == False).order_by(Product.name)
    )).scalars().all()
    return templates.TemplateResponse("admin/similar_product_form.html", {
        "request": request, "current_user": current_user,
        "similar_product": None, "products": products,
    })


@router.post("/similar-products/new", response_class=HTMLResponse)
async def admin_similar_product_create_submit(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    product_id_raw = form.get("product_id")
    similar_product_id_raw = form.get("similar_product_id")
    if not product_id_raw or not similar_product_id_raw:
        raise HTTPException(status_code=400, detail="Product and similar product are required")
    if product_id_raw == similar_product_id_raw:
        raise HTTPException(status_code=400, detail="محصول و محصول مشابه نمی‌توانند یکسان باشند")

    existing = (await db.execute(
        select(SimilarProduct).where(
            SimilarProduct.product_id == uuid.UUID(product_id_raw),
            SimilarProduct.similar_product_id == uuid.UUID(similar_product_id_raw),
            SimilarProduct.is_removed == False,
        )
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="این ارتباط از قبل وجود دارد")

    sp = SimilarProduct(
        product_id=uuid.UUID(product_id_raw),
        similar_product_id=uuid.UUID(similar_product_id_raw),
        created_by_user_id=current_user.id,
    )
    db.add(sp)
    await db.flush()

    log_text = form.get("log") or ""
    if log_text:
        db.add(Log(
            record_id=sp.id,
            table_name="similar_products",
            description=log_text,
            created_by_user_id=current_user.id,
        ))
    return RedirectResponse(url="/administration/similar-products", status_code=303)


@router.get("/similar-products/{similar_product_id}/edit", response_class=HTMLResponse)
async def admin_similar_product_edit(
    request: Request,
    similar_product_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    sp = await db.get(SimilarProduct, uuid.UUID(similar_product_id))
    if sp is None or sp.is_removed:
        raise HTTPException(status_code=404, detail="Similar product not found")
    products = (await db.execute(
        select(Product).where(Product.is_removed == False).order_by(Product.name)
    )).scalars().all()
    return templates.TemplateResponse("admin/similar_product_form.html", {
        "request": request, "current_user": current_user,
        "similar_product": sp, "products": products,
    })


@router.post("/similar-products/{similar_product_id}/edit", response_class=HTMLResponse)
async def admin_similar_product_edit_submit(
    request: Request,
    similar_product_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    sp = await db.get(SimilarProduct, uuid.UUID(similar_product_id))
    if sp is None or sp.is_removed:
        raise HTTPException(status_code=404, detail="Similar product not found")

    form = await request.form()
    product_id_raw = form.get("product_id")
    similar_product_id_raw = form.get("similar_product_id")
    if product_id_raw:
        sp.product_id = uuid.UUID(product_id_raw)
    if similar_product_id_raw:
        sp.similar_product_id = uuid.UUID(similar_product_id_raw)
    await db.flush()

    log_text = form.get("log") or ""
    if log_text:
        db.add(Log(
            record_id=sp.id,
            table_name="similar_products",
            description=log_text,
            created_by_user_id=current_user.id,
        ))
    return RedirectResponse(url="/administration/similar-products", status_code=303)


@router.get("/similar-products/{similar_product_id}", response_class=HTMLResponse)
async def admin_similar_product_detail(
    request: Request,
    similar_product_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(SimilarProduct)
        .options(selectinload(SimilarProduct.product), selectinload(SimilarProduct.similar))
        .where(SimilarProduct.id == uuid.UUID(similar_product_id), SimilarProduct.is_removed == False)
    )
    sp = (await db.execute(stmt)).unique().scalar_one_or_none()
    if sp is None:
        raise HTTPException(status_code=404, detail="Similar product not found")
    return templates.TemplateResponse("admin/similar_product_detail.html", {
        "request": request, "current_user": current_user, "similar_product": sp,
    })


@router.post("/similar-products/{similar_product_id}/delete", response_class=HTMLResponse)
async def admin_similar_product_delete(
    request: Request,
    similar_product_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    sp = await db.get(SimilarProduct, uuid.UUID(similar_product_id))
    if sp is None or sp.is_removed:
        raise HTTPException(status_code=404, detail="Similar product not found")
    sp.is_removed = True
    await db.flush()
    db.add(Log(
        record_id=sp.id,
        table_name="similar_products",
        description="حذف محصول مشابه",
        created_by_user_id=current_user.id,
    ))
    return RedirectResponse(url="/administration/similar-products", status_code=303)


# ── Related Products ──

@router.get("/related-products", response_class=HTMLResponse)
async def admin_related_products(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(RelatedProduct)
        .options(selectinload(RelatedProduct.product), selectinload(RelatedProduct.relate_product))
        .where(RelatedProduct.is_removed == False)
        .order_by(RelatedProduct.insert_date.desc())
    )
    items = (await db.execute(stmt)).unique().scalars().all()
    return templates.TemplateResponse("admin/related_products.html", {
        "request": request, "current_user": current_user, "items": items,
    })


@router.get("/related-products/new", response_class=HTMLResponse)
async def admin_related_product_create(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    products = (await db.execute(
        select(Product).where(Product.is_removed == False).order_by(Product.name)
    )).scalars().all()
    return templates.TemplateResponse("admin/related_product_form.html", {
        "request": request, "current_user": current_user,
        "related_product": None, "products": products,
    })


@router.post("/related-products/new", response_class=HTMLResponse)
async def admin_related_product_create_submit(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    product_id_raw = form.get("product_id")
    relate_product_id_raw = form.get("relate_product_id")
    if not product_id_raw or not relate_product_id_raw:
        raise HTTPException(status_code=400, detail="Product and related product are required")
    if product_id_raw == relate_product_id_raw:
        raise HTTPException(status_code=400, detail="محصول و محصول مرتبط نمی‌توانند یکسان باشند")

    rp = RelatedProduct(
        product_id=uuid.UUID(product_id_raw),
        relate_product_id=uuid.UUID(relate_product_id_raw),
        created_by_user_id=current_user.id,
    )
    db.add(rp)
    await db.flush()

    log_text = form.get("log") or ""
    if log_text:
        db.add(Log(
            record_id=rp.id,
            table_name="related_products",
            description=log_text,
            created_by_user_id=current_user.id,
        ))
    return RedirectResponse(url="/administration/related-products", status_code=303)


@router.get("/related-products/{related_product_id}/edit", response_class=HTMLResponse)
async def admin_related_product_edit(
    request: Request,
    related_product_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    rp = await db.get(RelatedProduct, uuid.UUID(related_product_id))
    if rp is None or rp.is_removed:
        raise HTTPException(status_code=404, detail="Related product not found")
    products = (await db.execute(
        select(Product).where(Product.is_removed == False).order_by(Product.name)
    )).scalars().all()
    return templates.TemplateResponse("admin/related_product_form.html", {
        "request": request, "current_user": current_user,
        "related_product": rp, "products": products,
    })


@router.post("/related-products/{related_product_id}/edit", response_class=HTMLResponse)
async def admin_related_product_edit_submit(
    request: Request,
    related_product_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    rp = await db.get(RelatedProduct, uuid.UUID(related_product_id))
    if rp is None or rp.is_removed:
        raise HTTPException(status_code=404, detail="Related product not found")

    form = await request.form()
    product_id_raw = form.get("product_id")
    relate_product_id_raw = form.get("relate_product_id")
    if product_id_raw:
        rp.product_id = uuid.UUID(product_id_raw)
    if relate_product_id_raw:
        rp.relate_product_id = uuid.UUID(relate_product_id_raw)
    await db.flush()

    log_text = form.get("log") or ""
    if log_text:
        db.add(Log(
            record_id=rp.id,
            table_name="related_products",
            description=log_text,
            created_by_user_id=current_user.id,
        ))
    return RedirectResponse(url="/administration/related-products", status_code=303)


@router.get("/related-products/{related_product_id}", response_class=HTMLResponse)
async def admin_related_product_detail(
    request: Request,
    related_product_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(RelatedProduct)
        .options(selectinload(RelatedProduct.product), selectinload(RelatedProduct.relate_product))
        .where(RelatedProduct.id == uuid.UUID(related_product_id), RelatedProduct.is_removed == False)
    )
    rp = (await db.execute(stmt)).unique().scalar_one_or_none()
    if rp is None:
        raise HTTPException(status_code=404, detail="Related product not found")
    return templates.TemplateResponse("admin/related_product_detail.html", {
        "request": request, "current_user": current_user, "related_product": rp,
    })


@router.post("/related-products/{related_product_id}/delete", response_class=HTMLResponse)
async def admin_related_product_delete(
    request: Request,
    related_product_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    rp = await db.get(RelatedProduct, uuid.UUID(related_product_id))
    if rp is None or rp.is_removed:
        raise HTTPException(status_code=404, detail="Related product not found")
    rp.is_removed = True
    await db.flush()
    db.add(Log(
        record_id=rp.id,
        table_name="related_products",
        description="حذف محصول مرتبط",
        created_by_user_id=current_user.id,
    ))
    return RedirectResponse(url="/administration/related-products", status_code=303)


# ── Product Tags ──

@router.get("/product-tags", response_class=HTMLResponse)
async def admin_product_tags(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(ProductTag)
        .options(selectinload(ProductTag.product), selectinload(ProductTag.tag))
        .where(ProductTag.is_removed == False)
        .order_by(ProductTag.insert_date.desc())
    )
    items = (await db.execute(stmt)).unique().scalars().all()
    return templates.TemplateResponse("admin/product_tags.html", {
        "request": request, "current_user": current_user, "items": items,
    })


@router.get("/product-tags/new", response_class=HTMLResponse)
async def admin_product_tag_create(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    products = (await db.execute(
        select(Product).where(Product.is_removed == False).order_by(Product.name)
    )).scalars().all()
    tags = (await db.execute(
        select(Tag).where(Tag.is_removed == False).order_by(Tag.name)
    )).scalars().all()
    return templates.TemplateResponse("admin/product_tag_form.html", {
        "request": request, "current_user": current_user,
        "product_tag": None, "products": products, "tags": tags,
    })


@router.post("/product-tags/new", response_class=HTMLResponse)
async def admin_product_tag_create_submit(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    product_id_raw = form.get("product_id")
    tag_id_raw = form.get("tag_id")
    if not product_id_raw or not tag_id_raw:
        raise HTTPException(status_code=400, detail="Product and tag are required")

    existing = (await db.execute(
        select(ProductTag).where(
            ProductTag.product_id == uuid.UUID(product_id_raw),
            ProductTag.tag_id == uuid.UUID(tag_id_raw),
            ProductTag.is_removed == False,
        )
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="این ارتباط از قبل وجود دارد")

    pt = ProductTag(
        product_id=uuid.UUID(product_id_raw),
        tag_id=uuid.UUID(tag_id_raw),
        created_by_user_id=current_user.id,
    )
    db.add(pt)
    await db.flush()

    log_text = form.get("log") or ""
    if log_text:
        db.add(Log(
            record_id=pt.id,
            table_name="product_tags",
            description=log_text,
            created_by_user_id=current_user.id,
        ))
    return RedirectResponse(url="/administration/product-tags", status_code=303)


@router.get("/product-tags/{product_tag_id}/edit", response_class=HTMLResponse)
async def admin_product_tag_edit(
    request: Request,
    product_tag_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    pt = await db.get(ProductTag, uuid.UUID(product_tag_id))
    if pt is None or pt.is_removed:
        raise HTTPException(status_code=404, detail="Product tag not found")
    products = (await db.execute(
        select(Product).where(Product.is_removed == False).order_by(Product.name)
    )).scalars().all()
    tags = (await db.execute(
        select(Tag).where(Tag.is_removed == False).order_by(Tag.name)
    )).scalars().all()
    return templates.TemplateResponse("admin/product_tag_form.html", {
        "request": request, "current_user": current_user,
        "product_tag": pt, "products": products, "tags": tags,
    })


@router.post("/product-tags/{product_tag_id}/edit", response_class=HTMLResponse)
async def admin_product_tag_edit_submit(
    request: Request,
    product_tag_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    pt = await db.get(ProductTag, uuid.UUID(product_tag_id))
    if pt is None or pt.is_removed:
        raise HTTPException(status_code=404, detail="Product tag not found")

    form = await request.form()
    product_id_raw = form.get("product_id")
    tag_id_raw = form.get("tag_id")
    if product_id_raw:
        pt.product_id = uuid.UUID(product_id_raw)
    if tag_id_raw:
        pt.tag_id = uuid.UUID(tag_id_raw)
    await db.flush()

    log_text = form.get("log") or ""
    if log_text:
        db.add(Log(
            record_id=pt.id,
            table_name="product_tags",
            description=log_text,
            created_by_user_id=current_user.id,
        ))
    return RedirectResponse(url="/administration/product-tags", status_code=303)


@router.get("/product-tags/{product_tag_id}", response_class=HTMLResponse)
async def admin_product_tag_detail(
    request: Request,
    product_tag_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(ProductTag)
        .options(selectinload(ProductTag.product), selectinload(ProductTag.tag))
        .where(ProductTag.id == uuid.UUID(product_tag_id), ProductTag.is_removed == False)
    )
    pt = (await db.execute(stmt)).unique().scalar_one_or_none()
    if pt is None:
        raise HTTPException(status_code=404, detail="Product tag not found")
    return templates.TemplateResponse("admin/product_tag_detail.html", {
        "request": request, "current_user": current_user, "product_tag": pt,
    })


@router.post("/product-tags/{product_tag_id}/delete", response_class=HTMLResponse)
async def admin_product_tag_delete(
    request: Request,
    product_tag_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    pt = await db.get(ProductTag, uuid.UUID(product_tag_id))
    if pt is None or pt.is_removed:
        raise HTTPException(status_code=404, detail="Product tag not found")
    pt.is_removed = True
    await db.flush()
    db.add(Log(
        record_id=pt.id,
        table_name="product_tags",
        description="حذف برچسب محصول",
        created_by_user_id=current_user.id,
    ))
    return RedirectResponse(url="/administration/product-tags", status_code=303)


# ── Technical Feature Enums ──

@router.get("/technical-feature-enums", response_class=HTMLResponse)
async def admin_technical_feature_enums(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    items = (await db.execute(
        select(TechnicalFeatureEnum)
        .where(TechnicalFeatureEnum.is_removed == False)
        .order_by(TechnicalFeatureEnum.persian_name)
    )).scalars().all()
    return templates.TemplateResponse("admin/technical_feature_enums.html", {
        "request": request, "current_user": current_user, "items": items,
    })


@router.get("/technical-feature-enums/new", response_class=HTMLResponse)
async def admin_technical_feature_enum_create(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    return templates.TemplateResponse("admin/technical_feature_enum_form.html", {
        "request": request, "current_user": current_user, "feature_enum": None,
    })


@router.post("/technical-feature-enums/new", response_class=HTMLResponse)
async def admin_technical_feature_enum_create_submit(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    persian_name = (form.get("persian_name") or "").strip()
    name = (form.get("name") or "").strip()

    fe = TechnicalFeatureEnum(
        persian_name=persian_name or None,
        name=name or None,
        created_by_user_id=current_user.id,
    )
    db.add(fe)
    await db.flush()

    log_text = form.get("log") or ""
    if log_text:
        db.add(Log(
            record_id=fe.id,
            table_name="technical_feature_enums",
            description=log_text,
            created_by_user_id=current_user.id,
        ))
    return RedirectResponse(url="/administration/technical-feature-enums", status_code=303)


@router.get("/technical-feature-enums/{enum_id}/edit", response_class=HTMLResponse)
async def admin_technical_feature_enum_edit(
    request: Request,
    enum_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    fe = await db.get(TechnicalFeatureEnum, uuid.UUID(enum_id))
    if fe is None or fe.is_removed:
        raise HTTPException(status_code=404, detail="Technical feature enum not found")
    return templates.TemplateResponse("admin/technical_feature_enum_form.html", {
        "request": request, "current_user": current_user, "feature_enum": fe,
    })


@router.post("/technical-feature-enums/{enum_id}/edit", response_class=HTMLResponse)
async def admin_technical_feature_enum_edit_submit(
    request: Request,
    enum_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    fe = await db.get(TechnicalFeatureEnum, uuid.UUID(enum_id))
    if fe is None or fe.is_removed:
        raise HTTPException(status_code=404, detail="Technical feature enum not found")

    form = await request.form()
    fe.persian_name = (form.get("persian_name") or "").strip() or None
    fe.name = (form.get("name") or "").strip() or None
    await db.flush()

    log_text = form.get("log") or ""
    if log_text:
        db.add(Log(
            record_id=fe.id,
            table_name="technical_feature_enums",
            description=log_text,
            created_by_user_id=current_user.id,
        ))
    return RedirectResponse(url="/administration/technical-feature-enums", status_code=303)


@router.get("/technical-feature-enums/{enum_id}", response_class=HTMLResponse)
async def admin_technical_feature_enum_detail(
    request: Request,
    enum_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    fe = await db.get(TechnicalFeatureEnum, uuid.UUID(enum_id))
    if fe is None or fe.is_removed:
        raise HTTPException(status_code=404, detail="Technical feature enum not found")
    return templates.TemplateResponse("admin/technical_feature_enum_detail.html", {
        "request": request, "current_user": current_user, "feature_enum": fe,
    })


@router.post("/technical-feature-enums/{enum_id}/delete", response_class=HTMLResponse)
async def admin_technical_feature_enum_delete(
    request: Request,
    enum_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    fe = await db.get(TechnicalFeatureEnum, uuid.UUID(enum_id))
    if fe is None or fe.is_removed:
        raise HTTPException(status_code=404, detail="Technical feature enum not found")
    name = fe.name or fe.persian_name or ""
    fe.is_removed = True
    await db.flush()
    db.add(Log(
        record_id=fe.id,
        table_name="technical_feature_enums",
        description=f"حذف انوم ویژگی فنی: {name}",
        created_by_user_id=current_user.id,
    ))
    return RedirectResponse(url="/administration/technical-feature-enums", status_code=303)


# ── Category Technical Features ──

@router.get("/category-technical-features", response_class=HTMLResponse)
async def admin_category_technical_features(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    items = (await db.execute(
        select(CategoryTechnicalFeature)
        .options(selectinload(CategoryTechnicalFeature.category), selectinload(CategoryTechnicalFeature.technical_feature))
        .where(CategoryTechnicalFeature.is_removed == False)
        .order_by(CategoryTechnicalFeature.insert_date.desc())
    )).unique().scalars().all()
    return templates.TemplateResponse("admin/category_technical_features.html", {
        "request": request, "current_user": current_user, "items": items,
    })


async def _ctf_dropdowns(db: AsyncSession):
    categories = (await db.execute(
        select(Category).where(Category.is_removed == False).order_by(Category.title)
    )).scalars().all()
    technical_features = (await db.execute(
        select(TechnicalFeature).where(TechnicalFeature.is_removed == False).order_by(TechnicalFeature.fa_name)
    )).scalars().all()
    return categories, technical_features


@router.get("/category-technical-features/new", response_class=HTMLResponse)
async def admin_category_technical_feature_create(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    categories, technical_features = await _ctf_dropdowns(db)
    return templates.TemplateResponse("admin/category_technical_feature_form.html", {
        "request": request, "current_user": current_user, "ctf": None,
        "categories": categories, "technical_features": technical_features,
    })


@router.post("/category-technical-features/new", response_class=HTMLResponse)
async def admin_category_technical_feature_create_submit(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    category_id = form.get("category_id")
    technical_feature_id = form.get("technical_feature_id")
    if not category_id or not technical_feature_id:
        raise HTTPException(status_code=400, detail="Category and feature are required")

    exists = (await db.execute(
        select(CategoryTechnicalFeature.id).where(
            CategoryTechnicalFeature.is_removed == False,
            CategoryTechnicalFeature.category_id == uuid.UUID(category_id),
            CategoryTechnicalFeature.technical_feature_id == uuid.UUID(technical_feature_id),
        )
    )).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=400, detail="این دسته‌بندی و ویژگی فنی قبلاً تعریف شده")

    ctf = CategoryTechnicalFeature(
        category_id=uuid.UUID(category_id),
        technical_feature_id=uuid.UUID(technical_feature_id),
        created_by_user_id=current_user.id,
    )
    db.add(ctf)
    await db.flush()
    db.add(Log(
        record_id=ctf.id,
        table_name="category_technical_features",
        description="ایجاد دسته‌بندی ویژگی فنی",
        created_by_user_id=current_user.id,
    ))
    return RedirectResponse(url="/administration/category-technical-features", status_code=303)


@router.get("/category-technical-features/{ctf_id}/edit", response_class=HTMLResponse)
async def admin_category_technical_feature_edit(
    request: Request,
    ctf_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    ctf = (await db.execute(
        select(CategoryTechnicalFeature)
        .options(selectinload(CategoryTechnicalFeature.category), selectinload(CategoryTechnicalFeature.technical_feature))
        .where(CategoryTechnicalFeature.id == uuid.UUID(ctf_id), CategoryTechnicalFeature.is_removed == False)
    )).scalar_one_or_none()
    if ctf is None:
        raise HTTPException(status_code=404, detail="Category technical feature not found")
    categories, technical_features = await _ctf_dropdowns(db)
    return templates.TemplateResponse("admin/category_technical_feature_form.html", {
        "request": request, "current_user": current_user, "ctf": ctf,
        "categories": categories, "technical_features": technical_features,
    })


@router.post("/category-technical-features/{ctf_id}/edit", response_class=HTMLResponse)
async def admin_category_technical_feature_edit_submit(
    request: Request,
    ctf_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    ctf = (await db.execute(
        select(CategoryTechnicalFeature)
        .where(CategoryTechnicalFeature.id == uuid.UUID(ctf_id), CategoryTechnicalFeature.is_removed == False)
    )).scalar_one_or_none()
    if ctf is None:
        raise HTTPException(status_code=404, detail="Category technical feature not found")

    form = await request.form()
    category_id = form.get("category_id")
    technical_feature_id = form.get("technical_feature_id")
    if not category_id or not technical_feature_id:
        raise HTTPException(status_code=400, detail="Category and Technical Feature are required")

    ctf.category_id = uuid.UUID(category_id)
    ctf.technical_feature_id = uuid.UUID(technical_feature_id)
    await db.flush()

    db.add(Log(
        record_id=ctf.id,
        table_name="category_technical_features",
        description="ویرایش دسته‌بندی ویژگی فنی",
        created_by_user_id=current_user.id,
    ))
    return RedirectResponse(url="/administration/category-technical-features", status_code=303)


@router.post("/category-technical-features/{ctf_id}/delete", response_class=HTMLResponse)
async def admin_category_technical_feature_delete(
    request: Request,
    ctf_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    ctf = (await db.execute(
        select(CategoryTechnicalFeature)
        .where(CategoryTechnicalFeature.id == uuid.UUID(ctf_id), CategoryTechnicalFeature.is_removed == False)
    )).scalar_one_or_none()
    if ctf is None:
        raise HTTPException(status_code=404, detail="Category technical feature not found")
    ctf.is_removed = True
    await db.flush()
    db.add(Log(
        record_id=ctf.id,
        table_name="category_technical_features",
        description="حذف دسته‌بندی ویژگی فنی",
        created_by_user_id=current_user.id,
    ))
    return RedirectResponse(url="/administration/category-technical-features", status_code=303)


# ── Technical Tables ──

@router.get("/technical-tables", response_class=HTMLResponse)
async def admin_technical_tables(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    items = (await db.execute(
        select(TechnicalTable).where(TechnicalTable.is_removed == False).order_by(TechnicalTable.title)
    )).scalars().all()
    return templates.TemplateResponse("admin/technical_tables.html", {
        "request": request, "current_user": current_user, "items": items,
    })


@router.get("/technical-tables/new", response_class=HTMLResponse)
async def admin_technical_table_create(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    return templates.TemplateResponse("admin/technical_table_form.html", {
        "request": request, "current_user": current_user, "table": None,
    })


@router.post("/technical-tables/new", response_class=HTMLResponse)
async def admin_technical_table_create_submit(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    title = (form.get("title") or "").strip()
    en_title = (form.get("en_title") or "").strip()
    columns = _to_int(form.get("columns"), 0)
    header = (form.get("header") or "").strip()

    tt = TechnicalTable(
        title=title or None, en_title=en_title or None,
        columns=columns, header=header or None, created_by_user_id=current_user.id,
    )
    db.add(tt)
    await db.flush()
    db.add(Log(
        record_id=tt.id, table_name="technical_tables",
        description=f"ایجاد جدول فنی: {title}", created_by_user_id=current_user.id,
    ))
    return RedirectResponse(url="/administration/technical-tables", status_code=303)


@router.get("/technical-tables/{table_id}/edit", response_class=HTMLResponse)
async def admin_technical_table_edit(
    request: Request,
    table_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    tt = await db.get(TechnicalTable, uuid.UUID(table_id))
    if tt is None or tt.is_removed:
        raise HTTPException(status_code=404, detail="Technical table not found")
    return templates.TemplateResponse("admin/technical_table_form.html", {
        "request": request, "current_user": current_user, "table": tt,
    })


@router.post("/technical-tables/{table_id}/edit", response_class=HTMLResponse)
async def admin_technical_table_edit_submit(
    request: Request,
    table_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    tt = await db.get(TechnicalTable, uuid.UUID(table_id))
    if tt is None or tt.is_removed:
        raise HTTPException(status_code=404, detail="Technical table not found")

    form = await request.form()
    tt.title = (form.get("title") or "").strip() or None
    tt.en_title = (form.get("en_title") or "").strip() or None
    tt.columns = _to_int(form.get("columns"), 0)
    tt.header = (form.get("header") or "").strip() or None
    await db.flush()

    db.add(Log(
        record_id=tt.id, table_name="technical_tables",
        description=f"ویرایش جدول فنی: {tt.title}", created_by_user_id=current_user.id,
    ))
    return RedirectResponse(url="/administration/technical-tables", status_code=303)


@router.get("/technical-tables/{table_id}", response_class=HTMLResponse)
async def admin_technical_table_detail(
    request: Request,
    table_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    tt = await db.get(TechnicalTable, uuid.UUID(table_id))
    if tt is None or tt.is_removed:
        raise HTTPException(status_code=404, detail="Technical table not found")
    return templates.TemplateResponse("admin/technical_table_detail.html", {
        "request": request, "current_user": current_user, "table": tt,
    })


@router.post("/technical-tables/{table_id}/delete", response_class=HTMLResponse)
async def admin_technical_table_delete(
    request: Request,
    table_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    tt = await db.get(TechnicalTable, uuid.UUID(table_id))
    if tt is None or tt.is_removed:
        raise HTTPException(status_code=404, detail="Technical table not found")
    name = tt.title or ""
    tt.is_removed = True
    await db.flush()
    db.add(Log(
        record_id=tt.id, table_name="technical_tables",
        description=f"حذف جدول فنی: {name}", created_by_user_id=current_user.id,
    ))
    return RedirectResponse(url="/administration/technical-tables", status_code=303)


# ── Technical Table Products ──

@router.get("/technical-table-products", response_class=HTMLResponse)
async def admin_technical_table_products(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    items = (await db.execute(
        select(TechnicalTableProduct)
        .options(selectinload(TechnicalTableProduct.product), selectinload(TechnicalTableProduct.technical_table))
        .where(TechnicalTableProduct.is_removed == False)
        .order_by(TechnicalTableProduct.insert_date.desc())
    )).unique().scalars().all()
    return templates.TemplateResponse("admin/technical_table_products.html", {
        "request": request, "current_user": current_user, "items": items,
    })


@router.get("/technical-table-products/new", response_class=HTMLResponse)
async def admin_technical_table_product_create(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    products = (await db.execute(
        select(Product).where(Product.is_removed == False).order_by(Product.name)
    )).scalars().all()
    tables = (await db.execute(
        select(TechnicalTable).where(TechnicalTable.is_removed == False).order_by(TechnicalTable.title)
    )).scalars().all()
    return templates.TemplateResponse("admin/technical_table_product_form.html", {
        "request": request, "current_user": current_user, "ttp": None,
        "products": products, "tables": tables,
    })


@router.post("/technical-table-products/new", response_class=HTMLResponse)
async def admin_technical_table_product_create_submit(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    product_id = form.get("product_id")
    technical_table_id = form.get("technical_table_id")
    if not product_id or not technical_table_id:
        raise HTTPException(status_code=400, detail="Product and technical table are required")

    exists = (await db.execute(
        select(TechnicalTableProduct.id).where(
            TechnicalTableProduct.is_removed == False,
            TechnicalTableProduct.product_id == uuid.UUID(product_id),
            TechnicalTableProduct.technical_table_id == uuid.UUID(technical_table_id),
        )
    )).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=400, detail="این جدول فنی برای این محصول تعریف شده")

    ttp = TechnicalTableProduct(
        product_id=uuid.UUID(product_id),
        technical_table_id=uuid.UUID(technical_table_id),
        created_by_user_id=current_user.id,
    )
    db.add(ttp)
    await db.flush()
    db.add(Log(
        record_id=ttp.id, table_name="technical_table_products",
        description="ایجاد جدول فنی محصول", created_by_user_id=current_user.id,
    ))
    return RedirectResponse(url="/administration/technical-table-products", status_code=303)


@router.get("/technical-table-products/{ttp_id}/edit", response_class=HTMLResponse)
async def admin_technical_table_product_edit(
    request: Request,
    ttp_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    ttp = (await db.execute(
        select(TechnicalTableProduct)
        .options(selectinload(TechnicalTableProduct.product), selectinload(TechnicalTableProduct.technical_table))
        .where(TechnicalTableProduct.id == uuid.UUID(ttp_id), TechnicalTableProduct.is_removed == False)
    )).scalar_one_or_none()
    if ttp is None:
        raise HTTPException(status_code=404, detail="Technical table product not found")
    products = (await db.execute(
        select(Product).where(Product.is_removed == False).order_by(Product.name)
    )).scalars().all()
    tables = (await db.execute(
        select(TechnicalTable).where(TechnicalTable.is_removed == False).order_by(TechnicalTable.title)
    )).scalars().all()
    return templates.TemplateResponse("admin/technical_table_product_form.html", {
        "request": request, "current_user": current_user, "ttp": ttp,
        "products": products, "tables": tables,
    })


@router.post("/technical-table-products/{ttp_id}/edit", response_class=HTMLResponse)
async def admin_technical_table_product_edit_submit(
    request: Request,
    ttp_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    ttp = (await db.execute(
        select(TechnicalTableProduct)
        .where(TechnicalTableProduct.id == uuid.UUID(ttp_id), TechnicalTableProduct.is_removed == False)
    )).scalar_one_or_none()
    if ttp is None:
        raise HTTPException(status_code=404, detail="Technical table product not found")

    form = await request.form()
    product_id = form.get("product_id")
    technical_table_id = form.get("technical_table_id")
    if not product_id or not technical_table_id:
        raise HTTPException(status_code=400, detail="Product and technical table are required")

    ttp.product_id = uuid.UUID(product_id)
    ttp.technical_table_id = uuid.UUID(technical_table_id)
    await db.flush()

    db.add(Log(
        record_id=ttp.id, table_name="technical_table_products",
        description="ویرایش جدول فنی محصول", created_by_user_id=current_user.id,
    ))
    return RedirectResponse(url="/administration/technical-table-products", status_code=303)


@router.get("/technical-table-products/{ttp_id}", response_class=HTMLResponse)
async def admin_technical_table_product_detail(
    request: Request,
    ttp_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    ttp = (await db.execute(
        select(TechnicalTableProduct)
        .options(selectinload(TechnicalTableProduct.product), selectinload(TechnicalTableProduct.technical_table))
        .where(TechnicalTableProduct.id == uuid.UUID(ttp_id), TechnicalTableProduct.is_removed == False)
    )).scalar_one_or_none()
    if ttp is None:
        raise HTTPException(status_code=404, detail="Technical table product not found")
    return templates.TemplateResponse("admin/technical_table_product_detail.html", {
        "request": request, "current_user": current_user, "ttp": ttp,
    })


@router.post("/technical-table-products/{ttp_id}/delete", response_class=HTMLResponse)
async def admin_technical_table_product_delete(
    request: Request,
    ttp_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    ttp = (await db.execute(
        select(TechnicalTableProduct)
        .where(TechnicalTableProduct.id == uuid.UUID(ttp_id), TechnicalTableProduct.is_removed == False)
    )).scalar_one_or_none()
    if ttp is None:
        raise HTTPException(status_code=404, detail="Technical table product not found")
    ttp.is_removed = True
    await db.flush()
    db.add(Log(
        record_id=ttp.id, table_name="technical_table_products",
        description="حذف جدول فنی محصول", created_by_user_id=current_user.id,
    ))
    return RedirectResponse(url="/administration/technical-table-products", status_code=303)


# ── Technical Features ──

@router.get("/technical-features", response_class=HTMLResponse)
async def admin_technical_features(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    items = (await db.execute(
        select(TechnicalFeature).where(TechnicalFeature.is_removed == False).order_by(TechnicalFeature.fa_name)
    )).scalars().all()
    return templates.TemplateResponse("admin/technical_features.html", {
        "request": request, "current_user": current_user, "items": items,
    })


@router.get("/technical-features/new", response_class=HTMLResponse)
async def admin_technical_feature_create(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    enums = (await db.execute(
        select(TechnicalFeatureEnum).where(TechnicalFeatureEnum.is_removed == False).order_by(TechnicalFeatureEnum.persian_name)
    )).scalars().all()
    return templates.TemplateResponse("admin/technical_feature_form.html", {
        "request": request, "current_user": current_user, "feature": None, "enums": enums,
    })


@router.post("/technical-features/new", response_class=HTMLResponse)
async def admin_technical_feature_create_submit(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    name = (form.get("name") or "").strip()
    fa_name = (form.get("fa_name") or "").strip()
    description = (form.get("description") or "").strip()
    display_format = (form.get("display_format") or "").strip()
    linear_display = (form.get("linear_display") or "").strip()
    columns = _to_int(form.get("columns"), 1)
    priority = _to_int(form.get("priority"), 1500)
    visible_in_schema = form.get("visible_in_schema") == "on"

    feature = TechnicalFeature(
        name=name or None, fa_name=fa_name or None, description=description or None,
        display_format=display_format or None, linear_display=linear_display or None,
        columns=max(columns, 1), priority=priority, visible_in_schema=visible_in_schema,
        d_value=_checkbox_bool(form, "d_value"), unit=_checkbox_bool(form, "unit"),
        s_value=_checkbox_bool(form, "s_value"), e_value=_checkbox_bool(form, "e_value"),
        e_value1=_checkbox_bool(form, "e_value1"),
        b_value=_checkbox_bool(form, "b_value"),
        min_value=_checkbox_bool(form, "min_value"), min_unit=_checkbox_bool(form, "min_unit"),
        max_value=_checkbox_bool(form, "max_value"), max_unit=_checkbox_bool(form, "max_unit"),
        x_value=_checkbox_bool(form, "x_value"), x_unit=_checkbox_bool(form, "x_unit"),
        y_value=_checkbox_bool(form, "y_value"), y_unit=_checkbox_bool(form, "y_unit"),
        z_value=_checkbox_bool(form, "z_value"), z_unit=_checkbox_bool(form, "z_unit"),
        created_by_user_id=current_user.id,
    )
    db.add(feature)
    await db.flush()
    await _assign_feature_enums(db, feature, form.getlist("feature_enum_ids"), form.getlist("feature_enum1_ids"))
    db.add(Log(
        record_id=feature.id, table_name="technical_features",
        description=f"ایجاد ویژگی فنی: {fa_name or name}", created_by_user_id=current_user.id,
    ))
    return RedirectResponse(url="/administration/technical-features", status_code=303)


async def _assign_feature_enums(db: AsyncSession, feature: TechnicalFeature, enum_ids, enum1_ids):
    enum_ids = enum_ids or []
    enum1_ids = enum1_ids or []
    existing = (await db.execute(
        select(TechnicalFeatureEnum).where(
            TechnicalFeatureEnum.id.in_([uuid.UUID(x) for x in enum_ids + enum1_ids]),
            TechnicalFeatureEnum.is_removed == False,
        )
    )).scalars().all()
    for e in existing:
        if e.id in {uuid.UUID(x) for x in enum_ids}:
            e.technical_feature_id = feature.id
        else:
            e.technical_feature_id = None
        if e.id in {uuid.UUID(x) for x in enum1_ids}:
            e.technical_feature1_id = feature.id
        else:
            e.technical_feature1_id = None


@router.get("/technical-features/{feature_id}/edit", response_class=HTMLResponse)
async def admin_technical_feature_edit(
    request: Request,
    feature_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    feature = await db.get(TechnicalFeature, uuid.UUID(feature_id))
    if feature is None or feature.is_removed:
        raise HTTPException(status_code=404, detail="Technical feature not found")
    enums = (await db.execute(
        select(TechnicalFeatureEnum).where(TechnicalFeatureEnum.is_removed == False).order_by(TechnicalFeatureEnum.persian_name)
    )).scalars().all()
    return templates.TemplateResponse("admin/technical_feature_form.html", {
        "request": request, "current_user": current_user, "feature": feature, "enums": enums,
    })


@router.post("/technical-features/{feature_id}/edit", response_class=HTMLResponse)
async def admin_technical_feature_edit_submit(
    request: Request,
    feature_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    feature = await db.get(TechnicalFeature, uuid.UUID(feature_id))
    if feature is None or feature.is_removed:
        raise HTTPException(status_code=404, detail="Technical feature not found")

    form = await request.form()
    feature.name = (form.get("name") or "").strip() or None
    feature.fa_name = (form.get("fa_name") or "").strip() or None
    feature.description = (form.get("description") or "").strip() or None
    feature.display_format = (form.get("display_format") or "").strip() or None
    feature.linear_display = (form.get("linear_display") or "").strip() or None
    feature.columns = max(_to_int(form.get("columns"), 1), 1)
    feature.priority = _to_int(form.get("priority"), 1500)
    feature.visible_in_schema = form.get("visible_in_schema") == "on"

    feature.d_value = _checkbox_bool(form, "d_value")
    feature.unit = _checkbox_bool(form, "unit")
    feature.s_value = _checkbox_bool(form, "s_value")
    feature.e_value = _checkbox_bool(form, "e_value")
    feature.e_value1 = _checkbox_bool(form, "e_value1")
    feature.b_value = _checkbox_bool(form, "b_value")
    feature.min_value = _checkbox_bool(form, "min_value")
    feature.min_unit = _checkbox_bool(form, "min_unit")
    feature.max_value = _checkbox_bool(form, "max_value")
    feature.max_unit = _checkbox_bool(form, "max_unit")
    feature.x_value = _checkbox_bool(form, "x_value")
    feature.x_unit = _checkbox_bool(form, "x_unit")
    feature.y_value = _checkbox_bool(form, "y_value")
    feature.y_unit = _checkbox_bool(form, "y_unit")
    feature.z_value = _checkbox_bool(form, "z_value")
    feature.z_unit = _checkbox_bool(form, "z_unit")
    await _assign_feature_enums(db, feature, form.getlist("feature_enum_ids"), form.getlist("feature_enum1_ids"))
    await db.flush()

    db.add(Log(
        record_id=feature.id, table_name="technical_features",
        description=f"ویرایش ویژگی فنی: {feature.fa_name or feature.name}", created_by_user_id=current_user.id,
    ))
    return RedirectResponse(url="/administration/technical-features", status_code=303)


@router.get("/technical-features/{feature_id}", response_class=HTMLResponse)
async def admin_technical_feature_detail(
    request: Request,
    feature_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    feature = await db.get(TechnicalFeature, uuid.UUID(feature_id))
    if feature is None or feature.is_removed:
        raise HTTPException(status_code=404, detail="Technical feature not found")
    return templates.TemplateResponse("admin/technical_feature_detail.html", {
        "request": request, "current_user": current_user, "feature": feature,
    })


@router.post("/technical-features/{feature_id}/delete", response_class=HTMLResponse)
async def admin_technical_feature_delete(
    request: Request,
    feature_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    feature = await db.get(TechnicalFeature, uuid.UUID(feature_id))
    if feature is None or feature.is_removed:
        raise HTTPException(status_code=404, detail="Technical feature not found")
    name = feature.name or feature.fa_name or ""
    feature.is_removed = True
    await db.flush()
    db.add(Log(
        record_id=feature.id, table_name="technical_features",
        description=f"حذف ویژگی فنی: {name}", created_by_user_id=current_user.id,
    ))
    return RedirectResponse(url="/administration/technical-features", status_code=303)


# ── Category Options ──

@router.get("/category-options", response_class=HTMLResponse)
async def admin_category_options(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    items = (await db.execute(
        select(CategoryOption).where(CategoryOption.is_removed == False).order_by(CategoryOption.name)
    )).scalars().all()
    return templates.TemplateResponse("admin/category_options.html", {
        "request": request, "current_user": current_user, "items": items,
    })


@router.get("/category-options/new", response_class=HTMLResponse)
async def admin_category_option_create(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    return templates.TemplateResponse("admin/category_option_form.html", {
        "request": request, "current_user": current_user, "category_option": None,
    })


@router.post("/category-options/new", response_class=HTMLResponse)
async def admin_category_option_create_submit(
    request: Request,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    name = (form.get("name") or "").strip()
    try:
        co = CategoryOption(name=name, created_by_user_id=current_user.id)
        db.add(co)
        await db.flush()
    except Exception:
        raise HTTPException(status_code=400, detail="این گزینه قبلاً تعریف شده")
    db.add(Log(
        record_id=co.id, table_name="category_options",
        description=f"ایجاد گزینه دسته‌بندی: {name}", created_by_user_id=current_user.id,
    ))
    return RedirectResponse(url="/administration/category-options", status_code=303)


@router.get("/category-options/{co_id}/edit", response_class=HTMLResponse)
async def admin_category_option_edit(
    request: Request,
    co_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    co = await db.get(CategoryOption, uuid.UUID(co_id))
    if co is None or co.is_removed:
        raise HTTPException(status_code=404, detail="Category option not found")
    return templates.TemplateResponse("admin/category_option_form.html", {
        "request": request, "current_user": current_user, "category_option": co,
    })


@router.post("/category-options/{co_id}/edit", response_class=HTMLResponse)
async def admin_category_option_edit_submit(
    request: Request,
    co_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    co = await db.get(CategoryOption, uuid.UUID(co_id))
    if co is None or co.is_removed:
        raise HTTPException(status_code=404, detail="Category option not found")

    form = await request.form()
    name = (form.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="نام الزامی است")
    co.name = name
    await db.flush()

    db.add(Log(
        record_id=co.id, table_name="category_options",
        description=f"ویرایش گزینه دسته‌بندی: {co.name}", created_by_user_id=current_user.id,
    ))
    return RedirectResponse(url="/administration/category-options", status_code=303)


@router.get("/category-options/{co_id}", response_class=HTMLResponse)
async def admin_category_option_detail(
    request: Request,
    co_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    co = await db.get(CategoryOption, uuid.UUID(co_id))
    if co is None or co.is_removed:
        raise HTTPException(status_code=404, detail="Category option not found")
    return templates.TemplateResponse("admin/category_option_detail.html", {
        "request": request, "current_user": current_user, "category_option": co,
    })


@router.post("/category-options/{co_id}/delete", response_class=HTMLResponse)
async def admin_category_option_delete(
    request: Request,
    co_id: str,
    current_user: User = Depends(require_any_role("Admin", "Product Manager")),
    db: AsyncSession = Depends(get_db),
):
    co = await db.get(CategoryOption, uuid.UUID(co_id))
    if co is None or co.is_removed:
        raise HTTPException(status_code=404, detail="Category option not found")
    name = co.name or ""
    co.is_removed = True
    await db.flush()
    db.add(Log(
        record_id=co.id, table_name="category_options",
        description=f"حذف گزینه دسته‌بندی: {name}", created_by_user_id=current_user.id,
    ))
    return RedirectResponse(url="/administration/category-options", status_code=303)


def _to_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _checkbox_bool(form, key):
    return form.get(key) == "on"


# ── Role Claims ──

@router.get("/role-claims", response_class=HTMLResponse)
async def admin_role_claims(
    request: Request,
    page: int = Query(1),
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    items, total = await identity_service.get_role_claims_with_relations(db, page, 50)
    return templates.TemplateResponse("admin/role_claims.html", {
        "request": request, "current_user": current_user,
        "items": items, "total": total, "page": page, "total_pages": (total + 49) // 50,
    })


@router.get("/role-claims/new", response_class=HTMLResponse)
async def admin_role_claim_create(
    request: Request,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    roles = (await db.execute(select(Role).where(Role.is_removed == False))).scalars().all()
    from app.models.enums import OperationType
    return templates.TemplateResponse("admin/role_claim_form.html", {
        "request": request, "current_user": current_user,
        "rc": None, "roles": roles, "operation_types": list(OperationType),
    })


@router.post("/role-claims/new", response_class=HTMLResponse)
async def admin_role_claim_create_submit(
    request: Request,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    roles = (await db.execute(select(Role).where(Role.is_removed == False))).scalars().all()
    from app.models.enums import OperationType
    try:
        rc = await identity_service.create_role_claim(db, dict(form), current_user.id)
        return RedirectResponse(url="/administration/role-claims", status_code=303)
    except ValueError as e:
        return templates.TemplateResponse("admin/role_claim_form.html", {
            "request": request, "current_user": current_user,
            "rc": None, "roles": roles, "operation_types": list(OperationType),
            "error": str(e), "form_data": dict(form),
        })


@router.get("/role-claims/{claim_id}/edit", response_class=HTMLResponse)
async def admin_role_claim_edit(
    request: Request,
    claim_id: str,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    rc = await identity_service.get_role_claim_by_id(db, uuid.UUID(claim_id))
    if not rc:
        raise HTTPException(status_code=404, detail="Role claim not found")
    roles = (await db.execute(select(Role).where(Role.is_removed == False))).scalars().all()
    from app.models.enums import OperationType
    return templates.TemplateResponse("admin/role_claim_form.html", {
        "request": request, "current_user": current_user,
        "rc": rc, "roles": roles, "operation_types": list(OperationType),
    })


@router.post("/role-claims/{claim_id}/edit", response_class=HTMLResponse)
async def admin_role_claim_edit_submit(
    request: Request,
    claim_id: str,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    rc = await identity_service.get_role_claim_by_id(db, uuid.UUID(claim_id))
    if not rc:
        raise HTTPException(status_code=404, detail="Role claim not found")
    form = await request.form()
    roles = (await db.execute(select(Role).where(Role.is_removed == False))).scalars().all()
    from app.models.enums import OperationType
    try:
        await identity_service.update_role_claim(db, rc, dict(form), current_user.id)
        return RedirectResponse(url="/administration/role-claims", status_code=303)
    except ValueError as e:
        return templates.TemplateResponse("admin/role_claim_form.html", {
            "request": request, "current_user": current_user,
            "rc": rc, "roles": roles, "operation_types": list(OperationType),
            "error": str(e), "form_data": dict(form),
        })


@router.get("/role-claims/{claim_id}", response_class=HTMLResponse)
async def admin_role_claim_detail(
    request: Request,
    claim_id: str,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    rc = await identity_service.get_role_claim_by_id(db, uuid.UUID(claim_id))
    if not rc:
        raise HTTPException(status_code=404, detail="Role claim not found")
    return templates.TemplateResponse("admin/role_claim_detail.html", {
        "request": request, "current_user": current_user, "rc": rc,
    })


@router.post("/role-claims/{claim_id}/delete", response_class=HTMLResponse)
async def admin_role_claim_delete(
    request: Request,
    claim_id: str,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    rc = await identity_service.get_role_claim_by_id(db, uuid.UUID(claim_id))
    if not rc:
        raise HTTPException(status_code=404, detail="Role claim not found")
    await identity_service.soft_delete_role_claim(db, rc, current_user.id)
    return RedirectResponse(url="/administration/role-claims", status_code=303)


# ── User Roles ──

@router.get("/user-roles", response_class=HTMLResponse)
async def admin_user_roles(
    request: Request,
    page: int = Query(1),
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    items, total = await identity_service.get_user_roles_with_relations(db, page, 50)
    return templates.TemplateResponse("admin/user_roles.html", {
        "request": request, "current_user": current_user,
        "items": items, "total": total, "page": page, "total_pages": (total + 49) // 50,
    })


@router.get("/user-roles/new", response_class=HTMLResponse)
async def admin_user_role_create(
    request: Request,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    users = (await db.execute(select(User).where(User.is_removed == False).order_by(User.first_name))).scalars().all()
    roles = (await db.execute(select(Role).where(Role.is_removed == False))).scalars().all()
    return templates.TemplateResponse("admin/user_role_form.html", {
        "request": request, "current_user": current_user,
        "ur": None, "users": users, "roles": roles,
    })


@router.post("/user-roles/new", response_class=HTMLResponse)
async def admin_user_role_create_submit(
    request: Request,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()
    users_list = (await db.execute(select(User).where(User.is_removed == False).order_by(User.first_name))).scalars().all()
    roles = (await db.execute(select(Role).where(Role.is_removed == False))).scalars().all()
    try:
        ur = await identity_service.create_user_role(db, dict(form), current_user.id)
        return RedirectResponse(url="/administration/user-roles", status_code=303)
    except ValueError as e:
        return templates.TemplateResponse("admin/user_role_form.html", {
            "request": request, "current_user": current_user,
            "ur": None, "users": users_list, "roles": roles,
            "error": str(e), "form_data": dict(form),
        })


@router.get("/user-roles/{ur_id}/edit", response_class=HTMLResponse)
async def admin_user_role_edit(
    request: Request,
    ur_id: str,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    ur = await identity_service.get_user_role_by_id(db, uuid.UUID(ur_id))
    if not ur:
        raise HTTPException(status_code=404, detail="User role not found")
    users_list = (await db.execute(select(User).where(User.is_removed == False).order_by(User.first_name))).scalars().all()
    roles = (await db.execute(select(Role).where(Role.is_removed == False))).scalars().all()
    return templates.TemplateResponse("admin/user_role_form.html", {
        "request": request, "current_user": current_user,
        "ur": ur, "users": users_list, "roles": roles,
    })


@router.post("/user-roles/{ur_id}/edit", response_class=HTMLResponse)
async def admin_user_role_edit_submit(
    request: Request,
    ur_id: str,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    ur = await identity_service.get_user_role_by_id(db, uuid.UUID(ur_id))
    if not ur:
        raise HTTPException(status_code=404, detail="User role not found")
    form = await request.form()
    try:
        await identity_service.update_user_role(db, ur, dict(form), current_user.id)
        return RedirectResponse(url="/administration/user-roles", status_code=303)
    except ValueError as e:
        users_list = (await db.execute(select(User).where(User.is_removed == False).order_by(User.first_name))).scalars().all()
        roles = (await db.execute(select(Role).where(Role.is_removed == False))).scalars().all()
        return templates.TemplateResponse("admin/user_role_form.html", {
            "request": request, "current_user": current_user,
            "ur": ur, "users": users_list, "roles": roles,
            "error": str(e), "form_data": dict(form),
        })


@router.get("/user-roles/{ur_id}", response_class=HTMLResponse)
async def admin_user_role_detail(
    request: Request,
    ur_id: str,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    ur = await identity_service.get_user_role_by_id(db, uuid.UUID(ur_id))
    if not ur:
        raise HTTPException(status_code=404, detail="User role not found")
    return templates.TemplateResponse("admin/user_role_detail.html", {
        "request": request, "current_user": current_user, "ur": ur,
    })


@router.post("/user-roles/{ur_id}/delete", response_class=HTMLResponse)
async def admin_user_role_delete(
    request: Request,
    ur_id: str,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    ur = await identity_service.get_user_role_by_id(db, uuid.UUID(ur_id))
    if not ur:
        raise HTTPException(status_code=404, detail="User role not found")
    await identity_service.soft_delete_user_role(db, ur, current_user.id)
    return RedirectResponse(url="/administration/user-roles", status_code=303)