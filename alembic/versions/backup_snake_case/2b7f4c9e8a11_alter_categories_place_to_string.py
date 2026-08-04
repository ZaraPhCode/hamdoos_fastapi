"""alter categories.place to string

Revision ID: 2b7f4c9e8a11
Revises: 371737714c04
Create Date: 2026-08-01 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2b7f4c9e8a11'
down_revision: Union[str, None] = '371737714c04'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('categories', 'place',
                    existing_type=sa.Integer(),
                    type_=sa.String(length=200),
                    existing_nullable=True)


def downgrade() -> None:
    op.alter_column('categories', 'place',
                    existing_type=sa.String(length=200),
                    type_=sa.Integer(),
                    existing_nullable=True)
