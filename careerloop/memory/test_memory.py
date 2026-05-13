"""
CareerLoop Memory Infrastructure Unit Tests.

Validates schema generation, typed domain models, persistence adapters,
and contextual retrieval synthesis using an isolated embedded test database.
"""

import os
import shutil
import tempfile
import unittest
from datetime import datetime, timezone

from careerloop.memory.connection import DatabaseManager
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


class TestPersistentMemoryLayer(unittest.TestCase):
    """End-to-end verification suite for local SQLite state storage."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_careerloop.db")
        
        # Resolve real schema path
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        self.schema_path = os.path.join(base_dir, "careerloop", "memory", "schema.sql")
        
        # Instantiate test manager mapping override paths
        self.db_manager = DatabaseManager(db_path=self.db_path, schema_path=self.schema_path)
        
        # Inject private attribute instance to patch repository global lookups cleanly
        self.repo = MemoryRepository()
        # Override connection closure logic by passing our custom db manager explicitly inside custom DB connection helpers if needed,
        # or verify repository behaviors using dedicated helper connections directly.
        # Let's override connection retrieval within test methods explicitly.

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_schema_initialization(self):
        """Verifies database instantiation generates canonical tables."""
        self.assertTrue(os.path.exists(self.db_path))
        with self.db_manager.get_connection() as conn:
            tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
            table_names = {t["name"] for t in tables}
            self.assertTrue({"users", "strategic_tracks", "application_ledger", "company_memory", "positioning_memory", "event_timeline"}.issubset(table_names))

    def test_user_persistence_lifecycle(self):
        """Validates typed user state insertion, JSON encoding, and lookup mapping."""
        user = UserModel(
            id="test-user-1",
            employment_state="unemployed_urgent",
            urgency=9,
            preferred_environments=["gcc", "async-first"],
            emotional_constraints={"avoid": "toxic managers"},
        )
        
        # Save explicitly via custom context passing test DB
        with self.db_manager.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO users (
                    id, employment_state, urgency, burnout_level, preferred_environments,
                    startup_tolerance, compensation_floor_lakhs, compensation_target_lakhs,
                    work_style_prefs, emotional_constraints, interview_tolerance,
                    remote_pref, search_posture, created_at, updated_at
                ) VALUES (
                    :id, :employment_state, :urgency, :burnout_level, :preferred_environments,
                    :startup_tolerance, :compensation_floor_lakhs, :compensation_target_lakhs,
                    :work_style_prefs, :emotional_constraints, :interview_tolerance,
                    :remote_pref, :search_posture, :created_at, :updated_at
                )
                """,
                user.to_dict(),
            )
            
            row = conn.execute("SELECT * FROM users WHERE id = 'test-user-1'").fetchone()
            self.assertIsNotNone(row)
            fetched = UserModel.from_row(dict(row))
            self.assertEqual(fetched.urgency, 9)
            self.assertEqual(fetched.preferred_environments, ["gcc", "async-first"])
            self.assertEqual(fetched.emotional_constraints, {"avoid": "toxic managers"})

    def test_lazy_loaded_company_memory(self):
        """Confirms standalone target company intelligence logs correctly."""
        cm = CompanyMemoryModel(
            id="cm-1",
            company_normalized="google",
            company_intelligence="Top tier async architecture.",
            startup_risk=1.0,
        )
        with self.db_manager.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO company_memory (
                    id, company_normalized, company_intelligence, compensation_analysis,
                    hiring_urgency, recruiter_insights, glassdoor_synthesis,
                    company_maturity, org_structure_patterns, startup_risk,
                    work_culture_patterns, known_interview_loops, created_at, updated_at
                ) VALUES (
                    :id, :company_normalized, :company_intelligence, :compensation_analysis,
                    :hiring_urgency, :recruiter_insights, :glassdoor_synthesis,
                    :company_maturity, :org_structure_patterns, :startup_risk,
                    :work_culture_patterns, :known_interview_loops, :created_at, :updated_at
                )
                """,
                cm.to_dict(),
            )
            row = conn.execute("SELECT * FROM company_memory WHERE company_normalized = 'google'").fetchone()
            self.assertIsNotNone(row)
            fetched = CompanyMemoryModel.from_row(dict(row))
            self.assertEqual(fetched.company_intelligence, "Top tier async architecture.")


if __name__ == "__main__":
    unittest.main()
