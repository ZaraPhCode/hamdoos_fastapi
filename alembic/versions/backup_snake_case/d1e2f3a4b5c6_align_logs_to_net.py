"""align logs table schema with .NET Logger (table/type as int enums)

Revision ID: d1e2f3a4b5c6
Revises: c7d8e9f0a1b2
Create Date: 2026-08-04 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'd1e2f3a4b5c6'
down_revision: Union[str, None] = 'c7d8e9f0a1b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('logs', sa.Column('table', sa.Integer(), nullable=True))

    conn = op.get_bind()
    from app.models.log_enums import resolve_table_int, resolve_type_int

    rows = conn.execute(text("SELECT id, table_name, type FROM logs")).fetchall()
    for row in rows:
        table_int = resolve_table_int(row[1]) if row[1] is not None else 0
        type_int = resolve_type_int(row[2]) if row[2] is not None else 0
        conn.execute(
            text('UPDATE logs SET "table" = :t, "type" = :tp WHERE id = :rid'),
            {"t": table_int, "tp": type_int, "rid": row[0]},
        )

    op.drop_column('logs', 'desc')

    op.alter_column(
        'logs', 'table',
        existing_type=sa.Integer(),
        existing_nullable=True,
        nullable=False,
    )

    op.drop_column('logs', 'table_name')

    op.alter_column(
        'logs', 'type',
        existing_type=sa.String(length=50),
        type_=sa.Integer(),
        existing_nullable=True,
        nullable=False,
        postgresql_using='"type"::integer',
    )


def downgrade() -> None:
    op.alter_column(
        'logs', 'type',
        existing_type=sa.Integer(),
        type_=sa.String(length=50),
        existing_nullable=False,
        nullable=True,
    )
    op.add_column('logs', sa.Column('table_name', sa.String(length=100), nullable=True))
    op.alter_column('logs', 'table', existing_type=sa.Integer(), nullable=True)
    op.add_column('logs', sa.Column('desc', sa.String(length=500), nullable=True))

    conn = op.get_bind()
    from app.models.log_enums import LOG_TABLE_NAME, LOG_TYPE_NAME

    rows = conn.execute(text('SELECT id, "table", "type", table_name FROM logs')).fetchall()
    for row in rows:
        table_name = LOG_TABLE_NAME.get(int(row[1] or 0), str(row[1] or 0))
        conn.execute(
            text("UPDATE logs SET table_name = :tn WHERE id = :rid"),
            {"tn": table_name, "rid": row[0]},
        )
    op.drop_column('logs', 'table')
