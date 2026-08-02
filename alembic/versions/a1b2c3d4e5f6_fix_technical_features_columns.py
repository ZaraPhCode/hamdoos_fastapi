"""fix technical_features value/flag column types to match .NET

Revision ID: a1b2c3d4e5f6
Revises: 2b7f4c9e8a11
Create Date: 2026-08-02 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '2b7f4c9e8a11'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('technical_features', 'linear_display',
                    existing_type=sa.Boolean(),
                    type_=sa.String(length=200),
                    existing_nullable=True,
                    nullable=True)

    for col in ('d_value', 'unit', 's_value', 'e_value', 'e_value1',
                'b_value', 'min_value', 'min_unit', 'max_value', 'max_unit',
                'x_value', 'x_unit', 'y_value', 'y_unit', 'z_value', 'z_unit'):
        op.alter_column('technical_features', col,
                        existing_type=sa.String(),
                        type_=sa.Boolean(),
                        existing_nullable=True,
                        postgresql_using=f'{col}::boolean')


def downgrade() -> None:
    op.alter_column('technical_features', 'linear_display',
                    existing_type=sa.String(length=200),
                    type_=sa.Boolean(),
                    existing_nullable=True)

    for col in ('d_value', 'unit', 's_value', 'e_value', 'e_value1',
                'b_value', 'min_value', 'min_unit', 'max_value', 'max_unit',
                'x_value', 'x_unit', 'y_value', 'y_unit', 'z_value', 'z_unit'):
        op.alter_column('technical_features', col,
                        existing_type=sa.Boolean(),
                        type_=sa.String(),
                        existing_nullable=True)
