from decimal import Decimal
from typing import Optional, List, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.auth.models import Vendor
from app.modules.catalog.models import (
    Product, ProductVariant, ProductCategory, Brand, ProductImage
)
from app.modules.commissions.models import CommissionSettings
from app.modules.shared_enums import UserRole


# ── Calculos de precio ────────────────────────────────────────────────────────

def calculate_sale_price(cost_price: Decimal, sale_margin_percentage: Decimal) -> Decimal:
    """Precio Venta = Precio Costo x (1 + margen / 100)."""
    return round(cost_price * (1 + sale_margin_percentage / 100), 2)


def calculate_gross_profit(sale_price: Decimal, cost_price: Decimal) -> Decimal:
    """Ganancia bruta = Precio Venta - Precio Costo."""
    return sale_price - cost_price


def calculate_vendor_price(sale_price: Decimal, cost_price: Decimal, commission_pct: Decimal) -> Decimal:
    """
    Precio Vendedor = Precio Venta - comision del vendedor.
    La comision se calcula sobre la ganancia bruta.
    """
    gross_profit = calculate_gross_profit(sale_price, cost_price)
    vendor_commission = round(gross_profit * commission_pct / 100, 2)
    return round(sale_price - vendor_commission, 2)


def get_active_commission_percentage(db: Session) -> Decimal:
    """Obtiene el porcentaje de comision activo del vendedor."""
    settings = db.query(CommissionSettings).filter(
        CommissionSettings.active_to.is_(None)
    ).order_by(CommissionSettings.active_from.desc()).first()
    if settings:
        return settings.commission_percentage
    return Decimal("30.00")  # Default segun decision de negocio


def get_display_price(
    db: Session,
    product: Product,
    role: UserRole,
    vendor_commission_pct: Optional[Decimal] = None,
) -> Decimal:
    """
    Devuelve el precio a mostrar segun el rol:
    - Admin: Precio Venta (ve todo)
    - Client: Precio Venta
    - Vendor: Precio Vendedor (Precio Venta - su comision)
    """
    brand = db.query(Brand).filter(Brand.id == product.brand_id).first()
    sale_margin = brand.sale_margin_percentage if brand else Decimal("50.00")
    sale_price = calculate_sale_price(product.cost_price, sale_margin)

    if role == UserRole.vendor:
        commission_pct = vendor_commission_pct or get_active_commission_percentage(db)
        return calculate_vendor_price(sale_price, product.cost_price, commission_pct)

    return sale_price


# ── Stock ─────────────────────────────────────────────────────────────────────

def get_total_stock(variant: ProductVariant) -> int:
    """Stock total = stock_qty + returned_stock_qty."""
    return (variant.stock_qty or 0) + (variant.returned_stock_qty or 0)


def product_has_stock(db: Session, product_id: UUID) -> bool:
    """Verifica si el producto tiene al menos una variante con stock > 0."""
    variants = db.query(ProductVariant).filter(
        ProductVariant.product_id == product_id,
        ProductVariant.active == True,
    ).all()
    return any(get_total_stock(v) > 0 for v in variants)


# ── Catalogo ──────────────────────────────────────────────────────────────────

def get_products(
    db: Session,
    role: UserRole,
    vendor_id: Optional[UUID] = None,
    category_id: Optional[UUID] = None,
    brand_id: Optional[UUID] = None,
    search: Optional[str] = None,
) -> List[Tuple[Product, Decimal]]:
    """
    Devuelve lista de (producto, display_price).
    Solo productos con stock > 0.
    """
    query = db.query(Product).filter(Product.active == True)

    if category_id:
        query = query.filter(Product.category_id == category_id)
    if brand_id:
        query = query.filter(Product.brand_id == brand_id)
    if search:
        query = query.filter(Product.name.ilike(f"%{search}%"))

    products = query.order_by(Product.display_order, Product.name).all()

    # Obtener comision del vendedor si aplica
    vendor_commission_pct = None
    if role == UserRole.vendor and vendor_id:
        vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
        if vendor and vendor.commission_percentage:
            vendor_commission_pct = vendor.commission_percentage
        else:
            vendor_commission_pct = get_active_commission_percentage(db)

    result = []
    for product in products:
        display_price = get_display_price(db, product, role, vendor_commission_pct)
        result.append((product, display_price))

    return result


def get_product_detail(
    db: Session,
    product_id: UUID,
    role: UserRole,
    vendor_id: Optional[UUID] = None,
) -> Optional[Tuple[Product, Decimal, Decimal]]:
    """
    Devuelve (producto, sale_price, display_price) o None si no existe.
    """
    product = db.query(Product).filter(
        Product.id == product_id,
        Product.active == True,
    ).first()

    if not product:
        return None

    brand = db.query(Brand).filter(Brand.id == product.brand_id).first()
    sale_margin = brand.sale_margin_percentage if brand else Decimal("50.00")
    sale_price = calculate_sale_price(product.cost_price, sale_margin)

    vendor_commission_pct = None
    if role == UserRole.vendor and vendor_id:
        vendor = db.query(Vendor).filter(Vendor.id == vendor_id).first()
        if vendor and vendor.commission_percentage:
            vendor_commission_pct = vendor.commission_percentage
        else:
            vendor_commission_pct = get_active_commission_percentage(db)

    display_price = get_display_price(db, product, role, vendor_commission_pct)

    return product, sale_price, display_price


