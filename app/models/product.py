from __future__ import annotations

import uuid
from typing import Optional
from datetime import datetime

from sqlalchemy import (
    Column, String, Boolean, DateTime, ForeignKey, Text, Integer, Numeric, UniqueConstraint, Index
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base, BaseEntityMixin


class Category(Base, BaseEntityMixin):
    __tablename__ = "categories"

    title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    en_title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    product_count: Mapped[int] = mapped_column(Integer, default=0)
    keywords: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    meta_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    slug: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    is_disable: Mapped[bool] = mapped_column(Boolean, default=False)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    poster_image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    place: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    parent_category_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    no_display: Mapped[bool] = mapped_column(Boolean, default=False)

    parent: Mapped[Optional["Category"]] = relationship("Category", remote_side="Category.id", back_populates="children", lazy="selectin")
    children: Mapped[list["Category"]] = relationship("Category", back_populates="parent", lazy="selectin")
    products: Mapped[list["Product"]] = relationship("Product", back_populates="category", lazy="selectin")
    category_technical_features: Mapped[list["CategoryTechnicalFeature"]] = relationship("CategoryTechnicalFeature", back_populates="category", lazy="selectin")
    medias: Mapped[list["Media"]] = relationship("Media", back_populates="category", lazy="selectin")


class Brand(Base, BaseEntityMixin):
    __tablename__ = "brands"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    count: Mapped[int] = mapped_column(Integer, default=0)

    products: Mapped[list["Product"]] = relationship("Product", back_populates="brand", lazy="selectin")


class ProductType(Base, BaseEntityMixin):
    __tablename__ = "product_types"

    fa_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    en_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    products: Mapped[list["Product"]] = relationship("Product", back_populates="product_type", lazy="selectin")


class ProductUnit(Base, BaseEntityMixin):
    __tablename__ = "product_units"

    name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    abbreviation: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    product_unit_tax_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    products: Mapped[list["Product"]] = relationship("Product", back_populates="product_unit", lazy="selectin")


class Currency(Base, BaseEntityMixin):
    __tablename__ = "currencies"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    currency_details: Mapped[list["CurrencyDetail"]] = relationship("CurrencyDetail", back_populates="currency", lazy="selectin")
    products: Mapped[list["Product"]] = relationship("Product", back_populates="currency", lazy="selectin")


class Product(Base, BaseEntityMixin):
    __tablename__ = "products"

    name: Mapped[str] = mapped_column(String(500), unique=True, nullable=False)
    en_name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    slug: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    en_slug: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    part_number: Mapped[Optional[str]] = mapped_column(String(100), unique=True, nullable=True)
    short_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    introduction: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    short_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    keywords: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    meta_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    concatenated: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    en_concatenated: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    price: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    max_price: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    price_after_discount: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    discount_amount: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    discount_percentage: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    currency_price: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    profit_rate: Mapped[Optional[float]] = mapped_column(Numeric(14, 4), nullable=True)
    taxes_and_duties: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    total_amount_plus_taxes: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    vat_rate: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)

    stock_quantity: Mapped[int] = mapped_column(Integer, default=0)
    stock_supply_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    minimum_purchase: Mapped[int] = mapped_column(Integer, default=1)
    max_number_of_purchases: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    order_point: Mapped[int] = mapped_column(Integer, default=0)
    points_from_purchases: Mapped[int] = mapped_column(Integer, default=0)
    views: Mapped[int] = mapped_column(Integer, default=0)
    rate: Mapped[float] = mapped_column(Numeric(3, 2), default=0)
    sale: Mapped[int] = mapped_column(Integer, default=0)
    release_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    purchase_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    default_variation: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    taobao_choice_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    delivery_day: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    number_of_variations: Mapped[int] = mapped_column(Integer, default=0)
    restocked: Mapped[bool] = mapped_column(Boolean, default=False)
    is_bundle: Mapped[bool] = mapped_column(Boolean, default=False)
    is_calibrated: Mapped[bool] = mapped_column(Boolean, default=False)
    is_new: Mapped[bool] = mapped_column(Boolean, default=False)
    is_special: Mapped[bool] = mapped_column(Boolean, default=False)
    on_sale: Mapped[bool] = mapped_column(Boolean, default=False)
    suggested: Mapped[bool] = mapped_column(Boolean, default=False)
    no_display: Mapped[bool] = mapped_column(Boolean, default=False)
    automatic_price_calculation: Mapped[bool] = mapped_column(Boolean, default=False)

    tax_unique_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    image_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    image_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    medium_image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    medium_image_large_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    large_image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    feature_image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    category_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    brand_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id", ondelete="SET NULL"), nullable=True)
    product_type_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("product_types.id", ondelete="SET NULL"), nullable=True)
    product_unit_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("product_units.id", ondelete="SET NULL"), nullable=True)
    currency_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("currencies.id", ondelete="SET NULL"), nullable=True)

    category: Mapped[Optional[Category]] = relationship("Category", back_populates="products", lazy="selectin")
    brand: Mapped[Optional[Brand]] = relationship("Brand", back_populates="products", lazy="selectin")
    product_type: Mapped[Optional[ProductType]] = relationship("ProductType", back_populates="products", lazy="selectin")
    product_unit: Mapped[Optional[ProductUnit]] = relationship("ProductUnit", back_populates="products", lazy="selectin")
    currency: Mapped[Optional[Currency]] = relationship("Currency", back_populates="products", lazy="selectin")

    product_images: Mapped[list["ProductImage"]] = relationship("ProductImage", back_populates="product", lazy="selectin", cascade="all, delete-orphan")
    varieties: Mapped[list["Variety"]] = relationship("Variety", back_populates="product", lazy="selectin")
    product_tags: Mapped[list["ProductTag"]] = relationship("ProductTag", back_populates="product", lazy="selectin")
    related_products: Mapped[list["RelatedProduct"]] = relationship("RelatedProduct", back_populates="product", lazy="selectin", foreign_keys="RelatedProduct.product_id")
    similar_products: Mapped[list["SimilarProduct"]] = relationship("SimilarProduct", back_populates="product", lazy="selectin", foreign_keys="SimilarProduct.product_id")
    menu_datasheets: Mapped[list["MenuDatasheet"]] = relationship("MenuDatasheet", back_populates="product", lazy="selectin")
    supplier_products: Mapped[list["SupplierProduct"]] = relationship("SupplierProduct", back_populates="product", lazy="selectin")
    technical_table_products: Mapped[list["TechnicalTableProduct"]] = relationship("TechnicalTableProduct", back_populates="product", lazy="selectin")
    comments: Mapped[list["Comment"]] = relationship("Comment", back_populates="product", lazy="selectin")
    created_by_user: Mapped[Optional["User"]] = relationship("User", foreign_keys="Product.created_by_user_id", lazy="selectin")

    # Created-by-user relationship for product list display
    created_by_user: Mapped[Optional["User"]] = relationship("User", foreign_keys="Product.created_by_user_id", lazy="selectin")


