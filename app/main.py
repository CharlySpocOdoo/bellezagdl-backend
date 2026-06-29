from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

from app.config import settings
from app.database import check_db_connection

from app.modules.admin.wholesale_clients import router_admin as wholesale_clients_router  
from app.modules.auth.router import router as auth_router
from app.modules.vendors.router import router_admin as vendors_admin_router, router_vendor as vendors_router
from app.modules.catalog.router import router as catalog_router, router_admin as catalog_products_admin_router
from app.modules.admin.catalog_import import router_admin as catalog_import_router
from app.modules.orders.router import router as orders_router, router_admin as orders_admin_router
from app.modules.delivery.router import router_delivery, router_shipments
from app.modules.commissions.router import router_admin as commissions_admin_router, router_vendor as commissions_vendor_router
from app.modules.financials.router import router as financials_router

app = FastAPI(
    title="BellezaGDL API",
    description="API de la plataforma e-commerce con red de vendedores.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=(
        ["*"] if settings.environment == "local"
	else ["https://rosadelima.shop", "https://www.rosadelima.shop"]
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(wholesale_clients_router, prefix="/v1/admin/wholesale-clients", tags=["Admin - Mayoreo"])  
app.include_router(auth_router, prefix="/v1/auth", tags=["Auth"])
app.include_router(vendors_admin_router, prefix="/v1/admin/vendors", tags=["Admin - Vendedores"])
app.include_router(vendors_router, prefix="/v1/vendors", tags=["Vendedores"])
app.include_router(catalog_router, prefix="/v1/catalog", tags=["Catalogo"])
app.include_router(catalog_products_admin_router, prefix="/v1/admin/products", tags=["Admin - Productos"])
app.include_router(catalog_import_router, prefix="/v1", tags=["Admin — Catalogo"])
app.include_router(orders_router, prefix="/v1/orders", tags=["Pedidos"])
app.include_router(orders_admin_router, prefix="/v1/admin/orders", tags=["Admin - Pedidos"])
app.include_router(router_delivery, prefix="/v1/delivery-persons", tags=["Repartidores"])
app.include_router(router_shipments, prefix="/v1/admin/shipments", tags=["Admin - Shipments"])
app.include_router(commissions_admin_router, prefix="/v1/admin/commissions", tags=["Admin - Comisiones"])
app.include_router(commissions_vendor_router, prefix="/v1/vendors", tags=["Vendedores"])
app.include_router(financials_router, prefix="/v1/admin", tags=["Admin - Financiero"])


@app.get("/health", tags=["Sistema"])
def health_check():
    db_ok = check_db_connection()
    return {
        "status": "ok" if db_ok else "degraded",
        "database": "connected" if db_ok else "unreachable",
        "environment": settings.environment,
        "version": "1.0.0",
    }


handler = Mangum(app)
