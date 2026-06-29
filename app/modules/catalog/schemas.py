from pydantic import BaseModel
from typing import Optional, List, Dict
from uuid import UUID
from datetime import datetime
from decimal import Decimal


class CategoryResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    parent_id: Optional[UUID] = None
    display_order: int = 0
    active: bool
    children: List["CategoryResponse"] = []

    class Config:
        from_attributes = True


CategoryResponse.model_rebuild()


class BrandResponse(BaseModel):
    id: UUID
    name: str
    logo_url: Optional[str] = None
    origin: Optional[str] = None
    active: bool

    class Config:
        from_attributes = True


class ProductImageResponse(BaseModel):
    id: UUID
    url: str
    thumb_url: Optional[str] = None
    display_order: int = 0
    is_primary: bool = False

    class Config:
        from_attributes = True


class ProductVariantResponse(BaseModel):
    id: UUID
    sku: str
    variant_name: Optional[str] = None
    stock_qty: int
    returned_stock_qty: int
    total_stock: int
    image_url: Optional[str] = None
    active: bool
    display_order: int = 0

    class Config:
        from_attributes = True


class ProductListResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    description: Optional[str] = None
    category_id: UUID
    category_name: Optional[str] = None
    brand_id: UUID
    brand_name: Optional[str] = None
    image_url: Optional[str] = None
    image_thumb_url: Optional[str] = None
    tags: Optional[List[str]] = None
    display_price: Decimal
    is_oferta_activa: bool = False
    precio_original: Optional[Decimal] = None
    active: bool
    sku_template: Optional[str] = None
    variants: List["ProductVariantResponse"] = []

    class Config:
        from_attributes = True

class ProductDetailResponse(ProductListResponse):
    list_price: Optional[Decimal] = None    # Solo visible para admin
    cost_price: Optional[Decimal] = None    # Solo visible para admin
    retail_price: Optional[Decimal] = None  # Solo visible para admin
    modo_de_uso: Optional[str] = None
    beneficios: Optional[str] = None
    ingredientes: Optional[str] = None
    atributos: Optional[Dict[str, str]] = None
    images: List[ProductImageResponse] = []


class UpdateOfertaRequest(BaseModel):
    """
    Define el estado completo de la oferta de un producto — no es un PATCH
    parcial. Para desactivar una oferta, enviar los 4 campos en null.
    """
    oferta_inicio: Optional[datetime] = None
    oferta_fin: Optional[datetime] = None
    precio_oferta: Optional[Decimal] = None
    descuento_oferta_pct: Optional[Decimal] = None


class SyncResultResponse(BaseModel):
    status: str
    products_scanned: int = 0
    products_updated: int = 0
    images_uploaded: int = 0
    duration_ms: int = 0
    errors: List[str] = []
