from __future__ import annotations

import uuid
from typing import Optional
from datetime import datetime

from sqlalchemy import (
    String, Boolean, DateTime, ForeignKey, Text, Integer, Numeric, UniqueConstraint, Index, Float
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base, BaseEntityMixin
from app.models.enum_types import (
    ProductStatusEnum, TagTypeEnum, MenuDatasheetTypeEnum, ContentTypeEnum,
)


class Category(Base, BaseEntityMixin):
    __tablename__ = "Categories"

    title: Mapped[str] = mapped_column("Title", Text, nullable=False)
    en_title: Mapped[str] = mapped_column("EnTitle", String(100), nullable=False)
    description: Mapped[str] = mapped_column("Description", Text, nullable=False)
    product_count: Mapped[int] = mapped_column("ProductCount", Integer, nullable=False, default=0)
    keywords: Mapped[str] = mapped_column("Keywords", Text, nullable=False)
    meta_description: Mapped[str] = mapped_column("MetaDescription", Text, nullable=False)
    slug: Mapped[str] = mapped_column("Slug", Text, nullable=False)
    is_disable: Mapped[bool] = mapped_column("IsDisable", Boolean, default=False)
    priority: Mapped[int] = mapped_column("Priority", Integer, nullable=False, default=0)
    poster_image_url: Mapped[Optional[str]] = mapped_column("PosterImageURL", Text, nullable=True)
    place: Mapped[Optional[str]] = mapped_column("Place", Text, nullable=True)
    parent_category_id: Mapped[Optional[uuid.UUID]] = mapped_column("ParentCategoryId", UUID(as_uuid=True), ForeignKey("Categories.Id", ondelete="SET NULL"), nullable=True)
    no_display: Mapped[bool] = mapped_column("NoDisplay", Boolean, default=False)

    parent: Mapped[Optional["Category"]] = relationship("Category", remote_side="Category.id", back_populates="children", lazy="selectin")
    children: Mapped[list["Category"]] = relationship("Category", back_populates="parent", lazy="selectin")
    products: Mapped[list["Product"]] = relationship("Product", back_populates="category", lazy="selectin")
    category_technical_features: Mapped[list["CategoryTechnicalFeature"]] = relationship("CategoryTechnicalFeature", back_populates="category", lazy="selectin")
    medias: Mapped[list["Media"]] = relationship("Media", back_populates="category", lazy="selectin")


class Brand(Base, BaseEntityMixin):
    __tablename__ = "Brands"

    name: Mapped[str] = mapped_column("Name", Text, nullable=False)
    count: Mapped[int] = mapped_column("Count", Integer, nullable=False, default=0)

    products: Mapped[list["Product"]] = relationship("Product", back_populates="brand", lazy="selectin")


class ProductType(Base, BaseEntityMixin):
    __tablename__ = "ProductTypes"

    fa_name: Mapped[str] = mapped_column("FaName", Text, nullable=False)
    en_name: Mapped[str] = mapped_column("EnName", Text, nullable=False)

    products: Mapped[list["Product"]] = relationship("Product", back_populates="product_type", lazy="selectin")


class ProductUnit(Base, BaseEntityMixin):
    __tablename__ = "ProductUnits"

    name: Mapped[str] = mapped_column("Name", Text, nullable=False)
    abbreviation: Mapped[str] = mapped_column("Abbreviation", Text, nullable=False)
    product_unit_tax_id: Mapped[str] = mapped_column("ProductUnitTaxId", Text, nullable=False)

    products: Mapped[list["Product"]] = relationship("Product", back_populates="product_unit", lazy="selectin")


class Currency(Base, BaseEntityMixin):
    __tablename__ = "Currencies"

    name: Mapped[str] = mapped_column("Name", String(450), unique=True, nullable=False)

    currency_details: Mapped[list["CurrencyDetail"]] = relationship("CurrencyDetail", back_populates="currency", lazy="selectin")
    products: Mapped[list["Product"]] = relationship("Product", back_populates="currency", lazy="selectin")


class Product(Base, BaseEntityMixin):
    __tablename__ = "Products"

    int_id: Mapped[int] = mapped_column("IntId", Integer, nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column("Name", String(450), unique=True, nullable=False)
    en_name: Mapped[str] = mapped_column("EnName", String(250), nullable=False)
    slug: Mapped[str] = mapped_column("Slug", Text, nullable=False)
    en_slug: Mapped[str] = mapped_column("EnSlug", String(100), nullable=False)
    part_number: Mapped[str] = mapped_column("PartNumber", String(450), unique=True, nullable=False)
    short_name: Mapped[Optional[str]] = mapped_column("ShortName", Text, nullable=True)
    model: Mapped[str] = mapped_column("Model", Text, nullable=False)
    introduction: Mapped[str] = mapped_column("Introduction", Text, nullable=False)
    short_description: Mapped[str] = mapped_column("ShortDescription", Text, nullable=False)
    keywords: Mapped[str] = mapped_column("Keywords", Text, nullable=False)
    meta_description: Mapped[str] = mapped_column("MetaDescription", Text, nullable=False)
    concatenated: Mapped[str] = mapped_column("Concatenated", Text, nullable=False)
    en_concatenated: Mapped[str] = mapped_column("EnConcatenated", Text, nullable=False)

    price: Mapped[float] = mapped_column("Price", Numeric(14, 2), nullable=False)
    max_price: Mapped[Optional[float]] = mapped_column("MaxPrice", Numeric(14, 2), nullable=True)
    price_after_discount: Mapped[float] = mapped_column("PriceAfterDiscount", Numeric(14, 2), nullable=False)
    discount_amount: Mapped[float] = mapped_column("DiscountAmount", Numeric(14, 2), nullable=False)
    discount_percentage: Mapped[float] = mapped_column("DiscountPercentage", Numeric(14, 2), nullable=False)
    currency_price: Mapped[float] = mapped_column("CurrencyPrice", Numeric(14, 2), nullable=False)
    profit_rate: Mapped[float] = mapped_column("ProfitRate", Numeric(14, 4), nullable=False)
    taxes_and_duties: Mapped[float] = mapped_column("TaxesAndDuties", Numeric(14, 2), nullable=False)
    total_amount_plus_taxes: Mapped[float] = mapped_column("TotalAmountPlusTaxesAndDuties", Numeric(14, 2), nullable=False)
    vat_rate: Mapped[float] = mapped_column("VATRate", Numeric(14, 2), nullable=False)

    stock_quantity: Mapped[int] = mapped_column("StockQuantity", Integer, default=0)
    stock_supply_date: Mapped[Optional[datetime]] = mapped_column("StockSupplyDate", DateTime(timezone=True), nullable=True)
    minimum_purchase: Mapped[int] = mapped_column("MinimumPurchase", Integer, default=1)
    max_number_of_purchases: Mapped[int] = mapped_column("MaxNumberOfPurchases", Integer, nullable=False)
    order_point: Mapped[int] = mapped_column("OrderPoint", Integer, default=0)
    points_from_purchases: Mapped[int] = mapped_column("PointsFromPurchases", Integer, default=0)
    views: Mapped[int] = mapped_column("Views", Integer, default=0)
    rate: Mapped[int] = mapped_column("Rate", Integer, nullable=False, default=0)
    sale: Mapped[int] = mapped_column("Sale", Integer, default=0)
    release_date: Mapped[datetime] = mapped_column("ReleaseDate", DateTime(timezone=True), nullable=False)
    purchase_date: Mapped[datetime] = mapped_column("PurchaseDate", DateTime(timezone=True), nullable=False)

    status: Mapped[str] = mapped_column("Status", ProductStatusEnum, nullable=False, default="Unknown")
    type: Mapped[int] = mapped_column("Type", Integer, nullable=False, default=0)
    default_variation: Mapped[bool] = mapped_column("DefaultVariation", Boolean, nullable=False, default=False)
    taobao_choice_id: Mapped[Optional[uuid.UUID]] = mapped_column("TaobaoChoiceId", UUID(as_uuid=True), nullable=True)
    delivery_day: Mapped[int] = mapped_column("DeliveryDay", Integer, nullable=False)
    number_of_variations: Mapped[int] = mapped_column("NumberOfVariations", Integer, default=0)
    restocked: Mapped[bool] = mapped_column("Restocked", Boolean, default=False)
    is_bundle: Mapped[bool] = mapped_column("IsBundle", Boolean, default=False)
    is_calibrated: Mapped[bool] = mapped_column("IsCalibrated", Boolean, default=False)
    is_new: Mapped[bool] = mapped_column("IsNew", Boolean, default=False)
    is_special: Mapped[bool] = mapped_column("IsSpecial", Boolean, default=False)
    on_sale: Mapped[bool] = mapped_column("OnSale", Boolean, default=False)
    suggested: Mapped[bool] = mapped_column("Suggested", Boolean, default=False)
    no_display: Mapped[bool] = mapped_column("NoDisplay", Boolean, default=False)
    automatic_price_calculation: Mapped[bool] = mapped_column("AutomaticPriceCalculation", Boolean, default=False)

    tax_unique_id: Mapped[str] = mapped_column("TaxUniqueId", String(13), nullable=False)

    image_id: Mapped[Optional[uuid.UUID]] = mapped_column("ImageId", UUID(as_uuid=True), nullable=True)
    image_description: Mapped[Optional[str]] = mapped_column("ImageDescription", Text, nullable=True)
    image_title: Mapped[Optional[str]] = mapped_column("ImageTitle", Text, nullable=True)
    medium_image_url: Mapped[Optional[str]] = mapped_column("MediumImageURL", Text, nullable=True)
    medium_image_large_url: Mapped[Optional[str]] = mapped_column("MediumImageLargeURL", Text, nullable=True)
    large_image_url: Mapped[Optional[str]] = mapped_column("LargeImageURL", Text, nullable=True)
    feature_image_url: Mapped[Optional[str]] = mapped_column("FeatureImageURL", Text, nullable=True)

    category_id: Mapped[uuid.UUID] = mapped_column("CategoryId", UUID(as_uuid=True), ForeignKey("Categories.Id", ondelete="SET NULL"), nullable=False)
    brand_id: Mapped[Optional[uuid.UUID]] = mapped_column("BrandId", UUID(as_uuid=True), ForeignKey("Brands.Id", ondelete="SET NULL"), nullable=True)
    product_type_id: Mapped[Optional[uuid.UUID]] = mapped_column("ProductTypeId", UUID(as_uuid=True), ForeignKey("ProductTypes.Id", ondelete="SET NULL"), nullable=True)
    product_unit_id: Mapped[Optional[uuid.UUID]] = mapped_column("ProductUnitId", UUID(as_uuid=True), ForeignKey("ProductUnits.Id", ondelete="SET NULL"), nullable=True)
    currency_id: Mapped[Optional[uuid.UUID]] = mapped_column("CurrencyId", UUID(as_uuid=True), ForeignKey("Currencies.Id", ondelete="SET NULL"), nullable=True)

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


class Variety(Base, BaseEntityMixin):
    __tablename__ = "Varieties"

    product_id: Mapped[uuid.UUID] = mapped_column("ProductId", UUID(as_uuid=True), ForeignKey("Products.Id", ondelete="CASCADE"), nullable=False)
    part_number: Mapped[Optional[str]] = mapped_column("PartNumber", String(450), unique=True, nullable=True)
    place: Mapped[Optional[str]] = mapped_column("Place", Text, nullable=True)
    stock_quantity: Mapped[int] = mapped_column("StockQuantity", Integer, default=0)
    stock_supply_date: Mapped[Optional[datetime]] = mapped_column("StockSupplyDate", DateTime(timezone=True), nullable=True)
    minimum_purchase: Mapped[int] = mapped_column("MinimumPurchase", Integer, nullable=False, default=1)
    price: Mapped[float] = mapped_column("Price", Numeric(14, 2), nullable=False)
    price_after_discount: Mapped[Optional[float]] = mapped_column("PriceAfterDiscount", Numeric(14, 2), nullable=True)
    discount_amount: Mapped[float] = mapped_column("DiscountAmount", Numeric(14, 2), nullable=False)
    currency_price: Mapped[float] = mapped_column("CurrencyPrice", Numeric(14, 2), nullable=False)
    profit_rate: Mapped[float] = mapped_column("ProfitRate", Numeric(14, 2), nullable=False)
    automatic_price_calculation: Mapped[bool] = mapped_column("AutomaticPriceCalculation", Boolean, default=False)
    currency_id: Mapped[Optional[uuid.UUID]] = mapped_column("CurrencyId", UUID(as_uuid=True), ForeignKey("Currencies.Id", ondelete="SET NULL"), nullable=True)

    product: Mapped[Product] = relationship("Product", back_populates="varieties")
    currency_rel: Mapped[Optional[Currency]] = relationship("Currency")
    product_varieties: Mapped[list["ProductVariety"]] = relationship("ProductVariety", back_populates="variety", lazy="selectin")


class CategoryOption(Base, BaseEntityMixin):
    __tablename__ = "CategoryOptions"

    name: Mapped[str] = mapped_column("Name", String(450), unique=True, nullable=False)

    product_varieties: Mapped[list["ProductVariety"]] = relationship("ProductVariety", back_populates="category_option", lazy="selectin")


class ProductVariety(Base, BaseEntityMixin):
    __tablename__ = "ProductVarieties"

    variety_id: Mapped[uuid.UUID] = mapped_column("VarietyId", UUID(as_uuid=True), ForeignKey("Varieties.Id", ondelete="CASCADE"), nullable=False)
    category_option_id: Mapped[uuid.UUID] = mapped_column("CategoryOptionId", UUID(as_uuid=True), ForeignKey("CategoryOptions.Id", ondelete="CASCADE"), nullable=False)
    value: Mapped[str] = mapped_column("Value", Text, nullable=False)

    variety: Mapped[Variety] = relationship("Variety", back_populates="product_varieties")
    category_option: Mapped[CategoryOption] = relationship("CategoryOption", back_populates="product_varieties")

    __table_args__ = (
        UniqueConstraint("CategoryOptionId", "VarietyId", name="uq_product_variety_option"),
    )


class ProductImage(Base, BaseEntityMixin):
    __tablename__ = "ProductImages"

    product_id: Mapped[uuid.UUID] = mapped_column("ProductId", UUID(as_uuid=True), ForeignKey("Products.Id", ondelete="CASCADE"), nullable=False)
    medium_image_url: Mapped[str] = mapped_column("MediumImageURL", Text, nullable=False)
    small_image_url: Mapped[Optional[str]] = mapped_column("SmallImageURL", Text, nullable=True)
    large_image_url: Mapped[Optional[str]] = mapped_column("LargeImageURL", Text, nullable=True)
    small_image_large_url: Mapped[Optional[str]] = mapped_column("SmallImageLargeURL", Text, nullable=True)
    medium_image_large_url: Mapped[Optional[str]] = mapped_column("MediumImageLargeURL", Text, nullable=True)
    large_image_large_url: Mapped[Optional[str]] = mapped_column("LargeImageLargeURL", Text, nullable=True)
    title: Mapped[Optional[str]] = mapped_column("Title", Text, nullable=True)
    description: Mapped[Optional[str]] = mapped_column("Description", Text, nullable=True)
    display_photo: Mapped[bool] = mapped_column("DisplayPhoto", Boolean, default=False)
    picture_order: Mapped[int] = mapped_column("PictureOrder", Integer, default=0)
    scale: Mapped[float] = mapped_column("Scale", Float, nullable=False, default=0)

    product: Mapped[Product] = relationship("Product", back_populates="product_images")

    __table_args__ = (
        Index("ix_product_image_order", "PictureOrder", "Id", unique=True),
    )


class Tag(Base, BaseEntityMixin):
    __tablename__ = "Tags"

    name: Mapped[str] = mapped_column("Name", Text, nullable=False)
    type: Mapped[Optional[str]] = mapped_column("Type", TagTypeEnum, nullable=True)

    product_tags: Mapped[list["ProductTag"]] = relationship("ProductTag", back_populates="tag", lazy="selectin")


class ProductTag(Base, BaseEntityMixin):
    __tablename__ = "ProductTags"

    product_id: Mapped[uuid.UUID] = mapped_column("ProductId", UUID(as_uuid=True), ForeignKey("Products.Id", ondelete="CASCADE"), nullable=False)
    tag_id: Mapped[uuid.UUID] = mapped_column("TagId", UUID(as_uuid=True), ForeignKey("Tags.Id", ondelete="CASCADE"), nullable=False)

    product: Mapped[Product] = relationship("Product", back_populates="product_tags")
    tag: Mapped[Tag] = relationship("Tag", back_populates="product_tags")

    __table_args__ = (
        UniqueConstraint("TagId", "ProductId", name="uq_product_tag"),
    )


class RelatedProduct(Base, BaseEntityMixin):
    __tablename__ = "RelatedProducts"

    product_id: Mapped[uuid.UUID] = mapped_column("ProductId", UUID(as_uuid=True), ForeignKey("Products.Id", ondelete="NO ACTION"), nullable=False)
    relate_product_id: Mapped[uuid.UUID] = mapped_column("RelateProductId", UUID(as_uuid=True), ForeignKey("Products.Id", ondelete="NO ACTION"), nullable=False)
    feature_image_url: Mapped[Optional[str]] = mapped_column("FeatureImageURL", Text, nullable=True)

    product: Mapped[Product] = relationship("Product", back_populates="related_products", foreign_keys=[product_id])
    relate_product: Mapped[Product] = relationship("Product", foreign_keys=[relate_product_id])


class SimilarProduct(Base, BaseEntityMixin):
    __tablename__ = "SimilarProducts"

    product_id: Mapped[uuid.UUID] = mapped_column("ProductId", UUID(as_uuid=True), ForeignKey("Products.Id", ondelete="NO ACTION"), nullable=False)
    similar_product_id: Mapped[uuid.UUID] = mapped_column("SimilarProductId", UUID(as_uuid=True), ForeignKey("Products.Id", ondelete="NO ACTION"), nullable=False)
    feature_image_url: Mapped[Optional[str]] = mapped_column("FeatureImageURL", Text, nullable=True)

    product: Mapped[Product] = relationship("Product", back_populates="similar_products", foreign_keys=[product_id])
    similar: Mapped[Product] = relationship("Product", foreign_keys=[similar_product_id])

    __table_args__ = (
        UniqueConstraint("ProductId", "SimilarProductId", name="uq_similar_product"),
    )


class SuggestedProduct(Base, BaseEntityMixin):
    __tablename__ = "SuggestedProducts"

    product_id: Mapped[uuid.UUID] = mapped_column("ProductId", UUID(as_uuid=True), ForeignKey("Products.Id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column("UserId", UUID(as_uuid=True), ForeignKey("Users.Id", ondelete="SET NULL"), nullable=True)

    product: Mapped[Product] = relationship("Product")


class FavoriteProductList(Base, BaseEntityMixin):
    __tablename__ = "FavoriteProductLists"

    user_id: Mapped[uuid.UUID] = mapped_column("UserId", UUID(as_uuid=True), ForeignKey("Users.Id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column("Name", Text, nullable=False)
    count: Mapped[int] = mapped_column("Count", Integer, nullable=False, default=0)
    token: Mapped[uuid.UUID] = mapped_column("Token", UUID(as_uuid=True), unique=True, nullable=False)
    is_default: Mapped[bool] = mapped_column("Default", Boolean, nullable=False, default=False)
    int_id: Mapped[int] = mapped_column("IntId", Integer, unique=True, nullable=False)

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], back_populates="favorite_product_lists")
    favorite_list_items: Mapped[list["FavoriteListItem"]] = relationship(
        "FavoriteListItem",
        back_populates="favorite_product_list",
        lazy="selectin",
        primaryjoin="and_(FavoriteListItem.favorite_product_list_id == FavoriteProductList.id, FavoriteListItem.is_removed == False)",
    )


class FavoriteListItem(Base, BaseEntityMixin):
    __tablename__ = "FavoriteListItems"

    product_id: Mapped[uuid.UUID] = mapped_column("ProductId", UUID(as_uuid=True), ForeignKey("Products.Id", ondelete="CASCADE"), nullable=False)
    favorite_product_list_id: Mapped[uuid.UUID] = mapped_column("FavoriteProductListId", UUID(as_uuid=True), ForeignKey("FavoriteProductLists.Id", ondelete="CASCADE"), nullable=False)
    quantity: Mapped[int] = mapped_column("Quantity", Integer, nullable=False, default=1)

    product: Mapped[Product] = relationship("Product")
    favorite_product_list: Mapped[FavoriteProductList] = relationship("FavoriteProductList", back_populates="favorite_list_items")


class VisitedProduct(Base, BaseEntityMixin):
    __tablename__ = "VisitedProducts"

    product_id: Mapped[uuid.UUID] = mapped_column("ProductId", UUID(as_uuid=True), ForeignKey("Products.Id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column("UserId", UUID(as_uuid=True), ForeignKey("Users.Id", ondelete="CASCADE"), nullable=False)

    product: Mapped[Product] = relationship("Product")
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], back_populates="visited_products")


class MenuDatasheet(Base, BaseEntityMixin):
    __tablename__ = "MenuDatasheets"

    product_id: Mapped[uuid.UUID] = mapped_column("ProductId", UUID(as_uuid=True), ForeignKey("Products.Id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column("Type", MenuDatasheetTypeEnum, nullable=False, default="Datasheet")
    file_url: Mapped[str] = mapped_column("FileURL", Text, nullable=False)
    complete_file_url: Mapped[Optional[str]] = mapped_column("CompleteFileURL", Text, nullable=True)

    product: Mapped[Product] = relationship("Product", back_populates="menu_datasheets")


class PriceHistory(Base, BaseEntityMixin):
    __tablename__ = "PriceHistories"

    product_id: Mapped[uuid.UUID] = mapped_column("ProductId", UUID(as_uuid=True), ForeignKey("Products.Id", ondelete="CASCADE"), nullable=False)
    price: Mapped[Optional[float]] = mapped_column("Price", Numeric(14, 2), nullable=True)

    product: Mapped[Product] = relationship("Product")


class Warranty(Base, BaseEntityMixin):
    __tablename__ = "Warranties"

    product_id: Mapped[uuid.UUID] = mapped_column("ProductId", UUID(as_uuid=True), ForeignKey("Products.Id", ondelete="CASCADE"), nullable=False)
    follow_up_id: Mapped[Optional[str]] = mapped_column("FollowUpId", String(100), nullable=True)
    start_date: Mapped[Optional[datetime]] = mapped_column("StartDate", DateTime(timezone=True), nullable=True)
    finish_date: Mapped[Optional[datetime]] = mapped_column("FinishDate", DateTime(timezone=True), nullable=True)
    type: Mapped[Optional[str]] = mapped_column("Type", String(50), nullable=True)
    conditions: Mapped[Optional[str]] = mapped_column("Conditions", Text, nullable=True)
    manufacturer_id: Mapped[Optional[uuid.UUID]] = mapped_column("ManufacturerId", UUID(as_uuid=True), ForeignKey("Manufacturers.Id", ondelete="SET NULL"), nullable=True)


class CategoryMedia(Base, BaseEntityMixin):
    __tablename__ = "CategoryMedias"

    category_id: Mapped[uuid.UUID] = mapped_column("CategoryId", UUID(as_uuid=True), ForeignKey("Categories.Id", ondelete="CASCADE"), nullable=False)
    url: Mapped[Optional[str]] = mapped_column("Url", String(500), nullable=True)
    title: Mapped[Optional[str]] = mapped_column("Title", String(500), nullable=True)
    type: Mapped[Optional[str]] = mapped_column("Type", ContentTypeEnum, nullable=True)


class ProductMedia(Base, BaseEntityMixin):
    __tablename__ = "ProductMedias"

    product_id: Mapped[uuid.UUID] = mapped_column("ProductId", UUID(as_uuid=True), ForeignKey("Products.Id", ondelete="CASCADE"), nullable=False)
    url: Mapped[Optional[str]] = mapped_column("Url", String(500), nullable=True)
    thumbnail_url: Mapped[Optional[str]] = mapped_column("ThumbnailUrl", String(500), nullable=True)
    large_url: Mapped[Optional[str]] = mapped_column("LargeUrl", String(500), nullable=True)
    video_url: Mapped[Optional[str]] = mapped_column("VideoUrl", String(500), nullable=True)
    title: Mapped[Optional[str]] = mapped_column("Title", String(500), nullable=True)
    description: Mapped[Optional[str]] = mapped_column("Description", Text, nullable=True)
    display_photo: Mapped[bool] = mapped_column("DisplayPhoto", Boolean, default=False)
    type: Mapped[Optional[str]] = mapped_column("Type", ContentTypeEnum, nullable=True)
    is_video: Mapped[bool] = mapped_column("IsVideo", Boolean, default=False)
    is_bundle_media: Mapped[bool] = mapped_column("IsBundleMedia", Boolean, default=False)