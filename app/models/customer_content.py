import uuid
from typing import Optional
from datetime import datetime

from sqlalchemy import String, Boolean, ForeignKey, Text, Integer, Numeric, UniqueConstraint, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base, BaseEntityMixin
from app.models.enum_types import (
    CustomerTypeEnum, RefundMethodEnum, UserActionTypeEnum, RateEnum, ContentTypeEnum,
)


class Customer(Base, BaseEntityMixin):
    __tablename__ = "Customers"

    registration_number: Mapped[Optional[str]] = mapped_column("RegistrationNumber", String(100), nullable=True)
    economical_number: Mapped[Optional[str]] = mapped_column("EconomicalNumber", String(100), nullable=True)
    company_name: Mapped[Optional[str]] = mapped_column("CompanyName", String(200), nullable=True)
    type: Mapped[Optional[str]] = mapped_column("Type", CustomerTypeEnum, nullable=True)
    is_confirmed: Mapped[bool] = mapped_column("IsConfirmed", Boolean, default=False)
    points: Mapped[int] = mapped_column("Points", Integer, default=0)
    refund_method: Mapped[Optional[str]] = mapped_column("RefundMethod", RefundMethodEnum, nullable=True)
    sheba_number: Mapped[Optional[str]] = mapped_column("ShebaNumber", String(50), nullable=True)
    card_number: Mapped[Optional[str]] = mapped_column("CardNumber", String(50), nullable=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column("UserId", UUID(as_uuid=True), ForeignKey("Users.Id", ondelete="SET NULL"), nullable=True)

    user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[user_id])


class Notification(Base, BaseEntityMixin):
    __tablename__ = "Notifications"

    name: Mapped[Optional[str]] = mapped_column("Name", String(200), nullable=True)
    description: Mapped[Optional[str]] = mapped_column("Description", Text, nullable=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column("UserId", UUID(as_uuid=True), ForeignKey("Users.Id", ondelete="SET NULL"), nullable=True)

    user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[user_id])


class NotifiedProduct(Base, BaseEntityMixin):
    __tablename__ = "NotifiedProducts"

    variety_id: Mapped[uuid.UUID] = mapped_column("VarietyId", UUID(as_uuid=True), ForeignKey("Varieties.Id", ondelete="SET NULL"), nullable=False)
    sms_response_date: Mapped[Optional[datetime]] = mapped_column("SmsResponseDate", DateTime(timezone=True), nullable=True)
    email_response_date: Mapped[Optional[datetime]] = mapped_column("EmailResponseDate", DateTime(timezone=True), nullable=True)

    created_by_user: Mapped["User"] = relationship("User", back_populates="notified_products")
    variety: Mapped[Optional["Variety"]] = relationship("Variety")

    __table_args__ = (
        UniqueConstraint("VarietyId", "CreatedByUserId", name="uq_notified_product_user"),
    )


class SearchHistory(Base, BaseEntityMixin):
    __tablename__ = "SearchHistories"

    title: Mapped[Optional[str]] = mapped_column("Title", String(200), nullable=True)
    description: Mapped[Optional[str]] = mapped_column("Description", Text, nullable=True)
    price: Mapped[Optional[float]] = mapped_column("Price", Numeric(14, 2), nullable=True)
    category_id: Mapped[Optional[uuid.UUID]] = mapped_column("CategoryId", UUID(as_uuid=True), ForeignKey("Categories.Id", ondelete="SET NULL"), nullable=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column("UserId", UUID(as_uuid=True), ForeignKey("Users.Id", ondelete="SET NULL"), nullable=True)

    category: Mapped[Optional["Category"]] = relationship("Category")
    user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[user_id])
    search_details: Mapped[list["SearchDetail"]] = relationship("SearchDetail", back_populates="search_history", lazy="selectin")


