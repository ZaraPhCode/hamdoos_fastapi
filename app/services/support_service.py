"""Support business logic — tickets, chats, messages."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.support import Ticket, Chat, ChatMessage, ChatReferenceHistory
from app.models.identity import User
from app.models.customer_content import Media


TICKET_CATEGORIES = {
    "General": "عمومی",
    "Technical": "فنی",
    "OrderTracking": "پیگیری سفارش",
    "Financial": "مالی / پرداخت",
    "Suggestion": "پیشنهاد / انتقاد",
}

TICKET_PRIORITIES = {
    "Low": "کم",
    "Medium": "متوسط",
    "High": "زیاد",
}

TICKET_STATUSES = {
    "Open": "باز",
    "Answered": "پاسخ داده شده",
    "Closed": "بسته شده",
}

TICKET_ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "bmp", "gif", "webp", "pdf"}
TICKET_MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB

_MAGIC_BYTES = {
    "png": (b"\x89PNG\r\n\x1a\n", None),
    "jpg": (b"\xff\xd8\xff", None),
    "jpeg": (b"\xff\xd8\xff", None),
    "bmp": (b"BM", None),
    "gif": (b"GIF8", None),
    "webp": (b"RIFF", b"WEBP"),
    "pdf": (b"%PDF-", None),
}

# Suspicious PDF markers — JavaScript / auto-launching / embedded executables
_PDF_DANGER_MARKERS = (
    b"/javascript",
    b"/js",
    b"/launch",
    b"/openaction",
    b"/embeddedfile",
    b"/richmedia",
    b"/acroform",
)


def validate_ticket_attachment(filename: str, content: bytes) -> tuple[bool, Optional[str]]:
    """Validate a ticket attachment by extension, size, magic bytes and content.

    Returns (ok, error_message). A falsy filename/content is considered valid (no file).
    """
    if not filename:
        return True, None
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in TICKET_ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(e.upper() for e in TICKET_ALLOWED_EXTENSIONS))
        return False, f"فرمت فایل مجاز نیست. فرمت‌های مجاز: {allowed}"
    if len(content) > TICKET_MAX_FILE_SIZE:
        max_mb = TICKET_MAX_FILE_SIZE // (1024 * 1024)
        return False, f"حجم فایل بیشتر از حد مجاز ({max_mb} مگابایت) است."

    magic = _MAGIC_BYTES[ext]
    if not content.startswith(magic[0]) or (magic[1] and magic[1] not in content[:16]):
        return False, "محتوای فایل با پسوند آن مطابقت ندارد. فایل معتبر نیست."

    if ext in {"png", "jpg", "jpeg", "bmp", "gif", "webp"}:
        from PIL import Image
        import io
        try:
            img = Image.open(io.BytesIO(content))
            img.verify()
        except Exception:
            return False, "فایل تصویر خراب یا معتبر نیست."
    elif ext == "pdf":
        low = content[: min(len(content), 1_000_000)].lower()
        for marker in _PDF_DANGER_MARKERS:
            if marker in low:
                return False, "فایل PDF حاوی کد اجرایی مشکوک است و قابل پذیرش نیست."
    return True, None


# ── Tickets ──

async def _create_media(db: AsyncSession, file_path: str, file_name: str) -> Media:
    media = Media(
        id=uuid.uuid4(),
        url=file_path,
        title=file_name,
        type="Unknown",
        insert_date=datetime.now(timezone.utc),
        update_date=datetime.now(timezone.utc),
    )
    db.add(media)
    await db.flush()
    return media


async def create_ticket(
    db: AsyncSession,
    request,
    user_id: Optional[uuid.UUID] = None,
    file_path: Optional[str] = None,
    file_name: Optional[str] = None,
) -> Ticket:
    order_id = getattr(request, "order_id", None)
    if order_id:
        try:
            order_id = uuid.UUID(str(order_id))
        except (ValueError, TypeError):
            order_id = None

    ticket = Ticket(
        id=uuid.uuid4(),
        name=request.name,
        email=request.email,
        telephone=request.telephone,
        description=request.description,
        subject=request.subject,
        status="Open",
        category=getattr(request, "category", None),
        priority=getattr(request, "priority", None),
        order_id=order_id,
        user_id=user_id,
        insert_date=datetime.now(timezone.utc),
        update_date=datetime.now(timezone.utc),
    )
    db.add(ticket)
    await db.flush()

    # Create initial message from the ticket description
    if request.description:
        media_id = None
        if file_path and file_name:
            media = await _create_media(db, file_path, file_name)
            media_id = media.id
        msg = ChatMessage(
            id=uuid.uuid4(),
            message=request.description,
            is_seen=False,
            is_admin=False,
            ticket_id=ticket.id,
            user_id=user_id,
            media_id=media_id,
            insert_date=datetime.now(timezone.utc),
            update_date=datetime.now(timezone.utc),
        )
        db.add(msg)
        await db.flush()

    return ticket


def _ticket_load_options():
    return (
        selectinload(Ticket.chat_messages).selectinload(ChatMessage.user),
        selectinload(Ticket.chat_messages).selectinload(ChatMessage.media),
        selectinload(Ticket.order),
    )


async def get_ticket_by_id(db: AsyncSession, ticket_id: uuid.UUID) -> Optional[Ticket]:
    stmt = (
        select(Ticket)
        .options(*_ticket_load_options())
        .execution_options(populate_existing=True)
        .where(Ticket.id == ticket_id, Ticket.is_removed == False)
    )
    result = await db.execute(stmt)
    return result.unique().scalar_one_or_none()


async def get_user_tickets(
    db: AsyncSession,
    user_id: uuid.UUID,
    page: int = 1,
    page_size: int = 20,
    status_filter: Optional[str] = None,
) -> tuple[list[Ticket], int]:
    conditions = [Ticket.user_id == user_id, Ticket.is_removed == False]
    if status_filter:
        conditions.append(Ticket.status == status_filter)

    count_stmt = select(func.count(Ticket.id)).where(*conditions)
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    stmt = (
        select(Ticket)
        .options(*_ticket_load_options())
        .where(*conditions)
        .order_by(Ticket.insert_date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    tickets = result.unique().scalars().all()
    return list(tickets), total


async def get_all_tickets(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    status_filter: Optional[str] = None,
    category_filter: Optional[str] = None,
    priority_filter: Optional[str] = None,
) -> tuple[list[Ticket], int]:
    conditions = [Ticket.is_removed == False]
    if status_filter:
        conditions.append(Ticket.status == status_filter)
    if category_filter:
        conditions.append(Ticket.category == category_filter)
    if priority_filter:
        conditions.append(Ticket.priority == priority_filter)

    count_stmt = select(func.count(Ticket.id)).where(*conditions)
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    stmt = (
        select(Ticket)
        .options(*_ticket_load_options())
        .where(*conditions)
        .order_by(Ticket.insert_date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    tickets = result.unique().scalars().all()
    return list(tickets), total


async def reply_to_ticket(
    db: AsyncSession,
    ticket: Ticket,
    message_text: str,
    user_id: uuid.UUID,
    is_admin: bool = False,
    file_path: Optional[str] = None,
    file_name: Optional[str] = None,
) -> ChatMessage:
    media_id = None
    if file_path and file_name:
        media = await _create_media(db, file_path, file_name)
        media_id = media.id

    msg = ChatMessage(
        id=uuid.uuid4(),
        message=message_text,
        is_seen=False,
        is_admin=is_admin,
        ticket_id=ticket.id,
        user_id=user_id,
        media_id=media_id,
        insert_date=datetime.now(timezone.utc),
        update_date=datetime.now(timezone.utc),
    )
    db.add(msg)

    # Update ticket status — a user reply re-opens, an admin reply marks answered
    if ticket.status != "Closed":
        if is_admin:
            if ticket.status == "Open":
                ticket.status = "Answered"
        elif ticket.status == "Answered":
            ticket.status = "Open"

    ticket.update_date = datetime.now(timezone.utc)
    await db.flush()
    return msg


async def close_ticket(db: AsyncSession, ticket: Ticket) -> Ticket:
    ticket.status = "Closed"
    ticket.update_date = datetime.now(timezone.utc)
    return ticket


STALE_TICKET_DAYS = 7


async def close_stale_tickets(db: AsyncSession) -> int:
    """Auto-close open tickets with no activity (new message from user or support)
    in the last STALE_TICKET_DAYS days. Returns the number of closed tickets."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=STALE_TICKET_DAYS)
    stmt = (
        select(Ticket)
        .where(Ticket.status.in_(["Open", "Answered"]), Ticket.is_removed == False)
        .options(*_ticket_load_options())
    )
    result = await db.execute(stmt)
    tickets = result.unique().scalars().all()

    closed = 0
    for ticket in tickets:
        messages = ticket.chat_messages or []
        last_activity = ticket.insert_date
        for m in messages:
            if m.insert_date and m.insert_date > last_activity:
                last_activity = m.insert_date
        if last_activity < cutoff:
            ticket.status = "Closed"
            ticket.update_date = datetime.now(timezone.utc)
            closed += 1
    if closed:
        await db.flush()
    return closed


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
    order_reference = None
    if ticket.order:
        order_reference = getattr(ticket.order, "reference_code", None)
    return {
        "id": ticket.id,
        "name": ticket.name,
        "email": ticket.email,
        "telephone": ticket.telephone,
        "description": ticket.description,
        "subject": ticket.subject,
        "status": ticket.status,
        "category": ticket.category,
        "priority": ticket.priority,
        "order_id": ticket.order_id,
        "order_reference": order_reference,
        "user_id": ticket.user_id,
        "insert_date": ticket.insert_date,
        "messages": [
            {
                "id": m.id,
                "message": m.message,
                "is_seen": m.is_seen,
                "group_id": m.group_id,
                "ticket_id": m.ticket_id,
                "user_id": m.user_id,
                "is_admin": bool(m.is_admin) or (bool(m.user_id) and m.user_id != ticket.user_id),
                "sender_name": (
                    "پشتیبانی"
                    if (bool(m.is_admin) or (bool(m.user_id) and m.user_id != ticket.user_id))
                    else (m.user.full_name or m.user.user_name if m.user else (ticket.name or "کاربر"))
                ),
                "file_url": m.media.url if m.media else None,
                "file_name": m.media.title if m.media else None,
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