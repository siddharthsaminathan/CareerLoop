"""API configuration — all values sourced from env. No hardcoded secrets."""

import os

# Load .env at import time so the app is self-sufficient and never depends on the
# shell having exported vars (prevents the "SUPABASE_JWT_SECRET not set" 401 class
# of bugs when the server is launched without `set -a; source .env`).
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class Settings:
    # Supabase JWT secret — from Supabase dashboard → Settings → API → JWT Secret
    # Required for all environments. Must be set before running the server.
    SUPABASE_JWT_SECRET: str = os.getenv("SUPABASE_JWT_SECRET", "")

    # DB schema namespace. All tables live in careerloop.*
    DB_SCHEMA: str = os.getenv("CAREERLOOP_DB_SCHEMA", "careerloop")

    # CORS — comma-separated origins. "*" allows all (dev only).
    CORS_ORIGINS: list = (
        os.getenv("CAREERLOOP_API_CORS", "*").split(",")
        if os.getenv("CAREERLOOP_API_CORS")
        else ["*"]
    )

    API_TITLE: str = "CareerLoop API"
    API_VERSION: str = "v1"


settings = Settings()
