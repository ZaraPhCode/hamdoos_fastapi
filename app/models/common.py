import uuid
from typing import Optional
from datetime import datetime

from sqlalchemy import (
    String, Boolean, DateTime, ForeignKey, Text, Integer, Numeric, UniqueConstraint, Float
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.core.base import Base, BaseEntityMixin
from app.models.enum_types import CountryEnum
from app.models.log_enums import (
    LOG_TABLE_NAME,
    LOG_TYPE_NAME,
    resolve_table_int,
    resolve_type_int as _resolve_type_int,
)


class ProvinceCity(Base, BaseEntityMixin):
    __tablename__ = "ProvinceCities"

    name: Mapped[str] = mapped_column("Name", Text, nullable=False)
    int_id: Mapped[int] = mapped_column("IntId", Integer, nullable=False, unique=True)
    province_id: Mapped[Optional[int]] = mapped_column("ProvinceId", Integer, nullable=True)

    cities: Mapped[list["City"]] = relationship("City", back_populates="province", lazy="selectin")


class City(Base, BaseEntityMixin):
    """FastAPI-only table (not present in .NET)."""

    __tablename__ = "Cities"

    name: Mapped[str] = mapped_column("Name", String(100), nullable=False)
    province_id: Mapped[Optional[int]] = mapped_column("ProvinceId", Integer, ForeignKey("ProvinceCities.IntId"), nullable=True)

    province: Mapped[Optional[ProvinceCity]] = relationship("ProvinceCity", back_populates="cities")


class Address(Base, BaseEntityMixin):
    __tablename__ = "Addresses"

    user_id: Mapped[Optional[uuid.UUID]] = mapped_column("UserId", UUID(as_uuid=True), ForeignKey("Users.Id", ondelete="CASCADE"), nullable=True)
    postal_code: Mapped[str] = mapped_column("PostalCode", Text, nullable=False)
    address_description: Mapped[str] = mapped_column("AddressDescription", Text, nullable=False)
    first_name: Mapped[str] = mapped_column("FirstName", String(255), nullable=False)
    last_name: Mapped[str] = mapped_column("LastName", String(255), nullable=False)
    phone_number: Mapped[str] = mapped_column("PhoneNumber", String(32), nullable=False)
    phone_number_confirmed: Mapped[bool] = mapped_column("PhoneNumberConfirmed", Boolean, default=False)
    telephone: Mapped[Optional[str]] = mapped_column("Telephone", String(32), nullable=True)
    alias: Mapped[Optional[str]] = mapped_column("Alias", Text, nullable=True)
    country: Mapped[str] = mapped_column("Country", CountryEnum, nullable=False, default="Iran")
    province_city_id: Mapped[uuid.UUID] = mapped_column("ProvinceCityId", UUID(as_uuid=True), ForeignKey("ProvinceCities.Id"), nullable=False)
    province_id: Mapped[Optional[int]] = mapped_column("ProvinceId", Integer, nullable=True)

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], back_populates="addresses")
    province_city: Mapped[Optional[ProvinceCity]] = relationship("ProvinceCity")


