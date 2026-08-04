import uuid
from typing import Optional

from sqlalchemy import (
    String, Boolean, ForeignKey, Text, Integer, Numeric, Float, UniqueConstraint, Index
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base, BaseEntityMixin


class TechnicalFeature(Base, BaseEntityMixin):
    __tablename__ = "TechnicalFeatures"

    name: Mapped[str] = mapped_column("Name", Text, nullable=False)
    fa_name: Mapped[str] = mapped_column("FaName", Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column("Description", Text, nullable=True)
    display_format: Mapped[str] = mapped_column("DisplayFormat", Text, nullable=False)
    priority: Mapped[int] = mapped_column("Priority", Integer, nullable=False, default=0)
    linear_display: Mapped[Optional[str]] = mapped_column("LinearDisplay", Text, nullable=True)
    d_value: Mapped[bool] = mapped_column("DValue", Boolean, default=False)
    unit: Mapped[bool] = mapped_column("Unit", Boolean, default=False)
    s_value: Mapped[bool] = mapped_column("SValue", Boolean, default=False)
    e_value: Mapped[bool] = mapped_column("EValue", Boolean, default=False)
    e_value1: Mapped[bool] = mapped_column("EValue1", Boolean, default=False)
    b_value: Mapped[bool] = mapped_column("BValue", Boolean, default=False)
    min_value: Mapped[bool] = mapped_column("MinValue", Boolean, default=False)
    min_unit: Mapped[bool] = mapped_column("MinUnit", Boolean, default=False)
    max_value: Mapped[bool] = mapped_column("MaxValue", Boolean, default=False)
    max_unit: Mapped[bool] = mapped_column("MaxUnit", Boolean, default=False)
    x_value: Mapped[bool] = mapped_column("XValue", Boolean, default=False)
    x_unit: Mapped[bool] = mapped_column("XUnit", Boolean, default=False)
    y_value: Mapped[bool] = mapped_column("YValue", Boolean, default=False)
    y_unit: Mapped[bool] = mapped_column("YUnit", Boolean, default=False)
    z_value: Mapped[bool] = mapped_column("ZValue", Boolean, default=False)
    z_unit: Mapped[bool] = mapped_column("ZUnit", Boolean, default=False)
    columns: Mapped[int] = mapped_column("Columns", Integer, nullable=False, default=1)
    visible_in_schema: Mapped[bool] = mapped_column("VisibleInSchema", Boolean, default=True)

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
    __tablename__ = "TechnicalFeatureEnums"

    name: Mapped[str] = mapped_column("Name", Text, nullable=False)
    persian_name: Mapped[str] = mapped_column("PersianName", Text, nullable=False)
    technical_feature_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        "TechnicalFeatureId", UUID(as_uuid=True), ForeignKey("TechnicalFeatures.Id", ondelete="RESTRICT"), nullable=True
    )
    technical_feature1_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        "TechnicalFeature1Id", UUID(as_uuid=True), ForeignKey("TechnicalFeatures.Id", ondelete="RESTRICT"), nullable=True
    )

    technical_feature: Mapped[Optional[TechnicalFeature]] = relationship(
        "TechnicalFeature", back_populates="technical_feature_enums", foreign_keys=[technical_feature_id]
    )
    technical_feature1: Mapped[Optional[TechnicalFeature]] = relationship(
        "TechnicalFeature", back_populates="technical_feature_enums1", foreign_keys=[technical_feature1_id]
    )


class CategoryTechnicalFeature(Base, BaseEntityMixin):
    __tablename__ = "CategoryTechnicalFeatures"

    category_id: Mapped[uuid.UUID] = mapped_column("CategoryId", UUID(as_uuid=True), ForeignKey("Categories.Id", ondelete="CASCADE"), nullable=False)
    technical_feature_id: Mapped[uuid.UUID] = mapped_column("TechnicalFeatureId", UUID(as_uuid=True), ForeignKey("TechnicalFeatures.Id", ondelete="CASCADE"), nullable=False)

    category: Mapped["Category"] = relationship("Category", back_populates="category_technical_features")
    technical_feature: Mapped[TechnicalFeature] = relationship("TechnicalFeature", back_populates="category_technical_features")
    technical_feature_values: Mapped[list["TechnicalFeatureValue"]] = relationship(
        "TechnicalFeatureValue", back_populates="category_technical_feature", lazy="selectin"
    )

    __table_args__ = (
        UniqueConstraint("CategoryId", "TechnicalFeatureId", name="uq_category_tech_feature"),
        Index("ix_category_technical_feature", "CategoryId", "TechnicalFeatureId", unique=True),
    )


class TechnicalTable(Base, BaseEntityMixin):
    __tablename__ = "TechnicalTables"

    title: Mapped[str] = mapped_column("Title", Text, nullable=False)
    en_title: Mapped[str] = mapped_column("EnTitle", Text, nullable=False)
    columns: Mapped[int] = mapped_column("Columns", Integer, nullable=False, default=1)
    header: Mapped[str] = mapped_column("Header", Text, nullable=False)

    technical_table_products: Mapped[list["TechnicalTableProduct"]] = relationship(
        "TechnicalTableProduct", back_populates="technical_table", lazy="selectin"
    )


