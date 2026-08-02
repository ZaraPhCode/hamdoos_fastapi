
import uuid
from typing import Optional

from sqlalchemy import String, ForeignKey, Text, Integer, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base import Base, BaseEntityMixin


class Ticket(Base, BaseEntityMixin):
    __tablename__ = "tickets"

    name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    telephone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    subject: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    chat_messages: Mapped[list["ChatMessage"]] = relationship("ChatMessage", back_populates="ticket", lazy="selectin")


class Chat(Base, BaseEntityMixin):
    __tablename__ = "chats"

    title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    subject: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    chat_messages: Mapped[list["ChatMessage"]] = relationship("ChatMessage", back_populates="chat_group", lazy="selectin")


class ChatMessage(Base, BaseEntityMixin):
    __tablename__ = "chat_messages"

    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_seen: Mapped[bool] = mapped_column(Boolean, default=False)
    group_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("chats.id", ondelete="SET NULL"), nullable=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    media_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("medias.id", ondelete="SET NULL"), nullable=True)
    ticket_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("tickets.id", ondelete="SET NULL"), nullable=True)

    chat_group: Mapped[Optional[Chat]] = relationship("Chat", back_populates="chat_messages")
    ticket: Mapped[Optional[Ticket]] = relationship("Ticket", back_populates="chat_messages")
    media: Mapped[Optional["Media"]] = relationship("Media")


class ChatReferenceHistory(Base, BaseEntityMixin):
    __tablename__ = "chat_reference_histories"

    from_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    to_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)