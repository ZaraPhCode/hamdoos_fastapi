"""align site_settings columns with .NET SiteSetting entity

Revision ID: f1a2b3c4d5e6
Revises: e1f2a3b4c5d6
Create Date: 2026-08-04 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = 'e1f2a3b4c5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _renames():
    return [
        ("logo_url", "LogoURL"),
        ("bank_name", "BankName"),
        ("account_number", "AccountNumber"),
        ("card_number", "CardNumber"),
        ("sheba_number", "ShebaNumber"),
        ("account_owner", "AccountOwner"),
        ("about_us", "AboutUs"),
        ("how_to_buy", "HowToBuy"),
        ("free_delivery", "FreeDelivery"),
        ("contact_us", "ContactUs"),
        ("technical_support", "TechnicalSupport"),
        ("email", "Email"),
        ("telephone", "Telephone"),
        ("address", "Address"),
        ("copy_right", "CopyRight"),
        ("disable_captcha", "DisableCaptcha"),
        ("free_postage_limit", "FreePostageLimit"),
        ("free_packaging", "FreePackaging"),
        ("free_postage", "FreePostage"),
        ("payment_status_per_hour", "PaymentStatusPerHour"),
        ("postal_code", "PostalCode"),
        ("top_category_id", "TopCategoryId"),
        ("middle_category_id", "MiddleCategoryId"),
        ("bottom_category_id", "BottomCategoryId"),
        ("top_poster_category_id", "TopPosterCategoryId"),
        ("mid_left_poster_category_id", "MidLeftPosterCategoryId"),
        ("mid_right_poster_category_id", "MidRightPosterCategoryId"),
        ("middle_poster_category_id", "MiddlePosterCategoryId"),
        ("bottom_poster_category_id", "BottomPosterCategoryId"),
        ("technical_table_id", "TechnicalTableId"),
    ]


def upgrade() -> None:
    op.alter_column('site_settings', 'payment_status_per_hour',
                    existing_type=sa.Integer(), type_=sa.Float(), nullable=True)
    for old, new in _renames():
        op.alter_column('site_settings', old, new_column_name=new)


def downgrade() -> None:
    for old, new in reversed(_renames()):
        op.alter_column('site_settings', new, new_column_name=old)
    op.alter_column('site_settings', 'payment_status_per_hour',
                    existing_type=sa.Float(), type_=sa.Integer(), nullable=True)
