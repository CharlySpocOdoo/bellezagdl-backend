from datetime import datetime
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

def calculate_gross_profit(sale_price: Decimal, cost_price: Decimal) -> Decimal:
    """Ganancia bruta = Precio Venta - Precio Costo."""
    return sale_price - cost_price


def get_active_commission_percentage(db: Session) -> Decimal:
    """Obtiene el porcentaje de comision activo del vendedor."""
    settings = db.query(CommissionSettings).filter(
        CommissionSettings.active_to.is_(None)
    ).order_by(CommissionSettings.active_from.desc()).first()
    if settings:
        return settings.commission_percentage
    return Decimal("30.00")


def oferta_esta_activa(product: Product) -> bool:
    """
    Una oferta esta activa si la hora actual cae entre oferta_inicio y
    oferta_fin. No hay booleano de estado guardado — se calcula siempre al
    momento de consultar. Si falta cualquiera de las dos fechas, se trata
    como no activa (no se puede evaluar un rango incompleto).
    """
    if product.oferta_inicio is None or product.oferta_fin is None:
        return False
    ahora = datetime.utcnow()
    return product.oferta_inicio <= ahora <= product.oferta_fin


def get_precio_oferta(product: Product) -> Optional[Decimal]:
    """
    Precio de oferta si hay una activa, o None. precio_oferta tiene prioridad
    sobre descuento_oferta_pct cuando ambos tienen valor.
    """
    if not oferta_esta_activa(product):
        return None
    if product.precio_oferta is not None:
        return product.precio_oferta
    if product.descuento_oferta_pct is not None:
        return round(product.retail_price * (1 - product.descuento_oferta_pct / 100), 2)
    return None


def get_oferta_info(product: Product, role: UserRole) -> Tuple[bool, Optional[Decimal]]:
    """
    (is_oferta_activa, precio_original) para exponer en la API. Las ofertas
    solo aplican a client/vendor — wholesale y admin nunca las ven, sin
    importar si hay una oferta activa en el producto.
    """
    if role not in (UserRole.client, UserRole.vendor):
        return False, None
    if get_precio_oferta(product) is None:
        return False, None
    return True, product.retail_price


def get_display_price(
    db: Session,
    product: Product,
    role: UserRole,
) -> Decimal:
    """
    Devuelve el precio a mostrar segun el rol:
    - Admin:     retail_price (viene directo de la BD — antes era list_price × 1.50)
    - Client:    retail_price, o precio_oferta si hay una oferta activa
    - Vendor:    igual que client — sin comision descontada (la comision ya no
                 se calcula por producto, solo por pedido completo via order.total)
    - Wholesale: list_price — nunca ve precio de oferta
    """
    if role == UserRole.wholesale:
        return product.list_price

    if role in (UserRole.client, UserRole.vendor):
        precio_oferta = get_precio_oferta(product)
        if precio_oferta is not None:
            return precio_oferta

    return product.retail_price  # admin, o client/vendor sin oferta activa


def update_oferta(
    db: Session,
    product: Product,
    oferta_inicio: Optional[datetime],
    oferta_fin: Optional[datetime],
    precio_oferta: Optional[Decimal],
    descuento_oferta_pct: Optional[Decimal],
) -> Product:
    """
    Reemplaza por completo el estado de oferta del producto (no es un PATCH
    parcial) — para desactivar una oferta, se deben enviar los 4 campos en
    null explicitamente.
    """
    if oferta_inicio is not None and oferta_fin is not None:
        if oferta_fin <= oferta_inicio:
            raise ValueError("oferta_fin debe ser posterior a oferta_inicio")
        if precio_oferta is None and descuento_oferta_pct is None:
            raise ValueError(
                "No se puede activar una oferta sin precio_oferta o descuento_oferta_pct"
            )

    product.oferta_inicio = oferta_inicio
    product.oferta_fin = oferta_fin
    product.precio_oferta = precio_oferta
    product.descuento_oferta_pct = descuento_oferta_pct
    db.commit()
    db.refresh(product)
    return product


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
    query = db.query(Product).filter(Product.active == True)

    if category_id:
        query = query.filter(Product.category_id == category_id)
    if brand_id:
        query = query.filter(Product.brand_id == brand_id)
    if search:
        query = query.filter(Product.name.ilike(f"%{search}%"))

    products = query.order_by(Product.display_order, Product.name).all()

    result = []
    for product in products:
        display_price = get_display_price(db, product, role)
        result.append((product, display_price))

    return result


def get_product_detail(
    db: Session,
    product_id: UUID,
    role: UserRole,
    vendor_id: Optional[UUID] = None,
) -> Optional[Tuple[Product, Decimal, Decimal]]:
    product = db.query(Product).filter(
        Product.id == product_id,
        Product.active == True,
    ).first()

    if not product:
        return None

    display_price = get_display_price(db, product, role)

    return product, product.retail_price, display_price


def get_categories(db: Session) -> List[ProductCategory]:
    return db.query(ProductCategory).filter(
        ProductCategory.active == True,
        ProductCategory.parent_id.is_(None),
    ).order_by(ProductCategory.display_order, ProductCategory.name).all()


def get_brands(db: Session) -> List[Brand]:
    return db.query(Brand).filter(Brand.active == True).order_by(Brand.name).all()


def get_variants(db: Session, product_id: UUID) -> List[ProductVariant]:
    return db.query(ProductVariant).filter(
        ProductVariant.product_id == product_id,
        ProductVariant.active == True,
    ).order_by(ProductVariant.display_order).all()


def get_images(db: Session, product_id: UUID) -> List[ProductImage]:
    return db.query(ProductImage).filter(
        ProductImage.product_id == product_id,
    ).order_by(ProductImage.display_order).all()


# ── Mock sync con Odoo ────────────────────────────────────────────────────────

def sync_catalog_mock(db: Session, triggered_by_user_id: UUID) -> dict:
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