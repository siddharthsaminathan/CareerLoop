"""
CareerLoop Persistent Memory Layer — Local SQLite persistence infrastructure.

Exports models, repository interface, context-aware retrieval service,
and context manager interfaces for seamless integration across upstream workflows.
"""

from careerloop.memory.connection import DatabaseManager, get_db_manager, get_connection
from careerloop.memory.models import (
    UserModel,
    StrategicTrackModel,
    ApplicationLedgerModel,
    CompanyMemoryModel,
    PositioningMemoryModel,
    EventTimelineModel,
)
from careerloop.memory.repository import MemoryRepository
from careerloop.memory.retrieval import MemoryRetrievalService

__all__ = [
    "DatabaseManager",
    "get_db_manager",
    "get_connection",
    "UserModel",
    "StrategicTrackModel",
    "ApplicationLedgerModel",
    "CompanyMemoryModel",
    "PositioningMemoryModel",
    "EventTimelineModel",
    "MemoryRepository",
    "MemoryRetrievalService",
]
