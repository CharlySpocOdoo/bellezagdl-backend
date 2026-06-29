"""eliminar shipping_cost por completo

Revision ID: a1b2c3d4e5f6
Revises: 391fb06fa501
Create Date: 2026-06-26

"""
from alembic import op
import sqlalchemy as sa


revision = 'a1b2c3d4e5f6'
down_revision = '391fb06fa501'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column('orders', 'shipping_cost')
    op.drop_column('shipments', 'shipping_cost')
    op.drop_column('shipments', 'shipping_cost_waived')
    op.drop_column('commission_periods', 'shipping_charges')
    op.drop_column('commission_settings', 'min_shipment_amount_for_free_shipping')


def downgrade() -> None:
    op.add_column('commission_settings', sa.Column('min_shipment_amount_for_free_shipping', sa.Numeric(10, 2), nullable=True))
    op.add_column('commission_periods', sa.Column('shipping_charges', sa.Numeric(10, 2), nullable=False, server_default='0'))
    op.add_column('shipments', sa.Column('shipping_cost_waived', sa.Boolean(), nullable=True, server_default=sa.false()))
    op.add_column('shipments', sa.Column('shipping_cost', sa.Numeric(10, 2), nullable=True, server_default='0'))
    op.add_column('orders', sa.Column('shipping_cost', sa.Numeric(10, 2), nullable=True, server_default='0'))
