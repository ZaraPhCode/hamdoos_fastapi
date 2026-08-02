"""Notified products service — back-in-stock alerts for users.

Mirrors NotifiedProductController.cs and the notification flow from the .NET app.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer_content import NotifiedProduct
from app.models.product import Product, Variety
from app.models.identity import User
from app.services.email_service import EmailSender
from app.services.sms_service import SelectedSmsSender


async def add_notification_request(
    db: AsyncSession, user_id: uuid.UUID, variety_id: uuid.UUID
) -> NotifiedProduct:
    """Add a back-in-stock notification request. Mirrors NotifiedProduct.cs."""
    existing = await db.execute(
        select(NotifiedProduct).where(
            NotifiedProduct.created_by_user_id == user_id,
            NotifiedProduct.variety_id == variety_id,
            NotifiedProduct.is_removed == False,
        )
    )
    if existing.scalar_one_or_none():
        raise ValueError("Already subscribed to this product")

    np = NotifiedProduct(
        id=uuid.uuid4(), variety_id=variety_id, created_by_user_id=user_id,
        insert_date=datetime.now(timezone.utc), update_date=datetime.now(timezone.utc),
    )
    db.add(np)
    await db.flush()
    return np


async def remove_notification_request(
    db: AsyncSession, user_id: uuid.UUID, variety_id: uuid.UUID
) -> bool:
    result = await db.execute(
        select(NotifiedProduct).where(
            NotifiedProduct.created_by_user_id == user_id,
            NotifiedProduct.variety_id == variety_id,
            NotifiedProduct.is_removed == False,
        )
    )
    np = result.scalar_one_or_none()
    if np:
        np.is_removed = True
        await db.flush()
        return True
    return False


async def get_user_notifications(db: AsyncSession, user_id: uuid.UUID) -> list[dict]:
    stmt = (
        select(NotifiedProduct)
        .where(NotifiedProduct.created_by_user_id == user_id, NotifiedProduct.is_removed == False)
        .order_by(NotifiedProduct.insert_date.desc())
    )
    result = await db.execute(stmt)
    items = result.scalars().all()
    return [
        {
            "id": str(np.id),
            "variety_id": str(np.variety_id),
            "insert_date": np.insert_date,
        }
        for np in items
    ]


async def process_back_in_stock_notifications(db: AsyncSession):
    """Check all products with pending notifications and send alerts when stock arrives.
    Mirrors TimedHostedService periodic check."""
    stmt = (
        select(NotifiedProduct)
        .join(Variety, NotifiedProduct.variety_id == Variety.id)
        .join(Product, Variety.product_id == Product.id)
        .where(
            Product.stock_quantity > 0,
            NotifiedProduct.is_removed == False,
            NotifiedProduct.sms_response_date.is_(None),
        )
    )
    result = await db.execute(stmt)
    notifications = result.scalars().all()

    sms = SelectedSmsSender()
    email = EmailSender()
    sent_count = 0

    for np in notifications:
        variety = await db.get(Variety, np.variety_id)
        product = await db.get(Product, variety.product_id) if variety else None
        user = await db.get(User, np.created_by_user_id)
        if not all([variety, product, user]):
            continue

        product_url = f"/products/{product.slug or product.id}"
        if user.phone_number:
            await sms.send_notify_product(
                user.phone_number, user.full_name, product.name, product.part_number or "",
            )
        if user.email:
            await email.send_notify_product(user.email, user.full_name, product.name, product_url)

        np.sms_response_date = datetime.now(timezone.utc)
        np.email_response_date = datetime.now(timezone.utc)
        sent_count += 1

    await db.flush()
    return sent_count


async def record_user_action(
    db: AsyncSession, user_id: uuid.UUID, product_id: uuid.UUID, action_type: str,
    notes: Optional[str] = None,
):
    """Record a user action (visit, favorite, notify). Mirrors UserAction.cs."""
    from app.models.customer_content import UserAction
    action = UserAction(
        id=uuid.uuid4(), user_id=user_id, product_id=product_id,
        action_type=action_type, notes=notes,
        insert_date=datetime.now(timezone.utc), update_date=datetime.now(timezone.utc),
    )
    db.add(action)
    await db.flush()


async def record_search_history(
    db: AsyncSession, user_id: uuid.UUID, query: str, category_id: Optional[uuid.UUID] = None,
):
    """Record a search query. Mirrors SearchHistory.cs."""
    from app.models.customer_content import SearchHistory
    history = SearchHistory(
        id=uuid.uuid4(), user_id=user_id, title=query, category_id=category_id,
        insert_date=datetime.now(timezone.utc), update_date=datetime.now(timezone.utc),
    )
    db.add(history)
    await db.flush()