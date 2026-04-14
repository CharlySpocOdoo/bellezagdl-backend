from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, List
from uuid import UUID

from app.database import get_db
from app.modules.auth.dependencies import get_current_user, require_admin
from app.modules.auth.models import User, Vendor
from app.modules.catalog import service
from app.modules.catalog.models import ProductCategory, ProductVariant, ProductImage, Brand
from app.modules.catalog.schemas import (
    ProductListResponse, ProductDetailResponse,
    CategoryResponse, BrandResponse,
    ProductVariantResponse, ProductImageResponse,
    SyncResultResponse,
)
from app.modules.shared_enums import UserRole

router = APIRouter()


@router.get("/products", response_model=List[ProductListResponse])
def get_products(
    category_id: Optional[UUID] = Query(None),
    brand_id: Optional[UUID] = Query(None),
    search: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Catalogo de productos con stock > 0.
    Precio mostrado segun rol: Precio Venta para clientes y admins,
    Precio Vendedor para vendors.
    """
    vendor_id = None
    if current_user.role == UserRole.vendor:
        vendor = db.query(Vendor).filter(Vendor.user_id == current_user.id).first()
        if vendor:
            vendor_id = vendor.id

    products = service.get_products(
        db=db,
        role=current_user.role,
        vendor_id=vendor_id,
        category_id=category_id,
        brand_id=brand_id,
        search=search,
    )

    result = []
    for product, display_price in products:
        brand = db.query(Brand).filter(Brand.id == product.brand_id).first()
        category = db.query(ProductCategory).filter(ProductCategory.id == product.category_id).first()
        result.append(ProductListResponse(
            id=product.id,
            name=product.name,
            slug=product.slug,
            description=product.description,
            category_id=product.category_id,
            category_name=category.name if category else None,
            brand_id=product.brand_id,
            brand_name=brand.name if brand else None,
            image_url=product.image_url,
            image_thumb_url=product.image_thumb_url,
            tags=product.tags,
            display_price=display_price,
            active=product.active,
        ))
    return result


@router.get("/products/{product_id}", response_model=ProductDetailResponse)
def get_product_detail(
    product_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Detalle completo de un producto con variantes e imagenes."""
    vendor_id = None
    if current_user.role == UserRole.vendor:
        vendor = db.query(Vendor).filter(Vendor.user_id == current_user.id).first()
        if vendor:
            vendor_id = vendor.id

    result = service.get_product_detail(db, product_id, current_user.role, vendor_id)
    if not result:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    product, sale_price, display_price = result

    variants = service.get_variants(db, product.id)
    images = service.get_images(db, product.id)

    variant_responses = [
        ProductVariantResponse(
            id=v.id,
            sku=v.sku,
            variant_name=v.variant_name,
            stock_qty=v.stock_qty,
            returned_stock_qty=v.returned_stock_qty,
            total_stock=service.get_total_stock(v),
            image_url=v.image_url,
            active=v.active,
            display_order=v.display_order,
        )
        for v in variants
    ]

    image_responses = [
        ProductImageResponse(
            id=img.id,
            url=img.url,
            thumb_url=img.thumb_url,
            display_order=img.display_order,
            is_primary=img.is_primary,
        )
        for img in images
    ]

    brand = db.query(Brand).filter(Brand.id == product.brand_id).first()
    category = db.query(ProductCategory).filter(ProductCategory.id == product.category_id).first()

    return ProductDetailResponse(
        id=product.id,
        name=product.name,
        slug=product.slug,
        description=product.description,
        category_id=product.category_id,
        category_name=category.name if category else None,
        brand_id=product.brand_id,
        brand_name=brand.name if brand else None,
        brand_origin=brand.origin.value if brand and brand.origin else None,
        image_url=product.image_url,
        image_thumb_url=product.image_thumb_url,
        tags=product.tags,
        display_price=display_price,
        sale_price=sale_price,
        list_price=product.list_price if current_user.role == UserRole.admin else None,
        cost_price=product.cost_price if current_user.role == UserRole.admin else None,
        active=product.active,
        variants=variant_responses,
        images=image_responses,
    )


@router.get("/categories", response_model=List[CategoryResponse])
def get_categories(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Arbol de categorias para navegacion."""
    categories = service.get_categories(db)

    def build_tree(cat):
        children = db.query(ProductCategory).filter(
            ProductCategory.parent_id == cat.id,
            ProductCategory.active == True,
        ).order_by(ProductCategory.display_order).all()
        return CategoryResponse(
            id=cat.id,
            name=cat.name,
            slug=cat.slug,
            parent_id=cat.parent_id,
            display_order=cat.display_order,
            active=cat.active,
            children=[build_tree(c) for c in children],
        )

    return [build_tree(cat) for cat in categories]


@router.get("/brands", response_model=List[BrandResponse])
def get_brands(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Lista de marcas activas."""
    brands = service.get_brands(db)
    return [
        BrandResponse(
            id=b.id,
            name=b.name,
            logo_url=b.logo_url,
            origin=b.origin.value if b.origin else None,
            active=b.active,
        )
        for b in brands
    ]


@router.post("/sync", response_model=SyncResultResponse)
def sync_catalog(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Sincroniza el catalogo con Odoo.
    En local usa datos mock para pruebas.
    """
    result = service.sync_catalog_mock(db, current_user.id)
    return SyncResultResponse(**result)


@router.get("/sync-logs")
def get_sync_logs(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Historial de sincronizaciones del catalogo con Odoo."""
    from app.modules.admin.models import CatalogSyncLog
    logs = db.query(CatalogSyncLog).order_by(
        CatalogSyncLog.started_at.desc()
    ).limit(50).all()

    return [
        {
            "id": str(log.id),
            "source": log.source,
            "triggered_by": log.triggered_by,
            "status": log.status.value if log.status else None,
            "products_scanned": log.products_scanned,
            "products_updated": log.products_updated,
            "images_uploaded": log.images_uploaded,
            "duration_ms": log.duration_ms,
            "started_at": log.started_at.isoformat() if log.started_at else None,
            "finished_at": log.finished_at.isoformat() if log.finished_at else None,
            "errors": log.errors,
        }
        for log in logs
    ]
