"""Chat API routes — create, messages, seen status, admin."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.dependencies import get_current_active_user, get_admin_user
from app.models.identity import User
from app.schemas.support import ChatCreate, ChatMessageCreate, ChatResponse, PaginatedResponse
from app.services import support_service

router = APIRouter(prefix="/chats", tags=["Chats"])


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_chat(
    request: ChatCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    chat = await support_service.create_chat(db, request, current_user.id)
    return support_service.build_chat_response(chat)


@router.get("", response_model=list[dict])
async def get_user_chats(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    chats = await support_service.get_user_chats(db, current_user.id)
    return [support_service.build_chat_response(c) for c in chats]


@router.get("/{chat_id}", response_model=dict)
async def get_chat(
    chat_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        cid = uuid.UUID(chat_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid chat ID")
    chat = await support_service.get_chat_by_id(db, cid)
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    if chat.user_id != current_user.id and "Admin" not in {ur.role.name for ur in current_user.roles}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your chat")
    return support_service.build_chat_response(chat)


@router.post("/{chat_id}/messages", response_model=dict)
async def send_message(
    chat_id: str,
    request: ChatMessageCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        cid = uuid.UUID(chat_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid chat ID")
    chat = await support_service.get_chat_by_id(db, cid)
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chat not found")
    if chat.user_id != current_user.id and "Admin" not in {ur.role.name for ur in current_user.roles}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your chat")
    msg = await support_service.send_chat_message(db, cid, request.message, current_user.id)
    return support_service.build_chat_response(chat)


@router.post("/{chat_id}/seen", response_model=dict)
async def mark_seen(
    chat_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        cid = uuid.UUID(chat_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid chat ID")
    count = await support_service.mark_messages_seen(db, cid, current_user.id)
    return {"marked_seen": count}


@router.get("/admin/unread-count", response_model=dict)
async def get_unread_count(
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Get count of unread messages across all chats (admin only)."""
    from sqlalchemy import select, func
    from app.models.support import ChatMessage

    stmt = select(func.count(ChatMessage.id)).where(
        ChatMessage.is_seen == False,
        ChatMessage.user_id != current_user.id,
        ChatMessage.is_removed == False,
    )
    result = await db.execute(stmt)
    count = result.scalar() or 0
    return {"unread_count": count}