"""add closing and payment date to accounts_cards

Revision ID: 0002_account_card_dates
Revises: 0001_initial
Create Date: 2026-03-05
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0002_account_card_dates"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("accounts_cards", sa.Column("closing_date", sa.Date(), nullable=True))
    op.add_column("accounts_cards", sa.Column("payment_date", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("accounts_cards", "payment_date")
    op.drop_column("accounts_cards", "closing_date")
