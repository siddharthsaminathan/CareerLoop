"""Brief service — orchestrates brief reads + item selection."""

from careerloop_api.core.envelope import APIError
from careerloop_api.repositories.briefs_repo import BriefsRepo
from careerloop_api.services import serializers
from careerloop.session.session_store import SessionStore


class BriefService:
    def __init__(self, db):
        self.db = db
        self.repo = BriefsRepo(db)

    def latest(self, user_id: str) -> dict:
        b = self.repo.get_latest_brief(user_id)
        if not b:
            raise APIError("No brief found. Run a scan to generate your first brief.",
                           status_code=404, code="no_brief")
        items = self.repo.get_items(b["id"])
        return serializers.brief(b, items)

    def select_item(self, user_id: str, brief_id: str, item_index: int) -> dict:
        b = self.repo.get_brief_by_id(brief_id, user_id)
        if not b:
            raise APIError("Brief not found for this user.", status_code=404, code="brief_not_found")
        item = self.repo.get_item_at_index(brief_id, item_index)
        if not item:
            raise APIError(f"Item index {item_index} not found in this brief.",
                           status_code=404, code="item_not_found")

        # Persist active context to the session so chat/select stays coherent.
        job_id = str(item["job_id"]) if item.get("job_id") is not None else None
        try:
            store = SessionStore(self.db)
            session = store.get_session(user_id)
            session.active_artifact_type = "job_card"
            session.active_brief_id = brief_id
            session.active_job_id = job_id
            session.current_selection_index = item_index
            store.save_session(session)
        except Exception:
            # Selection still succeeds even if session persistence hiccups.
            pass

        return {
            "job_id": job_id,
            "active_artifact_type": "job_card",
            "active_brief_id": brief_id,
            "selected_index": item_index,
            "card": serializers.brief_item(item),
        }
