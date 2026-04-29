from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
import boto3
import pandas as pd
import io
from decimal import Decimal
from uuid import uuid4

from app.database import get_db
from app.modules.auth.dependencies import require_admin
from app.modules.auth.models import User
from app.modules.catalog.models import ProductCategory, Brand, Product, ProductVariant
from app.config import settings

router_admin = APIRouter(prefix="/admin/catalog", tags=["Admin — Catalogo"])

S3_IMPORT_KEY = "imports/productos.xlsx"


def _get_dataframe() -> pd.DataFrame:
    """Lee el Excel desde disco en local o desde S3 en produccion."""
    if settings.environment == "local":
        return pd.read_excel("productos.xlsx")
    else:
        s3 = boto3.client("s3", region_name=settings.aws_region)
        response = s3.get_object(Bucket=settings.s3_bucket_name, Key=S3_IMPORT_KEY)
        content = response["Body"].read()
        return pd.read_excel(io.BytesIO(content))


def _process_row(db: Session, row) -> dict:
    """Procesa una fila del Excel — agrega o elimina segun columna agregar."""
    categoria_nombre = str(row["categoria"]).strip()
    marca_nombre = str(row["marca"]).strip()
    descuento_pct = Decimal(str(row["descuento_marca_pct"]))
    producto_nombre = str(row["nombre"]).strip()
    precio_lista = Decimal(str(row["precio_lista"]))
    sku = str(row["sku"]).strip()
    variante_nombre = str(row["variante"]).strip()
    agregar = str(row["agregar"]).strip().lower()
    # Campos opcionales
    description = str(row["description"]).strip() if "description" in row and pd.notna(row["description"]) else None
    tags_raw = str(row["tags"]).strip() if "tags" in row and pd.notna(row["tags"]) else None
    tags = [t.strip() for t in tags_raw.split(",")] if tags_raw else None
    # URL de imagen construida automaticamente con el SKU
    image_url = f"https://{settings.s3_bucket_name}.s3.amazonaws.com/productos/{sku.lower()}.jpg"
    image_thumb_url = image_url

    if agregar == "no":
        variante = db.query(ProductVariant).filter(
            ProductVariant.sku == sku
        ).first()
        if variante:
            otras_variantes = db.query(ProductVariant).filter(
                ProductVariant.product_id == variante.product_id,
                ProductVariant.id != variante.id,
            ).count()
            db.delete(variante)
            if otras_variantes == 0:
                producto = db.query(Product).filter(
                    Product.id == variante.product_id
                ).first()
                if producto:
                    db.delete(producto)
            return {"action": "deleted", "sku": sku}
        return {"action": "not_found", "sku": sku}

    # agregar == "si" — crear o actualizar
    categoria = db.query(ProductCategory).filter(
        ProductCategory.name == categoria_nombre
    ).first()
    if not categoria:
        slug = categoria_nombre.lower().replace(" ", "-").replace("á","a").replace("é","e").replace("í","i").replace("ó","o").replace("ú","u")
        categoria = ProductCategory(
            id=uuid4(),
            name=categoria_nombre,
            slug=slug,
            active=True,
            display_order=0,
        )
        db.add(categoria)
        db.flush()

    marca = db.query(Brand).filter(Brand.name == marca_nombre).first()
    if not marca:
        marca = Brand(
            id=uuid4(),
            name=marca_nombre,
            brand_discount_percentage=descuento_pct,
            active=True,
        )
        db.add(marca)
        db.flush()
    else:
        marca.brand_discount_percentage = descuento_pct

    cost_price = round(precio_lista * (1 - descuento_pct / 100), 2)
    slug_producto = producto_nombre.lower().replace(" ", "-").replace("á","a").replace("é","e").replace("í","i").replace("ó","o").replace("ú","u")

    # Buscar por SKU — es el identificador unico
    variante_display = None if variante_nombre == "Unico" else variante_nombre
    variante = db.query(ProductVariant).filter(
        ProductVariant.sku == sku
    ).first()

    if variante:
        # Variante existe — actualizar producto y variante
        producto = db.query(Product).filter(
            Product.id == variante.product_id
        ).first()
        if producto:
            producto.name = producto_nombre
            producto.list_price = precio_lista
            producto.cost_price = Decimal(str(cost_price))
            producto.category_id = categoria.id
            producto.brand_id = marca.id
            slug_nuevo = f"{slug_producto}-{str(producto.id)[:8]}"
            producto.slug = slug_nuevo
            producto.image_url = image_url
            producto.image_thumb_url = image_thumb_url
            if description is not None:
                producto.description = description
            if tags is not None:
                producto.tags = tags
        variante.variant_name = variante_display
        action = "updated"
    else:
        # Variante nueva — buscar si el producto ya existe por nombre y marca
        producto = db.query(Product).filter(
            Product.name == producto_nombre,
            Product.brand_id == marca.id,
        ).first()
        if not producto:
            producto = Product(
                id=uuid4(),
                name=producto_nombre,
                slug=f"{slug_producto}-{str(uuid4())[:8]}",
                category_id=categoria.id,
                brand_id=marca.id,
                list_price=precio_lista,
                cost_price=Decimal(str(cost_price)),
                description=description,
                tags=tags,
                image_url=image_url,
                image_thumb_url=image_thumb_url,
                active=True,
                display_order=0,
            )
            db.add(producto)
            db.flush()
            action = "created"
        else:
            producto.list_price = precio_lista
            producto.cost_price = Decimal(str(cost_price))
            action = "updated"

        variante = ProductVariant(
            id=uuid4(),
            product_id=producto.id,
            sku=sku,
            variant_name=variante_display,
            stock_qty=0,
            returned_stock_qty=0,
            active=True,
            display_order=0,
        )
        db.add(variante)
        if action == "updated":
            action = "variant_added"

    return {"action": action, "sku": sku}


@router_admin.post("/import")
def import_catalog(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Lee productos.xlsx desde disco (local) o S3 (produccion) y actualiza el catalogo."""
    try:
        df = _get_dataframe()
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=f"No se pudo leer el archivo: {str(e)}"
        )

    required = {"categoria", "marca", "descuento_marca_pct", "nombre", "precio_lista", "sku", "variante", "agregar"}
    missing = required - set(df.columns)
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Columnas faltantes en el Excel: {missing}"
        )

    created = updated = deleted = not_found = errors = 0

    for i, row in df.iterrows():
        try:
            result = _process_row(db, row)
            if result["action"] == "created": created += 1
            elif result["action"] in ("updated", "variant_added"): updated += 1
            elif result["action"] == "deleted": deleted += 1
            elif result["action"] == "not_found": not_found += 1
        except Exception as e:
            errors += 1
            db.rollback()
            continue

    db.commit()

    return {
        "status": "completed",
        "created": created,
        "updated": updated,
        "deleted": deleted,
        "not_found": not_found,
        "errors": errors,
    }


@router_admin.delete("/clear")
def clear_catalog(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Elimina todos los productos variantes categorias y marcas."""
    try:
        db.execute(text("SET session_replication_role = replica"))
        db.execute(text("DELETE FROM product_images"))
        db.execute(text("DELETE FROM product_variants"))
        db.execute(text("DELETE FROM products"))
        db.execute(text("DELETE FROM product_categories"))
        db.execute(text("DELETE FROM brands"))
        db.execute(text("SET session_replication_role = DEFAULT"))
        db.commit()
        return {"status": "completed", "message": "Catalogo eliminado correctamente"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
