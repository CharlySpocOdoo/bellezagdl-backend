from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context

from app.config import settings
from app.database import Base

# Importar shared_enums primero para registrar todos los tipos
from app.modules import shared_enums  # noqa

# Dominio Catalogo — 2B-1
from app.modules.catalog.models import ProductCategory, Brand, Product, ProductVariant, ProductImage  # noqa

# Dominio Usuarios y Red — 2B-2
from app.modules.auth.models import User, RefreshToken, Vendor, Client, Invitation  # noqa

# Dominio Sistema — 2B-5
from app.modules.admin.models import DeliveryPerson, Supplier, SupplierContact, CatalogSyncLog, Notification, AuditLog  # noqa

# Dominio Financiero — 2B-4
from app.modules.commissions.models import CommissionSettings, CommissionPeriod, TaxSettings  # noqa

# Dominio Pedidos — 2B-3
from app.modules.orders.models import Order, OrderItem, OrderStatusHistory, Shipment  # noqa

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = settings.database_url
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = settings.database_url
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
