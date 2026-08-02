
import uuid
from typing import Optional

from sqlalchemy import (
    Column, String, Boolean, ForeignKey, Text, Integer, Numeric, UniqueConstraint, Index
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base, BaseEntityMixin


class TechnicalFeature(Base, BaseEntityMixin):
    __tablename__ = "technical_features"

    name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    fa_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    display_format: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    linear_display: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    d_value: Mapped[bool] = mapped_column(Boolean, default=False)
    unit: Mapped[bool] = mapped_column(Boolean, default=False)
    s_value: Mapped[bool] = mapped_column(Boolean, default=False)
    e_value: Mapped[bool] = mapped_column(Boolean, default=False)
    e_value1: Mapped[bool] = mapped_column(Boolean, default=False)
    b_value: Mapped[bool] = mapped_column(Boolean, default=False)
    min_value: Mapped[bool] = mapped_column(Boolean, default=False)
    min_unit: Mapped[bool] = mapped_column(Boolean, default=False)
    max_value: Mapped[bool] = mapped_column(Boolean, default=False)
    max_unit: Mapped[bool] = mapped_column(Boolean, default=False)
    x_value: Mapped[bool] = mapped_column(Boolean, default=False)
    x_unit: Mapped[bool] = mapped_column(Boolean, default=False)
    y_value: Mapped[bool] = mapped_column(Boolean, default=False)
    y_unit: Mapped[bool] = mapped_column(Boolean, default=False)
    z_value: Mapped[bool] = mapped_column(Boolean, default=False)
    z_unit: Mapped[bool] = mapped_column(Boolean, default=False)
    columns: Mapped[int] = mapped_column(Integer, default=1)
    visible_in_schema: Mapped[bool] = mapped_column(Boolean, default=True)

    category_technical_features: Mapped[list["CategoryTechnicalFeature"]] = relationship(
        "CategoryTechnicalFeature", back_populates="technical_feature", lazy="selectin"
    )
    technical_feature_enums: Mapped[list["TechnicalFeatureEnum"]] = relationship(
        "TechnicalFeatureEnum", back_populates="technical_feature", lazy="selectin",
        foreign_keys="TechnicalFeatureEnum.technical_feature_id"
    )
    technical_feature_enums1: Mapped[list["TechnicalFeatureEnum"]] = relationship(
        "TechnicalFeatureEnum", back_populates="technical_feature1", lazy="selectin",
        foreign_keys="TechnicalFeatureEnum.technical_feature1_id"
    )


class TechnicalFeatureEnum(Base, BaseEntityMixin):
    __tablename__ = "technical_feature_enums"

    name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    persian_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    technical_feature_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("technical_features.id", ondelete="RESTRICT"), nullable=True
    )
    technical_feature1_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("technical_features.id", ondelete="RESTRICT"), nullable=True
    )

    technical_feature: Mapped[Optional[TechnicalFeature]] = relationship(
        "TechnicalFeature", back_populates="technical_feature_enums", foreign_keys=[technical_feature_id]
    )
    technical_feature1: Mapped[Optional[TechnicalFeature]] = relationship(
        "TechnicalFeature", back_populates="technical_feature_enums1", foreign_keys=[technical_feature1_id]
    )


class CategoryTechnicalFeature(Base, BaseEntityMixin):
    __tablename__ = "category_technical_features"

    category_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("categories.id", ondelete="CASCADE"), nullable=False)
    technical_feature_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("technical_features.id", ondelete="CASCADE"), nullable=False)

    category: Mapped["Category"] = relationship("Category", back_populates="category_technical_features")
    technical_feature: Mapped[TechnicalFeature] = relationship("TechnicalFeature", back_populates="category_technical_features")
    technical_feature_values: Mapped[list["TechnicalFeatureValue"]] = relationship(
        "TechnicalFeatureValue", back_populates="category_technical_feature", lazy="selectin"
    )

    __table_args__ = (
        UniqueConstraint("category_id", "technical_feature_id", name="uq_category_tech_feature"),
        Index("ix_category_technical_feature", "category_id", "technical_feature_id", unique=True),
    )


class TechnicalTable(Base, BaseEntityMixin):
    __tablename__ = "technical_tables"

    title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    en_title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    columns: Mapped[int] = mapped_column(Integer, default=1)
    header: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    technical_table_products: Mapped[list["TechnicalTableProduct"]] = relationship(
        "TechnicalTableProduct", back_populates="technical_table", lazy="selectin"
    )


class TechnicalTableProduct(Base, BaseEntityMixin):
    __tablename__ = "technical_table_products"

    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    technical_table_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("technical_tables.id", ondelete="CASCADE"), nullable=False)

    product: Mapped["Product"] = relationship("Product", back_populates="technical_table_products")
    technical_table: Mapped[TechnicalTable] = relationship("TechnicalTable", back_populates="technical_table_products")
    technical_feature_values: Mapped[list["TechnicalFeatureValue"]] = relationship(
        "TechnicalFeatureValue", back_populates="technical_table_product", lazy="selectin"
    )

    __table_args__ = (
        UniqueConstraint("product_id", "technical_table_id", name="uq_product_tech_table"),
    )


class TechnicalFeatureValue(Base, BaseEntityMixin):
    __tablename__ = "technical_feature_values"

    technical_feature_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("technical_features.id", ondelete="CASCADE"), nullable=False
    )
    category_technical_feature_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("category_technical_features.id", ondelete="SET NULL"), nullable=True
    )
    technical_table_product_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("technical_table_products.id", ondelete="CASCADE"), nullable=True
    )
    technical_feature_enum_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("technical_feature_enums.id", ondelete="SET NULL"), nullable=True
    )
    technical_feature_enum1_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("technical_feature_enums.id", ondelete="SET NULL"), nullable=True
    )

    min_value: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    max_value: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    min_unit: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    max_unit: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    x_value: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    x_unit: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    y_value: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    y_unit: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    z_value: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    z_unit: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    d_value: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    unit: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    s_value: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    e_value: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    e_value1: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    b_value: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    general_feature: Mapped[bool] = mapped_column(Boolean, default=False)

    technical_feature: Mapped[TechnicalFeature] = relationship("TechnicalFeature")
    category_technical_feature: Mapped[Optional[CategoryTechnicalFeature]] = relationship(
        "CategoryTechnicalFeature", back_populates="technical_feature_values"
    )
    technical_table_product: Mapped[Optional[TechnicalTableProduct]] = relationship(
        "TechnicalTableProduct", back_populates="technical_feature_values"
    )
    technical_feature_enum: Mapped[Optional[TechnicalFeatureEnum]] = relationship(
        "TechnicalFeatureEnum", foreign_keys=[technical_feature_enum_id]
    )
    technical_feature_enum1: Mapped[Optional[TechnicalFeatureEnum]] = relationship(
        "TechnicalFeatureEnum", foreign_keys=[technical_feature_enum1_id]
    )

    __table_args__ = (
        UniqueConstraint("technical_table_product_id", "technical_feature_id", name="uq_tech_value_product_feature"),
    )


class Feature(Base, BaseEntityMixin):
    __tablename__ = "features"

    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class ProductAccessory(Base, BaseEntityMixin):
    __tablename__ = "product_accessories"

    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)