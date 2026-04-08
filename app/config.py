from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Base de datos
    database_url: str

    # JWT
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 30

    # AWS / MinIO
    aws_access_key_id: str
    aws_secret_access_key: str
    aws_region: str = "us-east-1"
    s3_bucket_name: str
    s3_endpoint_url: str | None = None

    # Email
    smtp_host: str
    smtp_port: int = 2525
    smtp_user: str
    smtp_password: str
    emails_from: str

    # Odoo
    odoo_url: str
    odoo_db: str
    odoo_user: str
    odoo_password: str

    # Ambiente
    environment: str = "local"

    class Config:
        env_file = ".env"


settings = Settings()
