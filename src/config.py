"""Application configuration."""
import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    model_config = SettingsConfigDict(env_file=".env", extra="allow")
    
    # Database - Supabase PostgreSQL connection
    # Format: postgresql://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "postgresql://postgres:postgres@localhost:5432/geo_bucket_db"
    )
    
    # Geo-bucket configuration
    GEO_BUCKET_GRID_SIZE: float = 0.005  # ~500 meters
    FUZZY_MATCH_THRESHOLD: float = 0.3   # pg_trgm similarity threshold
    
    # Location normalization
    LOCATION_STOP_WORDS: set = {"lagos", "nigeria", "state", "lga", "area", "estate"}


settings = Settings()

