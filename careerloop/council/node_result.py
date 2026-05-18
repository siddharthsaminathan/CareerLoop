"""
Strict node error handling for the Resume Council graph.
Each LLM-calling node returns a NodeResult; nodes check prior
errors and skip gracefully. Assembly refuses to proceed when
errors exist.
"""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class NodeResult:
    """Result of a single council node's LLM call.

    success=False means the node failed and errors should propagate.
    The orchestrator checks state["errors"] at the end and writes
    a failure_report.md if any node failed.
    """

    success: bool
    confidence: float = 0.0
    warnings: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    payload: Optional[dict] = None
