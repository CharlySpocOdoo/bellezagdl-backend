from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

from app.config import settings
from app.database import check_db_connection

from app.modules.auth.router import router as auth_router
from app.modules.vendors.router import router_admin as vendors_admin_router, router_vendor as vendors_router
from app.modules.catalog.router import router as catalog_router

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
        else ["https://bellezagdl.com", "https://staging.bellezagdl.com"]
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/v1/auth", tags=["Auth"])
app.include_router(vendors_admin_router, prefix="/v1/admin/vendors", tags=["Admin - Vendedores"])
app.include_router(vendors_router, prefix="/v1/vendors", tags=["Vendedores"])
app.include_router(catalog_router, prefix="/v1/catalog", tags=["Catalogo"])


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
