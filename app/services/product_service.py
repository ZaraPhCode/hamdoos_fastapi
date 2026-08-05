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
    PriceHistory,
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
            selectinload(Product.varieties),
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
    product = Product(
        id=uuid.uuid4(),
        **request.model_dump(exclude_unset=True),
        created_by_user_id=user_id,
        insert_date=datetime.now(timezone.utc),
        update_date=datetime.now(timezone.utc),
    )
    db.add(product)
    await db.flush()
    return product


async def update_product(db: AsyncSession, product: Product, request: ProductUpdate) -> Product:
    for key, value in request.model_dump(exclude_unset=True).items():
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


async def get_new_products(db: AsyncSession, limit: int = 10) -> list[Product]:
    stmt = (
        select(Product)
        .options(selectinload(Product.category), selectinload(Product.brand))
        .where(
            Product.is_new == True,
            Product.is_removed == False,
            Product.no_display == False,
        )
        .order_by(Product.insert_date.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.unique().scalars().all())


async def get_special_products(db: AsyncSession, limit: int = 12) -> list[Product]:
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
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.unique().scalars().all())


async def get_restocked_products(db: AsyncSession, limit: int = 12) -> list[Product]:
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
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.unique().scalars().all())


async def get_suggested_products(db: AsyncSession, limit: int = 12) -> list[Product]:
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
        .limit(limit)
    )
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