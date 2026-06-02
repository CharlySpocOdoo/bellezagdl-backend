"""ventas de mayoreo — wholesale

Revision ID: e76e03c0d04d
Revises: 70b9eb3347dd
Create Date: 2026-06-01

"""
from alembic import op
import sqlalchemy as sa


revision = 'e76e03c0d04d'
down_revision = '70b9eb3347dd'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Agregar wholesale al enum userrole
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'wholesale'")

    # 2. Crear enum saletype
    op.execute("CREATE TYPE saletype AS ENUM ('retail', 'wholesale')")

    # 3. vendor_id nullable en clients
    op.alter_column('clients', 'vendor_id', nullable=True)

    # 4. Nuevos campos en clients
    op.add_column('clients', sa.Column('business_name', sa.String(255), nullable=True))
    op.add_column('clients', sa.Column('rfc', sa.String(20), nullable=True))
    op.add_column('clients', sa.Column('fiscal_address', sa.Text(), nullable=True))

    # 5. sale_type en orders
    op.add_column('orders', sa.Column(
        'sale_type',
        sa.Enum('retail', 'wholesale', name='saletype', create_type=False),
        nullable=True,
        server_default='retail',
    ))

    # 6. vendor_id nullable en shipments
    op.alter_column('shipments', 'vendor_id', nullable=True)

    # 7. Nuevos campos en shipments
    op.add_column('shipments', sa.Column(
        'wholesale_client_id',
        sa.UUID(as_uuid=True),
        nullable=True,
    ))
    op.add_column('shipments', sa.Column(
        'sale_type',
        sa.Enum('retail', 'wholesale', name='saletype', create_type=False),
        nullable=True,
    ))
    op.create_foreign_key(
        'fk_shipments_wholesale_client_id',
        'shipments', 'clients',
        ['wholesale_client_id'], ['id'],
    )


def downgrade() -> None:
    op.drop_constraint('fk_shipments_wholesale_client_id', 'shipments', type_='foreignkey')
    op.drop_column('shipments', 'sale_type')
    op.drop_column('shipments', 'wholesale_client_id')
    op.alter_column('shipments', 'vendor_id', nullable=False)
    op.drop_column('orders', 'sale_type')
    op.drop_column('clients', 'fiscal_address')
    op.drop_column('clients', 'rfc')
    op.drop_column('clients', 'business_name')
    op.alter_column('clients', 'vendor_id', nullable=False)
    op.execute("DROP TYPE saletype")