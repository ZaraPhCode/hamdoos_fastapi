"""Product business logic — CRUD, search, filter, sort."""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, func, or_, and_, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.models.product import (
    Product, Category, Brand, ProductType, ProductUnit,
    Variety, ProductVariety, CategoryOption,
    Tag, ProductTag, RelatedProduct, SimilarProduct,
    PriceHistory, ProductImage, MenuDatasheet,
)
from app.models.product_features import (
    TechnicalFeature, TechnicalFeatureValue, CategoryTechnicalFeature,
    TechnicalTable, TechnicalTableProduct,
)
from app.models.invoice import SupplierProduct, Supplier
from app.models.identity import User
from app.models.customer_content import Media
from app.schemas.product import (
    ProductCreate, ProductUpdate, ProductSearchParams,
    PaginatedResponse, ProductListResponse, ProductDetailResponse,
    CategoryCreate, CategoryUpdate, CategoryResponse,
    BrandCreate, BrandResponse,
)


# ── Categories ──

async def get_category_tree(db: AsyncSession) -> list[Category]:
    stmt = (
        select(Category)
        .options(
            selectinload(Category.children)
            .selectinload(Category.children)
            .selectinload(Category.children),
        )
        .where(Category.parent_category_id.is_(None), Category.is_removed == False, Category.no_display == False)
        .order_by(Category.priority)
    )
    result = await db.execute(stmt)
    return result.unique().scalars().all()


async def get_category_by_id(db: AsyncSession, category_id: uuid.UUID) -> Optional[Category]:
    stmt = (
        select(Category)
        .options(selectinload(Category.children))
        .where(Category.id == category_id, Category.is_removed == False)
    )
    result = await db.execute(stmt)
    return result.unique().scalar_one_or_none()


async def get_category_by_en_title(db: AsyncSession, en_title: str) -> Optional[Category]:
    stmt = (
        select(Category)
        .options(selectinload(Category.children))
        .where(Category.en_title == en_title, Category.is_removed == False, Category.no_display == False)
    )
    result = await db.execute(stmt)
    return result.unique().scalar_one_or_none()


async def get_category_by_slug(db: AsyncSession, slug: str) -> Optional[Category]:
    stmt = (
        select(Category)
        .options(selectinload(Category.children))
        .where(Category.slug == slug, Category.is_removed == False, Category.no_display == False)
    )
    result = await db.execute(stmt)
    return result.unique().scalar_one_or_none()


async def create_category(db: AsyncSession, request: CategoryCreate, user_id: uuid.UUID) -> Category:
    category = Category(
        id=uuid.uuid4(),
        **request.model_dump(exclude_unset=True),
        created_by_user_id=user_id,
        insert_date=datetime.now(timezone.utc),
        update_date=datetime.now(timezone.utc),
    )
    db.add(category)
    await db.flush()
    return category


async def update_category(db: AsyncSession, category: Category, request: CategoryUpdate) -> Category:
    for key, value in request.model_dump(exclude_unset=True).items():
        setattr(category, key, value)
    category.update_date = datetime.now(timezone.utc)
    return category


async def delete_category(db: AsyncSession, category: Category) -> None:
    category.is_removed = True
    category.update_date = datetime.now(timezone.utc)