class Variety(Base, BaseEntityMixin):
    __tablename__ = "varieties"

    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    part_number: Mapped[Optional[str]] = mapped_column(String(100), unique=True, nullable=True)
    place: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    stock_quantity: Mapped[int] = mapped_column(Integer, default=0)
    stock_supply_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    minimum_purchase: Mapped[int] = mapped_column(Integer, default=1)
    price: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    price_after_discount: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    discount_amount: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    currency_price: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    profit_rate: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    automatic_price_calculation: Mapped[bool] = mapped_column(Boolean, default=False)
    currency_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("currencies.id", ondelete="SET NULL"), nullable=True)

    product: Mapped[Product] = relationship("Product", back_populates="varieties")
    currency_rel: Mapped[Optional[Currency]] = relationship("Currency")
    product_varieties: Mapped[list["ProductVariety"]] = relationship("ProductVariety", back_populates="variety", lazy="selectin")


class CategoryOption(Base, BaseEntityMixin):
    __tablename__ = "category_options"

    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)

    product_varieties: Mapped[list["ProductVariety"]] = relationship("ProductVariety", back_populates="category_option", lazy="selectin")


class ProductVariety(Base, BaseEntityMixin):
    __tablename__ = "product_varieties"

    variety_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("varieties.id", ondelete="CASCADE"), nullable=False)
    category_option_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("category_options.id", ondelete="CASCADE"), nullable=False)
    value: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    variety: Mapped[Variety] = relationship("Variety", back_populates="product_varieties")
    category_option: Mapped[CategoryOption] = relationship("CategoryOption", back_populates="product_varieties")

    __table_args__ = (
        UniqueConstraint("category_option_id", "variety_id", name="uq_product_variety_option"),
    )


