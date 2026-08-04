"""add weight & postage_date columns to orders table to match .NET Order entity

Revision ID: c7d8e9f0a1b2
Revises: a1b2c3d4e5f6
Create Date: 2026-08-03 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7d8e9f0a1b2'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('orders', sa.Column('weight', sa.String(length=200), nullable=True))
    op.add_column('orders', sa.Column('postage_date', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('orders', 'postage_date')
    op.drop_column('orders', 'weight')
