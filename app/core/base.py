from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class BaseEntityMixin:
    """Mixin matching the .NET BaseEntity. DB column names are .NET PascalCase so the
    .NET schema can be loaded into this PostgreSQL schema unchanged. Python attribute
    names stay snake_case so all app code/services keep working."""

    id: Mapped[uuid.UUID] = mapped_column(
        "Id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        "CreatedByUserId", UUID(as_uuid=True),
        ForeignKey("Users.Id", ondelete="SET NULL"), nullable=True
    )
    insert_date: Mapped[datetime] = mapped_column(
        "InsertDate", DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    update_date: Mapped[datetime] = mapped_column(
        "UpdateDate", DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    is_removed: Mapped[bool] = mapped_column(
        "IsRemoved", Boolean, default=False, nullable=False
    )