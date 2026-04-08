from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

from app.config import settings
from app.database import check_db_connection


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

# Aquí se agregan los routers conforme se construyen los módulos.
# Ejemplo (descomentar en 2C):
# from app.modules.auth.router import router as auth_router
# app.include_router(auth_router, prefix="/v1/auth", tags=["Auth"])


@app.get("/health", tags=["Sistema"])
def health_check():
    """
    Verifica que la API y la base de datos estén funcionando.
    Usado por el CI/CD para confirmar que el deploy fue exitoso.
    """
    db_ok = check_db_connection()
    return {
        "status": "ok" if db_ok else "degraded",
        "database": "connected" if db_ok else "unreachable",
        "environment": settings.environment,
        "version": "1.0.0",
    }


handler = Mangum(app)