class TechnicalTableProduct(Base, BaseEntityMixin):
    __tablename__ = "TechnicalTableProducts"

    product_id: Mapped[uuid.UUID] = mapped_column("ProductId", UUID(as_uuid=True), ForeignKey("Products.Id", ondelete="CASCADE"), nullable=False)
    technical_table_id: Mapped[uuid.UUID] = mapped_column("TechnicalTableId", UUID(as_uuid=True), ForeignKey("TechnicalTables.Id", ondelete="CASCADE"), nullable=False)

    product: Mapped["Product"] = relationship("Product", back_populates="technical_table_products")
    technical_table: Mapped[TechnicalTable] = relationship("TechnicalTable", back_populates="technical_table_products")
    technical_feature_values: Mapped[list["TechnicalFeatureValue"]] = relationship(
        "TechnicalFeatureValue", back_populates="technical_table_product", lazy="selectin"
    )

    __table_args__ = (
        UniqueConstraint("ProductId", "TechnicalTableId", name="uq_product_tech_table"),
    )


class TechnicalFeatureValue(Base, BaseEntityMixin):
    __tablename__ = "TechnicalFeatureValues"

    technical_feature_id: Mapped[uuid.UUID] = mapped_column(
        "TechnicalFeatureId", UUID(as_uuid=True), ForeignKey("TechnicalFeatures.Id", ondelete="CASCADE"), nullable=False
    )
    category_technical_feature_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        "CategoryTechnicalFeatureId", UUID(as_uuid=True), ForeignKey("CategoryTechnicalFeatures.Id", ondelete="SET NULL"), nullable=True
    )
    technical_table_product_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        "TechnicalTableProductId", UUID(as_uuid=True), ForeignKey("TechnicalTableProducts.Id", ondelete="CASCADE"), nullable=True
    )
    technical_feature_enum_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        "TechnicalFeatureEnumId", UUID(as_uuid=True), ForeignKey("TechnicalFeatureEnums.Id", ondelete="SET NULL"), nullable=True
    )
    technical_feature_enum1_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        "TechnicalFeatureEnum1Id", UUID(as_uuid=True), ForeignKey("TechnicalFeatureEnums.Id", ondelete="SET NULL"), nullable=True
    )

    min_value: Mapped[Optional[float]] = mapped_column("MinValue", Float, nullable=True)
    max_value: Mapped[Optional[float]] = mapped_column("MaxValue", Float, nullable=True)
    min_unit: Mapped[Optional[str]] = mapped_column("MinUnit", Text, nullable=True)
    max_unit: Mapped[Optional[str]] = mapped_column("MaxUnit", Text, nullable=True)
    x_value: Mapped[Optional[float]] = mapped_column("XValue", Float, nullable=True)
    x_unit: Mapped[Optional[str]] = mapped_column("XUnit", Text, nullable=True)
    y_value: Mapped[Optional[float]] = mapped_column("YValue", Float, nullable=True)
    y_unit: Mapped[Optional[str]] = mapped_column("YUnit", Text, nullable=True)
    z_value: Mapped[Optional[float]] = mapped_column("ZValue", Float, nullable=True)
    z_unit: Mapped[Optional[str]] = mapped_column("ZUnit", Text, nullable=True)
    d_value: Mapped[Optional[float]] = mapped_column("DValue", Float, nullable=True)
    unit: Mapped[Optional[str]] = mapped_column("Unit", Text, nullable=True)
    s_value: Mapped[Optional[str]] = mapped_column("SValue", Text, nullable=True)
    e_value: Mapped[Optional[str]] = mapped_column("EValue", String(200), nullable=True)
    e_value1: Mapped[Optional[str]] = mapped_column("EValue1", String(200), nullable=True)
    b_value: Mapped[Optional[bool]] = mapped_column("BValue", Boolean, nullable=True)
    general_feature: Mapped[bool] = mapped_column("GeneralFeature", Boolean, nullable=False, default=False)

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
        UniqueConstraint("TechnicalTableProductId", "TechnicalFeatureId", name="uq_tech_value_product_feature"),
    )


class Feature(Base, BaseEntityMixin):
    __tablename__ = "Features"

    product_id: Mapped[uuid.UUID] = mapped_column("ProductId", UUID(as_uuid=True), ForeignKey("Products.Id", ondelete="CASCADE"), nullable=False)
    description: Mapped[Optional[str]] = mapped_column("Description", Text, nullable=True)


class ProductAccessory(Base, BaseEntityMixin):
    __tablename__ = "ProductAccessories"

    product_id: Mapped[uuid.UUID] = mapped_column("ProductId", UUID(as_uuid=True), ForeignKey("Products.Id", ondelete="CASCADE"), nullable=False)
    name: Mapped[Optional[str]] = mapped_column("Name", String(200), nullable=True)