import uuid
from typing import Optional

from sqlalchemy import String, Boolean, ForeignKey, Text, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base, BaseEntityMixin
from app.models.enum_types import ManufacturerTypeEnum


class Manufacturer(Base, BaseEntityMixin):
    __tablename__ = "Manufacturers"

    name: Mapped[Optional[str]] = mapped_column("Name", String(200), nullable=True)
    telephone: Mapped[Optional[str]] = mapped_column("Telephone", String(50), nullable=True)
    website_url: Mapped[Optional[str]] = mapped_column("WebsiteUrl", String(500), nullable=True)
    email: Mapped[Optional[str]] = mapped_column("Email", String(200), nullable=True)
    type: Mapped[Optional[str]] = mapped_column("Type", ManufacturerTypeEnum, nullable=True)
    address: Mapped[Optional[str]] = mapped_column("Address", Text, nullable=True)


class ASHAInfo(Base, BaseEntityMixin):
    __tablename__ = "ASHAInfos"

    logo_url: Mapped[Optional[str]] = mapped_column("LogoUrl", String(500), nullable=True)
    footer_info: Mapped[Optional[str]] = mapped_column("FooterInfo", Text, nullable=True)
    bank_name: Mapped[Optional[str]] = mapped_column("BankName", String(200), nullable=True)
    account_number: Mapped[Optional[str]] = mapped_column("AccountNumber", String(100), nullable=True)
    card_number: Mapped[Optional[str]] = mapped_column("CardNumber", String(100), nullable=True)
    sheba: Mapped[Optional[str]] = mapped_column("Sheba", String(50), nullable=True)
    account_owner: Mapped[Optional[str]] = mapped_column("AccountOwner", String(200), nullable=True)
    about_us: Mapped[Optional[str]] = mapped_column("AboutUs", Text, nullable=True)
    how_to_buy: Mapped[Optional[str]] = mapped_column("HowToBuy", Text, nullable=True)
    free_delivery: Mapped[Optional[str]] = mapped_column("FreeDelivery", Text, nullable=True)
    contact_us: Mapped[Optional[str]] = mapped_column("ContactUs", Text, nullable=True)
    technical_support: Mapped[Optional[str]] = mapped_column("TechnicalSupport", Text, nullable=True)
    copy_right: Mapped[Optional[str]] = mapped_column("CopyRight", Text, nullable=True)


class Capability(Base, BaseEntityMixin):
    __tablename__ = "Capabilities"

    ability: Mapped[Optional[str]] = mapped_column("Ability", String(100), nullable=True)
    enable: Mapped[bool] = mapped_column("Enable", Boolean, default=False)


class Paragraph(Base, BaseEntityMixin):
    __tablename__ = "Paragraphs"

    title: Mapped[Optional[str]] = mapped_column("Title", String(200), nullable=True)
    description: Mapped[Optional[str]] = mapped_column("Description", Text, nullable=True)