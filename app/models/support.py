import uuid
from typing import Optional

from sqlalchemy import String, ForeignKey, Text, Integer, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base, BaseEntityMixin


class Ticket(Base, BaseEntityMixin):
    __tablename__ = "Tickets"

    name: Mapped[Optional[str]] = mapped_column("Name", String(200), nullable=True)
    email: Mapped[Optional[str]] = mapped_column("Email", String(200), nullable=True)
    telephone: Mapped[Optional[str]] = mapped_column("Telephone", String(50), nullable=True)
    description: Mapped[Optional[str]] = mapped_column("Description", Text, nullable=True)
    subject: Mapped[Optional[str]] = mapped_column("Subject", String(100), nullable=True)
    status: Mapped[Optional[str]] = mapped_column("Status", String(50), nullable=True)
    category: Mapped[Optional[str]] = mapped_column("Category", String(50), nullable=True)
    priority: Mapped[Optional[str]] = mapped_column("Priority", String(50), nullable=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column("UserId", UUID(as_uuid=True), ForeignKey("Users.Id", ondelete="SET NULL"), nullable=True)
    order_id: Mapped[Optional[uuid.UUID]] = mapped_column("OrderId", UUID(as_uuid=True), ForeignKey("Orders.Id", ondelete="SET NULL"), nullable=True)

    chat_messages: Mapped[list["ChatMessage"]] = relationship("ChatMessage", back_populates="ticket", lazy="selectin")
    order: Mapped[Optional["OrderModel"]] = relationship("OrderModel", foreign_keys=[order_id])


class Chat(Base, BaseEntityMixin):
    __tablename__ = "Chats"

    title: Mapped[Optional[str]] = mapped_column("Title", String(200), nullable=True)
    subject: Mapped[Optional[str]] = mapped_column("Subject", String(100), nullable=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column("UserId", UUID(as_uuid=True), ForeignKey("Users.Id", ondelete="SET NULL"), nullable=True)

    chat_messages: Mapped[list["ChatMessage"]] = relationship("ChatMessage", back_populates="chat_group", lazy="selectin")


class ChatMessage(Base, BaseEntityMixin):
    __tablename__ = "ChatMessages"

    message: Mapped[Optional[str]] = mapped_column("Message", Text, nullable=True)
    is_seen: Mapped[bool] = mapped_column("IsSeen", Boolean, default=False)
    is_admin: Mapped[bool] = mapped_column("IsAdmin", Boolean, default=False)
    group_id: Mapped[Optional[uuid.UUID]] = mapped_column("GroupId", UUID(as_uuid=True), ForeignKey("Chats.Id", ondelete="SET NULL"), nullable=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column("UserId", UUID(as_uuid=True), ForeignKey("Users.Id", ondelete="SET NULL"), nullable=True)
    media_id: Mapped[Optional[uuid.UUID]] = mapped_column("MediaId", UUID(as_uuid=True), ForeignKey("Medias.Id", ondelete="SET NULL"), nullable=True)
    ticket_id: Mapped[Optional[uuid.UUID]] = mapped_column("TicketId", UUID(as_uuid=True), ForeignKey("Tickets.Id", ondelete="SET NULL"), nullable=True)

    chat_group: Mapped[Optional[Chat]] = relationship("Chat", back_populates="chat_messages")
    ticket: Mapped[Optional[Ticket]] = relationship("Ticket", back_populates="chat_messages")
    media: Mapped[Optional["Media"]] = relationship("Media")
    user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[user_id])


class ChatReferenceHistory(Base, BaseEntityMixin):
    __tablename__ = "ChatReferenceHistories"

    from_user_id: Mapped[Optional[uuid.UUID]] = mapped_column("FromUserId", UUID(as_uuid=True), ForeignKey("Users.Id", ondelete="SET NULL"), nullable=True)
    to_user_id: Mapped[Optional[uuid.UUID]] = mapped_column("ToUserId", UUID(as_uuid=True), ForeignKey("Users.Id", ondelete="SET NULL"), nullable=True)