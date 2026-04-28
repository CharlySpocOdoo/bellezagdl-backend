from app.database import get_db

# Re-exporta get_db para que los módulos importen desde aquí.
# En 2C se agregan: get_current_user, require_admin, require_vendor, etc.

__all__ = ["get_db"]
