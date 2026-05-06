from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
from decimal import Decimal

from app.database import get_db
from app.modules.catalog.models import Brand, Product, ProductVariant
from app.modules.catalog.service import calculate_sale_price, get_variants, get_total_stock
from pydantic import BaseModel

router_public = APIRouter(prefix="/public", tags=["Vitrina Publica"])


# --- Schemas ---

class VitrinavariantResponse(BaseModel):
    id: UUID
    sku: str
    variant_name: Optional[str] = None
    image_url: Optional[str] = None
    active: bool
    display_order: int = 0

    class Config:
        from_attributes = True


class VitrinaProductResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    image_thumb_url: Optional[str] = None
    tags: Optional[List[str]] = None
    sale_price: Decimal
    brand_name: str
    category_name: Optional[str] = None
    variants: List[VitrinavariantResponse] = []

    class Config:
        from_attributes = True


# --- Endpoints ---

@router_public.get("/vitrina/{brand_slug}", response_model=List[VitrinaProductResponse])
def get_vitrina(brand_slug: str, db: Session = Depends(get_db)):
    """Listado publico de productos de una marca. Sin autenticacion."""
    brand = db.query(Brand).filter(
        Brand.name.ilike(brand_slug.replace("-", " ")),
        Brand.active == True,
    ).first()
    if not brand:
        raise HTTPException(status_code=404, detail="Marca no encontrada")

    products = db.query(Product).filter(
        Product.brand_id == brand.id,
        Product.active == True,
    ).all()

    result = []
    for product in products:
        variants = get_variants(db, product.id)
        sale_price = calculate_sale_price(product.cost_price, brand.sale_margin_percentage or Decimal("50"))
        variant_responses = [
            VitrinavariantResponse(
                id=v.id,
                sku=v.sku,
                variant_name=v.variant_name,
                image_url=v.image_url,
                active=v.active,
                display_order=v.display_order,
            )
            for v in variants if v.active
        ]
        result.append(VitrinaProductResponse(
            id=product.id,
            name=product.name,
            slug=product.slug,
            description=product.description,
            image_url=product.image_url,
            image_thumb_url=product.image_thumb_url,
            tags=product.tags,
            sale_price=sale_price,
            brand_name=brand.name,
            category_name=None,
            variants=variant_responses,
        ))

    return result


@router_public.get("/vitrina/{brand_slug}/products/{product_id}", response_model=VitrinaProductResponse)
def get_vitrina_product(brand_slug: str, product_id: UUID, db: Session = Depends(get_db)):
    """Detalle publico de un producto. Sin autenticacion."""
    brand = db.query(Brand).filter(
        Brand.name.ilike(brand_slug.replace("-", " ")),
        Brand.active == True,
    ).first()
    if not brand:
        raise HTTPException(status_code=404, detail="Marca no encontrada")

    product = db.query(Product).filter(
        Product.id == product_id,
        Product.brand_id == brand.id,
        Product.active == True,
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Producto no encontrado")

    variants = get_variants(db, product.id)
    sale_price = calculate_sale_price(product.cost_price, brand.sale_margin_percentage or Decimal("50"))
    variant_responses = [
        VitrinavariantResponse(
            id=v.id,
            sku=v.sku,
            variant_name=v.variant_name,
            image_url=v.image_url,
            active=v.active,
            display_order=v.display_order,
        )
        for v in variants if v.active
    ]

    return VitrinaProductResponse(
        id=product.id,
        name=product.name,
        slug=product.slug,
        description=product.description,
        image_url=product.image_url,
        image_thumb_url=product.image_thumb_url,
        tags=product.tags,
        sale_price=sale_price,
        brand_name=brand.name,
        category_name=None,
        variants=variant_responses,
    )
