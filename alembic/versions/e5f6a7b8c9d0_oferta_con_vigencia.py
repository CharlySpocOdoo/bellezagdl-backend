"""sistema de ofertas con vigencia por fecha en products

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-06-26

"""
from alembic import op
import sqlalchemy as sa


revision = 'e5f6a7b8c9d0'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('products', sa.Column('oferta_inicio', sa.DateTime(), nullable=True))
    op.add_column('products', sa.Column('oferta_fin', sa.DateTime(), nullable=True))
    op.add_column('products', sa.Column('precio_oferta', sa.Numeric(10, 2), nullable=True))
    op.add_column('products', sa.Column('descuento_oferta_pct', sa.Numeric(5, 2), nullable=True))


def downgrade() -> None:
    op.drop_column('products', 'descuento_oferta_pct')
    op.drop_column('products', 'precio_oferta')
    op.drop_column('products', 'oferta_fin')
    op.drop_column('products', 'oferta_inicio')
