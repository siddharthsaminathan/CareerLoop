from enum import Enum
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone

class ActionType(str, Enum):
    SHOW_STATUS = "SHOW_STATUS"
    SHOW_PROFILE = "SHOW_PROFILE"
    START_SCAN = "START_SCAN"
    SHOW_BRIEF = "SHOW_BRIEF"
    SELECT_BRIEF_ITEM = "SELECT_BRIEF_ITEM"
    REVIEW_JOB = "REVIEW_JOB"
    SKIP_JOB = "SKIP_JOB"
    SAVE_JOB = "SAVE_JOB"
    SHOW_COMPANY_INTEL = "SHOW_COMPANY_INTEL"
    SHOW_PEOPLE_TO_REACH = "SHOW_PEOPLE_TO_REACH"
    PREPARE_APPLICATION_PACK = "PREPARE_APPLICATION_PACK"
    EDIT_APPLICATION_PACK = "EDIT_APPLICATION_PACK"
    MARK_APPLIED = "MARK_APPLIED"
    SHOW_PIPELINE = "SHOW_PIPELINE"
    GENERAL_CHAT = "GENERAL_CHAT"
    HELP = "HELP"
    RESET_SESSION = "RESET_SESSION"

@dataclass
class Action:
    action_type: ActionType
    user_id: str
    session_id: Optional[str] = None
    artifact_id: Optional[str] = None
    artifact_type: Optional[str] = None
    target_id: Optional[str] = None
    raw_text: Optional[str] = None
    parsed_args: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

@dataclass
class ResponseEnvelope:
    response_type: str  # text | card | list | document | error
    text: str
    cards: List[Dict[str, Any]] = field(default_factory=list)
    actions: List[Dict[str, Any]] = field(default_factory=list)
    artifact_context_updates: Dict[str, Any] = field(default_factory=dict)
    state_updates: Dict[str, Any] = field(default_factory=dict)
    debug_metadata: Dict[str, Any] = field(default_factory=dict)
