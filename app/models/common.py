
import uuid
from typing import Optional
from datetime import datetime

from sqlalchemy import (
    Column, String, Boolean, DateTime, ForeignKey, Text, Integer, Numeric, UniqueConstraint, Float
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.core.base import Base, BaseEntityMixin
from app.models.log_enums import (
    LOG_TABLE_NAME,
    LOG_TYPE_NAME,
    resolve_table_int,
    resolve_type_int as _resolve_type_int,
)


class ProvinceCity(Base, BaseEntityMixin):
    __tablename__ = "province_cities"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    int_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, unique=True)
    province_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    cities: Mapped[list["City"]] = relationship("City", back_populates="province", lazy="selectin")


class City(Base, BaseEntityMixin):
    __tablename__ = "cities"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    province_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("province_cities.int_id"), nullable=True)

    province: Mapped[Optional[ProvinceCity]] = relationship("ProvinceCity", back_populates="cities")


class Address(Base, BaseEntityMixin):
    __tablename__ = "addresses"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    postal_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    address_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    phone_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    phone_number_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    telephone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    alias: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    province_city_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("province_cities.id"), nullable=True)
    province_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], back_populates="addresses")
    province_city: Mapped[Optional[ProvinceCity]] = relationship("ProvinceCity")


class SiteSetting(Base, BaseEntityMixin):
    __tablename__ = "site_settings"

    logo_url: Mapped[Optional[str]] = mapped_column("LogoURL", String(500), nullable=True)
    bank_name: Mapped[Optional[str]] = mapped_column("BankName", String(200), nullable=True)
    account_number: Mapped[Optional[str]] = mapped_column("AccountNumber", String(100), nullable=True)
    card_number: Mapped[Optional[str]] = mapped_column("CardNumber", String(100), nullable=True)
    sheba_number: Mapped[Optional[str]] = mapped_column("ShebaNumber", String(100), nullable=True)
    account_owner: Mapped[Optional[str]] = mapped_column("AccountOwner", String(200), nullable=True)
    about_us: Mapped[Optional[str]] = mapped_column("AboutUs", Text, nullable=True)
    how_to_buy: Mapped[Optional[str]] = mapped_column("HowToBuy", Text, nullable=True)
    free_delivery: Mapped[Optional[str]] = mapped_column("FreeDelivery", Text, nullable=True)
    contact_us: Mapped[Optional[str]] = mapped_column("ContactUs", Text, nullable=True)
    technical_support: Mapped[Optional[str]] = mapped_column("TechnicalSupport", Text, nullable=True)
    email: Mapped[Optional[str]] = mapped_column("Email", String(200), nullable=True)
    telephone: Mapped[Optional[str]] = mapped_column("Telephone", String(50), nullable=True)
    address: Mapped[Optional[str]] = mapped_column("Address", Text, nullable=True)
    copy_right: Mapped[Optional[str]] = mapped_column("CopyRight", Text, nullable=True)
    disable_captcha: Mapped[bool] = mapped_column("DisableCaptcha", Boolean, default=False)
    free_postage_limit: Mapped[Optional[float]] = mapped_column("FreePostageLimit", Numeric(14, 2), nullable=True)
    free_packaging: Mapped[bool] = mapped_column("FreePackaging", Boolean, default=False)
    free_postage: Mapped[bool] = mapped_column("FreePostage", Boolean, default=False)
    payment_status_per_hour: Mapped[Optional[float]] = mapped_column("PaymentStatusPerHour", Float, nullable=True)
    postal_code: Mapped[Optional[str]] = mapped_column("PostalCode", String(10), nullable=True)
    top_category_id: Mapped[Optional[uuid.UUID]] = mapped_column("TopCategoryId", UUID(as_uuid=True), ForeignKey("categories.id"), nullable=True)
    middle_category_id: Mapped[Optional[uuid.UUID]] = mapped_column("MiddleCategoryId", UUID(as_uuid=True), ForeignKey("categories.id"), nullable=True)
    bottom_category_id: Mapped[Optional[uuid.UUID]] = mapped_column("BottomCategoryId", UUID(as_uuid=True), ForeignKey("categories.id"), nullable=True)
    top_poster_category_id: Mapped[Optional[uuid.UUID]] = mapped_column("TopPosterCategoryId", UUID(as_uuid=True), ForeignKey("categories.id"), nullable=True)
    mid_left_poster_category_id: Mapped[Optional[uuid.UUID]] = mapped_column("MidLeftPosterCategoryId", UUID(as_uuid=True), ForeignKey("categories.id"), nullable=True)
    mid_right_poster_category_id: Mapped[Optional[uuid.UUID]] = mapped_column("MidRightPosterCategoryId", UUID(as_uuid=True), ForeignKey("categories.id"), nullable=True)
    middle_poster_category_id: Mapped[Optional[uuid.UUID]] = mapped_column("MiddlePosterCategoryId", UUID(as_uuid=True), ForeignKey("categories.id"), nullable=True)
    bottom_poster_category_id: Mapped[Optional[uuid.UUID]] = mapped_column("BottomPosterCategoryId", UUID(as_uuid=True), ForeignKey("categories.id"), nullable=True)
    technical_table_id: Mapped[Optional[uuid.UUID]] = mapped_column("TechnicalTableId", UUID(as_uuid=True), ForeignKey("technical_tables.id"), nullable=True)


class Captcha(Base, BaseEntityMixin):
    __tablename__ = "captchas"

    code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    disable: Mapped[bool] = mapped_column(Boolean, default=False)
    url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)


class BankInfo(Base, BaseEntityMixin):
    __tablename__ = "bank_infos"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    account_owner: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    sheba_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    card_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    bank_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], back_populates="bank_infos")


class MobileNumber(Base, BaseEntityMixin):
    __tablename__ = "mobile_numbers"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    phone_number: Mapped[str] = mapped_column(String(50), nullable=False)

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], back_populates="mobile_numbers")


class SmsCode(Base, BaseEntityMixin):
    __tablename__ = "sms_codes"

    code: Mapped[str] = mapped_column(String(10), nullable=False)
    phone_number: Mapped[str] = mapped_column(String(50), nullable=False)

    created_by_user: Mapped["User"] = relationship("User", back_populates="sms_codes")


class Log(Base, BaseEntityMixin):
    __tablename__ = "logs"

    record_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    record_int_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    table: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    type: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # ── table_name convenience property (mirrors .NET Table enum) ──
    @property
    def table_name(self) -> str:
        return LOG_TABLE_NAME.get(int(self.table or 0), str(self.table or 0))

    @table_name.setter
    def table_name(self, value) -> None:
        self.table = resolve_table_int(value)

    @validates("table")
    def _validate_table(self, key, value):
        return resolve_table_int(value)

    @validates("type")
    def _validate_type(self, key, value):
        return _resolve_type_int(value)

    @property
    def type_name(self) -> str:
        return LOG_TYPE_NAME.get(int(self.type or 0), str(self.type or 0))


class AdminParameter(Base, BaseEntityMixin):
    __tablename__ = "admin_parameters"

    ConfirmOrderPN: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default="")
    ConfrimOrderEm: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default="")