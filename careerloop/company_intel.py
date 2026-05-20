"""
CareerLoop Company Intelligence Engine.

Replaces the weak S3 LLM-recall-only implementation with a real, structured,
timeout-safe, cached intelligence system that downstream stages can consume.

Architecture:
  Layer 1 — JD-only extraction (always runs, no network, <1s)
  Layer 2 — Company website / careers page (timeout 10s)
  Layer 3 — Optional web/search enrichment (timeout 10s, opt-in)
  Layer 4 — JSON file cache (careerloop/data/company_memory/{slug}.json)

Hard timeout budget: 15s total for all network calls.
Cache hit: <3s. JD-only path: <5s.

Confidence caps:
  UNGROUNDED → max 0.2
  JD_ONLY    → max 0.45
  PARTIAL    → max 0.7
  READY      → max 0.9
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# ── Timeout constants ──────────────────────────────────────────────────────────
_WEB_SEARCH_TIMEOUT_SECONDS = 10
_TOTAL_NETWORK_BUDGET_SECONDS = 15

# ── Data model ─────────────────────────────────────────────────────────────────


@dataclass
class CompanyIntelligenceResult:
    """Full structured company intelligence for one company+role evaluation."""

    # Identity
    company_name: str = ""
    role_title: str = ""
    source_urls: list[str] = field(default_factory=list)
    grounding_status: str = "UNGROUNDED"  # READY | PARTIAL | JD_ONLY | UNGROUNDED
    confidence: float = 0.0
    generated_at: str = ""
    cache_key: str = ""
    ttl_days: int = 30

    # Company fundamentals
    company_summary: str = ""
    business_model: str = ""
    revenue_model: str = ""
    customer_segment: str = ""
    product_category: str = ""
    india_presence: str = "UNKNOWN"
    company_maturity: str = "UNKNOWN"
    growth_signals: list[str] = field(default_factory=list)
    stability_signals: list[str] = field(default_factory=list)
    hiring_urgency: str = "UNKNOWN"

    # Role context
    role_reason: str = ""
    likely_success_criteria: list[str] = field(default_factory=list)
    likely_failure_modes: list[str] = field(default_factory=list)

    # Culture & org
    culture_signals: list[str] = field(default_factory=list)
    communication_style: str = ""
    founder_or_leadership_signals: str = ""
    org_maturity: str = "UNKNOWN"
    technical_maturity: str = "UNKNOWN"
    ai_maturity: str = "UNKNOWN"
    likely_stack: str = ""

    # Interview & comp
    interview_implications: str = ""
    compensation_signals: str = ""
    red_flags: list[str] = field(default_factory=list)

    # Positioning
    positioning_implications: str = ""
    language_to_use: list[str] = field(default_factory=list)
    language_to_avoid: list[str] = field(default_factory=list)
    candidate_angles: list[str] = field(default_factory=list)
    transferability_angles: list[str] = field(default_factory=list)
    risks_to_soften: list[str] = field(default_factory=list)
    claims_to_avoid: list[str] = field(default_factory=list)
    resume_strategy_hint: str = ""
    outreach_strategy_hint: str = ""
    interview_strategy_hint: str = ""

    # Downstream compact contexts
    s6_positioning_context: dict[str, Any] = field(default_factory=dict)
    s7_rewrite_context: dict[str, Any] = field(default_factory=dict)

    # Honesty
    unknowns: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Full dict for JSON serialization / cache storage."""
        return {
            "company_name": self.company_name,
            "role_title": self.role_title,
            "source_urls": self.source_urls,
            "grounding_status": self.grounding_status,
            "confidence": self.confidence,
            "generated_at": self.generated_at,
            "cache_key": self.cache_key,
            "ttl_days": self.ttl_days,
            "company_summary": self.company_summary,
            "business_model": self.business_model,
            "revenue_model": self.revenue_model,
            "customer_segment": self.customer_segment,
            "product_category": self.product_category,
            "india_presence": self.india_presence,
            "company_maturity": self.company_maturity,
            "growth_signals": self.growth_signals,
            "stability_signals": self.stability_signals,
            "hiring_urgency": self.hiring_urgency,
            "role_reason": self.role_reason,
            "likely_success_criteria": self.likely_success_criteria,
            "likely_failure_modes": self.likely_failure_modes,
            "culture_signals": self.culture_signals,
            "communication_style": self.communication_style,
            "founder_or_leadership_signals": self.founder_or_leadership_signals,
            "org_maturity": self.org_maturity,
            "technical_maturity": self.technical_maturity,
            "ai_maturity": self.ai_maturity,
            "likely_stack": self.likely_stack,
            "interview_implications": self.interview_implications,
            "compensation_signals": self.compensation_signals,
            "red_flags": self.red_flags,
            "positioning_implications": self.positioning_implications,
            "language_to_use": self.language_to_use,
            "language_to_avoid": self.language_to_avoid,
            "candidate_angles": self.candidate_angles,
            "transferability_angles": self.transferability_angles,
            "risks_to_soften": self.risks_to_soften,
            "claims_to_avoid": self.claims_to_avoid,
            "resume_strategy_hint": self.resume_strategy_hint,
            "outreach_strategy_hint": self.outreach_strategy_hint,
            "interview_strategy_hint": self.interview_strategy_hint,
            "s6_positioning_context": self.s6_positioning_context,
            "s7_rewrite_context": self.s7_rewrite_context,
            "unknowns": self.unknowns,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CompanyIntelligenceResult":
        """Reconstruct from cached JSON dict. Only copies known fields."""
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        kwargs = {k: v for k, v in d.items() if k in known}
        return cls(**kwargs)


# ── Helpers ────────────────────────────────────────────────────────────────────


def _normalize_company(name: str) -> str:
    """Slugify company name for cache keys and file paths."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower().strip()).strip("-")
    return slug or "unknown"


def _cache_key(company: str, role_family: str = "") -> str:
    """Stable cache key from company + role family."""
    raw = f"{_normalize_company(company)}:{_normalize_company(role_family or 'any')}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _confidence_cap(grounding_status: str) -> float:
    return {
        "UNGROUNDED": 0.2,
        "JD_ONLY": 0.45,
        "PARTIAL": 0.7,
        "READY": 0.9,
    }.get(grounding_status, 0.2)


def _ttl_for_result(result: CompanyIntelligenceResult) -> int:
    """Shorter TTL when hiring urgency or red-flag signals are present."""
    if result.hiring_urgency in ("HIGH", "MEDIUM") or result.red_flags:
        return 7
    return 30


# ── Layer 1: JD-only extraction (deterministic, always runs) ───────────────────


def _extract_jd_signals(jd_text: str) -> dict[str, Any]:
    """Extract structured signals from JD text without any LLM call.

    Returns a dict of deterministic clues that feed into later synthesis.
    """
    jd_lower = jd_text.lower()
    signals: dict[str, Any] = {
        "business_terms": [],
        "product_terms": [],
        "domain_terms": [],
        "tone_markers": [],
        "explicit_requirements": [],
        "implied_context": [],
        "role_reason_clues": [],
    }

    # ── Business terms ──────────────────────────────────────────────────────
    _biz_terms = {
        "b2b": "b2b", "b2c": "b2c", "d2c": "d2c", "saas": "saas",
        "marketplace": "marketplace", "e-commerce": "ecommerce",
        "ecommerce": "ecommerce", "subscription": "subscription",
        "enterprise": "enterprise_sales", "smb": "smb",
        "omnichannel": "omnichannel", "retail": "retail",
        "supply chain": "supply_chain", "logistics": "logistics",
        "fintech": "fintech", "healthtech": "healthtech",
        "edtech": "edtech", "agritech": "agritech",
        "manufacturing": "manufacturing", "fashion": "fashion",
        "consumer": "consumer", "banking": "banking",
        "insurance": "insurance", "payments": "payments",
        "pharma": "pharmaceutical", "clinical": "healthcare",
        "diagnostics": "diagnostics", "biotech": "biotech",
    }
    for term, label in _biz_terms.items():
        if term in jd_lower:
            signals["business_terms"].append(label)

    # ── Product / domain terms ──────────────────────────────────────────────
    _prod_terms = {
        "ai": "ai_ml", "machine learning": "ai_ml", "llm": "ai_ml",
        "rag": "ai_ml", "embedding": "ai_ml", "nlp": "ai_ml",
        "data pipeline": "data_engineering", "etl": "data_engineering",
        "dashboard": "analytics", "analytics": "analytics",
        "api": "api_platform", "microservice": "microservices",
        "mobile": "mobile", "web": "web", "cloud": "cloud",
        "devops": "devops", "ci/cd": "devops", "kubernetes": "infra",
        "warehouse": "data_warehouse", "lake": "data_lake",
        "erp": "erp", "crm": "crm",
        "otb": "fashion_retail", "assortment": "fashion_retail",
        "merchandising": "fashion_retail", "buying": "fashion_retail",
        "womenswear": "fashion_retail", "jersey": "fashion_retail",
        "plm": "product_lifecycle", "sap": "sap",
        "pos": "pos", "inventory": "inventory",
    }
    for term, label in _prod_terms.items():
        if term in jd_lower:
            signals["product_terms"].append(label)

    # ── Domain categories ───────────────────────────────────────────────────
    _domains = {
        "quality": "quality_management", "control plan": "manufacturing_quality",
        "fmea": "manufacturing_quality", "dfmea": "manufacturing_quality",
        "pfmea": "manufacturing_quality", "5w2h": "manufacturing_quality",
        "8d": "manufacturing_quality", "production": "manufacturing",
        "clienteling": "retail_tech", "personalization": "personalization",
        "recommendation": "recommendation", "forecasting": "forecasting",
        "credit risk": "credit_risk", "loan": "lending",
        "compliance": "compliance", "regulatory": "compliance",
        "patient": "healthcare", "clinical trial": "clinical",
        "rna": "bioinformatics", "genomic": "bioinformatics",
        "catalog": "catalog_mgmt", "content management": "content_mgmt",
        "vendor": "vendor_mgmt", "supplier": "supply_chain",
        "procurement": "procurement", "sourcing": "sourcing",
        "purchase order": "procurement", "po": "procurement",
    }
    for term, label in _domains.items():
        if term in jd_lower:
            signals["domain_terms"].append(label)

    # ── Tone markers ────────────────────────────────────────────────────────
    if any(w in jd_lower for w in ["fast-paced", "startup", "move fast", "bias for action"]):
        signals["tone_markers"].append("startup_velocity")
    if any(w in jd_lower for w in ["0 to 1", "zero to one", "build from scratch", "greenfield"]):
        signals["tone_markers"].append("builder_mentality")
    if any(w in jd_lower for w in ["ownership", "end-to-end", "owns", "own the"]):
        signals["tone_markers"].append("ownership_culture")
    if any(w in jd_lower for w in ["customer", "user-focused", "customer-obsessed"]):
        signals["tone_markers"].append("customer_centric")
    if any(w in jd_lower for w in ["data-driven", "metrics", "analytical", "kpi"]):
        signals["tone_markers"].append("data_driven")
    if any(w in jd_lower for w in ["collaborate", "cross-functional", "stakeholder", "team"]):
        signals["tone_markers"].append("collaborative")
    if any(w in jd_lower for w in ["entrepreneurial", "founder", "scrappy", "hustle"]):
        signals["tone_markers"].append("entrepreneurial")

    # ── Explicit requirements ───────────────────────────────────────────────
    req_patterns = [
        (r"(\d+)\+?\s*(?:years|yrs)(?:\s*(?:of|in)\s*)([^.,;]+)", "years_experience"),
        (r"(?:proficiency|proficient|expert|strong)\s*(?:in|with)\s*([^.,;]+)", "skill_requirement"),
        (r"(?:must have|required|essential|mandatory)[:\s]+([^.,;]+)", "must_have"),
    ]
    for pattern, label in req_patterns:
        for m in re.finditer(pattern, jd_lower):
            signals["explicit_requirements"].append(f"{label}:{m.group(0)[:120]}")

    # ── Implied context ─────────────────────────────────────────────────────
    if any(w in jd_lower for w in ["ceo", "founder", "leadership team", "executive"]):
        signals["implied_context"].append("ceo_or_executive_facing")
    if any(w in jd_lower for w in ["remote", "hybrid", "wfh", "work from home"]):
        signals["implied_context"].append("remote_friendly")
    if any(w in jd_lower for w in ["bangalore", "bengaluru", "mumbai", "delhi", "chennai",
                                     "hyderabad", "pune", "gurgaon", "noida"]):
        signals["implied_context"].append("india_office_mentioned")
    if any(w in jd_lower for w in ["nift", "bits", "iit", "iim", "tier-1", "premier"]):
        signals["implied_context"].append("premier_institute_bias")
    if any(w in jd_lower for w in ["95%", "otb", "on-time", "kpi", "target"]):
        signals["implied_context"].append("metrics_driven")

    # ── Role reason clues ───────────────────────────────────────────────────
    role_clue_patterns = [
        (r"(?:we are|we're)\s*(?:looking for|hiring|building|expanding|scaling)\s*(?:a|an|our)?\s*([^.,;]{10,100})", "hiring_reason"),
        (r"(?:growing|expanding|scaling)\s*(?:our|the)\s*([^.,;]{10,100})", "growth_context"),
        (r"(?:you will|you'll)\s*(?:be|own|lead|build|drive|manage)\s*([^.,;]{10,100})", "role_scope"),
    ]
    for pattern, label in role_clue_patterns:
        for m in re.finditer(pattern, jd_lower):
            signals["role_reason_clues"].append(f"{label}:{m.group(1).strip()[:150]}")

    return signals


# ── Layer 2 + 3: Web enrichment (timeout-safe) ────────────────────────────────

_PAGE_FETCH_TIMEOUT_SECONDS = 5
_MAX_PAGES_TO_FETCH = 3


def _fetch_page_content(url: str, timeout: int = _PAGE_FETCH_TIMEOUT_SECONDS) -> str:
    """Fetch and extract readable text from a URL.

    Tries Playwright first (JS-rendered pages), falls back to requests + BeautifulSoup.
    Hard timeout ensures the pipeline never blocks.
    Returns empty string on any failure.
    """
    if not url or not url.startswith("http"):
        return ""

    def _try_playwright() -> str:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return ""
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
                text = page.inner_text("body")
                browser.close()
                return text[:3000] if text else ""
        except Exception:
            return ""

    def _try_requests() -> str:
        try:
            import requests
            from bs4 import BeautifulSoup
        except ImportError:
            return ""
        try:
            resp = requests.get(url, timeout=timeout, headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                              "CareerLoop/1.0 Company Intelligence"
            })
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
                tag.decompose()
            text = soup.get_text(separator="\n")
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
            return "\n".join(lines)[:3000]
        except Exception:
            return ""

    # Try Playwright first, fall back to requests
    with ThreadPoolExecutor(max_workers=1) as ex:
        future = ex.submit(_try_playwright)
        try:
            result = future.result(timeout=timeout + 2)
            if result:
                return result
        except FuturesTimeoutError:
            pass

    # Fall back to requests if Playwright failed
    return _try_requests()


def _gather_web_sources(company: str, job_url: str = "") -> list[dict[str, str]]:
    """Gather web sources with hard timeout. Never blocks the pipeline.

    DuckDuckGo search → fetch top page contents → return enriched sources.
    Each source gets a 'page_content' field with extracted text from the URL.
    Always returns quickly — exceptions and timeouts are caught silently.
    """
    sources: list[dict[str, str]] = []

    if job_url:
        sources.append({
            "title": f"Job posting for {company}",
            "url": job_url,
            "snippet": "Job posting URL supplied by pipeline.",
            "source_type": "jd_url",
        })

    # Web search is always attempted — never opt-in.
    # Timeout safety ensures the pipeline never blocks.
    def _search() -> list[dict[str, str]]:
        results: list[dict[str, str]] = []
        try:
            from duckduckgo_search import DDGS
        except Exception:
            try:
                from ddgs import DDGS
            except Exception:
                return results
        try:
            with DDGS() as ddgs:
                for item in ddgs.text(f"{company} company careers funding news", max_results=5):
                    results.append({
                        "title": item.get("title", ""),
                        "url": item.get("href", item.get("url", "")),
                        "snippet": item.get("body", item.get("snippet", "")),
                        "source_type": "web_search",
                    })
        except Exception:
            pass
        return [r for r in results if r.get("url") or r.get("snippet")]

    try:
        with ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(_search)
            try:
                web_results = future.result(timeout=_WEB_SEARCH_TIMEOUT_SECONDS)
                sources.extend(web_results)
            except FuturesTimeoutError:
                print(f"  !! S3 web search timed out after {_WEB_SEARCH_TIMEOUT_SECONDS}s")
    except Exception as e:
        print(f"  !! S3 web search error: {e}")

    # ── Fetch actual page content for top search results ─────────────────
    search_urls = [s for s in sources if s.get("source_type") == "web_search"]
    if search_urls:
        urls_to_fetch = [s["url"] for s in search_urls[:_MAX_PAGES_TO_FETCH] if s.get("url", "").startswith("http")]
        if urls_to_fetch:
            print(f"  → S3 fetching content from {len(urls_to_fetch)} URLs...")
            fetched_count = 0
            for source in search_urls[:_MAX_PAGES_TO_FETCH]:
                url = source.get("url", "")
                if not url.startswith("http"):
                    continue
                content = _fetch_page_content(url)
                if content:
                    source["page_content"] = content
                    fetched_count += 1
                    print(f"     ✓ {source.get('title', url)[:60]}: {len(content)} chars")
                else:
                    print(f"     ✗ {source.get('title', url)[:60]}: no content extracted")
            print(f"  → S3 fetched {fetched_count}/{len(urls_to_fetch)} pages")

    return sources


# ── Cache layer ────────────────────────────────────────────────────────────────


def _cache_dir(root: Path) -> Path:
    d = root / "careerloop" / "data" / "company_memory"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cache_path(root: Path, company: str) -> Path:
    return _cache_dir(root) / f"{_normalize_company(company)}.json"


def load_company_memory(root: Path, company: str) -> Optional[CompanyIntelligenceResult]:
    """Load cached company intelligence if fresh enough."""
    path = _cache_path(root, company)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        result = CompanyIntelligenceResult.from_dict(data)
        generated = result.generated_at
        if generated:
            try:
                gen_time = datetime.fromisoformat(generated)
                age_days = (datetime.now(timezone.utc) - gen_time).days
                if age_days > result.ttl_days:
                    return None  # stale
            except ValueError:
                pass
        return result
    except Exception:
        return None


def save_company_memory(root: Path, result: CompanyIntelligenceResult) -> Path:
    """Persist company intelligence to JSON cache."""
    path = _cache_path(root, result.company_name)
    result.cache_key = _cache_key(result.company_name, result.role_title or "")
    result.ttl_days = _ttl_for_result(result)
    if not result.generated_at:
        result.generated_at = datetime.now(timezone.utc).isoformat()
    data = result.to_dict()
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


# ── LLM synthesis ─────────────────────────────────────────────────────────────


_S3_SYNTHESIS_SYSTEM = """You are CareerLoop's Company Intelligence Engine.

Your job is to convert grounded evidence about a company and role into strategic career intelligence.

You must strictly separate your synthesis into Grounded Facts (direct matches from the input text), Plausible Inferences (logical reasoning derived solely from the provided signals), and Explicit Unknowns (missing information).

STRICT RULES TO PREVENT AI HALLUCINATIONS:
1. Grounded Facts MUST be derived directly from the provided text evidence. Do NOT use your general pre-training memory recall for facts about the company (such as headcount, actual revenues, funding rounds, specific leadership names, office locations) unless they are explicitly present in the provided input.
2. If the input evidence does not contain specific information for a field, you MUST set the value to "UNKNOWN" or empty lists/objects, and add it to the "unknowns" array. DO NOT invent or guess. "UNKNOWN" is a sign of high quality.
3. Plausible Inferences must be derived step-by-step from explicit text patterns. For example, "The JD states Range Review Presentation is a key duty -> Infer that presentation skills to management are highly valued."
4. Every fact, implication, or cultural signal must cite its source (e.g., "[JD]" or "[WEB]").

For downstream S7 rewrite context, provide a compact, actionable dictionary under "s7_rewrite_context" with:
- company_archetype: e.g., "design-led D2C brand", "enterprise SaaS", "YC startup"
- company_tone: e.g., "warm and design-aware", "direct and technical"
- product_context: what they build/sell
- business_problem: what problem this role is hired to solve
- role_success_criteria: what "great" looks like
- language_to_use: 3-5 specific words/phrases from evidence that resonate
- language_to_avoid: 3-5 generic/fluffy words/phrases to avoid
- proof_points_to_prefer: candidate evidence/projects they value most
- risks_to_soften: candidate gaps to reposition
- avoid_overclaiming_about: things the candidate must not exaggerate
- max_5_bullet_guidance: 1-sentence on how to tailor experience bullets

Return ONLY valid JSON matching the CompanyIntelligenceResult schema exactly."""


def _build_synthesis_prompt(
    company: str,
    role_title: str,
    jd_text: str,
    jd_signals: dict[str, Any],
    web_sources: list[dict[str, str]],
    candidate_context: Optional[dict[str, Any]] = None,
) -> str:
    """Build the structured synthesis prompt from all gathered evidence."""
    parts: list[str] = []

    parts.append(f"COMPANY: {company}")
    parts.append(f"ROLE: {role_title or 'Not specified'}")
    parts.append("")

    # ── JD excerpt (capped) ─────────────────────────────────────────────────
    jd_snippet = jd_text[:3000] if len(jd_text) > 3000 else jd_text
    parts.append(f"JD TEXT:\n{jd_snippet}")
    parts.append("")

    # ── Deterministic JD signals ────────────────────────────────────────────
    if jd_signals:
        parts.append("EXTRACTED JD SIGNALS (deterministic):")
        parts.append(json.dumps({k: v for k, v in jd_signals.items() if v}, indent=2))
        parts.append("")

    # ── Web sources (snippets + fetched page content) ────────────────────────
    web_search_sources = [s for s in web_sources if s.get("source_type") == "web_search"]
    if web_search_sources:
        parts.append("WEB SEARCH RESULTS (snippets):")
        for i, s in enumerate(web_search_sources[:5]):
            parts.append(f"{i+1}. [{s['title']}]({s['url']})")
            parts.append(f"   Snippet: {s['snippet'][:300]}")
            page_content = s.get("page_content", "")
            if page_content:
                parts.append(f"   Page content: {page_content[:1500]}")
        parts.append("")
    else:
        parts.append("WEB SEARCH RESULTS: None available. Use JD-only evidence.")
        parts.append("")

    # ── Candidate context (if provided) ─────────────────────────────────────
    if candidate_context:
        ctx_summary = {}
        for k in ("target_roles", "deal_breakers", "narrative", "superpower"):
            if k in candidate_context:
                ctx_summary[k] = candidate_context[k]
        if ctx_summary:
            parts.append("CANDIDATE CONTEXT:")
            parts.append(json.dumps(ctx_summary, indent=2))
            parts.append("")

    parts.append("TASK: Synthesize structured company intelligence from ONLY the evidence above.")
    parts.append("Return a JSON object matching the CompanyIntelligenceResult schema.")
    parts.append("If a field has no evidence, use empty string, empty list, or UNKNOWN.")
    parts.append("Set unknowns[] for every piece of information you could not determine from sources.")

    return "\n".join(parts)


# ── Main API ──────────────────────────────────────────────────────────────────


def build_company_intelligence(
    company: str,
    role_title: str,
    jd_text: str,
    job_url: str | None = None,
    candidate_context: dict[str, Any] | None = None,
    force_refresh: bool = False,
    root: Path | None = None,
    llm_client: Any = None,
) -> CompanyIntelligenceResult:
    """Build structured company intelligence with layered research.

    Args:
        company: Company name
        role_title: Job title for role-specific positioning
        jd_text: Full job description text
        job_url: Optional job posting URL
        candidate_context: Optional user profile for personalized implications
        force_refresh: Skip cache
        root: Repo root for cache paths
        llm_client: CouncilLLMClient instance for synthesis. If None, uses JD-only mode.

    Returns:
        Populated CompanyIntelligenceResult
    """
    repo_root = Path(root) if root else _find_repo_root()
    started_at = time.monotonic()

    # ── Cache check ─────────────────────────────────────────────────────────
    if not force_refresh:
        cached = load_company_memory(repo_root, company)
        if cached:
            elapsed = time.monotonic() - started_at
            print(f"  → S3 cache HIT for {company} ({elapsed:.1f}s)")
            return cached

    # ── Layer 1: JD extraction (always, deterministic) ──────────────────────
    jd_signals = _extract_jd_signals(jd_text) if jd_text else {}

    # ── Layer 2+3: Web sources (timeout-safe) ───────────────────────────────
    web_sources: list[dict[str, str]] = []
    try:
        with ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(_gather_web_sources, company, job_url or "")
            try:
                remaining = _TOTAL_NETWORK_BUDGET_SECONDS - (time.monotonic() - started_at)
                if remaining > 0:
                    web_sources = future.result(timeout=remaining)
                else:
                    future.cancel()
            except FuturesTimeoutError:
                print(f"  !! S3 web source gathering timed out")
    except Exception as e:
        print(f"  !! S3 web source error: {e}")

    # ── Determine grounding status ──────────────────────────────────────────
    has_web = any(s.get("source_type") == "web_search" for s in web_sources)
    has_jd = bool(jd_text and jd_text.strip() and len(jd_text.strip()) > 20)
    has_sources = bool(web_sources)

    if has_web and has_sources:
        grounding_status = "READY"
    elif has_sources or has_jd:
        grounding_status = "PARTIAL"
    elif has_jd:
        grounding_status = "JD_ONLY"
    else:
        grounding_status = "UNGROUNDED"

    max_conf = _confidence_cap(grounding_status)

    # ── If no LLM client, return JD-only result ─────────────────────────────
    if llm_client is None:
        result = _build_jd_only_result(
            company=company,
            role_title=role_title,
            jd_text=jd_text,
            jd_signals=jd_signals,
            web_sources=web_sources,
            job_url=job_url,
            grounding_status=grounding_status,
            max_conf=max_conf,
        )
        save_company_memory(repo_root, result)
        elapsed = time.monotonic() - started_at
        print(f"  → S3 JD-only for {company} | {grounding_status} | conf={result.confidence} | {elapsed:.1f}s")
        return result

    # ── LLM synthesis ───────────────────────────────────────────────────────
    prompt = _build_synthesis_prompt(
        company=company,
        role_title=role_title,
        jd_text=jd_text,
        jd_signals=jd_signals,
        web_sources=web_sources,
        candidate_context=candidate_context,
    )

    # ── LLM synthesis with timeout ──────────────────────────────────────────
    # DeepSeek can be slow — hard-cap the LLM call at 60s, fall back to JD-only.
    _LLM_TIMEOUT_SECONDS = 60

    def _call_llm() -> dict[str, Any]:
        raw = llm_client.complete_json(_S3_SYNTHESIS_SYSTEM, prompt, max_tokens=4000)
        return raw if isinstance(raw, dict) else {}

    payload: dict[str, Any] = {}
    llm_timed_out = False
    try:
        with ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(_call_llm)
            try:
                payload = future.result(timeout=_LLM_TIMEOUT_SECONDS)
            except FuturesTimeoutError:
                llm_timed_out = True
                print(f"  !! S3 LLM synthesis timed out after {_LLM_TIMEOUT_SECONDS}s — falling back to JD-only")
    except Exception as e:
        print(f"  !! S3 LLM synthesis failed: {e} — falling back to JD-only")

    if llm_timed_out or not payload:
        result = _build_jd_only_result(
            company=company, role_title=role_title, jd_text=jd_text,
            jd_signals=jd_signals, web_sources=web_sources, job_url=job_url,
            grounding_status=grounding_status, max_conf=max_conf,
        )
        save_company_memory(repo_root, result)
        return result

    # ── Fill empty LLM fields from JD signals ───────────────────────────────
    if not payload.get("company_summary"):
        payload["company_summary"] = _jd_summary(company, jd_signals)
    if not payload.get("business_model"):
        payload["business_model"] = _map_biz_terms_to_model(jd_signals.get("business_terms", []))

    # ── Assemble result from LLM payload + deterministic signals ────────────
    result = CompanyIntelligenceResult(
        company_name=company,
        role_title=role_title,
        source_urls=[s.get("url", "") for s in web_sources if s.get("url")],
        grounding_status=grounding_status,
        generated_at=datetime.now(timezone.utc).isoformat(),
        cache_key=_cache_key(company, role_title or ""),

        company_summary=payload.get("company_summary", ""),
        business_model=payload.get("business_model", ""),
        revenue_model=payload.get("revenue_model", ""),
        customer_segment=payload.get("customer_segment", ""),
        product_category=payload.get("product_category", ""),
        india_presence=payload.get("india_presence", "UNKNOWN"),
        company_maturity=payload.get("company_maturity", "UNKNOWN"),
        growth_signals=payload.get("growth_signals", []),
        stability_signals=payload.get("stability_signals", []),
        hiring_urgency=payload.get("hiring_urgency", "UNKNOWN"),

        role_reason=payload.get("role_reason", ""),
        likely_success_criteria=payload.get("likely_success_criteria", []),
        likely_failure_modes=payload.get("likely_failure_modes", []),

        culture_signals=payload.get("culture_signals", []),
        communication_style=payload.get("communication_style", ""),
        founder_or_leadership_signals=payload.get("founder_or_leadership_signals", ""),
        org_maturity=payload.get("org_maturity", "UNKNOWN"),
        technical_maturity=payload.get("technical_maturity", "UNKNOWN"),
        ai_maturity=payload.get("ai_maturity", "UNKNOWN"),
        likely_stack=payload.get("likely_stack", ""),

        interview_implications=payload.get("interview_implications", ""),
        compensation_signals=payload.get("compensation_signals", ""),
        red_flags=payload.get("red_flags", []),

        positioning_implications=payload.get("positioning_implications", ""),
        language_to_use=payload.get("language_to_use", []),
        language_to_avoid=payload.get("language_to_avoid", []),
        candidate_angles=payload.get("candidate_angles", []),
        transferability_angles=payload.get("transferability_angles", []),
        risks_to_soften=payload.get("risks_to_soften", []),
        claims_to_avoid=payload.get("claims_to_avoid", []),
        resume_strategy_hint=payload.get("resume_strategy_hint", ""),
        outreach_strategy_hint=payload.get("outreach_strategy_hint", ""),
        interview_strategy_hint=payload.get("interview_strategy_hint", ""),

        unknowns=payload.get("unknowns", []),
    )

    # ── Build downstream contexts ───────────────────────────────────────────
    result.s6_positioning_context = _build_s6_context(result)
    result.s7_rewrite_context = _build_s7_context(result)

    # ── Confidence calibration ──────────────────────────────────────────────
    llm_conf = payload.get("confidence", 0.5)
    result.confidence = min(llm_conf, max_conf)
    result.ttl_days = _ttl_for_result(result)

    # ── Cache ───────────────────────────────────────────────────────────────
    save_company_memory(repo_root, result)

    elapsed = time.monotonic() - started_at
    print(f"  → S3 synthesized for {company} | {grounding_status} | conf={result.confidence} | {elapsed:.1f}s")
    return result


def get_or_build_company_intelligence(
    company: str,
    role_title: str = "",
    jd_text: str = "",
    job_url: str | None = None,
    candidate_context: dict[str, Any] | None = None,
    force_refresh: bool = False,
    root: Path | None = None,
    llm_client: Any = None,
) -> CompanyIntelligenceResult:
    """Cache-aware wrapper. Returns cached result if fresh, else builds new."""
    return build_company_intelligence(
        company=company,
        role_title=role_title,
        jd_text=jd_text,
        job_url=job_url,
        candidate_context=candidate_context,
        force_refresh=force_refresh,
        root=root,
        llm_client=llm_client,
    )


# ── Downstream context builders ───────────────────────────────────────────────


def _build_s6_context(result: CompanyIntelligenceResult) -> dict[str, Any]:
    """Build compact positioning context for S6 positioning_node."""
    return {
        "company_archetype": result.communication_style or result.company_summary[:100],
        "business_model": result.business_model,
        "company_maturity": result.company_maturity,
        "india_presence": result.india_presence,
        "culture_signals": result.culture_signals[:5],
        "hiring_urgency": result.hiring_urgency,
        "positioning_implications": result.positioning_implications,
        "language_to_use": result.language_to_use,
        "language_to_avoid": result.language_to_avoid,
        "risks_to_soften": result.risks_to_soften,
        "claims_to_avoid": result.claims_to_avoid,
        "candidate_angles": result.candidate_angles,
        "red_flags": result.red_flags,
        "grounding_status": result.grounding_status,
        "confidence": result.confidence,
    }


def _build_s7_context(result: CompanyIntelligenceResult) -> dict[str, Any]:
    """Build compact rewrite context for S7 section_rewrites_node.

    This is the CRITICAL downstream artifact. S7 previously received only
    screening_keywords from role_decode. Now it receives structured company
    context so section rewrites actually adapt to the company.
    """
    return {
        "company_archetype": (
            result.communication_style
            or result.company_summary[:80]
            or "Unknown"
        ),
        "company_tone": _infer_tone(result),
        "product_context": result.product_category or result.business_model or "",
        "business_problem": result.role_reason or "",
        "role_success_criteria": result.likely_success_criteria[:3],
        "language_to_use": result.language_to_use or [],
        "language_to_avoid": result.language_to_avoid or [],
        "proof_points_to_prefer": _infer_preferred_proof_types(result),
        "risks_to_soften": result.risks_to_soften or [],
        "avoid_overclaiming_about": result.claims_to_avoid or [],
        "max_5_bullet_guidance": result.resume_strategy_hint or _fallback_bullet_guidance(result),
    }


def _infer_tone(result: CompanyIntelligenceResult) -> str:
    """Infer company communication tone from available signals."""
    if result.communication_style:
        return result.communication_style
    tone_markers = result.culture_signals or []
    if any(w in str(tone_markers).lower() for w in ["design", "brand", "creative", "editorial"]):
        return "warm and design-aware"
    if any(w in str(tone_markers).lower() for w in ["startup", "fast", "ship", "velocity"]):
        return "direct and fast-paced"
    if any(w in str(tone_markers).lower() for w in ["enterprise", "formal", "compliance"]):
        return "formal and process-oriented"
    if any(w in str(tone_markers).lower() for w in ["data", "analytics", "metrics"]):
        return "analytical and evidence-driven"
    return "professional and direct"


def _infer_preferred_proof_types(result: CompanyIntelligenceResult) -> list[str]:
    """Infer what types of candidate evidence this company values."""
    hints: list[str] = []
    cs = (result.communication_style or "").lower()
    cm = (result.company_maturity or "").lower()
    bm = (result.business_model or "").lower()

    if "startup" in cm or "early" in cm:
        hints.append("shipping under ambiguity")
        hints.append("0-to-1 product ownership")
    if "enterprise" in cm or "growth" in cm:
        hints.append("process and reliability")
        hints.append("stakeholder management at scale")
    if any(t in bm for t in ("d2c", "consumer", "retail", "fashion")):
        hints.append("customer-facing product outcomes")
        hints.append("brand-aware execution")
    if any(t in bm for t in ("saas", "b2b", "enterprise")):
        hints.append("measurable business impact")
        hints.append("technical depth with commercial awareness")

    if not hints:
        hints = [
            "measurable outcomes with numbers",
            "specific, defensible achievements",
            "evidence of ownership and initiative",
        ]
    return hints


def _fallback_bullet_guidance(result: CompanyIntelligenceResult) -> str:
    """Fallback bullet rewriting guidance when LLM didn't provide specific hints."""
    return (
        "Lead every bullet with a strong action verb and a measurable outcome. "
        "Replace weak verbs (Analyzed, Supported, Assisted) with ownership verbs "
        "(Built, Owned, Shipped, Drove). Keep all metrics exact."
    )


def summarize_for_downstream(result: CompanyIntelligenceResult) -> dict[str, Any]:
    """Produce a single downstream dict with s6 + s7 contexts.

    This is the primary interface for graph.py integration.
    """
    return {
        "s6_positioning_context": result.s6_positioning_context,
        "s7_rewrite_context": result.s7_rewrite_context,
    }


# ── JD-only fallback builder ──────────────────────────────────────────────────


def _build_jd_only_result(
    company: str,
    role_title: str,
    jd_text: str,
    jd_signals: dict[str, Any],
    web_sources: list[dict[str, str]],
    job_url: str | None,
    grounding_status: str,
    max_conf: float,
) -> CompanyIntelligenceResult:
    """Build a CompanyIntelligenceResult from JD-only deterministic extraction.

    No LLM call. Fast, safe, always works.
    """
    biz_terms = jd_signals.get("business_terms", [])
    prod_terms = jd_signals.get("product_terms", [])
    domain_terms = jd_signals.get("domain_terms", [])
    tone_markers = jd_signals.get("tone_markers", [])
    role_clues = jd_signals.get("role_reason_clues", [])

    # ── Company summary from JD signals ────────────────────────────────────
    summary_parts = [company]
    if biz_terms:
        summary_parts.append(f"operates in {', '.join(biz_terms[:3])}")
    if domain_terms:
        summary_parts.append(f"with focus on {', '.join(domain_terms[:3])}")
    company_summary = ". ".join(summary_parts) + "."

    # ── Business model from terms ──────────────────────────────────────────
    business_model = _map_biz_terms_to_model(biz_terms)

    # ── Customer segment ───────────────────────────────────────────────────
    if any(t in biz_terms for t in ("b2b", "enterprise_sales")):
        customer_segment = "B2B / Enterprise"
    elif any(t in biz_terms for t in ("b2c", "d2c", "consumer")):
        customer_segment = "B2C / Consumer"
    elif any(t in biz_terms for t in ("marketplace",)):
        customer_segment = "Marketplace"
    else:
        customer_segment = ""

    # ── Product category ───────────────────────────────────────────────────
    product_category = ", ".join(prod_terms[:5]) if prod_terms else ""

    # ── Language heuristics ────────────────────────────────────────────────
    language_to_use: list[str] = []
    language_to_avoid: list[str] = []
    if "startup_velocity" in tone_markers:
        language_to_use.extend(["shipped", "built", "owned"])
        language_to_avoid.extend(["spearheaded", "leveraged", "stakeholder alignment"])
    elif "enterprise" in str(biz_terms):
        language_to_use.extend(["delivered", "managed", "led"])
    else:
        language_to_use.extend(["built", "improved", "delivered"])
    language_to_avoid.extend(["agentic", "multi-agent", "autonomous", "swarm",
                               "AI revolution", "spearheaded", "synergy", "leverage"])

    # ── India presence ─────────────────────────────────────────────────────
    india_presence = "Likely (India role posting)" if "india_office_mentioned" in jd_signals.get("implied_context", []) else "UNKNOWN"

    # ── Role reason ─────────────────────────────────────────────────────────
    role_reason = ""
    for clue in role_clues:
        if clue.startswith("hiring_reason:") or clue.startswith("role_scope:"):
            role_reason = clue.split(":", 1)[1].strip()
            break
    if not role_reason:
        role_reason = f"Hiring for {role_title} — extract from JD context."

    # ── Build result ────────────────────────────────────────────────────────
    result = CompanyIntelligenceResult(
        company_name=company,
        role_title=role_title,
        source_urls=[s.get("url", "") for s in web_sources if s.get("url")],
        grounding_status=grounding_status,
        confidence=min(0.35, max_conf),
        generated_at=datetime.now(timezone.utc).isoformat(),
        cache_key=_cache_key(company, role_title or ""),
        ttl_days=30,

        company_summary=company_summary,
        business_model=business_model,
        customer_segment=customer_segment,
        product_category=product_category,
        india_presence=india_presence,
        company_maturity="UNKNOWN",
        hiring_urgency="UNKNOWN",

        role_reason=role_reason,
        culture_signals=tone_markers or [],
        communication_style=_infer_tone_from_markers(tone_markers),
        language_to_use=language_to_use,
        language_to_avoid=language_to_avoid,
        unknowns=[f"No web research available for {company}."] if not web_sources else [],
    )

    result.s6_positioning_context = _build_s6_context(result)
    result.s7_rewrite_context = _build_s7_context(result)
    return result


def _map_biz_terms_to_model(terms: list[str]) -> str:
    """Map detected business terms to a human-readable business model."""
    mapping = {
        "saas": "SaaS / Subscription",
        "b2b": "B2B",
        "b2c": "B2C",
        "d2c": "D2C",
        "ecommerce": "E-commerce",
        "marketplace": "Marketplace",
        "enterprise_sales": "Enterprise Sales",
        "fintech": "Fintech",
        "healthtech": "Healthtech",
        "edtech": "Edtech",
        "fashion": "Fashion / Retail",
        "retail": "Retail",
        "manufacturing": "Manufacturing",
        "consumer": "Consumer",
        "banking": "Banking / Financial Services",
    }
    matches = [mapping[t] for t in terms if t in mapping]
    return ", ".join(matches[:3]) if matches else ""


def _jd_summary(company: str, jd_signals: dict[str, Any]) -> str:
    """Build a company summary from JD signals when LLM returns empty."""
    biz = jd_signals.get("business_terms", [])
    prod = jd_signals.get("product_terms", [])
    domain = jd_signals.get("domain_terms", [])
    parts = [company]
    if biz:
        parts.append(f"operates in {', '.join(biz[:3])}")
    if prod or domain:
        focus = prod[:2] + domain[:2]
        if focus:
            parts.append(f"with a focus on {', '.join(focus[:3])}")
    return ". ".join(parts) + "."


def _infer_tone_from_markers(markers: list[str]) -> str:
    if "startup_velocity" in markers:
        return "fast-paced and builder-oriented"
    if "data_driven" in markers:
        return "analytical and metrics-focused"
    if "collaborative" in markers:
        return "collaborative and cross-functional"
    if "entrepreneurial" in markers:
        return "entrepreneurial and ownership-driven"
    return ""


def _find_repo_root() -> Path:
    """Find the repo root robustly — walk up from this file."""
    p = Path(__file__).resolve().parent.parent  # careerloop/.. → repo root
    return p
