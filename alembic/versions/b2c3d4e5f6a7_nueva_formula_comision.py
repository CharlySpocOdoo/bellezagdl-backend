"""nueva formula de comision — eliminar commission_amount_snapshot por item

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-26

"""
from alembic import op
import sqlalchemy as sa


revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column('order_items', 'commission_amount_snapshot')


def downgrade() -> None:
    op.add_column('order_items', sa.Column('commission_amount_snapshot', sa.Numeric(10, 2), nullable=True))