async def get_all_categories_flat(db: AsyncSession) -> list[Category]:
    stmt = (
        select(Category)
        .where(Category.is_removed == False, Category.no_display == False)
        .order_by(Category.priority)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_admin_categories(db: AsyncSession) -> list[Category]:
    """All non-removed categories ordered by title (matches .NET Categories Index), with parent + media."""
    stmt = (
        select(Category)
        .options(
            selectinload(Category.parent),
            selectinload(Category.medias),
        )
        .where(Category.is_removed == False)
        .order_by(Category.title)
    )
    result = await db.execute(stmt)
    return result.unique().scalars().all()


async def get_admin_category_tree(db: AsyncSession) -> list[Category]:
    """Full category list (no no_display filter) for the parent picker — matches .NET GetCategories.

    Returns the flat list; the route builds the tree in memory to avoid async lazy-loading.
    """
    stmt = (
        select(Category)
        .where(Category.is_removed == False)
        .order_by(Category.priority)
    )
    result = await db.execute(stmt)
    return result.unique().scalars().all()


# ── Brands ──

async def get_all_brands(db: AsyncSession) -> list[Brand]:
    stmt = (
        select(Brand)
        .where(Brand.is_removed == False)
        .order_by(Brand.name)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_brand_by_id(db: AsyncSession, brand_id: uuid.UUID) -> Optional[Brand]:
    stmt = select(Brand).where(Brand.id == brand_id, Brand.is_removed == False)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create_brand(db: AsyncSession, request: BrandCreate, user_id: uuid.UUID) -> Brand:
    brand = Brand(
        id=uuid.uuid4(),
        name=request.name,
        created_by_user_id=user_id,
        insert_date=datetime.now(timezone.utc),
        update_date=datetime.now(timezone.utc),
    )
    db.add(brand)
    await db.flush()
    return brand


# ── Products ──

def _normalize_media_url(url):
    """Convert a stored path like \\Media\\laser\\file.jpg to /media/laser/file.jpg.
    Only transforms paths that look like Media/... or \\Media\\...;
    leaves absolute URLs, full URLs, and None unchanged."""
    if not url:
        return url
    # Skip absolute URLs and full http/https URLs
    if url.startswith(("http://", "https://", "//", "/static/", "/media/")):
        return url
    normalized = url.replace("\\", "/").lstrip("/")
    if normalized.lower().startswith("media/"):
        normalized = normalized[len("media/"):]
    return "/media/" + normalized


def _build_product_list_response(product: Product) -> ProductListResponse:
    return ProductListResponse(
        id=product.id,
        int_id=product.int_id if hasattr(product, 'int_id') and product.int_id else 0,
        name=product.name,
        en_name=product.en_name,
        slug=product.slug,
        part_number=product.part_number,
        model=product.model,
        short_description=product.short_description,
        price=float(product.price) if product.price else None,
        price_after_discount=float(product.price_after_discount) if product.price_after_discount else None,
        discount_amount=float(product.discount_amount) if product.discount_amount else None,
        discount_percentage=float(product.discount_percentage) if product.discount_percentage else None,
        stock_quantity=product.stock_quantity,
        rate=float(product.rate) if product.rate else 0,
        views=product.views,
        sale=product.sale,
        is_new=product.is_new,
        is_special=product.is_special,
        on_sale=product.on_sale,
        status=product.status,
        category_id=product.category_id,
        brand_id=product.brand_id,
        number_of_variations=product.number_of_variations or 0,
        minimum_purchase=product.minimum_purchase or 1,
        medium_image_url=_normalize_media_url(product.medium_image_url),
        large_image_url=_normalize_media_url(product.large_image_url),
        feature_image_url=_normalize_media_url(product.feature_image_url),
        insert_date=product.insert_date,
        update_date=product.update_date,
        category_title=product.category.title if product.category else None,
        brand_name=product.brand.name if product.brand else None,
        created_by_user_name=product.created_by_user.full_name if product.created_by_user else None,
    )


async def search_products(db: AsyncSession, params: ProductSearchParams) -> tuple[list[Product], int]:
    stmt = (
        select(Product)
        .options(
            selectinload(Product.category),
            selectinload(Product.brand),
            selectinload(Product.created_by_user),
        )
        .where(Product.is_removed == False, Product.no_display == False)
    )

    count_stmt = select(func.count(Product.id)).where(Product.is_removed == False, Product.no_display == False)

    if params.query:
        like = f"%{params.query}%"
        filter_cond = or_(
            Product.name.ilike(like),
            Product.en_name.ilike(like),
            Product.part_number.ilike(like),
            Product.model.ilike(like),
            Product.short_description.ilike(like),
            Product.keywords.ilike(like),
        )
        stmt = stmt.where(filter_cond)
        count_stmt = count_stmt.where(filter_cond)

    if params.category_id:
        # Include subcategories
        cat_ids = await _get_category_and_child_ids(db, params.category_id)
        stmt = stmt.where(Product.category_id.in_(cat_ids))
        count_stmt = count_stmt.where(Product.category_id.in_(cat_ids))

    if params.brand_id:
        stmt = stmt.where(Product.brand_id == params.brand_id)
        count_stmt = count_stmt.where(Product.brand_id == params.brand_id)

    if params.min_price is not None:
        stmt = stmt.where(Product.price >= params.min_price)
        count_stmt = count_stmt.where(Product.price >= params.min_price)

    if params.max_price is not None:
        stmt = stmt.where(Product.price <= params.max_price)
        count_stmt = count_stmt.where(Product.price <= params.max_price)

    if params.on_sale is not None:
        stmt = stmt.where(Product.on_sale == params.on_sale)
        count_stmt = count_stmt.where(Product.on_sale == params.on_sale)

    if params.is_new is not None:
        stmt = stmt.where(Product.is_new == params.is_new)
        count_stmt = count_stmt.where(Product.is_new == params.is_new)

    if params.is_special is not None:
        stmt = stmt.where(Product.is_special == params.is_special)
        count_stmt = count_stmt.where(Product.is_special == params.is_special)

    if params.status:
        stmt = stmt.where(Product.status == params.status)
        count_stmt = count_stmt.where(Product.status == params.status)

    # Sorting
    sort_col = {
        "price": Product.price,
        "name": Product.name,
        "rate": Product.rate,
        "views": Product.views,
        "sale": Product.sale,
        "insert_date": Product.insert_date,
        "update_date": Product.update_date,
    }.get(params.sort_by or "insert_date", Product.insert_date)

    if params.sort_desc:
        stmt = stmt.order_by(sort_col.desc())
    else:
        stmt = stmt.order_by(sort_col.asc())

    # Count
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    # Pagination
    offset = (params.page - 1) * params.page_size
    stmt = stmt.offset(offset).limit(params.page_size)

    result = await db.execute(stmt)
    products = result.unique().scalars().all()

    return list(products), total


async def _get_category_and_child_ids(db: AsyncSession, category_id: uuid.UUID) -> list[uuid.UUID]:
    """Get category ID and all its children IDs recursively."""
    ids = [category_id]
    stmt = select(Category.id).where(Category.parent_category_id == category_id, Category.is_removed == False)
    result = await db.execute(stmt)
    child_ids = result.scalars().all()
    for cid in child_ids:
        ids.extend(await _get_category_and_child_ids(db, cid))
    return ids


async def search_products_net(
    db: AsyncSession,
    category_id: uuid.UUID | None = None,
    branch_ids: list[uuid.UUID] | None = None,
    brand_ids: list[uuid.UUID] | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    order: str = "AlphabetAsc",
    query: str | None = None,
    page: int = 1,
    page_size: int = 28,
    tags: list[str] | None = None,
) -> tuple[list[Product], int]:
    """Mirror .NET CategoryController.Index product search.

    - category_id → products in that category + all descendants
    - branch_ids  → restrict to the given (child) category ids only
    - order       → ProductOrder_t names: Sale, Id, AlphabetAsc, AlphabetDesc, Cheapest, Expensive
      (in-stock products always sort first, like the .NET comparers)
    """
    stmt = (
        select(Product)
        .options(
            selectinload(Product.category),
            selectinload(Product.brand),
            selectinload(Product.product_images),
        )
        .where(Product.is_removed == False, Product.no_display == False)
    )
    count_stmt = select(func.count(Product.id)).where(Product.is_removed == False, Product.no_display == False)

    if branch_ids:
        stmt = stmt.where(Product.category_id.in_(branch_ids))
        count_stmt = count_stmt.where(Product.category_id.in_(branch_ids))
    elif category_id:
        cat_ids = await _get_category_and_child_ids(db, category_id)
        stmt = stmt.where(Product.category_id.in_(cat_ids))
        count_stmt = count_stmt.where(Product.category_id.in_(cat_ids))

    if brand_ids:
        stmt = stmt.where(Product.brand_id.in_(brand_ids))
        count_stmt = count_stmt.where(Product.brand_id.in_(brand_ids))

    if min_price is not None:
        stmt = stmt.where(Product.price >= min_price)
        count_stmt = count_stmt.where(Product.price >= min_price)

    if max_price is not None:
        stmt = stmt.where(Product.price <= max_price)
        count_stmt = count_stmt.where(Product.price <= max_price)

    if query:
        like = f"%{query}%"
        filter_cond = or_(
            Product.name.ilike(like),
            Product.en_name.ilike(like),
            Product.part_number.ilike(like),
            Product.model.ilike(like),
            Product.short_description.ilike(like),
            Product.keywords.ilike(like),
        )
        stmt = stmt.where(filter_cond)
        count_stmt = count_stmt.where(filter_cond)

    if tags:
        tag_conds = []
        for tag in tags:
            if tag == "new":
                tag_conds.append(Product.is_new == True)
            elif tag == "special":
                tag_conds.append(Product.is_special == True)
            elif tag == "restocked":
                tag_conds.append(Product.restocked == True)
            elif tag == "suggested":
                tag_conds.append(Product.suggested == True)
        if tag_conds:
            tag_cond = tag_conds[0] if len(tag_conds) == 1 else or_(*tag_conds)
            stmt = stmt.where(tag_cond)
            count_stmt = count_stmt.where(tag_cond)

    # .NET comparers: in-stock first, then the chosen key
    in_stock = (Product.stock_quantity > 0).desc()
    sort_key = {
        "Sale": Product.sale.desc(),
        "Id": Product.id.asc(),
        "AlphabetAsc": Product.name.asc(),
        "AlphabetDesc": Product.name.desc(),
        "Cheapest": Product.price_after_discount.asc(),
        "Expensive": Product.price_after_discount.desc(),
    }.get(order, Product.name.asc())
    stmt = stmt.order_by(in_stock, sort_key)

    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)
    result = await db.execute(stmt)
    products = result.unique().scalars().all()

    return list(products), total


async def get_brand_facets(
    db: AsyncSession,
    category_id: uuid.UUID | None = None,
    branch_ids: list[uuid.UUID] | None = None,
) -> list[dict]:
    """Group products by brand (id, name, count) for the facet sidebar, mirroring .NET ViewData['Brands']."""
    stmt = (
        select(Product.brand_id, Brand.name, func.count(Product.id))
        .join(Brand, Product.brand_id == Brand.id)
        .where(Product.is_removed == False, Product.no_display == False, Product.brand_id.isnot(None))
    )
    if branch_ids:
        stmt = stmt.where(Product.category_id.in_(branch_ids))
    elif category_id:
        cat_ids = await _get_category_and_child_ids(db, category_id)
        stmt = stmt.where(Product.category_id.in_(cat_ids))
    stmt = stmt.group_by(Product.brand_id, Brand.name).order_by(Brand.name)
    result = await db.execute(stmt)
    return [
        {"id": str(bid), "name": name, "count": count}
        for bid, name, count in result.all()
    ]


async def get_category_price_range(
    db: AsyncSession,
    category_id: uuid.UUID | None = None,
    branch_ids: list[uuid.UUID] | None = None,
) -> tuple[float, float]:
    """Min/max product price for the facet slider, mirroring .NET maxSlider."""
    stmt = select(func.max(Product.price)).where(Product.is_removed == False, Product.no_display == False)
    if branch_ids:
        stmt = stmt.where(Product.category_id.in_(branch_ids))
    elif category_id:
        cat_ids = await _get_category_and_child_ids(db, category_id)
        stmt = stmt.where(Product.category_id.in_(cat_ids))
    result = await db.execute(stmt)
    return 0.0, float(result.scalar() or 0)



async def get_product_by_id(db: AsyncSession, product_id: uuid.UUID) -> Optional[Product]:
    stmt = (
        select(Product)
        .options(
            selectinload(Product.category),
            selectinload(Product.brand),
            selectinload(Product.product_type),
            selectinload(Product.product_unit),
            selectinload(Product.currency),
            selectinload(Product.product_images),
            selectinload(Product.menu_datasheets),
            selectinload(Product.varieties).selectinload(Variety.product_varieties).selectinload(ProductVariety.category_option),
            selectinload(Product.related_products).selectinload(RelatedProduct.relate_product),
            selectinload(Product.similar_products).selectinload(SimilarProduct.similar),
            selectinload(Product.technical_table_products)
            .selectinload(TechnicalTableProduct.technical_feature_values)
            .selectinload(TechnicalFeatureValue.technical_feature),
            selectinload(Product.technical_table_products)
            .selectinload(TechnicalTableProduct.technical_table),
            selectinload(Product.technical_table_products)
            .selectinload(TechnicalTableProduct.technical_feature_values)
            .selectinload(TechnicalFeatureValue.technical_feature_enum),
            selectinload(Product.technical_table_products)
            .selectinload(TechnicalTableProduct.technical_feature_values)
            .selectinload(TechnicalFeatureValue.technical_feature_enum1),
        )
        .where(Product.id == product_id, Product.is_removed == False)
    )
    result = await db.execute(stmt)
    return result.unique().scalar_one_or_none()


async def get_product_by_slug(db: AsyncSession, slug: str) -> Optional[Product]:
    stmt = (
        select(Product)
        .options(
            selectinload(Product.category),
            selectinload(Product.brand),
            selectinload(Product.product_images),
            selectinload(Product.menu_datasheets),
            selectinload(Product.varieties).selectinload(Variety.product_varieties).selectinload(ProductVariety.category_option),
            selectinload(Product.related_products).selectinload(RelatedProduct.relate_product),
            selectinload(Product.similar_products).selectinload(SimilarProduct.similar),
            selectinload(Product.technical_table_products)
            .selectinload(TechnicalTableProduct.technical_feature_values)
            .selectinload(TechnicalFeatureValue.technical_feature),
            selectinload(Product.technical_table_products)
            .selectinload(TechnicalTableProduct.technical_table),
            selectinload(Product.technical_table_products)
            .selectinload(TechnicalTableProduct.technical_feature_values)
            .selectinload(TechnicalFeatureValue.technical_feature_enum),
            selectinload(Product.technical_table_products)
            .selectinload(TechnicalTableProduct.technical_feature_values)
            .selectinload(TechnicalFeatureValue.technical_feature_enum1),
        )
        .where(Product.slug == slug, Product.is_removed == False, Product.no_display == False)
    )
    result = await db.execute(stmt)
    return result.unique().scalar_one_or_none()


async def get_product_full_details(db: AsyncSession, product_id: uuid.UUID) -> Optional[Product]:
    """Full product graph for the admin details page.

    Loads category, brand, type/unit/currency, images, datasheets,
    supplier products (with supplier), and technical table products with
    feature values + enums + technical table.
    """
    stmt = (
        select(Product)
        .options(
            selectinload(Product.category),
            selectinload(Product.brand),
            selectinload(Product.product_type),
            selectinload(Product.product_unit),
            selectinload(Product.currency),
            selectinload(Product.product_images),
            selectinload(Product.menu_datasheets),
            selectinload(Product.supplier_products).selectinload(SupplierProduct.supplier),
            selectinload(Product.related_products).selectinload(RelatedProduct.relate_product),
            selectinload(Product.similar_products).selectinload(SimilarProduct.similar),
            selectinload(Product.technical_table_products)
            .selectinload(TechnicalTableProduct.technical_table),
            selectinload(Product.technical_table_products)
            .selectinload(TechnicalTableProduct.technical_feature_values)
            .selectinload(TechnicalFeatureValue.technical_feature),
            selectinload(Product.technical_table_products)
            .selectinload(TechnicalTableProduct.technical_feature_values)
            .selectinload(TechnicalFeatureValue.technical_feature_enum),
            selectinload(Product.technical_table_products)
            .selectinload(TechnicalTableProduct.technical_feature_values)
            .selectinload(TechnicalFeatureValue.technical_feature_enum1),
        )
        .where(Product.id == product_id, Product.is_removed == False)
    )
    result = await db.execute(stmt)
    return result.unique().scalar_one_or_none()


async def create_product(db: AsyncSession, request: ProductCreate, user_id: uuid.UUID) -> Product:
    """Create a product with DB-compatible defaults.

    The ``Products`` table marks most columns NOT NULL (matching the .NET
    schema), while the API/form schemas keep them optional — fill every NOT
    NULL column here so a valid create never fails with a NULL/500 error.
    No database values are modified; only the new row is constructed.
    """
    from app.utils.common_works import generate_slug

    data = request.model_dump(exclude_unset=True)

    if data.get("category_id") is None:
        raise ValueError("Category is required")

    max_int_id = (await db.execute(select(func.max(Product.int_id)))).scalar() or 0
    data.setdefault("int_id", max_int_id + 1)

    name = (data.get("name") or "").strip()
    if not name:
        raise ValueError("Product name is required")
    if not data.get("slug"):
        data["slug"] = generate_slug(name)
    if not data.get("part_number"):
        data["part_number"] = f"AUTO-{data['int_id']}"

    text_fields = (
        "en_name", "en_slug", "model", "short_name", "introduction",
        "short_description", "keywords", "meta_description",
        "concatenated", "en_concatenated", "tax_unique_id",
    )
    for field in text_fields:
        if data.get(field) is None:
            data[field] = ""

    numeric_fields = (
        "price", "price_after_discount", "discount_amount",
        "discount_percentage", "currency_price", "profit_rate",
        "taxes_and_duties", "total_amount_plus_taxes", "vat_rate",
    )
    for field in numeric_fields:
        if data.get(field) is None:
            data[field] = 0

    int_fields = (
        "stock_quantity", "minimum_purchase", "max_number_of_purchases",
        "order_point", "points_from_purchases", "views", "rate", "sale",
        "delivery_day", "number_of_variations",
    )
    for field in int_fields:
        if data.get(field) is None:
            data[field] = 1 if field == "minimum_purchase" else 0

    now = datetime.now(timezone.utc)
    if data.get("release_date") is None:
        data["release_date"] = now
    if data.get("purchase_date") is None:
        data["purchase_date"] = now
    if not data.get("status"):
        data["status"] = "OutOfStock"
    if data.get("type") is None:
        data["type"] = 0
    if data.get("default_variation") is None:
        data["default_variation"] = False

    product = Product(
        id=uuid.uuid4(),
        **data,
        created_by_user_id=user_id,
        insert_date=now,
        update_date=now,
    )
    db.add(product)
    await db.flush()
    return product


# Columns that genuinely accept NULL on update — every other Product column
# is NOT NULL (matches the .NET schema), so None values are skipped.
_PRODUCT_NULLABLE_UPDATE_FIELDS = {
    "max_price",
    "short_name",
    "brand_id",
    "product_type_id",
    "product_unit_id",
    "currency_id",
    "taobao_choice_id",
}


async def update_product(db: AsyncSession, product: Product, request: ProductUpdate) -> Product:
    # Never write NULL into NOT NULL columns (explicit JSON/form nulls are
    # ignored, except for genuinely nullable columns) — prevents DB 500s.
    for key, value in request.model_dump(exclude_unset=True).items():
        if value is None and key not in _PRODUCT_NULLABLE_UPDATE_FIELDS:
            continue
        setattr(product, key, value)
    product.update_date = datetime.now(timezone.utc)
    return product


async def delete_product(db: AsyncSession, product: Product) -> None:
    product.is_removed = True
    product.update_date = datetime.now(timezone.utc)


async def increment_product_view(db: AsyncSession, product: Product) -> None:
    product.views = (product.views or 0) + 1
    product.update_date = datetime.now(timezone.utc)


async def get_related_products(db: AsyncSession, product: Product, limit: int = 6) -> list[Product]:
    related_ids = [rp.relate_product_id for rp in product.related_products if not rp.is_removed]
    if not related_ids:
        # Fallback: same category
        stmt = (
            select(Product)
            .options(selectinload(Product.category), selectinload(Product.brand))
            .where(
                Product.category_id == product.category_id,
                Product.id != product.id,
                Product.is_removed == False,
                Product.no_display == False,
            )
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.unique().scalars().all())

    stmt = (
        select(Product)
        .options(selectinload(Product.category), selectinload(Product.brand))
        .where(Product.id.in_(related_ids), Product.is_removed == False, Product.no_display == False)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.unique().scalars().all())


async def get_similar_products(db: AsyncSession, product: Product, limit: int = 6) -> list[Product]:
    similar_ids = [sp.similar_product_id for sp in product.similar_products if not sp.is_removed]
    if not similar_ids:
        return []
    stmt = (
        select(Product)
        .options(selectinload(Product.category), selectinload(Product.brand))
        .where(Product.id.in_(similar_ids), Product.is_removed == False, Product.no_display == False)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.unique().scalars().all())


async def get_products_by_category(
    db: AsyncSession, category_id: uuid.UUID, page: int = 1, page_size: int = 20
) -> tuple[list[Product], int]:
    cat_ids = await _get_category_and_child_ids(db, category_id)
    stmt = (
        select(Product)
        .options(selectinload(Product.category), selectinload(Product.brand))
        .where(
            Product.category_id.in_(cat_ids),
            Product.is_removed == False,
            Product.no_display == False,
        )
        .order_by(Product.insert_date.desc())
    )
    count_stmt = select(func.count(Product.id)).where(
        Product.category_id.in_(cat_ids),
        Product.is_removed == False,
        Product.no_display == False,
    )
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)
    result = await db.execute(stmt)
    products = result.unique().scalars().all()

    return list(products), total


