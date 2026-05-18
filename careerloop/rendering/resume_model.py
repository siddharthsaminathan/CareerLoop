"""
Normalized Resume Data Model.

This is the canonical structured representation that ALL template renderers
consume. No renderer should parse markdown directly — they receive a
NormalizedResume and format it for their specific layout.

The model is designed to be:
- Renderer-agnostic: works for HTML, PDF, LaTeX, plain text
- Language-agnostic: no hardcoded section titles, categories, or labels
- Complete: covers every data point the Council can produce
"""

from dataclasses import dataclass, field
from typing import List, Optional


# ── Header ────────────────────────────────────────────────────────────────────

@dataclass
class HeaderInfo:
    """Candidate identity and contact information."""
    name: str = ""
    phone: str = ""
    email: str = ""
    location: str = ""
    portfolio_url: str = ""
    portfolio_display: str = ""
    github_url: str = ""
    github_display: str = ""
    linkedin_url: str = ""
    linkedin_display: str = ""


# ── Skills ─────────────────────────────────────────────────────────────────────

@dataclass
class SkillRow:
    """One row in the skills table.

    Example:
        SkillRow(label="AI Systems", items=["LLM APIs", "RAG pipelines", "embeddings"])
    """
    label: str
    items: List[str] = field(default_factory=list)


# ── Experience ─────────────────────────────────────────────────────────────────

@dataclass
class ExperienceEntry:
    """One work experience entry.

    bullets is ALWAYS a list of strings, never a single string blob.
    description is an optional company/context paragraph (not a bullet).
    """
    role: str
    company: str
    location: str = ""
    dates: str = ""
    description: str = ""         # Company context paragraph (optional)
    bullets: List[str] = field(default_factory=list)  # MUST be array, NEVER blob


# ── Education ──────────────────────────────────────────────────────────────────

@dataclass
class EducationEntry:
    """One education entry."""
    degree: str
    institution: str
    dates: str = ""
    details: str = ""


# ── Full Resume ────────────────────────────────────────────────────────────────

@dataclass
class NormalizedResume:
    """The canonical structured resume.

    This is the SINGLE data model that every template renderer receives.
    No renderer ever touches raw markdown.

    Usage:
        from careerloop.rendering.normalizer import normalize
        resume: NormalizedResume = normalize(council_markdown)
    """
    header: HeaderInfo = field(default_factory=HeaderInfo)
    profile: str = ""                        # Raw profile/summary text
    skills: List[SkillRow] = field(default_factory=list)
    experience: List[ExperienceEntry] = field(default_factory=list)
    achievements: List[str] = field(default_factory=list)
    projects: List[str] = field(default_factory=list)
    education: List[EducationEntry] = field(default_factory=list)
    thesis: Optional[str] = None
    languages: List[str] = field(default_factory=list)
