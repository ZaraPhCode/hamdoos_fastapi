"""Admin API routes — dashboard, site settings, role management."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.core.dependencies import get_admin_user, require_any_role
from app.models.identity import User, Role, UserRole
from app.schemas.auth import UserResponse
from app.services import admin_service, auth_service
from app.services.admin_service import get_dashboard_stats, get_order_status_distribution, get_recent_orders, get_low_stock_products

router = APIRouter(prefix="/administration", tags=["Admin"])


# ── Dashboard ──

@router.get("/dashboard")
async def dashboard(
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    stats = await get_dashboard_stats(db)
    order_distribution = await get_order_status_distribution(db)
    recent_orders = await get_recent_orders(db, 10)
    low_stock = await get_low_stock_products(db, 5, 10)
    return {
        "stats": stats,
        "order_distribution": order_distribution,
        "recent_orders": recent_orders,
        "low_stock_products": low_stock,
    }


# ── Role Management ──

@router.get("/roles")
async def get_roles(
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Role).where(Role.is_removed == False).order_by(Role.name)
    result = await db.execute(stmt)
    roles = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "name": r.name,
            "description": r.description,
            "user_count": len(r.user_roles) if hasattr(r, 'user_roles') else 0,
        }
        for r in roles
    ]


@router.post("/roles", status_code=status.HTTP_201_CREATED)
async def create_role(
    name: str,
    description: str = "",
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(select(Role).where(Role.name == name))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Role already exists")
    role = Role(name=name, description=description)
    db.add(role)
    await db.flush()
    return {"id": str(role.id), "name": role.name, "description": role.description}


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: str,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    import uuid
    try:
        rid = uuid.UUID(role_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role ID")
    role = await db.get(Role, rid)
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    role.is_removed = True


@router.post("/users/{user_id}/roles", status_code=status.HTTP_201_CREATED)
async def assign_role(
    user_id: str,
    role_name: str,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    import uuid
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user ID")
    user = await db.get(User, uid)
    if not user or user.is_removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    role = (await db.execute(select(Role).where(Role.name == role_name))).scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")

    existing = await db.execute(
        select(UserRole).where(UserRole.user_id == uid, UserRole.role_id == role.id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User already has this role")

    user_role = UserRole(user_id=uid, role_id=role.id)
    db.add(user_role)
    await db.flush()
    return {"message": f"Role '{role_name}' assigned to user"}


@router.delete("/users/{user_id}/roles/{role_name}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_role(
    user_id: str,
    role_name: str,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    import uuid
    try:
        uid = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user ID")
    role = (await db.execute(select(Role).where(Role.name == role_name))).scalar_one_or_none()
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
    ur = await db.execute(
        select(UserRole).where(UserRole.user_id == uid, UserRole.role_id == role.id)
    )
    user_role = ur.scalar_one_or_none()
    if user_role:
        user_role.is_removed = True


# ── Site Settings ──

@router.get("/settings")
async def get_site_settings(
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.common import SiteSetting
    stmt = select(SiteSetting).where(SiteSetting.is_removed == False).limit(1)
    result = await db.execute(stmt)
    settings = result.scalar_one_or_none()
    if not settings:
        return {}
    return {
        "id": str(settings.id),
        "logo_url": settings.logo_url,
        "bank_name": settings.bank_name,
        "account_number": settings.account_number,
        "card_number": settings.card_number,
        "sheba_number": settings.sheba_number,
        "account_owner": settings.account_owner,
        "about_us": settings.about_us,
        "how_to_buy": settings.how_to_buy,
        "contact_us": settings.contact_us,
        "technical_support": settings.technical_support,
        "email": settings.email,
        "telephone": settings.telephone,
        "address": settings.address,
        "copy_right": settings.copy_right,
        "free_postage_limit": float(settings.free_postage_limit) if settings.free_postage_limit else None,
        "free_postage": settings.free_postage,
        "free_packaging": settings.free_packaging,
        "postal_code": settings.postal_code,
    }


@router.put("/settings")
async def update_site_settings(
    data: dict,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.common import SiteSetting
    stmt = select(SiteSetting).where(SiteSetting.is_removed == False).limit(1)
    result = await db.execute(stmt)
    settings = result.scalar_one_or_none()
    if not settings:
        from datetime import datetime, timezone
        import uuid
        settings = SiteSetting(id=uuid.uuid4(), insert_date=datetime.now(timezone.utc), update_date=datetime.now(timezone.utc))
        db.add(settings)
    for key, value in data.items():
        if hasattr(settings, key):
            setattr(settings, key, value)
    await db.flush()
    return {"message": "Settings updated"}


# ── Comments Moderation ──

@router.get("/comments")
async def get_comments(
    pending_only: bool = Query(False),
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.customer_content import Comment
    from app.models.product import Product
    stmt = (
        select(Comment)
        .where(Comment.is_removed == False)
    )
    if pending_only:
        stmt = stmt.where(Comment.is_confirmed == False)
    stmt = stmt.order_by(Comment.insert_date.desc()).limit(50)
    result = await db.execute(stmt)
    comments = result.scalars().all()
    return [
        {
            "id": str(c.id),
            "name": c.name,
            "description": c.description,
            "rate": c.rate,
            "is_confirmed": c.is_confirmed,
            "is_buyer": c.is_buyer,
            "insert_date": c.insert_date.isoformat() if c.insert_date else None,
            "product_id": str(c.product_id) if c.product_id else None,
        }
        for c in comments
    ]


@router.put("/comments/{comment_id}/approve")
async def approve_comment(
    comment_id: str,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    import uuid
    from app.models.customer_content import Comment
    try:
        cid = uuid.UUID(comment_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid comment ID")
    comment = await db.get(Comment, cid)
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    comment.is_confirmed = True
    return {"message": "Comment approved"}


# ── Quick Stats for sidebar ──

@router.get("/quick-stats")
async def quick_stats(
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models.order import OrderModel as Order
    pending_orders = await db.execute(
        select(func.count(Order.id)).where(
            Order.order_status.in_(["Ordering", "AwaitingPayment"]),
            Order.is_removed == False,
        )
    )
    from app.models.customer_content import Comment
    pending_comments = await db.execute(
        select(func.count(Comment.id)).where(
            Comment.is_confirmed == False, Comment.is_removed == False
        )
    )
    from app.models.product import Product
    out_of_stock = await db.execute(
        select(func.count(Product.id)).where(
            Product.stock_quantity <= 0, Product.is_removed == False
        )
    )
    return {
        "pending_orders": pending_orders.scalar() or 0,
        "pending_comments": pending_comments.scalar() or 0,
        "out_of_stock": out_of_stock.scalar() or 0,
    }