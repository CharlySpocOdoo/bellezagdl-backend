"""rediseño de catalogo 3A — retail_price y campos descriptivos en products

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-06-26

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = 'd4e5f6a7b8c9'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('products', sa.Column('retail_price', sa.Numeric(10, 2), nullable=True))
    op.add_column('products', sa.Column('modo_de_uso', sa.Text(), nullable=True))
    op.add_column('products', sa.Column('beneficios', sa.Text(), nullable=True))
    op.add_column('products', sa.Column('ingredientes', sa.Text(), nullable=True))
    op.add_column('products', sa.Column('atributos', postgresql.JSONB(), nullable=True))

    # Backfill: productos ya cargados (15% del catalogo) no tienen retail_price
    # todavia — sin esto, display_price quedaria NULL para client/vendor/admin
    # en todo el catalogo existente hasta que se reimporte el Excel nuevo.
    # Se usa la formula vieja (list_price x 1.50) como valor de transicion —
    # la reimportacion del Excel 3A lo sobreescribe con precio_menudeo real.
    op.execute("UPDATE products SET retail_price = list_price * 1.50 WHERE retail_price IS NULL")


def downgrade() -> None:
    op.drop_column('products', 'atributos')
    op.drop_column('products', 'ingredientes')
    op.drop_column('products', 'beneficios')
    op.drop_column('products', 'modo_de_uso')
    op.drop_column('products', 'retail_price')
