import pandas as pd
import sys
import os
from decimal import Decimal
from uuid import uuid4

# Agregar el path del proyecto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.modules.catalog.models import ProductCategory, Brand, Product, ProductVariant

def load_products(excel_path: str):
    df = pd.read_excel(excel_path)
    db = SessionLocal()
    
    productos_creados = 0
    variantes_creadas = 0
    errores = []

    try:
        for _, row in df.iterrows():
            try:
                categoria_nombre = str(row['categoria']).strip()
                marca_nombre = str(row['marca']).strip()
                descuento_pct = Decimal(str(row['descuento_marca_pct']))
                producto_nombre = str(row['nombre']).strip()
                precio_lista = Decimal(str(row['precio_lista']))
                sku = str(row['sku']).strip()
                variante_nombre = str(row['variante']).strip()

                # --- Categoria ---
                categoria = db.query(ProductCategory).filter(
                    ProductCategory.name == categoria_nombre
                ).first()
                if not categoria:
                    slug = categoria_nombre.lower().replace(' ', '-').replace('á','a').replace('é','e').replace('í','i').replace('ó','o').replace('ú','u')
                    categoria = ProductCategory(
                        id=uuid4(),
                        name=categoria_nombre,
                        slug=slug,
                        active=True,
                        display_order=0,
                    )
                    db.add(categoria)
                    db.flush()
                    print(f"  Categoria creada: {categoria_nombre}")

                # --- Marca ---
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
                    print(f"  Marca creada: {marca_nombre}")
                else:
                    marca.brand_discount_percentage = descuento_pct

                # --- Producto ---
                cost_price = round(precio_lista * (1 - descuento_pct / 100), 2)
                slug_producto = producto_nombre.lower().replace(' ', '-').replace('á','a').replace('é','e').replace('í','i').replace('ó','o').replace('ú','u')

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
                        active=True,
                        display_order=0,
                    )
                    db.add(producto)
                    db.flush()
                    productos_creados += 1
                    print(f"  Producto creado: {producto_nombre}")
                else:
                    producto.list_price = precio_lista
                    producto.cost_price = Decimal(str(cost_price))

                # --- Variante ---
                variante_display = None if variante_nombre == 'Unico' else variante_nombre
                variante = db.query(ProductVariant).filter(
                    ProductVariant.sku == sku
                ).first()
                if not variante:
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
                    variantes_creadas += 1
                    print(f"    Variante creada: {sku} — {variante_nombre}")
                else:
                    variante.variant_name = variante_display
                    variante.product_id = producto.id

            except Exception as e:
                errores.append(f"Fila {_+2}: {str(e)}")
                print(f"  ERROR en fila {_+2}: {e}")
                continue

        db.commit()
        print(f"\n✅ Carga completada:")
        print(f"   Productos creados: {productos_creados}")
        print(f"   Variantes creadas: {variantes_creadas}")
        if errores:
            print(f"   Errores: {len(errores)}")
            for error in errores:
                print(f"   - {error}")

    except Exception as e:
        db.rollback()
        print(f"\n❌ Error general: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    excel_path = sys.argv[1] if len(sys.argv) > 1 else "productos.xlsx"
    if not os.path.exists(excel_path):
        print(f"❌ No se encontro el archivo: {excel_path}")
        sys.exit(1)
    print(f"Cargando productos desde: {excel_path}")
    load_products(excel_path)