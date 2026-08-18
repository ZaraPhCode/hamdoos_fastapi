"""Pydantic schemas for support (tickets and chats)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ── Ticket ──

class TicketCreate(BaseModel):
    name: str = Field(..., max_length=200)
    email: Optional[str] = None
    telephone: Optional[str] = None
    description: str = Field(..., min_length=1)
    subject: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[str] = None
    order_id: Optional[UUID] = None


class TicketReply(BaseModel):
    message: str = Field(..., min_length=1)
    is_admin: bool = False


class TicketResponse(BaseModel):
    id: UUID
    name: Optional[str] = None
    email: Optional[str] = None
    telephone: Optional[str] = None
    description: Optional[str] = None
    subject: Optional[str] = None
    status: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[str] = None
    order_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    insert_date: Optional[datetime] = None
    messages: list[ChatMessageResponse] = []

    model_config = {"from_attributes": True}


class TicketListResponse(BaseModel):
    id: UUID
    name: Optional[str] = None
    email: Optional[str] = None
    subject: Optional[str] = None
    status: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[str] = None
    message_count: int = 0
    last_message_date: Optional[datetime] = None
    insert_date: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── Chat Message ──

class ChatMessageCreate(BaseModel):
    message: str = Field(..., min_length=1)
    group_id: Optional[UUID] = None
    ticket_id: Optional[UUID] = None
    media_id: Optional[UUID] = None


class ChatMessageResponse(BaseModel):
    id: UUID
    message: Optional[str] = None
    is_seen: bool = False
    group_id: Optional[UUID] = None
    ticket_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    user_name: Optional[str] = None
    is_admin: bool = False
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    insert_date: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── Chat ──

class ChatCreate(BaseModel):
    title: Optional[str] = None
    subject: Optional[str] = None


class ChatResponse(BaseModel):
    id: UUID
    title: Optional[str] = None
    subject: Optional[str] = None
    user_id: Optional[UUID] = None
    messages: list[ChatMessageResponse] = []
    insert_date: Optional[datetime] = None

    model_config = {"from_attributes": True}


class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    page_size: int
    total_pages: int