import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Boolean, Integer, Numeric,
    DateTime, ForeignKey, Text
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy import Enum as SAEnum

from app.database import Base
from app.modules.shared_enums import BrandOrigin


class ProductCategory(Base):
    __tablename__ = "product_categories"

    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name              = Column(String(255), nullable=False)
    slug              = Column(String(255), unique=True, nullable=False)
    parent_id         = Column(UUID(as_uuid=True), ForeignKey("product_categories.id"), nullable=True)
    display_order     = Column(Integer, default=0)
    active            = Column(Boolean, default=True)
    external_id       = Column(String(255), nullable=True)
    source            = Column(String(50), nullable=True)
    created_at        = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at        = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    parent            = relationship("ProductCategory", remote_side=[id], back_populates="children")
    children          = relationship("ProductCategory", back_populates="parent")
    products          = relationship("Product", back_populates="category")


class Brand(Base):
    __tablename__ = "brands"

    id                        = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name                      = Column(String(255), nullable=False)
    logo_url                  = Column(Text, nullable=True)
    brand_discount_percentage = Column(Numeric(5, 2), default=0, nullable=False)
    sale_margin_percentage    = Column(Numeric(5, 2), default=50, nullable=False)
    origin                    = Column(SAEnum(BrandOrigin), nullable=True)
    active                    = Column(Boolean, default=True)
    external_id               = Column(String(255), nullable=True)
    source                    = Column(String(50), nullable=True)
    created_at                = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at                = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    products                  = relationship("Product", back_populates="brand")


class Product(Base):
    __tablename__ = "products"

    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    category_id       = Column(UUID(as_uuid=True), ForeignKey("product_categories.id"), nullable=False)
    brand_id          = Column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False)
    name              = Column(String(255), nullable=False)
    slug              = Column(String(255), unique=True, nullable=False)
    description       = Column(Text, nullable=True)
    list_price        = Column(Numeric(10, 2), nullable=False)
    cost_price        = Column(Numeric(10, 2), nullable=False)
    image_url         = Column(Text, nullable=True)
    image_thumb_url   = Column(Text, nullable=True)
    active            = Column(Boolean, default=True)
    display_order     = Column(Integer, default=0)
    external_id       = Column(String(255), nullable=True)
    source            = Column(String(50), nullable=True)
    last_synced_at    = Column(DateTime, nullable=True)
    source_updated_at = Column(DateTime, nullable=True)
    tags              = Column(ARRAY(String), nullable=True)

    category          = relationship("ProductCategory", back_populates="products")
    brand             = relationship("Brand", back_populates="products")
    variants          = relationship("ProductVariant", back_populates="product")
    images            = relationship("ProductImage", back_populates="product")


class ProductVariant(Base):
    __tablename__ = "product_variants"

    id                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id          = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    sku                 = Column(String(100), unique=True, nullable=False)
    variant_name        = Column(String(255), nullable=True)
    cost_price_override = Column(Numeric(10, 2), nullable=True)
    stock_qty           = Column(Integer, default=0, nullable=False)
    returned_stock_qty  = Column(Integer, default=0, nullable=False)
    image_url           = Column(Text, nullable=True)
    active              = Column(Boolean, default=True)
    display_order       = Column(Integer, default=0)
    external_id         = Column(String(255), nullable=True)
    source              = Column(String(50), nullable=True)

    product             = relationship("Product", back_populates="variants")
    images              = relationship("ProductImage", back_populates="variant")


class ProductImage(Base):
    __tablename__ = "product_images"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id    = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    variant_id    = Column(UUID(as_uuid=True), ForeignKey("product_variants.id"), nullable=True)
    url           = Column(Text, nullable=False)
    thumb_url     = Column(Text, nullable=True)
    s3_key        = Column(String(500), nullable=True)
    display_order = Column(Integer, default=0)
    is_primary    = Column(Boolean, default=False)

    product       = relationship("Product", back_populates="images")
    variant       = relationship("ProductVariant", back_populates="images")