class SiteSetting(Base, BaseEntityMixin):
    __tablename__ = "SiteSettings"

    logo_url: Mapped[Optional[str]] = mapped_column("LogoURL", Text, nullable=True)
    bank_name: Mapped[Optional[str]] = mapped_column("BankName", Text, nullable=True)
    account_number: Mapped[Optional[str]] = mapped_column("AccountNumber", Text, nullable=True)
    card_number: Mapped[Optional[str]] = mapped_column("CardNumber", Text, nullable=True)
    sheba_number: Mapped[Optional[str]] = mapped_column("ShebaNumber", Text, nullable=True)
    account_owner: Mapped[Optional[str]] = mapped_column("AccountOwner", Text, nullable=True)
    about_us: Mapped[Optional[str]] = mapped_column("AboutUs", Text, nullable=True)
    how_to_buy: Mapped[Optional[str]] = mapped_column("HowToBuy", Text, nullable=True)
    free_delivery: Mapped[Optional[str]] = mapped_column("FreeDelivery", Text, nullable=True)
    contact_us: Mapped[Optional[str]] = mapped_column("ContactUs", Text, nullable=True)
    technical_support: Mapped[Optional[str]] = mapped_column("TechnicalSupport", Text, nullable=True)
    email: Mapped[Optional[str]] = mapped_column("Email", Text, nullable=True)
    telephone: Mapped[Optional[str]] = mapped_column("Telephone", Text, nullable=True)
    address: Mapped[Optional[str]] = mapped_column("Address", Text, nullable=True)
    copy_right: Mapped[Optional[str]] = mapped_column("CopyRight", Text, nullable=True)
    disable_captcha: Mapped[bool] = mapped_column("DisableCaptcha", Boolean, default=False)
    free_postage_limit: Mapped[float] = mapped_column("FreePostageLimit", Numeric(14, 2), nullable=False)
    free_packaging: Mapped[bool] = mapped_column("FreePackaging", Boolean, default=False)
    free_postage: Mapped[bool] = mapped_column("FreePostage", Boolean, default=False)
    payment_status_per_hour: Mapped[float] = mapped_column("PaymentStatusPerHour", Float, nullable=False)
    postal_code: Mapped[str] = mapped_column("PostalCode", String(10), nullable=False)
    top_category_id: Mapped[Optional[uuid.UUID]] = mapped_column("TopCategoryId", UUID(as_uuid=True), ForeignKey("Categories.Id"), nullable=True)
    middle_category_id: Mapped[Optional[uuid.UUID]] = mapped_column("MiddleCategoryId", UUID(as_uuid=True), ForeignKey("Categories.Id"), nullable=True)
    bottom_category_id: Mapped[Optional[uuid.UUID]] = mapped_column("BottomCategoryId", UUID(as_uuid=True), ForeignKey("Categories.Id"), nullable=True)
    top_poster_category_id: Mapped[Optional[uuid.UUID]] = mapped_column("TopPosterCategoryId", UUID(as_uuid=True), ForeignKey("Categories.Id"), nullable=True)
    mid_left_poster_category_id: Mapped[Optional[uuid.UUID]] = mapped_column("MidLeftPosterCategoryId", UUID(as_uuid=True), ForeignKey("Categories.Id"), nullable=True)
    mid_right_poster_category_id: Mapped[Optional[uuid.UUID]] = mapped_column("MidRightPosterCategoryId", UUID(as_uuid=True), ForeignKey("Categories.Id"), nullable=True)
    middle_poster_category_id: Mapped[Optional[uuid.UUID]] = mapped_column("MiddlePosterCategoryId", UUID(as_uuid=True), ForeignKey("Categories.Id"), nullable=True)
    bottom_poster_category_id: Mapped[Optional[uuid.UUID]] = mapped_column("BottomPosterCategoryId", UUID(as_uuid=True), ForeignKey("Categories.Id"), nullable=True)
    technical_table_id: Mapped[Optional[uuid.UUID]] = mapped_column("TechnicalTableId", UUID(as_uuid=True), ForeignKey("TechnicalTables.Id"), nullable=True)

    # Custom image URL substitutes for the homepage posters. When set, they take
    # priority over the poster category image; otherwise the category's
    # poster_image_url is used. Managed in the admin "تنظیمات سایت" form.
    top_poster_image_url: Mapped[Optional[str]] = mapped_column("TopPosterImageUrl", Text, nullable=True)
    middle_poster_image_url: Mapped[Optional[str]] = mapped_column("MiddlePosterImageUrl", Text, nullable=True)
    mid_left_poster_image_url: Mapped[Optional[str]] = mapped_column("MidLeftPosterImageUrl", Text, nullable=True)
    mid_right_poster_image_url: Mapped[Optional[str]] = mapped_column("MidRightPosterImageUrl", Text, nullable=True)
    bottom_poster_image_url: Mapped[Optional[str]] = mapped_column("BottomPosterImageUrl", Text, nullable=True)

    # Sidebar support poster (shown on the homepage/category sidebar). When
    # empty, falls back to SITE_INFO.sidebar.support_image.
    sidebar_support_category_id: Mapped[Optional[uuid.UUID]] = mapped_column("SideBarSupportCategoryId", UUID(as_uuid=True), ForeignKey("Categories.Id"), nullable=True)
    sidebar_support_image_url: Mapped[Optional[str]] = mapped_column("SideBarSupportImageUrl", Text, nullable=True)


