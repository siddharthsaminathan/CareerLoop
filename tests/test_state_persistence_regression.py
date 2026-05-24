import os
import sqlite3
import tempfile
import unittest
from contextlib import contextmanager

from careerloop.onboarding.onboarding_flow import OnboardingFlow
from careerloop.session.session_store import Session, SessionStore
from careerloop.session.states import UserState


class DictRow(dict):
    pass


def row_factory(cursor, row):
    return DictRow(zip([d[0] for d in cursor.description], row))


class SQLiteCursor:
    def __init__(self, conn):
        self.cur = conn.cursor()

    def execute(self, sql, params=()):
        self.cur.execute(sql.replace("%s", "?"), params)
        return self

    def fetchone(self):
        return self.cur.fetchone()

    def fetchall(self):
        return self.cur.fetchall()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass


class SQLiteConn:
    def __init__(self, path):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = row_factory

    def cursor(self):
        return SQLiteCursor(self.conn)

    def commit(self):
        self.conn.commit()

    def rollback(self):
        self.conn.rollback()

    def close(self):
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, *_):
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.close()


class FakeDbManager:
    def __init__(self, db_path):
        self.db_path = db_path

    @contextmanager
    def get_connection(self):
        conn = SQLiteConn(self.db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()


class StatePersistenceRegressionTest(unittest.TestCase):
    def setUp(self):
        os.environ.pop("DATABASE_URL", None)
        self.tmp = tempfile.NamedTemporaryFile(delete=False)
        self.tmp.close()
        with sqlite3.connect(self.tmp.name) as conn:
            conn.executescript(
                """
                CREATE TABLE users (
                    id TEXT PRIMARY KEY,
                    email TEXT,
                    full_name TEXT,
                    master_cv_markdown TEXT,
                    work_style_prefs TEXT DEFAULT '{}',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE sessions (
                    user_id TEXT PRIMARY KEY,
                    state TEXT DEFAULT 'IDLE',
                    current_job_id TEXT,
                    onboarding_step INTEGER DEFAULT 0,
                    temp_profile_data TEXT DEFAULT '{}',
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
        self.store = SessionStore(FakeDbManager(self.tmp.name))

    def tearDown(self):
        os.unlink(self.tmp.name)

    def insert_complete_user(self, user_id="u1"):
        with sqlite3.connect(self.tmp.name) as conn:
            conn.execute(
                """
                INSERT INTO users (id, email, master_cv_markdown, work_style_prefs)
                VALUES (?, ?, ?, ?)
                """,
                (
                    user_id,
                    f"{user_id}@example.com",
                    "## CV\nExperienced AI engineer",
                    """{
                        "target_roles": "AI Engineer",
                        "target_cities": "Bangalore",
                        "salary_expectations": "25 LPA",
                        "notice_period": "30 days",
                        "aggressiveness": "quality over quantity"
                    }""",
                ),
            )

    def test_legacy_daily_brief_state_loads_and_persists_as_profile_complete(self):
        self.insert_complete_user()
        with sqlite3.connect(self.tmp.name) as conn:
            conn.execute(
                "INSERT INTO sessions (user_id, state) VALUES (?, ?)",
                ("u1", "DAILY_BRIEF_SENT"),
            )

        session = self.store.get_session("u1")

        self.assertEqual(session.state, UserState.PROFILE_COMPLETE)
        with sqlite3.connect(self.tmp.name) as conn:
            state = conn.execute(
                "SELECT state FROM sessions WHERE user_id = ?", ("u1",)
            ).fetchone()[0]
        self.assertEqual(state, "PROFILE_COMPLETE")

    def test_invalid_session_recovers_to_profile_complete_when_profile_is_complete(self):
        self.insert_complete_user()
        with sqlite3.connect(self.tmp.name) as conn:
            conn.execute(
                "INSERT INTO sessions (user_id, state) VALUES (?, ?)",
                ("u1", "BROKEN_STATE"),
            )

        session = self.store.get_session("u1")

        self.assertEqual(session.state, UserState.PROFILE_COMPLETE)

    def test_onboarding_commit_does_not_overwrite_existing_fields_with_blanks(self):
        self.insert_complete_user()
        flow = OnboardingFlow(self.store)

        flow._commit_profile_to_db(
            "u1",
            {
                "cv_content": "",
                "target_roles": "AI Product Lead",
                "target_cities": "",
                "salary_expectations": "N/A",
                "notice_period": "",
                "aggressiveness": "selective",
            },
        )

        with sqlite3.connect(self.tmp.name) as conn:
            row = conn.execute(
                "SELECT master_cv_markdown, work_style_prefs FROM users WHERE id = ?",
                ("u1",),
            ).fetchone()

        self.assertIn("Experienced AI engineer", row[0])
        self.assertIn("AI Product Lead", row[1])
        self.assertIn("Bangalore", row[1])
        self.assertIn("25 LPA", row[1])
        self.assertIn("selective", row[1])


if __name__ == "__main__":
    unittest.main()
