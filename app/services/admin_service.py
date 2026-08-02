"""Admin dashboard business logic — stats, counts, analytics."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any

from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.identity import User, Role, UserRole
from app.models.product import Product, Category, Brand, ProductImage
from app.models.order import OrderModel as Order, OrderProduct, OrderStatusRecord
from app.models.invoice import Invoice
from app.models.customer_content import Comment


async def get_dashboard_stats(db: AsyncSession) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)

    # User counts
    total_users = await _count(db, select(User).where(User.is_removed == False))
    new_users_30d = await _count(db, select(User).where(User.insert_date >= thirty_days_ago, User.is_removed == False))

    # Product counts
    total_products = await _count(db, select(Product).where(Product.is_removed == False, Product.no_display == False))
    out_of_stock = await _count(
        db, select(Product).where(Product.stock_quantity <= 0, Product.is_removed == False)
    )

    # Category & Brand counts
    total_categories = await _count(db, select(Category).where(Category.is_removed == False, Category.no_display == False))
    total_brands = await _count(db, select(Brand).where(Brand.is_removed == False))

    # Order stats
    total_orders = await _count(db, select(Order).where(Order.is_removed == False))
    pending_orders = await _count(
        db, select(Order).where(
            Order.order_status.in_(["Ordering", "AwaitingPayment", "Paid", "ConfirmedPayment", "Processing"]),
            Order.is_removed == False,
        )
    )
    new_orders_30d = await _count(db, select(Order).where(Order.insert_date >= thirty_days_ago, Order.is_removed == False))

    # Revenue (from paid orders)
    revenue_result = await db.execute(
        select(func.coalesce(func.sum(Order.payable), 0)).where(
            Order.order_status.in_(["Paid", "ConfirmedPayment", "Processing", "Sending", "Posted"]),
            Order.is_removed == False,
        )
    )
    total_revenue = float(revenue_result.scalar() or 0)

    # Comment stats
    total_comments = await _count(db, select(Comment).where(Comment.is_removed == False))
    pending_comments = await _count(db, select(Comment).where(Comment.is_confirmed == False, Comment.is_removed == False))

    # Role counts
    admin_count = 0
    user_role_stmt = (
        select(func.count(UserRole.id))
        .join(Role, UserRole.role_id == Role.id)
        .where(Role.name == "Admin", UserRole.is_removed == False)
    )
    admin_result = await db.execute(user_role_stmt)
    admin_count = admin_result.scalar() or 0

    return {
        "total_users": total_users,
        "new_users_30d": new_users_30d,
        "total_products": total_products,
        "out_of_stock": out_of_stock,
        "total_categories": total_categories,
        "total_brands": total_brands,
        "total_orders": total_orders,
        "pending_orders": pending_orders,
        "new_orders_30d": new_orders_30d,
        "total_revenue": total_revenue,
        "total_comments": total_comments,
        "pending_comments": pending_comments,
        "admin_count": admin_count,
    }


async def get_order_status_distribution(db: AsyncSession) -> list[dict]:
    stmt = (
        select(Order.order_status, func.count(Order.id))
        .where(Order.is_removed == False)
        .group_by(Order.order_status)
    )
    result = await db.execute(stmt)
    return [{"status": row[0], "count": row[1]} for row in result]


async def get_recent_orders(db: AsyncSession, limit: int = 10) -> list[dict]:
    stmt = (
        select(Order)
        .where(Order.is_removed == False)
        .order_by(Order.insert_date.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    orders = result.scalars().all()
    return [
        {
            "id": str(o.id),
            "reference_code": o.reference_code,
            "order_status": o.order_status,
            "payable": float(o.payable) if o.payable else 0,
            "first_name": o.first_name,
            "last_name": o.last_name,
            "insert_date": o.insert_date.isoformat() if o.insert_date else None,
        }
        for o in orders
    ]


async def get_low_stock_products(db: AsyncSession, threshold: int = 5, limit: int = 10) -> list[dict]:
    stmt = (
        select(Product)
        .where(
            Product.stock_quantity <= threshold,
            Product.stock_quantity > 0,
            Product.is_removed == False,
            Product.no_display == False,
        )
        .order_by(Product.stock_quantity)
        .limit(limit)
    )
    result = await db.execute(stmt)
    products = result.scalars().all()
    return [
        {
            "id": str(p.id),
            "name": p.name,
            "part_number": p.part_number,
            "stock_quantity": p.stock_quantity,
            "price": float(p.price) if p.price else 0,
        }
        for p in products
    ]


async def _count(db: AsyncSession, stmt) -> int:
    count_stmt = select(func.count()).select_from(stmt.subquery())
    result = await db.execute(count_stmt)
    return result.scalar() or 0