"""
Grounding adapter for Resume Council Company Intelligence.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class ResearchSource:
    title: str
    url: str
    snippet: str
    source_type: str = "search"

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass
class CompanyResearchBundle:
    company: str
    website: str = ""
    fetched_at: str = ""
    sources: list[ResearchSource] = field(default_factory=list)
    manual_input: str = ""
    grounding_status: str = "UNGROUNDED"
    gaps: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "company": self.company,
            "website": self.website,
            "fetched_at": self.fetched_at,
            "sources": [s.to_dict() for s in self.sources],
            "manual_input": self.manual_input,
            "grounding_status": self.grounding_status,
            "gaps": self.gaps,
        }


class CompanyResearchAdapter:
    def gather(self, company: str, website: str = "", jd_text: str = "", manual_input: str = "") -> CompanyResearchBundle:
        fetched_at = datetime.now(timezone.utc).isoformat()
        bundle = CompanyResearchBundle(
            company=company,
            website=website,
            fetched_at=fetched_at,
            manual_input=manual_input or "",
        )

        sources: list[ResearchSource] = []
        if website:
            sources.append(ResearchSource(
                title=f"Company website for {company}",
                url=website,
                snippet="Website URL supplied by job data or user input; content not fetched in offline mode.",
                source_type="website",
            ))

        if jd_text:
            sources.append(ResearchSource(
                title=f"Job description for {company}",
                url="job_description",
                snippet=jd_text[:500],
                source_type="jd",
            ))

        if manual_input:
            sources.append(ResearchSource(
                title=f"Manual research notes for {company}",
                url="manual_input",
                snippet=manual_input[:500],
                source_type="manual",
            ))

        if os.getenv("CAREERLOOP_ENABLE_WEB_RESEARCH", "").lower() in {"1", "true", "yes"}:
            sources.extend(self._search_web(company))

        bundle.sources = sources
        if any(s.source_type == "search" for s in sources):
            bundle.grounding_status = "READY"
        elif sources:
            bundle.grounding_status = "PARTIAL" if website or manual_input else "UNGROUNDED"
        else:
            bundle.grounding_status = "UNGROUNDED"

        if not any(s.source_type == "search" for s in sources):
            bundle.gaps.append("No live web/search results available; company facts must be treated as JD/manual-only.")
        if not website:
            bundle.gaps.append("Company website not available in job data.")

        return bundle

    def _search_web(self, company: str) -> list[ResearchSource]:
        try:
            from duckduckgo_search import DDGS
        except Exception:
            try:
                from ddgs import DDGS
            except Exception:
                return []

        results: list[ResearchSource] = []
        try:
            with DDGS() as ddgs:
                for item in ddgs.text(f"{company} company careers funding news", max_results=5):
                    results.append(ResearchSource(
                        title=item.get("title", ""),
                        url=item.get("href", item.get("url", "")),
                        snippet=item.get("body", item.get("snippet", "")),
                        source_type="search",
                    ))
        except Exception:
            return []
        return [r for r in results if r.url or r.snippet]


def quality_score(bundle: CompanyResearchBundle) -> dict[str, Any]:
    source_count = len(bundle.sources)
    diversity = len({s.source_type for s in bundle.sources})
    has_search = any(s.source_type == "search" for s in bundle.sources)
    score = 0
    score += min(source_count, 5) * 10
    score += diversity * 10
    score += 30 if has_search else 0
    score -= len(bundle.gaps) * 5
    score = max(0, min(100, score))
    status = "READY" if score >= 70 else "PARTIAL" if score >= 35 else "UNGROUNDED"
    return {
        "score": score,
        "status": status,
        "source_count": source_count,
        "source_diversity": diversity,
        "gaps": bundle.gaps,
    }
