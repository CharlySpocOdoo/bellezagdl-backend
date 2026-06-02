"""vendor_id nullable en orders

Revision ID: 391fb06fa501
Revises: e76e03c0d04d
Create Date: 2026-06-01

"""
from alembic import op
import sqlalchemy as sa


revision = '391fb06fa501'
down_revision = 'e76e03c0d04d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column('orders', 'vendor_id', nullable=True)


def downgrade() -> None:
    op.alter_column('orders', 'vendor_id', nullable=False) 