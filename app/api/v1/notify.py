"""Notified products, search history, user actions API routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.dependencies import get_current_active_user
from app.models.identity import User
from app.services.notified_product_service import (
    add_notification_request, remove_notification_request,
    get_user_notifications, record_user_action, record_search_history,
)

router = APIRouter(prefix="/notify", tags=["Notifications"])


@router.post("/back-in-stock", status_code=status.HTTP_201_CREATED)
async def subscribe_back_in_stock(
    variety_id: str = Query(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        vid = uuid.UUID(variety_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid variety ID")
    try:
        np = await add_notification_request(db, current_user.id, vid)
        return {"message": "Notification request registered", "id": str(np.id)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/back-in-stock")
async def unsubscribe_back_in_stock(
    variety_id: str = Query(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        vid = uuid.UUID(variety_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid variety ID")
    await remove_notification_request(db, current_user.id, vid)
    return {"message": "Notification request removed"}


@router.get("/my-notifications")
async def my_notifications(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    items = await get_user_notifications(db, current_user.id)
    return {"items": items}


@router.post("/action", status_code=status.HTTP_201_CREATED)
async def log_user_action(
    product_id: str = Query(...), action_type: str = Query(...),
    notes: str = Query(""),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        pid = uuid.UUID(product_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid product ID")
    await record_user_action(db, current_user.id, pid, action_type, notes)
    return {"message": "Action recorded"}


@router.post("/search-history", status_code=status.HTTP_201_CREATED)
async def log_search(
    query: str = Query(...), category_id: str = Query(""),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    cid = uuid.UUID(category_id) if category_id else None
    await record_search_history(db, current_user.id, query, cid)
    return {"message": "Search recorded"}


# ── Auto Email/SMS Hooks ──

@router.post("/hooks/order-confirmed", status_code=status.HTTP_200_OK)
async def order_confirmed_hook(order_id: str = Query(...), db: AsyncSession = Depends(get_db)):
    """Auto-send email and SMS when order is paid/confirmed. Called from payment callback."""
    from app.models.order import OrderModel as Order
    from app.services.email_service import EmailSender
    from app.services.sms_service import SelectedSmsSender

    try:
        oid = uuid.UUID(order_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid order ID")

    order = await db.get(Order, oid)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    user = await db.get(User, order.user_id)

    email = EmailSender()
    sms = SelectedSmsSender()
    results = []

    if user and user.email:
        ok = await email.send_order_confirmation(
            user.email, user.full_name, order.reference_code or 0,
            float(order.payable or 0), order.date,
        )
        results.append(f"email={'ok' if ok else 'fail'}")
    if user and user.phone_number:
        ok = await sms.send_order_notification(
            user.phone_number, user.full_name, order.reference_code or 0,
            float(order.payable or 0), order.date,
        )
        results.append(f"sms={'ok' if ok else 'fail'}")

    return {"message": "Notifications sent", "results": results}


@router.post("/hooks/payment-confirmed", status_code=status.HTTP_200_OK)
async def payment_confirmed_hook(
    order_id: str = Query(...), ref_id: int = Query(0),
    db: AsyncSession = Depends(get_db),
):
    """Auto-send payment confirmation email."""
    from app.models.order import OrderModel as Order
    from app.services.email_service import EmailSender

    try:
        oid = uuid.UUID(order_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid order ID")

    order = await db.get(Order, oid)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    user = await db.get(User, order.user_id)

    email = EmailSender()
    if user and user.email:
        await email.send_payment_confirmation(
            user.email, user.full_name, order.reference_code or 0,
            ref_id, float(order.payable or 0),
        )
    return {"message": "Payment confirmation sent"}