"""Brief service — orchestrates brief reads + item selection."""

import logging

from careerloop_api.core.envelope import APIError
from careerloop_api.repositories.briefs_repo import BriefsRepo
from careerloop_api.services import serializers
from careerloop.session.session_store import SessionStore

logger = logging.getLogger("careerloop_api.services.brief")


class BriefService:
    def __init__(self, db):
        self.db = db
        self.repo = BriefsRepo(db)

    def latest(self, user_id: str, offset: int = 0) -> dict:
        b = self.repo.get_latest_brief(user_id, offset=offset)
        if not b:
            raise APIError("No brief found for this offset.",
                           status_code=404, code="no_brief")
        items = self.repo.get_items(b["id"])
        has_more = self.repo.get_latest_brief(user_id, offset=offset + 1) is not None
        
        data = serializers.brief(b, items)
        data["has_more"] = has_more
        data["offset"] = offset
        return data

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
        except Exception as e:
            logger.warning("Session persistence failed for user %s brief %s item %d: %s",
                           user_id[:12], brief_id[:12], item_index, e)
            # Selection still succeeds even if session persistence hiccups.

        return {
            "job_id": job_id,
            "active_artifact_type": "job_card",
            "active_brief_id": brief_id,
            "selected_index": item_index,
            "card": serializers.brief_item(item),
        }
