
import uuid
from typing import Optional
from datetime import datetime

from sqlalchemy import String, Boolean, ForeignKey, Text, Integer, Numeric, UniqueConstraint, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base, BaseEntityMixin


class Customer(Base, BaseEntityMixin):
    __tablename__ = "customers"

    registration_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    economical_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    company_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    points: Mapped[int] = mapped_column(Integer, default=0)
    refund_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    sheba_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    card_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[user_id])


class Notification(Base, BaseEntityMixin):
    __tablename__ = "notifications"

    name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[user_id])


class NotifiedProduct(Base, BaseEntityMixin):
    __tablename__ = "notified_products"

    variety_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("varieties.id", ondelete="SET NULL"), nullable=True)
    sms_response_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    email_response_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_by_user: Mapped["User"] = relationship("User", back_populates="notified_products")
    variety: Mapped[Optional["Variety"]] = relationship("Variety")

    __table_args__ = (
        UniqueConstraint("variety_id", "created_by_user_id", name="uq_notified_product_user"),
    )


class SearchHistory(Base, BaseEntityMixin):
    __tablename__ = "search_histories"

    title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    price: Mapped[Optional[float]] = mapped_column(Numeric(14, 2), nullable=True)
    category_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    category: Mapped[Optional["Category"]] = relationship("Category")
    user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[user_id])
    search_details: Mapped[list["SearchDetail"]] = relationship("SearchDetail", back_populates="search_history", lazy="selectin")


class SearchDetail(Base, BaseEntityMixin):
    __tablename__ = "search_details"

    search_history_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("search_histories.id", ondelete="CASCADE"), nullable=False)
    min_product_feature_value_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    max_product_feature_value_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)

    search_history: Mapped[SearchHistory] = relationship("SearchHistory", back_populates="search_details")


class UserAction(Base, BaseEntityMixin):
    __tablename__ = "user_actions"

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    action_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    product_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL"), nullable=True)


class Comment(Base, BaseEntityMixin):
    __tablename__ = "comments"

    rate: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    count_of_likes: Mapped[int] = mapped_column(Integer, default=0)
    count_of_dislikes: Mapped[int] = mapped_column(Integer, default=0)
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    is_buyer: Mapped[bool] = mapped_column(Boolean, default=False)
    is_reply: Mapped[bool] = mapped_column(Boolean, default=False)
    answered_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    product_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL"), nullable=True)

    created_by_user: Mapped["User"] = relationship("User", foreign_keys="Comment.created_by_user_id", back_populates="comments")
    answered_by_user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[answered_by_user_id])
    product: Mapped["Product"] = relationship("Product", back_populates="comments")


class Media(Base, BaseEntityMixin):
    __tablename__ = "medias"

    url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    display_photo: Mapped[bool] = mapped_column(Boolean, default=False)
    poster_image: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    picture_order: Mapped[int] = mapped_column(Integer, default=0)
    product_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    category_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True)

    product: Mapped[Optional["Product"]] = relationship("Product")
    category: Mapped[Optional["Category"]] = relationship("Category", back_populates="medias")