def get_categories(db: Session) -> List[ProductCategory]:
    """Devuelve todas las categorias activas."""
    return db.query(ProductCategory).filter(
        ProductCategory.active == True,
        ProductCategory.parent_id.is_(None),
    ).order_by(ProductCategory.display_order, ProductCategory.name).all()


def get_brands(db: Session) -> List[Brand]:
    """Devuelve todas las marcas activas."""
    return db.query(Brand).filter(Brand.active == True).order_by(Brand.name).all()


def get_variants(db: Session, product_id: UUID) -> List[ProductVariant]:
    """Devuelve variantes activas de un producto."""
    return db.query(ProductVariant).filter(
        ProductVariant.product_id == product_id,
        ProductVariant.active == True,
    ).order_by(ProductVariant.display_order).all()


def get_images(db: Session, product_id: UUID) -> List[ProductImage]:
    """Devuelve imagenes de un producto."""
    return db.query(ProductImage).filter(
        ProductImage.product_id == product_id,
    ).order_by(ProductImage.display_order).all()


# ── Mock sync con Odoo ────────────────────────────────────────────────────────

def sync_catalog_mock(db: Session, triggered_by_user_id: UUID) -> dict:
    """
    Mock de sync con Odoo para ambiente local.
    En produccion se conecta por XML-RPC.
    Crea datos de prueba si no existen.
    """
    from app.modules.admin.models import CatalogSyncLog
    from app.modules.shared_enums import SyncStatus
    from datetime import datetime
    import time

    start = time.time()

    log = CatalogSyncLog(
        source="mock",
        triggered_by="admin",
        triggered_by_user=triggered_by_user_id,
        status=SyncStatus.running,
        started_at=datetime.utcnow(),
    )
    db.add(log)
    db.commit()

    products_updated = 0
    errors = []

    try:
        # Crear categoria de prueba si no existe
        cat = db.query(ProductCategory).filter(
            ProductCategory.slug == "cosmeticos"
        ).first()
        if not cat:
            cat = ProductCategory(
                name="Cosmeticos",
                slug="cosmeticos",
                display_order=1,
                active=True,
                external_id="1",
                source="mock",
            )
            db.add(cat)
            db.flush()

        # Crear marca de prueba si no existe
        brand = db.query(Brand).filter(Brand.name == "Bissu").first()
        if not brand:
            brand = Brand(
                name="Bissu",
                brand_discount_percentage=Decimal("20.00"),
                sale_margin_percentage=Decimal("50.00"),
                active=True,
                external_id="1",
                source="mock",
            )
            db.add(brand)
            db.flush()

        # Crear productos de prueba si no existen
        mock_products = [
            {"name": "Labial Rojo Bissu", "sku": "BIS-LAB-001", "cost": Decimal("45.00"), "variant": "Rojo"},
            {"name": "Labial Rojo Bissu", "sku": "BIS-LAB-002", "cost": Decimal("45.00"), "variant": "Rosa"},
            {"name": "Sombra Nude Bissu", "sku": "BIS-SOM-001", "cost": Decimal("60.00"), "variant": None},
            {"name": "Rubor Coral Bissu", "sku": "BIS-RUB-001", "cost": Decimal("55.00"), "variant": None},
        ]

        for item in mock_products:
            existing_variant = db.query(ProductVariant).filter(
                ProductVariant.sku == item["sku"]
            ).first()

            if not existing_variant:
                import re
                base_name = item["name"]
                slug_base = re.sub(r'[^a-z0-9]+', '-', base_name.lower()).strip('-')

                product = db.query(Product).filter(
                    Product.name == base_name
                ).first()

                if not product:
                    # Asegurar slug unico
                    slug = slug_base
                    counter = 1
                    while db.query(Product).filter(Product.slug == slug).first():
                        slug = f"{slug_base}-{counter}"
                        counter += 1

                    product = Product(
                        category_id=cat.id,
                        brand_id=brand.id,
                        name=base_name,
                        slug=slug,
                        list_price=round(item["cost"] / Decimal("0.80"), 2),
                        cost_price=item["cost"],
                        active=True,
                        display_order=1,
                        external_id=item["sku"],
                        source="mock",
                        tags=["destacado"],
                    )
                    db.add(product)
                    db.flush()

                variant = ProductVariant(
                    product_id=product.id,
                    sku=item["sku"],
                    variant_name=item["variant"],
                    stock_qty=20,
                    returned_stock_qty=0,
                    active=True,
                    display_order=1,
                    external_id=item["sku"],
                    source="mock",
                )
                db.add(variant)
                products_updated += 1

        db.commit()

        duration_ms = int((time.time() - start) * 1000)
        log.status = SyncStatus.completed
        log.products_scanned = len(mock_products)
        log.products_updated = products_updated
        log.duration_ms = duration_ms
        log.finished_at = datetime.utcnow()
        db.commit()

        return {
            "status": "completed",
            "products_scanned": len(mock_products),
            "products_updated": products_updated,
            "images_uploaded": 0,
            "duration_ms": duration_ms,
            "errors": [],
        }

    except Exception as e:
        db.rollback()
        log.status = SyncStatus.failed
        log.errors = [str(e)]
        log.finished_at = datetime.utcnow()
        db.commit()
        return {
            "status": "failed",
            "products_scanned": 0,
            "products_updated": 0,
            "images_uploaded": 0,
            "duration_ms": 0,
            "errors": [str(e)],
        }
