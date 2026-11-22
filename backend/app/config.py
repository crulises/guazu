from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración por variables de entorno. Nada acoplado a Supabase por nombre."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Cualquier Postgres con PostGIS. Por defecto, el del Supabase CLI local de guazu.
    database_url: str = "postgresql://postgres:postgres@127.0.0.1:55322/postgres"

    # API del proveedor de auth (GoTrue), usada por /v1/auth/* (corte 1).
    auth_url: str | None = "http://127.0.0.1:55321/auth/v1"
    auth_api_key: str | None = None
    jwks_url: str | None = "http://127.0.0.1:55321/auth/v1/.well-known/jwks.json"
    jwt_secret: str = "super-secret-jwt-token-with-at-least-32-characters-long"
    jwt_audience: str = "authenticated"

    # Proxies confiables delante del backend (0 = ninguno: se usa la IP del socket).
    proxy_hops: int = 0

    # Orígenes web que pueden llamar a la API (panel de plataforma), separados por coma.
    cors_origins: str = "http://localhost:8180,http://127.0.0.1:8180"

    log_level: str = "INFO"

    # Lo fija el build de la imagen; /v1/salud lo informa («Acerca de» de las apps).
    app_version: str = "0.0.0-dev"
    app_commit: str = "local"
    app_built_at: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