async def get_featured_products(db: AsyncSession, limit: int = 10) -> list[Product]:
    stmt = (
        select(Product)
        .options(selectinload(Product.category), selectinload(Product.brand))
        .where(
            Product.is_special == True,
            Product.is_removed == False,
            Product.no_display == False,
        )
        .order_by(Product.insert_date.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.unique().scalars().all())


async def get_new_products(db: AsyncSession, limit: Optional[int] = None) -> list[Product]:
    stmt = (
        select(Product)
        .options(selectinload(Product.category), selectinload(Product.brand))
        .where(
            Product.is_new == True,
            Product.is_removed == False,
            Product.no_display == False,
        )
        .order_by(Product.insert_date.desc())
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    result = await db.execute(stmt)
    return list(result.unique().scalars().all())


async def get_special_products(db: AsyncSession, limit: Optional[int] = None) -> list[Product]:
    """Specials for the homepage tabs — mirrors .NET IsSpecial && stock > 0."""
    stmt = (
        select(Product)
        .options(selectinload(Product.category), selectinload(Product.brand), selectinload(Product.product_images))
        .where(
            Product.is_special == True,
            Product.stock_quantity > 0,
            Product.is_removed == False,
            Product.no_display == False,
        )
        .order_by(Product.insert_date.desc())
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    result = await db.execute(stmt)
    return list(result.unique().scalars().all())


async def get_restocked_products(db: AsyncSession, limit: Optional[int] = None) -> list[Product]:
    """Restocked products for the homepage tabs — mirrors .NET Restocked && stock > 0."""
    stmt = (
        select(Product)
        .options(selectinload(Product.category), selectinload(Product.brand), selectinload(Product.product_images))
        .where(
            Product.restocked == True,
            Product.stock_quantity > 0,
            Product.is_removed == False,
            Product.no_display == False,
        )
        .order_by(Product.insert_date.desc())
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    result = await db.execute(stmt)
    return list(result.unique().scalars().all())


async def get_suggested_products(db: AsyncSession, limit: Optional[int] = None) -> list[Product]:
    """Suggested products for the homepage — mirrors .NET Suggested && stock > 0."""
    stmt = (
        select(Product)
        .options(selectinload(Product.category), selectinload(Product.brand), selectinload(Product.product_images))
        .where(
            Product.suggested == True,
            Product.stock_quantity > 0,
            Product.is_removed == False,
            Product.no_display == False,
        )
        .order_by(Product.insert_date.desc())
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    result = await db.execute(stmt)
    return list(result.unique().scalars().all())


async def get_home_products_by_category(db: AsyncSession, category_id: uuid.UUID) -> list[Product]:
    """Products in a category + all its children with stock — mirrors .NET GetProductByCategoryIdHomeAsync."""
    cat_ids = await _get_category_and_child_ids(db, category_id)
    stmt = (
        select(Product)
        .options(selectinload(Product.category), selectinload(Product.brand), selectinload(Product.product_images))
        .where(
            Product.category_id.in_(cat_ids),
            Product.stock_quantity > 0,
            Product.is_removed == False,
            Product.no_display == False,
        )
        .order_by(Product.insert_date.desc())
    )
    result = await db.execute(stmt)
    return list(result.unique().scalars().all())


async def get_best_selling_products(db: AsyncSession, limit: int = 10) -> list[Product]:
    stmt = (
        select(Product)
        .options(selectinload(Product.category), selectinload(Product.brand))
        .where(
            Product.is_removed == False,
            Product.no_display == False,
        )
        .order_by(Product.sale.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.unique().scalars().all())


# ── Product duplication (تکثیر کردن) ──
# Mirrors ASHA.Shop.Presentation/Areas/Administration/Controllers/Products/
# ProductsController.Duplicate (GET + POST) in the original .NET app:
# the admin edits Name/EnName/PartNumber/Slug/EnSlug/Keywords for the copy,
# every other scalar is cloned from the source product, then supplier links,
# technical tables + feature values, images, similar/related links and
# datasheets are deep-copied (media URLs rewritten to the new EnSlug folder
# and the image files copied on disk).

_DUPLICATE_REQUIRED_FIELDS = ("name", "en_name", "part_number", "slug", "en_slug")


def rewrite_media_url(old_url: Optional[str], new_slug: str) -> Optional[str]:
    """Rewrite a media URL to the new slug folder — mirrors .NET ProductImage.Duplicate.

    .NET: FileURL.Substring(0, secondIndex + 1) + newEnSlug + FileURL.Substring(firstIndex)
    where firstIndex = last '/' and secondIndex = second-last '/'.
    """
    if not old_url or not new_slug:
        return old_url
    normalized = old_url.replace("\\", "/")
    first = normalized.rfind("/")
    if first <= 0:
        return old_url
    second = normalized.rfind("/", 0, first)
    if second < 0:
        return old_url
    return normalized[: second + 1] + new_slug + normalized[first:]


def _media_relative_path(url: Optional[str]) -> Optional[str]:
    """Convert a stored media URL to a path relative to the media root."""
    if not url:
        return None
    normalized = url.replace("\\", "/").strip()
    if normalized.startswith(("http://", "https://", "//")):
        return None
    while normalized.startswith("~/"):
        normalized = normalized[2:]
    normalized = normalized.lstrip("/")
    lowered = normalized.lower()
    if lowered.startswith("media/"):
        normalized = normalized[len("media/"):]
    if not normalized:
        return None
    return normalized


def copy_product_media_files(source_urls: list[str], new_slug: str) -> bool:
    """Copy the source product's media folder to the new slug folder.

    Mirrors .NET ProductsController.CopyFiles: the folder holding the source
    images (e.g. <root>/.../<oldSlug>/) is copied to <root>/.../<newSlug>/.
    Returns True only when the destination folder was verified to contain
    files afterwards — callers must keep the ORIGINAL URLs when this returns
    False (e.g. files served remotely via MEDIA_BASE_URL), otherwise the new
    rows would point at a folder that exists nowhere and render as broken
    images. Checks /app/media first (production volume mounted from the old
    .NET wwwroot/Media), then the bundled app/static/Media copy.
    """
    import os
    import shutil

    if not source_urls or not new_slug:
        return False
    rels = [_media_relative_path(u) for u in source_urls]
    rels = [r for r in rels if r and "/" in r]
    if not rels:
        return False
    src_rel_dir = os.path.dirname(rels[0])
    parent_rel = os.path.dirname(src_rel_dir)
    dest_rel_dir = f"{parent_rel}/{new_slug}" if parent_rel else new_slug
    for root in ("/app/media", "app/static/Media"):
        src_abs = os.path.join(root, src_rel_dir)
        dest_abs = os.path.join(root, dest_rel_dir)
        if os.path.abspath(src_abs) == os.path.abspath(dest_abs):
            continue
        try:
            if os.path.isdir(src_abs):
                shutil.copytree(src_abs, dest_abs, dirs_exist_ok=True)
        except Exception:
            continue
    for root in ("/app/media", "app/static/Media"):
        try:
            if os.path.isdir(os.path.join(root, dest_rel_dir)) and os.listdir(os.path.join(root, dest_rel_dir)):
                return True
        except Exception:
            continue
    return False


async def duplicate_product(
    db: AsyncSession,
    source_id: uuid.UUID,
    *,
    name: str,
    en_name: str,
    part_number: str,
    slug: str,
    en_slug: str,
    keywords: str = "",
    user_id: Optional[uuid.UUID] = None,
) -> Product:
    """Deep-copy a product and its sub-resources — mirrors .NET Duplicate POST.

    Raises ValueError with a Persian message when the new Name/EnName/
    PartNumber collides with an existing product (same checks as .NET).
    """
    from app.models.common import Log

    source = await get_product_full_details(db, source_id)
    if source is None:
        raise ValueError("محصول یافت نشد")

    name = (name or "").strip()
    en_name = (en_name or "").strip()
    part_number = (part_number or "").strip()
    slug = (slug or "").strip()
    en_slug = (en_slug or "").strip()
    keywords = (keywords or "").strip()
    if not name or not en_name or not part_number or not slug or not en_slug:
        raise ValueError("نام، نام انگلیسی، شماره قطعه، اسلاگ و اسلاگ انگلیسی الزامی هستند")

    for field, value, msg in (
        ("part_number", part_number, "شماره قطعه تکراری است"),
        ("name", name, "نام تکراری است"),
        ("en_name", en_name, "نام انگلیسی تکراری است"),
    ):
        exists = await db.execute(
            select(Product.id).where(
                getattr(Product, field) == value, Product.is_removed == False
            )
        )
        if exists.scalar_one_or_none() is not None:
            raise ValueError(msg)

    max_int_id = (await db.execute(select(func.max(Product.int_id)))).scalar() or 0
    now = datetime.now(timezone.utc)
    new_id = uuid.uuid4()

    duplicated = Product(
        id=new_id,
        int_id=max_int_id + 1,
        # Six fields edited by the admin on the Duplicate form:
        name=name,
        en_name=en_name,
        part_number=part_number,
        slug=slug,
        en_slug=en_slug,
        keywords=keywords or source.keywords or "",
        # Everything else cloned from the source (mirrors .NET Product.Duplicate,
        # plus carry-over of remaining NOT NULL columns so the row stays valid):
        short_name=source.short_name,
        model=source.model or "",
        introduction=source.introduction or "",
        short_description=source.short_description or "",
        meta_description=source.meta_description or "",
        concatenated=source.concatenated or "",
        en_concatenated=source.en_concatenated or "",
        price=source.price or 0,
        max_price=source.max_price,
        price_after_discount=source.price_after_discount or 0,
        discount_amount=source.discount_amount or 0,
        discount_percentage=source.discount_percentage or 0,
        currency_price=source.currency_price or 0,
        profit_rate=source.profit_rate or 0,
        taxes_and_duties=source.taxes_and_duties or 0,
        total_amount_plus_taxes=source.total_amount_plus_taxes or 0,
        vat_rate=source.vat_rate or 0,
        stock_quantity=source.stock_quantity or 0,
        stock_supply_date=source.stock_supply_date,
        minimum_purchase=source.minimum_purchase or 1,
        max_number_of_purchases=source.max_number_of_purchases or 0,
        order_point=source.order_point or 0,
        points_from_purchases=source.points_from_purchases or 0,
        views=0,
        rate=source.rate or 0,
        sale=0,
        release_date=source.release_date or now,
        purchase_date=source.purchase_date or now,
        status=source.status,
        type=source.type,
        default_variation=source.default_variation,
        taobao_choice_id=source.taobao_choice_id,
        delivery_day=source.delivery_day or 0,
        number_of_variations=0,
        restocked=source.restocked,
        is_bundle=source.is_bundle,
        is_calibrated=source.is_calibrated,
        is_new=source.is_new,
        is_special=source.is_special,
        on_sale=source.on_sale,
        suggested=source.suggested,
        no_display=source.no_display,
        automatic_price_calculation=source.automatic_price_calculation,
        tax_unique_id=source.tax_unique_id or "",
        image_id=None,
        image_description=source.image_description,
        image_title=source.image_title,
        medium_image_url=source.medium_image_url,
        medium_image_large_url=source.medium_image_large_url,
        large_image_url=source.large_image_url,
        feature_image_url=source.feature_image_url,
        category_id=source.category_id,
        brand_id=source.brand_id,
        product_type_id=source.product_type_id,
        product_unit_id=source.product_unit_id,
        currency_id=source.currency_id,
        created_by_user_id=user_id,
        insert_date=now,
        update_date=now,
    )
    db.add(duplicated)
    await db.flush()
    db.add(Log(
        record_id=duplicated.id, table_name="products",
        description=f"تکثیر محصول {source.name} به {duplicated.name}",
        created_by_user_id=user_id, type="Create",
    ))

    # Copy the media folders FIRST and rewrite URLs only when the copy is
    # verified. If the files are served remotely (no local media tree), the
    # copy is impossible — keep the original working URLs so the عکس column
    # keeps rendering instead of pointing at a nonexistent folder.
    _src_images = [
        i for i in (source.product_images or [])
        if not i.is_removed and (i.medium_image_url or i.small_image_url or i.large_image_url)
    ]
    _images_copied = copy_product_media_files(
        [i.medium_image_url or i.small_image_url or i.large_image_url for i in _src_images],
        en_slug,
    ) if _src_images else False
    _src_datasheets = [
        i for i in (source.menu_datasheets or [])
        if not i.is_removed and (i.file_url or i.complete_file_url)
    ]
    _datasheets_copied = copy_product_media_files(
        [i.file_url or i.complete_file_url for i in _src_datasheets],
        en_slug,
    ) if _src_datasheets else False

    # Supplier links (mirrors CopySupplierProductsAsync).
    supplier_rows = (await db.execute(
        select(SupplierProduct).where(
            SupplierProduct.product_id == source.id,
            SupplierProduct.is_removed == False,
        )
    )).scalars().all()
    for item in supplier_rows:
        sup = SupplierProduct(
            id=uuid.uuid4(),
            supplier_id=item.supplier_id,
            product_id=new_id,
            link=item.link,
            created_by_user_id=user_id,
            insert_date=now,
            update_date=now,
        )
        db.add(sup)
        await db.flush()
        db.add(Log(
            record_id=sup.id, table_name="supplier_products",
            description=f"تکثیر تامین‌کننده محصول: {duplicated.name}",
            created_by_user_id=user_id, type="Create",
        ))

    # Technical tables + feature values.
    table_rows = (await db.execute(
        select(TechnicalTableProduct)
        .options(selectinload(TechnicalTableProduct.technical_feature_values))
        .where(
            TechnicalTableProduct.product_id == source.id,
            TechnicalTableProduct.is_removed == False,
        )
    )).scalars().all()
    for item in table_rows:
        table_product = TechnicalTableProduct(
            id=uuid.uuid4(),
            technical_table_id=item.technical_table_id,
            product_id=new_id,
            created_by_user_id=user_id,
            insert_date=now,
            update_date=now,
        )
        db.add(table_product)
        await db.flush()
        db.add(Log(
            record_id=table_product.id, table_name="technical_table_products",
            description=f"تکثیر جدول فنی محصول: {duplicated.name}",
            created_by_user_id=user_id, type="Create",
        ))
        for v in item.technical_feature_values:
            if v.is_removed:
                continue
            value = TechnicalFeatureValue(
                id=uuid.uuid4(),
                technical_feature_id=v.technical_feature_id,
                category_technical_feature_id=v.category_technical_feature_id,
                technical_table_product_id=table_product.id,
                technical_feature_enum_id=v.technical_feature_enum_id,
                technical_feature_enum1_id=v.technical_feature_enum1_id,
                min_value=v.min_value,
                max_value=v.max_value,
                min_unit=v.min_unit,
                max_unit=v.max_unit,
                x_value=v.x_value,
                x_unit=v.x_unit,
                y_value=v.y_value,
                y_unit=v.y_unit,
                z_value=v.z_value,
                z_unit=v.z_unit,
                d_value=v.d_value,
                unit=v.unit,
                s_value=v.s_value,
                e_value=v.e_value,
                e_value1=v.e_value1,
                b_value=v.b_value,
                general_feature=v.general_feature,
                created_by_user_id=user_id,
                insert_date=now,
                update_date=now,
            )
            db.add(value)
            await db.flush()
            db.add(Log(
                record_id=value.id, table_name="technical_feature_values",
                description=f"تکثیر مقدار ویژگی فنی محصول: {duplicated.name}",
                created_by_user_id=user_id, type="Create",
            ))

    # Product images (mirrors ProductImage.Duplicate URL rewriting — but only
    # when the folder copy above succeeded; otherwise keep working URLs).
    for item in sorted(source.product_images or [], key=lambda x: x.picture_order or 0):
        if item.is_removed:
            continue
        image = ProductImage(
            id=uuid.uuid4(),
            product_id=new_id,
            medium_image_url=rewrite_media_url(item.medium_image_url, en_slug) if _images_copied else item.medium_image_url,
            small_image_url=rewrite_media_url(item.small_image_url, en_slug) if _images_copied else item.small_image_url,
            large_image_url=rewrite_media_url(item.large_image_url, en_slug) if _images_copied else item.large_image_url,
            small_image_large_url=rewrite_media_url(item.small_image_large_url, en_slug) if _images_copied else item.small_image_large_url,
            medium_image_large_url=rewrite_media_url(item.medium_image_large_url, en_slug) if _images_copied else item.medium_image_large_url,
            large_image_large_url=rewrite_media_url(item.large_image_large_url, en_slug) if _images_copied else item.large_image_large_url,
            title=item.title,
            description=item.description,
            display_photo=item.display_photo,
            picture_order=item.picture_order or 0,
            scale=item.scale or 0,
            created_by_user_id=user_id,
            insert_date=now,
            update_date=now,
        )
        db.add(image)
        await db.flush()
        db.add(Log(
            record_id=image.id, table_name="product_images",
            description=f"تکثیر عکس محصول: {duplicated.name}",
            created_by_user_id=user_id, type="Create",
        ))

    # Similar / related links.
    for item in source.similar_products or []:
        if item.is_removed:
            continue
        similar = SimilarProduct(
            id=uuid.uuid4(),
            product_id=new_id,
            similar_product_id=item.similar_product_id,
            feature_image_url=item.feature_image_url,
            created_by_user_id=user_id,
            insert_date=now,
            update_date=now,
        )
        db.add(similar)
        await db.flush()
        db.add(Log(
            record_id=similar.id, table_name="similar_products",
            description=f"تکثیر محصول مشابه: {duplicated.name}",
            created_by_user_id=user_id, type="Create",
        ))
    for item in source.related_products or []:
        if item.is_removed:
            continue
        related = RelatedProduct(
            id=uuid.uuid4(),
            product_id=new_id,
            relate_product_id=item.relate_product_id,
            feature_image_url=item.feature_image_url,
            created_by_user_id=user_id,
            insert_date=now,
            update_date=now,
        )
        db.add(related)
        await db.flush()
        db.add(Log(
            record_id=related.id, table_name="related_products",
            description=f"تکثیر محصول مرتبط: {duplicated.name}",
            created_by_user_id=user_id, type="Create",
        ))

    # Datasheets (mirrors MenuDatasheet FileURL rewriting — same copy guard).
    for item in source.menu_datasheets or []:
        if item.is_removed:
            continue
        datasheet = MenuDatasheet(
            id=uuid.uuid4(),
            product_id=new_id,
            type=item.type,
            file_url=rewrite_media_url(item.file_url, en_slug) if _datasheets_copied else item.file_url,
            complete_file_url=rewrite_media_url(item.complete_file_url, en_slug) if _datasheets_copied else item.complete_file_url,
            created_by_user_id=user_id,
            insert_date=now,
            update_date=now,
        )
        db.add(datasheet)
        await db.flush()
        db.add(Log(
            record_id=datasheet.id, table_name="menu_datasheets",
            description=f"تکثیر برگه اطلاعات محصول: {duplicated.name}",
            created_by_user_id=user_id, type="Create",
        ))

    return duplicated