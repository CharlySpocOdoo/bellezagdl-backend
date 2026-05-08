from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
import boto3
import io
from decimal import Decimal
from uuid import uuid4
from openpyxl import load_workbook

from app.database import get_db
from app.modules.auth.dependencies import require_admin
from app.modules.auth.models import User
from app.modules.catalog.models import ProductCategory, Brand, Product, ProductVariant
from app.config import settings

router_admin = APIRouter(prefix="/admin/catalog", tags=["Admin — Catalogo"])

S3_IMPORT_KEY = "imports/productos.xlsx"


def _get_worksheet():
    if settings.environment == "local":
        wb = load_workbook("productos.xlsx", data_only=True)
    else:
        s3 = boto3.client("s3", region_name=settings.aws_region)
        response = s3.get_object(Bucket=settings.s3_bucket_name, Key=S3_IMPORT_KEY)
        content = response["Body"].read()
        wb = load_workbook(io.BytesIO(content), data_only=True)
    return wb.active


def _notna(value) -> bool:
    return value is not None and str(value).strip() != ""


def _process_row(db: Session, row: dict) -> dict:
    categoria_nombre = str(row["categoria"]).strip()
    marca_nombre = str(row["marca"]).strip()
    descuento_pct = Decimal(str(row["descuento_marca_pct"]))
    producto_nombre = str(row["nombre"]).strip()
    precio_lista = Decimal(str(row["precio_lista"]))
    sku = str(row["sku"]).strip()
    variante_nombre = str(row["variante"]).strip()
    agregar = str(row["agregar"]).strip().lower()
    description = str(row["description"]).strip() if _notna(row.get("description")) else None
    tags_raw = str(row["tags"]).strip() if _notna(row.get("tags")) else None
    tags = [t.strip() for t in tags_raw.split(",")] if tags_raw else None
    disponible_oferta = str(row.get('oferta', '')).strip().lower() == 'si' if _notna(row.get('oferta')) else False
    precio_oferta_val = Decimal(str(row['precio_oferta'])) if _notna(row.get('precio_oferta')) and disponible_oferta else None
    image_url = f"https://{settings.s3_bucket_name}.s3.amazonaws.com/productos/{sku.upper()}.jpg"
    image_thumb_url = image_url

    categoria = db.query(ProductCategory).filter(ProductCategory.name == categoria_nombre).first()
    if not categoria:
        slug_base = categoria_nombre.lower().replace(" ", "-").replace("á","a").replace("é","e").replace("í","i").replace("ó","o").replace("ú","u")
        # Verificar que el slug no exista ya
        slug = slug_base
        slug_exists = db.query(ProductCategory).filter(ProductCategory.slug == slug).first()
        if slug_exists:
            slug = f"{slug_base}-{str(uuid4())[:4]}"
        categoria = ProductCategory(id=uuid4(), name=categoria_nombre, slug=slug, active=True, display_order=0)
        db.add(categoria)
        db.flush()

    marca = db.query(Brand).filter(Brand.name == marca_nombre).first()
    if not marca:
        marca = Brand(id=uuid4(), name=marca_nombre, brand_discount_percentage=descuento_pct, active=True)
        db.add(marca)
        db.flush()
    else:
        marca.brand_discount_percentage = descuento_pct
    if agregar == "no":
        # Si es el template (variante=Unico) guardar sku_template sin crear variante
        if variante_nombre == "Unico":
            # La marca y categoria ya fueron procesadas arriba
            producto = db.query(Product).filter(
                Product.name == producto_nombre,
                Product.brand_id == marca.id,
            ).first()
            if producto:
                producto.sku_template = sku
                return {"action": "updated", "sku": sku}
            return {"action": "not_found", "sku": sku}
        # Si no es template — eliminar variante por SKU
        variante = db.query(ProductVariant).filter(ProductVariant.sku == sku).first()
        if variante:
            otras_variantes = db.query(ProductVariant).filter(
                ProductVariant.product_id == variante.product_id,
                ProductVariant.id != variante.id,
            ).count()
            db.delete(variante)
            if otras_variantes == 0:
                producto = db.query(Product).filter(Product.id == variante.product_id).first()
                if producto:
                    db.delete(producto)
            return {"action": "deleted", "sku": sku}
        return {"action": "not_found", "sku": sku}


    cost_price = round(precio_lista * (1 - descuento_pct / 100), 2)
    slug_producto = producto_nombre.lower().replace(" ", "-").replace("á","a").replace("é","e").replace("í","i").replace("ó","o").replace("ú","u")
    variante_display = None if variante_nombre == "Unico" else variante_nombre
    variante = db.query(ProductVariant).filter(ProductVariant.sku == sku).first()

    if variante:
        producto = db.query(Product).filter(Product.id == variante.product_id).first()
        if producto:
            producto.name = producto_nombre
            producto.list_price = precio_lista
            producto.cost_price = Decimal(str(cost_price))
            # No sobreescribir disponible_oferta — se maneja desde el template
            # No sobreescribir precio_oferta — se maneja desde el template
            producto.category_id = categoria.id
            producto.brand_id = marca.id
            producto.slug = f"{slug_producto}-{str(producto.id)[:8]}"
            producto.image_url = image_url
            producto.image_thumb_url = image_thumb_url
            if description is not None:
                producto.description = description
            if tags is not None:
                producto.tags = tags
        variante.variant_name = variante_display
        action = "updated"
    else:
        producto = db.query(Product).filter(Product.name == producto_nombre, Product.brand_id == marca.id).first()
        if not producto:
            producto = Product(
                id=uuid4(), name=producto_nombre,
                slug=f"{slug_producto}-{str(uuid4())[:8]}",
                category_id=categoria.id, brand_id=marca.id,
                list_price=precio_lista, cost_price=Decimal(str(cost_price)),
                description=description, tags=tags,
                image_url=image_url, image_thumb_url=image_thumb_url,
                disponible_oferta=disponible_oferta, precio_oferta=precio_oferta_val,
                active=True, display_order=0,
            )
            db.add(producto)
            db.flush()
            action = "created"
        else:
            producto.list_price = precio_lista
            producto.cost_price = Decimal(str(cost_price))
            # No sobreescribir disponible_oferta — se maneja desde el template
            # No sobreescribir precio_oferta — se maneja desde el template
            action = "updated"

        variante = ProductVariant(
            id=uuid4(), product_id=producto.id, sku=sku,
            variant_name=variante_display, stock_qty=0, returned_stock_qty=0,
            image_url=image_url, active=True, display_order=0,
        )
        db.add(variante)
        if action == "updated":
            action = "variant_added"

    # Si es producto simple (variante=Unico y agregar=si) guardar sku_template
    if variante_nombre == "Unico" and producto:
        producto.sku_template = sku

    return {"action": action, "sku": sku}