class Captcha(Base, BaseEntityMixin):
    __tablename__ = "Captchas"

    code: Mapped[int] = mapped_column("Code", Integer, nullable=False)
    disable: Mapped[bool] = mapped_column("Disable", Boolean, default=False)
    url: Mapped[str] = mapped_column("Url", Text, nullable=False)


class BankInfo(Base, BaseEntityMixin):
    """.NET table is ``BankInfoes``."""

    __tablename__ = "BankInfoes"

    user_id: Mapped[Optional[uuid.UUID]] = mapped_column("UserId", UUID(as_uuid=True), ForeignKey("Users.Id", ondelete="CASCADE"), nullable=True)
    account_owner: Mapped[str] = mapped_column("AccountOwner", Text, nullable=False)
    sheba_number: Mapped[str] = mapped_column("ShebaNumber", Text, nullable=False)
    card_number: Mapped[Optional[str]] = mapped_column("CardNumber", Text, nullable=True)
    bank_name: Mapped[str] = mapped_column("BankName", Text, nullable=False)

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], back_populates="bank_infos")


class MobileNumber(Base, BaseEntityMixin):
    __tablename__ = "MobileNumbers"

    user_id: Mapped[Optional[uuid.UUID]] = mapped_column("UserId", UUID(as_uuid=True), ForeignKey("Users.Id", ondelete="CASCADE"), nullable=True)
    phone_number: Mapped[str] = mapped_column("PhoneNumber", String(32), nullable=False)

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], back_populates="mobile_numbers")


class SmsCode(Base, BaseEntityMixin):
    __tablename__ = "SmsCodes"

    code: Mapped[str] = mapped_column("Code", String(6), nullable=False)
    phone_number: Mapped[Optional[str]] = mapped_column("PhoneNumber", Text, nullable=True)

    created_by_user: Mapped["User"] = relationship("User", back_populates="sms_codes")


class Log(Base, BaseEntityMixin):
    __tablename__ = "Logs"

    record_id: Mapped[Optional[uuid.UUID]] = mapped_column("RecordId", UUID(as_uuid=True), nullable=True)
    record_int_id: Mapped[Optional[int]] = mapped_column("RecordIntId", Integer, nullable=True)
    table: Mapped[int] = mapped_column("Table", Integer, nullable=False, default=0)
    description: Mapped[str] = mapped_column("Description", Text, nullable=False)
    type: Mapped[int] = mapped_column("Type", Integer, nullable=False, default=0)

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
    __tablename__ = "AdminParameters"

    ConfirmOrderPN: Mapped[str] = mapped_column("ConfirmOrderPN", Text, nullable=False, default="")
    ConfrimOrderEm: Mapped[str] = mapped_column("ConfrimOrderEm", Text, nullable=False, default="")


class SiteNotice(Base, BaseEntityMixin):
    """A site-wide message shown as a banner below the site header.

    Admin-managed. Each notice has a type (info / announcement / hint) that maps
    to its own color style (see ``NOTICE_STYLES`` in site_config.py), an optional
    start/end window, and a manual active flag so it can be shown or hidden
    without deleting it.
    """

    __tablename__ = "SiteNotices"

    message: Mapped[str] = mapped_column("Message", Text, nullable=False)
    notice_type: Mapped[str] = mapped_column("NoticeType", String(32), nullable=False, default="Info")
    start_date: Mapped[Optional[datetime]] = mapped_column("StartDate", DateTime(timezone=True), nullable=True)
    end_date: Mapped[Optional[datetime]] = mapped_column("EndDate", DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column("IsActive", Boolean, nullable=False, default=True)