class SearchDetail(Base, BaseEntityMixin):
    __tablename__ = "SearchDetails"

    search_history_id: Mapped[uuid.UUID] = mapped_column("SearchHistoryId", UUID(as_uuid=True), ForeignKey("SearchHistories.Id", ondelete="CASCADE"), nullable=False)
    min_product_feature_value_id: Mapped[Optional[uuid.UUID]] = mapped_column("MinProductFeatureValueId", UUID(as_uuid=True), nullable=True)
    max_product_feature_value_id: Mapped[Optional[uuid.UUID]] = mapped_column("MaxProductFeatureValueId", UUID(as_uuid=True), nullable=True)

    search_history: Mapped[SearchHistory] = relationship("SearchHistory", back_populates="search_details")


class UserAction(Base, BaseEntityMixin):
    __tablename__ = "UserActions"

    notes: Mapped[Optional[str]] = mapped_column("Notes", Text, nullable=True)
    action_type: Mapped[Optional[str]] = mapped_column("ActionType", UserActionTypeEnum, nullable=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column("UserId", UUID(as_uuid=True), ForeignKey("Users.Id", ondelete="SET NULL"), nullable=True)
    product_id: Mapped[Optional[uuid.UUID]] = mapped_column("ProductId", UUID(as_uuid=True), ForeignKey("Products.Id", ondelete="SET NULL"), nullable=True)


class Comment(Base, BaseEntityMixin):
    __tablename__ = "Comments"

    rate: Mapped[str] = mapped_column("Rate", RateEnum, nullable=False, default="NotEntered")
    name: Mapped[str] = mapped_column("Name", Text, nullable=False)
    description: Mapped[str] = mapped_column("Description", Text, nullable=False)
    count_of_likes: Mapped[int] = mapped_column("CountOfLikes", Integer, default=0)
    count_of_dislikes: Mapped[int] = mapped_column("CountOfDislikes", Integer, default=0)
    is_confirmed: Mapped[bool] = mapped_column("IsConfirmed", Boolean, default=False)
    is_buyer: Mapped[bool] = mapped_column("IsBuyer", Boolean, default=False)
    is_reply: Mapped[bool] = mapped_column("IsReply", Boolean, default=False)
    answered_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column("AnsweredByUserId", UUID(as_uuid=True), ForeignKey("Users.Id", ondelete="SET NULL"), nullable=True)
    product_id: Mapped[uuid.UUID] = mapped_column("ProductId", UUID(as_uuid=True), ForeignKey("Products.Id", ondelete="SET NULL"), nullable=False)

    created_by_user: Mapped["User"] = relationship("User", foreign_keys="Comment.created_by_user_id", back_populates="comments")
    answered_by_user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[answered_by_user_id])
    product: Mapped["Product"] = relationship("Product", back_populates="comments")


class Media(Base, BaseEntityMixin):
    __tablename__ = "Medias"

    url: Mapped[str] = mapped_column("URL", Text, nullable=False)
    title: Mapped[str] = mapped_column("Title", Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column("Description", Text, nullable=True)
    display_photo: Mapped[bool] = mapped_column("DisplayPhoto", Boolean, default=False)
    is_video: Mapped[bool] = mapped_column("IsVideo", Boolean, default=False)
    poster_image: Mapped[bool] = mapped_column("PosterImage", Boolean, default=False)
    type: Mapped[str] = mapped_column("Type", ContentTypeEnum, nullable=False, default="Unknown")
    picture_order: Mapped[int] = mapped_column("PictureOrder", Integer, nullable=False, default=0)
    product_id: Mapped[Optional[uuid.UUID]] = mapped_column("ProductId", UUID(as_uuid=True), ForeignKey("Products.Id", ondelete="SET NULL"), nullable=True)
    category_id: Mapped[Optional[uuid.UUID]] = mapped_column("CategoryId", UUID(as_uuid=True), ForeignKey("Categories.Id", ondelete="SET NULL"), nullable=True)

    product: Mapped[Optional["Product"]] = relationship("Product")
    category: Mapped[Optional["Category"]] = relationship("Category", back_populates="medias")