@router_admin.post("/import")
def import_catalog(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        ws = _get_worksheet()
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"No se pudo leer el archivo: {str(e)}")

    headers = [cell.value for cell in ws[1]]
    required = {"categoria", "marca", "descuento_marca_pct", "nombre", "precio_lista", "sku", "variante", "agregar"}
    missing = required - set(h for h in headers if h)
    if missing:
        raise HTTPException(status_code=422, detail=f"Columnas faltantes en el Excel: {missing}")

    created = updated = deleted = not_found = errors = 0
    sku_template_pendiente = None
    oferta_pendiente = None
    precio_oferta_pendiente = None
    nombre_template_pendiente = None

    for row_values in ws.iter_rows(min_row=2, values_only=True):
        if not any(v is not None for v in row_values):
            continue
        row = dict(zip(headers, row_values))
        agregar_val = str(row.get('agregar', '')).strip().lower()
        variante_val = str(row.get('variante', '')).strip()
        nombre_val = str(row.get('nombre', '')).strip()
        if variante_val == 'Unico' and agregar_val == 'no':
            sku_template_pendiente = str(row.get('sku', '')).strip()
            oferta_pendiente = str(row.get('oferta', '')).strip().lower() == 'si' if _notna(row.get('oferta')) else False
            precio_oferta_pendiente = Decimal(str(row.get('precio_oferta', '0'))) if _notna(row.get('precio_oferta')) else None
            nombre_template_pendiente = nombre_val
            continue
        try:
            result = _process_row(db, row)
            if sku_template_pendiente and nombre_template_pendiente == nombre_val:
                from app.modules.catalog.models import Product as ProductModel
                prod_obj = db.query(ProductModel).filter(ProductModel.name == nombre_val).first()
                if prod_obj:
                    prod_obj.sku_template = sku_template_pendiente
                    prod_obj.disponible_oferta = oferta_pendiente
                    prod_obj.precio_oferta = precio_oferta_pendiente
                    oferta_pendiente = None
                    precio_oferta_pendiente = None
                    sku_template_pendiente = None
                    nombre_template_pendiente = None
            if result["action"] == "created": created += 1
            elif result["action"] in ("updated", "variant_added"): updated += 1
            elif result["action"] == "deleted": deleted += 1
            elif result["action"] == "not_found": not_found += 1
        except Exception as e:
            errors += 1
            print(f"ERROR fila {idx}: {str(e)}")
            db.rollback()
            continue

    db.commit()
    return {"status": "completed", "created": created, "updated": updated, "deleted": deleted, "not_found": not_found, "errors": errors}


@router_admin.delete("/clear")
def clear_catalog(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
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
