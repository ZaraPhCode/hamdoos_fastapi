"""align admin_parameters columns with .NET AdminParameter entity

Revision ID: e1f2a3b4c5d6
Revises: d1e2f3a4b5c6
Create Date: 2026-08-04 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'e1f2a3b4c5d6'
down_revision: Union[str, None] = 'd1e2f3a4b5c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('admin_parameters', sa.Column('ConfirmOrderPN', sa.Text(), nullable=True))
    op.add_column('admin_parameters', sa.Column('ConfrimOrderEm', sa.Text(), nullable=True))

    conn = op.get_bind()
    conn.execute(
        text('UPDATE admin_parameters SET "ConfirmOrderPN" = confirm_order_pn, '
             '"ConfrimOrderEm" = confirm_order_em')
    )

    op.drop_column('admin_parameters', 'confirm_order_pn')
    op.drop_column('admin_parameters', 'confirm_order_em')

    op.alter_column('admin_parameters', 'ConfirmOrderPN', existing_type=sa.Text(), nullable=False)
    op.alter_column('admin_parameters', 'ConfrimOrderEm', existing_type=sa.Text(), nullable=False)


def downgrade() -> None:
    op.add_column('admin_parameters', sa.Column('confirm_order_pn', sa.String(length=50), nullable=True))
    op.add_column('admin_parameters', sa.Column('confirm_order_em', sa.String(length=200), nullable=True))

    conn = op.get_bind()
    conn.execute(
        text('UPDATE admin_parameters SET confirm_order_pn = "ConfirmOrderPN", '
             'confirm_order_em = "ConfrimOrderEm"')
    )

    op.alter_column('admin_parameters', 'ConfirmOrderPN', existing_type=sa.Text(), nullable=True)
    op.alter_column('admin_parameters', 'ConfrimOrderEm', existing_type=sa.Text(), nullable=True)
    op.drop_column('admin_parameters', 'ConfrimOrderEm')
    op.drop_column('admin_parameters', 'ConfirmOrderPN')
