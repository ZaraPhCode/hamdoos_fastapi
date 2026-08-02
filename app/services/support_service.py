"""Support business logic — tickets, chats, messages."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.support import Ticket, Chat, ChatMessage, ChatReferenceHistory
from app.models.identity import User


# ── Tickets ──

async def create_ticket(db: AsyncSession, request, user_id: Optional[uuid.UUID] = None) -> Ticket:
    ticket = Ticket(
        id=uuid.uuid4(),
        name=request.name,
        email=request.email,
        telephone=request.telephone,
        description=request.description,
        subject=request.subject,
        status="Open",
        user_id=user_id,
        insert_date=datetime.now(timezone.utc),
        update_date=datetime.now(timezone.utc),
    )
    db.add(ticket)
    await db.flush()

    # Create initial message from the ticket description
    if request.description:
        msg = ChatMessage(
            id=uuid.uuid4(),
            message=request.description,
            is_seen=False,
            ticket_id=ticket.id,
            user_id=user_id,
            insert_date=datetime.now(timezone.utc),
            update_date=datetime.now(timezone.utc),
        )
        db.add(msg)
        await db.flush()

    return ticket


async def get_ticket_by_id(db: AsyncSession, ticket_id: uuid.UUID) -> Optional[Ticket]:
    stmt = (
        select(Ticket)
        .options(
            selectinload(Ticket.chat_messages).order_by(ChatMessage.insert_date),
        )
        .where(Ticket.id == ticket_id, Ticket.is_removed == False)
    )
    result = await db.execute(stmt)
    return result.unique().scalar_one_or_none()


async def get_user_tickets(
    db: AsyncSession, user_id: uuid.UUID, page: int = 1, page_size: int = 20
) -> tuple[list[Ticket], int]:
    count_stmt = select(func.count(Ticket.id)).where(
        Ticket.user_id == user_id, Ticket.is_removed == False
    )
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    stmt = (
        select(Ticket)
        .options(selectinload(Ticket.chat_messages))
        .where(Ticket.user_id == user_id, Ticket.is_removed == False)
        .order_by(Ticket.insert_date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    tickets = result.unique().scalars().all()
    return list(tickets), total


async def get_all_tickets(
    db: AsyncSession, page: int = 1, page_size: int = 20, status_filter: Optional[str] = None
) -> tuple[list[Ticket], int]:
    conditions = [Ticket.is_removed == False]
    if status_filter:
        conditions.append(Ticket.status == status_filter)

    count_stmt = select(func.count(Ticket.id)).where(*conditions)
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    stmt = (
        select(Ticket)
        .options(selectinload(Ticket.chat_messages))
        .where(*conditions)
        .order_by(Ticket.insert_date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    tickets = result.unique().scalars().all()
    return list(tickets), total


async def reply_to_ticket(
    db: AsyncSession, ticket: Ticket, message_text: str, user_id: uuid.UUID
) -> ChatMessage:
    msg = ChatMessage(
        id=uuid.uuid4(),
        message=message_text,
        is_seen=False,
        ticket_id=ticket.id,
        user_id=user_id,
        insert_date=datetime.now(timezone.utc),
        update_date=datetime.now(timezone.utc),
    )
    db.add(msg)

    # Update ticket status
    ticket.status = "Answered" if ticket.status == "Open" else ticket.status
    ticket.update_date = datetime.now(timezone.utc)
    await db.flush()
    return msg


async def close_ticket(db: AsyncSession, ticket: Ticket) -> Ticket:
    ticket.status = "Closed"
    ticket.update_date = datetime.now(timezone.utc)
    return ticket


# ── Chats ──

async def create_chat(db: AsyncSession, request, user_id: uuid.UUID) -> Chat:
    chat = Chat(
        id=uuid.uuid4(),
        title=request.title,
        subject=request.subject,
        user_id=user_id,
        insert_date=datetime.now(timezone.utc),
        update_date=datetime.now(timezone.utc),
    )
    db.add(chat)
    await db.flush()
    return chat


async def get_chat_by_id(db: AsyncSession, chat_id: uuid.UUID) -> Optional[Chat]:
    stmt = (
        select(Chat)
        .options(selectinload(Chat.chat_messages).order_by(ChatMessage.insert_date))
        .where(Chat.id == chat_id, Chat.is_removed == False)
    )
    result = await db.execute(stmt)
    return result.unique().scalar_one_or_none()


async def get_user_chats(db: AsyncSession, user_id: uuid.UUID) -> list[Chat]:
    stmt = (
        select(Chat)
        .options(selectinload(Chat.chat_messages))
        .where(Chat.user_id == user_id, Chat.is_removed == False)
        .order_by(Chat.insert_date.desc())
    )
    result = await db.execute(stmt)
    return list(result.unique().scalars().all())


async def send_chat_message(
    db: AsyncSession, chat_id: uuid.UUID, message_text: str, user_id: uuid.UUID
) -> ChatMessage:
    msg = ChatMessage(
        id=uuid.uuid4(),
        message=message_text,
        is_seen=False,
        group_id=chat_id,
        user_id=user_id,
        insert_date=datetime.now(timezone.utc),
        update_date=datetime.now(timezone.utc),
    )
    db.add(msg)
    await db.flush()
    return msg


async def mark_messages_seen(db: AsyncSession, chat_id: uuid.UUID, user_id: uuid.UUID) -> int:
    stmt = select(ChatMessage).where(
        ChatMessage.group_id == chat_id,
        ChatMessage.user_id != user_id,
        ChatMessage.is_seen == False,
    )
    result = await db.execute(stmt)
    messages = result.scalars().all()
    for msg in messages:
        msg.is_seen = True
    await db.flush()
    return len(messages)


def build_ticket_response(ticket: Ticket) -> dict:
    return {
        "id": ticket.id,
        "name": ticket.name,
        "email": ticket.email,
        "telephone": ticket.telephone,
        "description": ticket.description,
        "subject": ticket.subject,
        "status": ticket.status,
        "user_id": ticket.user_id,
        "insert_date": ticket.insert_date,
        "messages": [
            {
                "id": m.id,
                "message": m.message,
                "is_seen": m.is_seen,
                "group_id": m.group_id,
                "user_id": m.user_id,
                "insert_date": m.insert_date,
            }
            for m in (ticket.chat_messages or [])
        ] if hasattr(ticket, 'chat_messages') else [],
    }


def build_chat_response(chat: Chat) -> dict:
    return {
        "id": chat.id,
        "title": chat.title,
        "subject": chat.subject,
        "user_id": chat.user_id,
        "insert_date": chat.insert_date,
        "messages": [
            {
                "id": m.id,
                "message": m.message,
                "is_seen": m.is_seen,
                "group_id": m.group_id,
                "user_id": m.user_id,
                "insert_date": m.insert_date,
            }
            for m in (chat.chat_messages or [])
        ] if hasattr(chat, 'chat_messages') else [],
    }