class ProductImage(Base, BaseEntityMixin):
    __tablename__ = "product_images"

    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    medium_image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    small_image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    large_image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    display_photo: Mapped[bool] = mapped_column(Boolean, default=False)
    picture_order: Mapped[int] = mapped_column(Integer, default=0)
    scale: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    product: Mapped[Product] = relationship("Product", back_populates="product_images")

    __table_args__ = (
        Index("ix_product_image_order", "picture_order", "id", unique=True),
    )


class Tag(Base, BaseEntityMixin):
    __tablename__ = "tags"

    name: Mapped[str] = mapped_column(String(100), nullable=False)

    product_tags: Mapped[list["ProductTag"]] = relationship("ProductTag", back_populates="tag", lazy="selectin")


class ProductTag(Base, BaseEntityMixin):
    __tablename__ = "product_tags"

    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    tag_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tags.id", ondelete="CASCADE"), nullable=False)

    product: Mapped[Product] = relationship("Product", back_populates="product_tags")
    tag: Mapped[Tag] = relationship("Tag", back_populates="product_tags")

    __table_args__ = (
        UniqueConstraint("tag_id", "product_id", name="uq_product_tag"),
    )


class RelatedProduct(Base, BaseEntityMixin):
    __tablename__ = "related_products"

    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="NO ACTION"), nullable=False)
    relate_product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="NO ACTION"), nullable=False)
    feature_image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    product: Mapped[Product] = relationship("Product", back_populates="related_products", foreign_keys=[product_id])
    relate_product: Mapped[Product] = relationship("Product", foreign_keys=[relate_product_id])


class SimilarProduct(Base, BaseEntityMixin):
    __tablename__ = "similar_products"

    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="NO ACTION"), nullable=False)
    similar_product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="NO ACTION"), nullable=False)
    feature_image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    product: Mapped[Product] = relationship("Product", back_populates="similar_products", foreign_keys=[product_id])
    similar: Mapped[Product] = relationship("Product", foreign_keys=[similar_product_id])

    __table_args__ = (
        UniqueConstraint("product_id", "similar_product_id", name="uq_similar_product"),
    )


class SuggestedProduct(Base, BaseEntityMixin):
    __tablename__ = "suggested_products"

    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    product: Mapped[Product] = relationship("Product")


class FavoriteProductList(Base, BaseEntityMixin):
    __tablename__ = "favorite_product_lists"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    count: Mapped[int] = mapped_column(Integer, default=0)
    token: Mapped[Optional[str]] = mapped_column(String(200), unique=True, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    int_id: Mapped[Optional[int]] = mapped_column(Integer, unique=True, nullable=True)

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], back_populates="favorite_product_lists")
    favorite_list_items: Mapped[list["FavoriteListItem"]] = relationship("FavoriteListItem", back_populates="favorite_product_list", lazy="selectin")


class FavoriteListItem(Base, BaseEntityMixin):
    __tablename__ = "favorite_list_items"

    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    favorite_product_list_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("favorite_product_lists.id", ondelete="CASCADE"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1)

    product: Mapped[Product] = relationship("Product")
    favorite_product_list: Mapped[FavoriteProductList] = relationship("FavoriteProductList", back_populates="favorite_list_items")


class VisitedProduct(Base, BaseEntityMixin):
    __tablename__ = "visited_products"

    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    product: Mapped[Product] = relationship("Product")
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], back_populates="visited_products")


class MenuDatasheet(Base, BaseEntityMixin):
    __tablename__ = "menu_datasheets"

    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    file_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    complete_file_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    product: Mapped[Product] = relationship("Product", back_populates="menu_datasheets")


class PriceHistory(Base, BaseEntityMixin):
    __tablename__ = "price_histories"

    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    price: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)

    product: Mapped[Product] = relationship("Product")


class Warranty(Base, BaseEntityMixin):
    __tablename__ = "warranties"

    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    follow_up_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    start_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finish_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    conditions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    manufacturer_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("manufacturers.id", ondelete="SET NULL"), nullable=True)


class CategoryMedia(Base, BaseEntityMixin):
    __tablename__ = "category_medias"

    category_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("categories.id", ondelete="CASCADE"), nullable=False)
    url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)


class ProductMedia(Base, BaseEntityMixin):
    __tablename__ = "product_medias"

    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    thumbnail_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    large_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    video_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    display_photo: Mapped[bool] = mapped_column(Boolean, default=False)
    type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_video: Mapped[bool] = mapped_column(Boolean, default=False)
    is_bundle_media: Mapped[bool] = mapped_column(Boolean, default=False)