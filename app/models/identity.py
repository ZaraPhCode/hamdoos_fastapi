
import uuid
from typing import Optional
from datetime import datetime

from sqlalchemy import (
    Column, String, Boolean, DateTime, ForeignKey, Text, Integer, UniqueConstraint, Index
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base, BaseEntityMixin


class User(Base, BaseEntityMixin):
    __tablename__ = "users"

    user_name: Mapped[str] = mapped_column(String(256), unique=True, nullable=False, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    phone_number: Mapped[Optional[str]] = mapped_column(String(20), unique=True, nullable=True, index=True)
    phone_number_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    email_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    first_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    national_id: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    has_password: Mapped[bool] = mapped_column(Boolean, default=False)
    count_of_completed_information: Mapped[int] = mapped_column(Integer, default=0)
    next_order_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=True)
    access_failed_count: Mapped[int] = mapped_column(Integer, default=0)
    lockout_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    lockout_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    two_factor_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    security_stamp: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    concurrency_stamp: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    normalized_user_name: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    normalized_email: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)

    # Relationships
    roles: Mapped[list["UserRole"]] = relationship("UserRole", foreign_keys="UserRole.user_id", back_populates="user", lazy="selectin")
    addresses: Mapped[list["Address"]] = relationship("Address", foreign_keys="Address.user_id", back_populates="user", lazy="selectin")
    bank_infos: Mapped[list["BankInfo"]] = relationship("BankInfo", foreign_keys="BankInfo.user_id", back_populates="user", lazy="selectin")
    mobile_numbers: Mapped[list["MobileNumber"]] = relationship("MobileNumber", foreign_keys="MobileNumber.user_id", back_populates="user", lazy="selectin")
    identity_informations: Mapped[list["IdentityInformation"]] = relationship("IdentityInformation", foreign_keys="IdentityInformation.user_id", back_populates="user", lazy="selectin")
    comments: Mapped[list["Comment"]] = relationship("Comment", foreign_keys="Comment.created_by_user_id", back_populates="created_by_user", lazy="selectin")
    orders: Mapped[list["OrderModel"]] = relationship("OrderModel", foreign_keys="OrderModel.user_id", back_populates="user", lazy="selectin")
    invoices: Mapped[list["Invoice"]] = relationship("Invoice", foreign_keys="Invoice.user_id", back_populates="user", lazy="selectin")
    receipts: Mapped[list["Receipt"]] = relationship("Receipt", foreign_keys="Receipt.user_id", back_populates="user", lazy="selectin")
    visited_products: Mapped[list["VisitedProduct"]] = relationship("VisitedProduct", foreign_keys="VisitedProduct.user_id", back_populates="user", lazy="selectin")
    favorite_product_lists: Mapped[list["FavoriteProductList"]] = relationship("FavoriteProductList", foreign_keys="FavoriteProductList.user_id", back_populates="user", lazy="selectin")
    sms_codes: Mapped[list["SmsCode"]] = relationship("SmsCode", back_populates="created_by_user", lazy="selectin")
    payment_requests: Mapped[list["PaymentRequest"]] = relationship("PaymentRequest", foreign_keys="PaymentRequest.user_id", back_populates="user", lazy="selectin")
    notified_products: Mapped[list["NotifiedProduct"]] = relationship("NotifiedProduct", back_populates="created_by_user", lazy="selectin")

    @property
    def full_name(self) -> str:
        return f"{self.first_name or ''} {self.last_name or ''}".strip()


class Role(Base, BaseEntityMixin):
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(256), unique=True, nullable=False, index=True)
    normalized_name: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    concurrency_stamp: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    role_claims: Mapped[list["RoleClaim"]] = relationship("RoleClaim", back_populates="role", lazy="selectin")
    user_roles: Mapped[list["UserRole"]] = relationship("UserRole", back_populates="role", lazy="selectin")


class UserRole(Base, BaseEntityMixin):
    __tablename__ = "user_roles"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)

    user: Mapped[User] = relationship("User", foreign_keys=[user_id], back_populates="roles")
    role: Mapped[Role] = relationship("Role", back_populates="user_roles")

    __table_args__ = (
        UniqueConstraint("user_id", "role_id", name="uq_user_role"),
    )


class RoleClaim(Base, BaseEntityMixin):
    __tablename__ = "role_claims"

    role_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
    claim_type: Mapped[str] = mapped_column(String(256), nullable=False)
    claim_value: Mapped[str] = mapped_column(String(500), nullable=False)
    operation_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    operation_name: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)

    role: Mapped[Role] = relationship("Role", back_populates="role_claims")


class Claim(Base, BaseEntityMixin):
    __tablename__ = "claims"

    type: Mapped[str] = mapped_column(String(256), nullable=False)
    operation_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    __table_args__ = (
        UniqueConstraint("type", "operation_type", name="uq_claim_type_op"),
    )


class IdentityInformation(Base, BaseEntityMixin):
    __tablename__ = "identity_informations"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    national_code_or_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    economic_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    postal_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    final_consumer: Mapped[bool] = mapped_column(Boolean, default=False)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    province: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    phone_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    user: Mapped[User] = relationship("User", foreign_keys=[user_id], back_populates="identity_informations")

    __table_args__ = (
        UniqueConstraint("name", "user_id", name="uq_identity_name_user"),
        UniqueConstraint("national_code_or_id", "user_id", name="uq_identity_national_user"),
    )


class UserLogin(Base, BaseEntityMixin):
    __tablename__ = "user_logins"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    login_provider: Mapped[str] = mapped_column(String(256), nullable=False)
    provider_key: Mapped[str] = mapped_column(String(256), nullable=False)
    provider_display_name: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)


class UserToken(Base, BaseEntityMixin):
    __tablename__ = "user_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    login_provider: Mapped[str] = mapped_column(String(256), nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)