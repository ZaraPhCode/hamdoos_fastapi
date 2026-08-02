
import uuid
from typing import Optional

from sqlalchemy import String, Boolean, ForeignKey, Text, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base, BaseEntityMixin


class Manufacturer(Base, BaseEntityMixin):
    __tablename__ = "manufacturers"

    name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    telephone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    website_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class ASHAInfo(Base, BaseEntityMixin):
    __tablename__ = "asha_infos"

    logo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    footer_info: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    bank_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    account_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    card_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    sheba: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    account_owner: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    about_us: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    how_to_buy: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    free_delivery: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    contact_us: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    technical_support: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    copy_right: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class Capability(Base, BaseEntityMixin):
    __tablename__ = "capabilities"

    ability: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    enable: Mapped[bool] = mapped_column(Boolean, default=False)


class Paragraph(Base, BaseEntityMixin):
    __tablename__ = "paragraphs"

    title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)