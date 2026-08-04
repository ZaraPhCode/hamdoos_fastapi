import uuid
from typing import Optional
from datetime import datetime

from sqlalchemy import (
    String, Boolean, DateTime, ForeignKey, Text, Integer, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base, BaseEntityMixin
from app.models.enum_types import GenderEnum, IdentityStatusEnum, IdentityTypeEnum, OperationTypeEnum


class User(Base, BaseEntityMixin):
    __tablename__ = "Users"

    user_name: Mapped[str] = mapped_column("UserName", String(256), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column("Email", String(256), nullable=False)
    phone_number: Mapped[str] = mapped_column("PhoneNumber", String(450), unique=True, nullable=False, index=True)
    phone_number_confirmed: Mapped[bool] = mapped_column("PhoneNumberConfirmed", Boolean, default=False)
    email_confirmed: Mapped[bool] = mapped_column("EmailConfirmed", Boolean, default=False)
    first_name: Mapped[str] = mapped_column("FirstName", String(25), nullable=False)
    last_name: Mapped[str] = mapped_column("LastName", String(25), nullable=False)
    national_id: Mapped[Optional[str]] = mapped_column("NationalId", String(10), nullable=True)
    gender: Mapped[str] = mapped_column("Gender", GenderEnum, nullable=False, default="Unknown")
    password_hash: Mapped[Optional[str]] = mapped_column("PasswordHash", Text, nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column("AvatarUrl", String(500), nullable=True)
    has_password: Mapped[bool] = mapped_column("HasPassword", Boolean, default=False)
    count_of_completed_information: Mapped[int] = mapped_column("CountOfCompletedInformation", Integer, default=0)
    next_order_id: Mapped[Optional[uuid.UUID]] = mapped_column("NextOrderId", UUID(as_uuid=True), ForeignKey("Orders.Id", use_alter=True), nullable=True)
    access_failed_count: Mapped[int] = mapped_column("AccessFailedCount", Integer, default=0)
    lockout_enabled: Mapped[bool] = mapped_column("LockoutEnabled", Boolean, default=False)
    lockout_end: Mapped[Optional[datetime]] = mapped_column("LockoutEnd", DateTime(timezone=True), nullable=True)
    two_factor_enabled: Mapped[bool] = mapped_column("TwoFactorEnabled", Boolean, default=False)
    security_stamp: Mapped[Optional[str]] = mapped_column("SecurityStamp", Text, nullable=True)
    concurrency_stamp: Mapped[Optional[str]] = mapped_column("ConcurrencyStamp", Text, nullable=True)
    normalized_user_name: Mapped[Optional[str]] = mapped_column("NormalizedUserName", String(256), nullable=True)
    normalized_email: Mapped[Optional[str]] = mapped_column("NormalizedEmail", String(256), nullable=True)

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

    @property
    def is_authenticated(self) -> bool:
        return True


class Role(Base, BaseEntityMixin):
    __tablename__ = "Roles"

    name: Mapped[str] = mapped_column("Name", String(256), unique=True, nullable=False, index=True)
    normalized_name: Mapped[Optional[str]] = mapped_column("NormalizedName", String(256), nullable=True)
    description: Mapped[Optional[str]] = mapped_column("Description", Text, nullable=True)
    concurrency_stamp: Mapped[Optional[str]] = mapped_column("ConcurrencyStamp", Text, nullable=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column("UserId", UUID(as_uuid=True), nullable=True)

    role_claims: Mapped[list["RoleClaim"]] = relationship("RoleClaim", back_populates="role", lazy="selectin")
    user_roles: Mapped[list["UserRole"]] = relationship("UserRole", back_populates="role", lazy="selectin")


class UserRole(Base, BaseEntityMixin):
    __tablename__ = "UserRoles"

    user_id: Mapped[uuid.UUID] = mapped_column("UserId", UUID(as_uuid=True), ForeignKey("Users.Id", ondelete="CASCADE"), nullable=False)
    role_id: Mapped[uuid.UUID] = mapped_column("RoleId", UUID(as_uuid=True), ForeignKey("Roles.Id", ondelete="CASCADE"), nullable=False)

    user: Mapped[User] = relationship("User", foreign_keys=[user_id], back_populates="roles")
    role: Mapped[Role] = relationship("Role", back_populates="user_roles")

    __table_args__ = (
        UniqueConstraint("UserId", "RoleId", name="uq_user_role"),
    )


class RoleClaim(Base, BaseEntityMixin):
    __tablename__ = "RoleClaims"

    role_id: Mapped[uuid.UUID] = mapped_column("RoleId", UUID(as_uuid=True), ForeignKey("Roles.Id", ondelete="CASCADE"), nullable=False)
    claim_type: Mapped[str] = mapped_column("ClaimType", Text, nullable=False)
    claim_value: Mapped[str] = mapped_column("ClaimValue", Text, nullable=False)
    operation_type: Mapped[str] = mapped_column("OperationType", OperationTypeEnum, nullable=False, default="Unknown")
    operation_name: Mapped[str] = mapped_column("OperationName", Text, nullable=False)

    role: Mapped[Role] = relationship("Role", back_populates="role_claims")


class UserClaim(Base, BaseEntityMixin):
    """.NET AspNetUserClaims equivalent: user-scoped claims (added to match .NET schema)."""

    __tablename__ = "UserClaims"

    user_id: Mapped[uuid.UUID] = mapped_column("UserId", UUID(as_uuid=True), ForeignKey("Users.Id", ondelete="CASCADE"), nullable=False)
    claim_type: Mapped[str] = mapped_column("ClaimType", Text, nullable=False)
    claim_value: Mapped[str] = mapped_column("ClaimValue", Text, nullable=False)

    user: Mapped[User] = relationship("User", foreign_keys=[user_id])


class Claim(Base, BaseEntityMixin):
    __tablename__ = "Claims"

    type: Mapped[str] = mapped_column("Type", Text, nullable=False)
    operation_type: Mapped[str] = mapped_column("OperationType", OperationTypeEnum, nullable=False, default="Unknown")

    __table_args__ = (
        UniqueConstraint("Type", "OperationType", name="uq_claim_type_op"),
    )


class IdentityInformation(Base, BaseEntityMixin):
    __tablename__ = "IdentityInformations"

    user_id: Mapped[uuid.UUID] = mapped_column("UserId", UUID(as_uuid=True), ForeignKey("Users.Id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column("Name", String(450), nullable=False)
    national_code_or_id: Mapped[str] = mapped_column("NationalCodeOrId", String(12), nullable=False)
    economic_code: Mapped[Optional[str]] = mapped_column("EconomicCode", String(14), nullable=True)
    postal_code: Mapped[str] = mapped_column("PostalCode", String(10), nullable=False)
    type: Mapped[str] = mapped_column("Type", IdentityTypeEnum, nullable=False, default="Real")
    status: Mapped[str] = mapped_column("Status", IdentityStatusEnum, nullable=False, default="AwaitingConfirmation")
    final_consumer: Mapped[bool] = mapped_column("FinalConsumer", Boolean, default=False)
    address: Mapped[str] = mapped_column("Address", Text, nullable=False)
    city: Mapped[str] = mapped_column("City", Text, nullable=False)
    province: Mapped[str] = mapped_column("Province", Text, nullable=False)
    country: Mapped[str] = mapped_column("Country", Text, nullable=False)
    phone_number: Mapped[str] = mapped_column("PhoneNumber", Text, nullable=False)

    user: Mapped[User] = relationship("User", foreign_keys=[user_id], back_populates="identity_informations")

    __table_args__ = (
        UniqueConstraint("Name", "UserId", name="uq_identity_name_user"),
        UniqueConstraint("NationalCodeOrId", "UserId", name="uq_identity_national_user"),
    )


class UserLogin(Base, BaseEntityMixin):
    __tablename__ = "UserLogins"

    user_id: Mapped[uuid.UUID] = mapped_column("UserId", UUID(as_uuid=True), ForeignKey("Users.Id", ondelete="CASCADE"), nullable=False)
    login_provider: Mapped[str] = mapped_column("LoginProvider", String(256), nullable=False)
    provider_key: Mapped[str] = mapped_column("ProviderKey", String(256), nullable=False)
    provider_display_name: Mapped[Optional[str]] = mapped_column("ProviderDisplayName", String(256), nullable=True)


class UserToken(Base, BaseEntityMixin):
    __tablename__ = "UserTokens"

    user_id: Mapped[uuid.UUID] = mapped_column("UserId", UUID(as_uuid=True), ForeignKey("Users.Id", ondelete="CASCADE"), nullable=False)
    login_provider: Mapped[str] = mapped_column("LoginProvider", String(256), nullable=False)
    name: Mapped[str] = mapped_column("Name", String(256), nullable=False)
    value: Mapped[Optional[str]] = mapped_column("Value", Text, nullable=True)