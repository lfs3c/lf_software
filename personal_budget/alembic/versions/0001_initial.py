"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-03-05
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=80), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)

    op.create_table(
        "months",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=7), nullable=False),
        sa.Column("is_closed", sa.Boolean(), nullable=False),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "label", name="uq_month_user_label"),
    )
    op.create_index(op.f("ix_months_is_closed"), "months", ["is_closed"], unique=False)
    op.create_index(op.f("ix_months_label"), "months", ["label"], unique=False)
    op.create_index(op.f("ix_months_user_id"), "months", ["user_id"], unique=False)

    op.create_table(
        "accounts_cards",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("nickname", sa.String(length=120), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("last4", sa.String(length=4), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_accounts_cards_nickname"), "accounts_cards", ["nickname"], unique=False)
    op.create_index(op.f("ix_accounts_cards_type"), "accounts_cards", ["type"], unique=False)
    op.create_index(op.f("ix_accounts_cards_user_id"), "accounts_cards", ["user_id"], unique=False)

    op.create_table(
        "bills",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("paid", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts_cards.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_bills_account_id"), "bills", ["account_id"], unique=False)
    op.create_index(op.f("ix_bills_due_date"), "bills", ["due_date"], unique=False)
    op.create_index(op.f("ix_bills_paid"), "bills", ["paid"], unique=False)
    op.create_index(op.f("ix_bills_user_id"), "bills", ["user_id"], unique=False)

    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("month_id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("category", sa.String(length=120), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("tx_date", sa.Date(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts_cards.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["month_id"], ["months.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_transactions_account_id"), "transactions", ["account_id"], unique=False)
    op.create_index(op.f("ix_transactions_category"), "transactions", ["category"], unique=False)
    op.create_index(op.f("ix_transactions_kind"), "transactions", ["kind"], unique=False)
    op.create_index(op.f("ix_transactions_month_id"), "transactions", ["month_id"], unique=False)
    op.create_index(op.f("ix_transactions_tx_date"), "transactions", ["tx_date"], unique=False)
    op.create_index(op.f("ix_transactions_user_id"), "transactions", ["user_id"], unique=False)

    op.create_table(
        "month_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("month_id", sa.Integer(), nullable=False),
        sa.Column("totals_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("categories_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["month_id"], ["months.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("month_id"),
    )
    op.create_index(op.f("ix_month_snapshots_month_id"), "month_snapshots", ["month_id"], unique=True)
    op.create_index(op.f("ix_month_snapshots_user_id"), "month_snapshots", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_month_snapshots_user_id"), table_name="month_snapshots")
    op.drop_index(op.f("ix_month_snapshots_month_id"), table_name="month_snapshots")
    op.drop_table("month_snapshots")

    op.drop_index(op.f("ix_transactions_user_id"), table_name="transactions")
    op.drop_index(op.f("ix_transactions_tx_date"), table_name="transactions")
    op.drop_index(op.f("ix_transactions_month_id"), table_name="transactions")
    op.drop_index(op.f("ix_transactions_kind"), table_name="transactions")
    op.drop_index(op.f("ix_transactions_category"), table_name="transactions")
    op.drop_index(op.f("ix_transactions_account_id"), table_name="transactions")
    op.drop_table("transactions")

    op.drop_index(op.f("ix_bills_user_id"), table_name="bills")
    op.drop_index(op.f("ix_bills_paid"), table_name="bills")
    op.drop_index(op.f("ix_bills_due_date"), table_name="bills")
    op.drop_index(op.f("ix_bills_account_id"), table_name="bills")
    op.drop_table("bills")

    op.drop_index(op.f("ix_accounts_cards_user_id"), table_name="accounts_cards")
    op.drop_index(op.f("ix_accounts_cards_type"), table_name="accounts_cards")
    op.drop_index(op.f("ix_accounts_cards_nickname"), table_name="accounts_cards")
    op.drop_table("accounts_cards")

    op.drop_index(op.f("ix_months_user_id"), table_name="months")
    op.drop_index(op.f("ix_months_label"), table_name="months")
    op.drop_index(op.f("ix_months_is_closed"), table_name="months")
    op.drop_table("months")

    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_table("users")
