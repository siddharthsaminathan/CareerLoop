import json
from typing import Dict, Any, Optional

class KimiBridgeExecutor:
    """
    Headless Execution Layer using Kimi K2 Webbridge.
    This module takes an Application Pack and a target URL, and automates
    the ATS data entry upon "Approve & Auto-Apply".
    """
    
    def __init__(self, api_key: Optional[str] = None, endpoint: Optional[str] = None):
        """
        Initialize the Kimi Webbridge executor.
        Will be configured to talk to the Hostinger-deployed Hermes agent.
        """
        self.api_key = api_key
        self.endpoint = endpoint or "https://hermes.hostinger.careerloop.internal/api/execute"

    def dry_run(self, job_url: str, application_pack: Dict[str, Any]) -> Dict[str, Any]:
        """
        Returns a preview of what would be executed for one approved job.
        Does not fill fields or submit anything.
        """
        fields = []
        for field, value in application_pack.items():
            value_preview = value
            if isinstance(value, str) and len(value) > 80:
                value_preview = value[:80] + "..."
            fields.append({"field": field, "preview": value_preview})
        return {
            "mode": "dry_run",
            "job_url": job_url,
            "endpoint": self.endpoint,
            "field_count": len(fields),
            "fields": fields,
            "submission_performed": False,
        }

    def execute_approved(
        self,
        job_url: str,
        application_pack: Dict[str, Any],
        approval_token: str,
    ) -> Dict[str, Any]:
        """
        Executes assisted apply for one explicitly approved job.
        Must be called only with a per-job approval token created by the chat layer.
        """
        if not approval_token or not approval_token.strip():
            raise ValueError("approval_token is required for execute_approved().")

        # Placeholder contract for the real Hermes integration.
        # We intentionally avoid claiming submission succeeded until the real HTTP bridge is implemented.
        payload = {
            "url": job_url,
            "pack": application_pack,
            "approval_token": approval_token,
            "mode": "single_job_assisted_execution",
        }
        return {
            "mode": "execute_approved",
            "status": "queued_for_bridge",
            "endpoint": self.endpoint,
            "submission_performed": False,
            "payload_preview": json.dumps(
                {"url": payload["url"], "approval_token": payload["approval_token"][:8] + "***"},
                ensure_ascii=True,
            ),
            "notes": (
                "Execution queued for one approved job only. "
                "No unattended queue processing or bulk submit is performed."
            ),
        }
