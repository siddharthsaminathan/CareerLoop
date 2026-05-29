"""DB dependency — reuses the existing CareerLoop DatabaseManager singleton."""

from careerloop.memory.connection import get_db_manager


def get_db():
    """FastAPI dependency: returns the shared DatabaseManager."""
    return get_db_manager()
