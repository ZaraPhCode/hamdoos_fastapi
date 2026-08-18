"""Ticket API routes — create, list, reply, admin management."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.core.dependencies import get_current_active_user, get_admin_user, require_any_role
from app.models.identity import User
from app.schemas.support import TicketCreate, TicketReply, TicketResponse, PaginatedResponse
from app.services import support_service

router = APIRouter(prefix="/tickets", tags=["Support Tickets"])


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    request: TicketCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a support ticket (logged-in users only)."""
    ticket = await support_service.create_ticket(db, request, current_user.id)
    await db.commit()
    ticket = await support_service.get_ticket_by_id(db, ticket.id)
    return support_service.build_ticket_response(ticket)


@router.get("", response_model=PaginatedResponse)
async def get_user_tickets(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    tickets, total = await support_service.get_user_tickets(
        db, current_user.id, page, page_size, status_filter
    )
    items = [support_service.build_ticket_response(t) for t in tickets]
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size, total_pages=(total + page_size - 1) // page_size)


@router.get("/{ticket_id}", response_model=dict)
async def get_ticket(
    ticket_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        tid = uuid.UUID(ticket_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid ticket ID")
    ticket = await support_service.get_ticket_by_id(db, tid)
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    if ticket.user_id != current_user.id and "Admin" not in {ur.role.name for ur in current_user.roles}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your ticket")
    return support_service.build_ticket_response(ticket)


@router.post("/{ticket_id}/reply", response_model=dict)
async def reply_to_ticket(
    ticket_id: str,
    request: TicketReply,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        tid = uuid.UUID(ticket_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid ticket ID")
    ticket = await support_service.get_ticket_by_id(db, tid)
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    if ticket.user_id != current_user.id and "Admin" not in {ur.role.name for ur in current_user.roles}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your ticket")
    msg = await support_service.reply_to_ticket(db, ticket, request.message, current_user.id, is_admin=request.is_admin)
    await db.commit()
    ticket = await support_service.get_ticket_by_id(db, ticket.id)
    return support_service.build_ticket_response(ticket)


@router.post("/{ticket_id}/close", response_model=dict)
async def close_ticket(
    ticket_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        tid = uuid.UUID(ticket_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid ticket ID")
    ticket = await support_service.get_ticket_by_id(db, tid)
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    if ticket.user_id != current_user.id and "Admin" not in {ur.role.name for ur in current_user.roles}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your ticket")
    await support_service.close_ticket(db, ticket)
    await db.commit()
    ticket = await support_service.get_ticket_by_id(db, ticket.id)
    return support_service.build_ticket_response(ticket)


# ── Admin Endpoints ──

@router.get("/admin/all", response_model=PaginatedResponse)
async def get_all_tickets(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None),
    category_filter: Optional[str] = Query(None),
    priority_filter: Optional[str] = Query(None),
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    tickets, total = await support_service.get_all_tickets(
        db, page, page_size, status_filter, category_filter, priority_filter
    )
    items = [support_service.build_ticket_response(t) for t in tickets]
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size, total_pages=(total + page_size - 1) // page_size)