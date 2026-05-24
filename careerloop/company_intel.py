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
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from careerloop.sources.portal_scraper import PortalScraper
from careerloop.sources.scrapegraph_adapter import ScrapeGraphAdapter

# ── Timeout constants ──────────────────────────────────────────────────────────
_WEB_SEARCH_TIMEOUT_SECONDS = 12
_TOTAL_NETWORK_BUDGET_SECONDS = 18

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
    red_flags_detail: list[dict[str, str]] = field(default_factory=list)  # [{signal, source, severity}]
    recruiter_info: dict[str, str] = field(default_factory=dict)  # {name, link, role}

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

    # People intelligence (Phase 2)
    key_people: list[dict[str, str]] = field(default_factory=list)  # [{name, title, source}]
    founder_background: str = ""
    hiring_manager_context: str = ""

    # Interview intelligence (Phase 2)
    interview_questions_likely: list[str] = field(default_factory=list)
    culture_keywords: list[str] = field(default_factory=list)
    glassdoor_signal: str = ""  # brief culture signal from Glassdoor snippets
    reddit_signal: str = ""  # brief sentiment from Reddit mentions

    # Source tracking
    sources_by_type: dict[str, int] = field(default_factory=dict)  # {source_type: count}

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
            "red_flags_detail": self.red_flags_detail,
            "recruiter_info": self.recruiter_info,
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
            "key_people": self.key_people,
            "founder_background": self.founder_background,
            "hiring_manager_context": self.hiring_manager_context,
            "interview_questions_likely": self.interview_questions_likely,
            "culture_keywords": self.culture_keywords,
            "glassdoor_signal": self.glassdoor_signal,
            "reddit_signal": self.reddit_signal,
            "sources_by_type": self.sources_by_type,
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


def _derive_company_domain(company: str, job_url: str = "") -> str:
    """Best-effort domain derivation from job URL or company name."""
    if job_url:
        from urllib.parse import urlparse
        parsed = urlparse(job_url)
        host = (parsed.hostname or "").lower()
        # Strip common ATS and job board domains — we want the company's own site
        ats_hosts = {"greenhouse.io", "lever.co", "ashbyhq.com", "workable.com",
                     "breezy.hr", "recruitee.com", "jobs.lever.co", "boards.greenhouse.io",
                     "linkedin.com", "indeed.com", "naukri.com", "cutshort.io", "instahyre.com"}
        if host and not any(ats in host for ats in ats_hosts):
            return host
    # Fallback: guess from company name
    slug = re.sub(r"[^a-z0-9]", "", company.lower())
    return f"{slug}.com"


def _extract_people_from_html(html_text: str, source_label: str = "company_website") -> list[dict[str, str]]:
    """Extract people names and titles from team/about page HTML text.

    Looks for patterns like "Name — Title", "Name, Title", or names under
    headings like Team, Leadership, Founders.
    """
    people: list[dict[str, str]] = []
    seen_names: set[str] = set()

    # Pattern: "FirstName LastName — Title" or "FirstName LastName, Title"
    # Common on team pages
    for m in re.finditer(
        r"([A-Z][a-z]+(?:\s[A-Z][a-z]+){1,3})\s*[—–\-,|]\s*"
        r"((?:CEO|CTO|COO|CFO|VP|Head|Director|Manager|Engineer|Designer|Founder|"
        r"Co-Founder|Chief|President|Partner|Lead|Principal)[^\n]{0,60})",
        html_text
    ):
        name = m.group(1).strip()
        title = m.group(2).strip()
        if name not in seen_names and len(name) > 4:
            people.append({"name": name, "title": title, "source": source_label})
            seen_names.add(name)

    # LinkedIn-specific: "Posted by\nFirstName LastName\nTitle"
    for m in re.finditer(r"Posted by\s*\n\s*([A-Z][a-z]+\s[A-Z][a-z]+)\s*\n\s*([^\n]{5,100})", html_text):
        name = m.group(1).strip()
        title = m.group(2).strip()
        if name not in seen_names:
            people.append({"name": name, "title": title, "source": "linkedin"})
            seen_names.add(name)

    return people[:15]  # cap at 15


def _scrape_company_website(domain: str) -> list[dict[str, str]]:
    """Fetch key pages from the company website: /, /about, /team, /careers.

    Returns sources with page_content populated.
    """
    results: list[dict[str, str]] = []
    paths = ["/about", "/about-us", "/team", "/our-team", "/careers"]
    base = f"https://{domain}"

    for path in paths:
        url = f"{base}{path}"
        try:
            content = _fetch_page_content(url, timeout=5)
            if content and len(content) > 100:
                results.append({
                    "title": f"Company page: {domain}{path}",
                    "url": url,
                    "snippet": content[:200],
                    "page_content": content[:3000],
                    "source_type": "company_website",
                })
                print(f"     ✓ {domain}{path}: {len(content)} chars")
        except Exception:
            pass

    return results


def _run_ddg_query(query: str, source_type: str, max_results: int = 3) -> list[dict[str, str]]:
    """Run a single DuckDuckGo query, return structured results."""
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
            for item in ddgs.text(query, max_results=max_results):
                results.append({
                    "title": item.get("title", ""),
                    "url": item.get("href", item.get("url", "")),
                    "snippet": item.get("body", item.get("snippet", "")),
                    "source_type": source_type,
                })
    except Exception:
        pass
    return [r for r in results if r.get("url") or r.get("snippet")]


def _gather_web_sources(company: str, job_url: str = "") -> list[dict[str, str]]:
    """Gather web sources with MECE targeted queries. Never blocks the pipeline.

    5 parallel search queries (each source-typed) + company website scrape
    + page content fetch for top results. All timeout-safe.
    """
    sources: list[dict[str, str]] = []

    if job_url:
        sources.append({
            "title": f"Job posting for {company}",
            "url": job_url,
            "snippet": "Job posting URL supplied by pipeline.",
            "source_type": "jd_url",
        })

    # ── Simplified company name for better search results ──────────────────
    search_name = re.sub(r"\s+(Pvt\s*Ltd|Ltd|Inc|Corp|LLP|Private\s+Limited).*$", "", company, flags=re.IGNORECASE).strip()
    if len(search_name.split()) > 3:
        # If still long, take first 3 words
        search_name = " ".join(search_name.split()[:3])

    # ── MECE query set: 5 targeted searches ─────────────────────────────
    queries = [
        # D5: Market position — funding, news, growth
        (f'{search_name} funding valuation growth raised 2024 OR 2025', "market_news"),
        # D2: Culture — Glassdoor reviews
        (f'site:glassdoor.com OR site:glassdoor.co.in {search_name} reviews summary', "glassdoor"),
        # D2+D4: Culture + Role — Reddit sentiment
        (f'site:reddit.com {search_name} work interview culture salary', "reddit"),
        # D3: People — founders, leadership
        (f'{search_name} CEO founder leadership team', "people_search"),
        # D1+D5: Identity + market — general company context
        (f'{search_name} company about products tech stack', "web_search"),
    ]

    def _run_all_queries(results_ref: list[dict[str, str]]) -> None:
        with ThreadPoolExecutor(max_workers=5) as ex:
            futures = {
                ex.submit(_run_ddg_query, q, stype, 3): stype
                for q, stype in queries
            }
            # Wait for as many as possible within the timeout, but gather them incrementally
            for fut in as_completed(futures):
                try:
                    # Individual query timeout is generous
                    results_ref.extend(fut.result(timeout=7))
                except Exception:
                    pass

    web_results: list[dict[str, str]] = []
    try:
        with ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(_run_all_queries, web_results)
            try:
                future.result(timeout=_WEB_SEARCH_TIMEOUT_SECONDS)
            except FuturesTimeoutError:
                print(f"  !! S3 web search timed out after {_WEB_SEARCH_TIMEOUT_SECONDS}s — kept {len(web_results)} results")
        
        if web_results:
            sources.extend(web_results)
            # Count by type
            type_counts: dict[str, int] = {}
            for s in web_results:
                st = s.get("source_type", "unknown")
                type_counts[st] = type_counts.get(st, 0) + 1
            print(f"  → S3 MECE queries: {type_counts}")
    except Exception as e:
        print(f"  !! S3 web search error: {e}")

    # ── Specialized Scrapers (Phase 2 & 3: LinkedIn & Glassdoor) ───────

    def _run_specialized_scrapers():
        # 1. LinkedIn Job Page (D3 - Recruiter info)
        if job_url and ("linkedin.com/jobs" in job_url or "linkedin.com/feed" in job_url):
            print(f"  → S3 scraping LinkedIn job page (D3)...")
            try:
                scraper = PortalScraper()
                portal_res = scraper.scrape(job_url)
                if portal_res.has_jobs or portal_res.dom_jobs:
                    # Capture description and DOM snippets for synthesis
                    content = " ".join([j.get("description", "") for j in portal_res.all_jobs])
                    if not content and portal_res.dom_jobs:
                        content = str(portal_res.dom_jobs[0])
                    
                    if content:
                        sources.append({
                            "url": job_url,
                            "title": "LinkedIn Scraped Intelligence",
                            "page_content": content[:5000],
                            "source_type": "linkedin_scraping"
                        })
            except Exception as e:
                print(f"  !! LinkedIn scrape failed: {e}")

        # 2. Glassdoor (D2 - Culture Red Flags)
        gd_url = next((s.get("url") for s in web_results if s.get("source_type") == "glassdoor"), None)
        if gd_url:
            print(f"  → S3 extracting Glassdoor signals (D2)...")
            try:
                adapter = ScrapeGraphAdapter()
                if adapter.available:
                    res = adapter.extract(gd_url)
                    if res:
                        sources.append({
                            "url": gd_url,
                            "title": "Glassdoor Extraction",
                            "page_content": json.dumps(res),
                            "source_type": "glassdoor_extraction"
                        })
                else:
                    # Fallback to standard fetch if ScrapeGraph unavailable
                    content = _fetch_page_content(gd_url, timeout=8)
                    if content:
                        sources.append({
                            "url": gd_url,
                            "title": "Glassdoor Page Content",
                            "page_content": content,
                            "source_type": "glassdoor_extraction"
                        })
            except Exception as e:
                print(f"  !! Glassdoor extraction failed: {e}")

    try:
        with ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(_run_specialized_scrapers)
            future.result(timeout=10)
    except Exception:
        pass

    # ── Company website scrape (D1: Identity/Product) ─────────────────
    domain = _derive_company_domain(company, job_url)
    if domain:
        print(f"  → S3 scraping company website: {domain}")
        try:
            with ThreadPoolExecutor(max_workers=1) as ex:
                future = ex.submit(_scrape_company_website, domain)
                try:
                    site_results = future.result(timeout=10)
                    sources.extend(site_results)
                    print(f"  → S3 company website: {len(site_results)} pages fetched")
                except FuturesTimeoutError:
                    print(f"  !! S3 company website scrape timed out")
        except Exception as e:
            print(f"  !! S3 company website error: {e}")

    # ── Fetch actual page content for non-site search results ───────────
    search_urls = [
        s for s in sources
        if s.get("source_type") in ("web_search", "market_news", "people_search")
           and not s.get("page_content")
    ]
    if search_urls:
        urls_to_fetch = [s for s in search_urls[:2] if s.get("url", "").startswith("http")]
        if urls_to_fetch:
            print(f"  → S3 fetching content from {len(urls_to_fetch)} news/web URLs...")
            for source in urls_to_fetch:
                url = source.get("url", "")
                content = _fetch_page_content(url, timeout=6)
                if content:
                    source["page_content"] = content
                    print(f"     ✓ {source.get('title', url)[:60]}: {len(content)} chars")

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

Your job is to convert multi-source evidence about a company and role into strategic career intelligence. You receive evidence from up to 7 source types: JD, company website, Glassdoor, Reddit, people/leadership search, market/funding news, and general web. Each source type tells you something different.

STRICT EVIDENCE RULES:
1. Grounded Facts MUST come from the provided text evidence. Do NOT use pre-training recall for company facts (headcount, revenue, funding, leadership names, office locations) unless explicitly in the input.
2. If a field has no evidence, set to "UNKNOWN" or empty list/object. Add to "unknowns" array. "UNKNOWN" = high quality.
3. Every claim must cite its source: [JD], [WEBSITE], [GLASSDOOR], [REDDIT], [NEWS], [WEB].

SOURCE-SPECIFIC EXTRACTION:
- COMPANY WEBSITE → identity, mission, actual product, team names, culture claims
- GLASSDOOR → culture score, interview style, management, salary range signals
- REDDIT → unfiltered sentiment, red flags, honest employee/candidate experience
- PEOPLE/LEADERSHIP → founder background, key hires, org structure clues
- MARKET/NEWS → funding stage, growth trajectory, competitive position

NEW FIELDS TO POPULATE:
- recruiter_info: {name, link, role} — from LinkedIn scraping or JD "Posted by" section
- red_flags_detail: [{signal, source, severity}] — specific negative signals (layoffs, toxic culture, late pay)
- key_people: [{name, title, source}] — from website team page or people search
- founder_background: 1-2 sentences on founder(s) background and vision
- hiring_manager_context: any signal about who the hire reports to
- interview_questions_likely: 3-5 likely interview topics based on JD + Glassdoor
- culture_keywords: 5-10 culture words that resonate (from website + Glassdoor)
- glassdoor_signal: 1-2 sentence summary of Glassdoor sentiment (or "No data")
- reddit_signal: 1-2 sentence summary of Reddit mentions (or "No data")

For downstream S7 rewrite context, provide a compact dictionary under "s7_rewrite_context" with:
- company_archetype: e.g., "design-led D2C brand with AI ambitions"
- company_tone: e.g., "warm and design-aware"
- product_context: what they build/sell
- business_problem: what problem this role is hired to solve
- role_success_criteria: what "great" looks like in 6 months
- language_to_use: 5-8 specific words/phrases from evidence that resonate with this company
- language_to_avoid: 5 generic/fluffy words to avoid
- proof_points_to_prefer: candidate evidence/projects they'd value most
- risks_to_soften: candidate gaps to reposition
- avoid_overclaiming_about: things NOT to exaggerate
- founder_context: 1-line on founder personality/background (for culture fit)
- hiring_reason: why this role exists NOW (growth? replacement? new initiative?)
- culture_fit_signals: 3-5 culture traits to mirror in resume language
- interview_prep_hints: 2-3 key topics to prepare for
- max_5_bullet_guidance: 1-sentence on how to tailor experience bullets

Return ONLY valid JSON matching the CompanyIntelligenceResult schema."""


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

    # ── Web sources by type (MECE) ────────────────────────────────────────
    source_types = {
        "company_website": "COMPANY WEBSITE PAGES (official)",
        "linkedin_scraping": "LINKEDIN JOB DETAILS & PEOPLE (scraped)",
        "glassdoor_extraction": "GLASSDOOR DEEP ANALYSIS (scraped)",
        "glassdoor": "GLASSDOOR SNIPPETS",
        "reddit": "REDDIT MENTIONS (sentiment)",
        "people_search": "PEOPLE/LEADERSHIP SIGNALS",
        "market_news": "MARKET/FUNDING NEWS",
        "web_search": "GENERAL WEB RESULTS",
    }
    any_web = False
    for stype, label in source_types.items():
        typed = [s for s in web_sources if s.get("source_type") == stype]
        if typed:
            any_web = True
            parts.append(f"{label}:")
            for i, s in enumerate(typed[:4]):
                parts.append(f"  {i+1}. [{s.get('title', '?')}]({s.get('url', '')})")
                snippet = s.get("snippet", "")
                if snippet:
                    parts.append(f"     Snippet: {snippet[:300]}")
                page_content = s.get("page_content", "")
                if page_content:
                    parts.append(f"     Content: {page_content[:1500]}")
            parts.append("")
    if not any_web:
        parts.append("WEB SOURCES: None available. Use JD-only evidence.")
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

    # ── Layer 2+3: Web sources (timeout-safe, skip if no LLM) ────────────────
    web_sources: list[dict[str, str]] = []
    if llm_client is None:
        print(f"  → S3 no LLM client, skipping web enrichment (JD-only mode)")
    else:
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

    # ── Determine grounding status (MECE-aware) ─────────────────────────────
    has_jd = bool(jd_text and jd_text.strip() and len(jd_text.strip()) > 20)
    source_types_found = set(s.get("source_type", "") for s in web_sources)
    source_types_found.discard("")
    source_types_found.discard("jd_url")
    n_source_types = len(source_types_found)

    if n_source_types >= 3:
        grounding_status = "READY"  # Multi-source triangulation
    elif n_source_types >= 1:
        grounding_status = "PARTIAL"
    elif has_jd:
        grounding_status = "JD_ONLY"
    else:
        grounding_status = "UNGROUNDED"
    print(f"  → S3 grounding: {grounding_status} ({n_source_types} source types: {source_types_found})")

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
        red_flags_detail=payload.get("red_flags_detail", []),
        recruiter_info=payload.get("recruiter_info", {}),

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

        # Phase 2 fields from LLM
        key_people=payload.get("key_people", []),
        founder_background=payload.get("founder_background", ""),
        hiring_manager_context=payload.get("hiring_manager_context", ""),
        interview_questions_likely=payload.get("interview_questions_likely", []),
        culture_keywords=payload.get("culture_keywords", []),
        glassdoor_signal=payload.get("glassdoor_signal", ""),
        reddit_signal=payload.get("reddit_signal", ""),
    )

    # ── Extract people from company website & LinkedIn (determinstic fallback & OutreachEngine integration) ──
    if llm_client is not None and company:
        try:
            from careerloop.outreach_engine import OutreachEngine
            print(f"  → S3 running OutreachEngine lead generation for {company}...")
            engine = OutreachEngine(api_key=llm_client.api_key)
            
            # Step 1: Classify route
            route_details = engine.classify_route(jd_text or "")
            
            # Step 2: Discover recruiter / EM leads
            leads = engine.discover_leads(company)
            
            # Step 3 & 4: Relevance parsing & ranking
            match_result = engine.parse_and_rank_leads(leads, jd_text or "")
            
            recruiter = match_result.get("recruiter")
            hm = match_result.get("hiring_manager")
            
            # Persist key_people list
            for lead in match_result.get("all_leads", []):
                result.key_people.append({
                    "name": lead.get("name", ""),
                    "title": lead.get("title", ""),
                    "source": "linkedin",
                    "plausibility_score": lead.get("score", 0)
                })
                
            # Persist recruiter_info target
            best_target = hm if hm else (recruiter if recruiter else None)
            if best_target:
                result.recruiter_info = {
                    "name": best_target.get("name", ""),
                    "link": best_target.get("linkedin_url", ""),
                    "role": best_target.get("title", ""),
                    "plausibility_score": str(best_target.get("plausibility_score", 0)),
                    "route": route_details.get("route", "Route C"),
                    "reason": best_target.get("reason", "")
                }
                
                # Step 5: Synthesize humanized outreach pack
                cand = candidate_context.get("candidate", {}) if candidate_context else {}
                narr = candidate_context.get("narrative", {}) if candidate_context else {}
                user_prof = {
                    "full_name": cand.get("full_name", ""),
                    "headline": narr.get("headline", ""),
                    "narrative": narr.get("exit_story", ""),
                    "superpowers": narr.get("superpowers", []),
                    "proof_points": narr.get("proof_points", [])
                }
                outreach_pack = engine.generate_outreach_pack(best_target, user_prof, jd_text or "", route_details.get("route", "Route C"))
                result.outreach_strategy_hint = f"OUTREACH PACK:\nDM: {outreach_pack.get('outreach_dm')}\n\nExit Line: {outreach_pack.get('exit_line')}\n\nEmail Guesses: {', '.join(outreach_pack.get('email_guesses', []))}"
                print(f"     ✓ Outreach target matched: {best_target.get('name')} ({best_target.get('title')}) via {route_details.get('route')}")
        except Exception as e:
            print(f"  !! OutreachEngine integration failed: {e}")
    else:
        # Fallback to deterministic regex for offline / no-LLM mode
        people_sources = [
            s for s in web_sources 
            if s.get("source_type") in ("company_website", "linkedin_scraping")
        ]
        for source in people_sources:
            content = source.get("page_content", "")
            if content:
                label = "linkedin" if source.get("source_type") == "linkedin_scraping" else "company_website"
                extracted = _extract_people_from_html(content, source_label=label)
                for p in extracted:
                    if not any(ep.get("name") == p["name"] for ep in result.key_people):
                        result.key_people.append(p)
                        # If this came from LinkedIn and we don't have recruiter_info name yet, try to set it
                        if label == "linkedin" and not result.recruiter_info.get("name"):
                            result.recruiter_info["name"] = p["name"]
                            if not result.recruiter_info.get("link"):
                                result.recruiter_info["link"] = source.get("url", "")
    
    if result.key_people:
        print(f"  → S3 people extracted: {len(result.key_people)} ({', '.join(p['name'] for p in result.key_people[:3])}...)")

    # ── Source tracking ─────────────────────────────────────────────────────
    type_counts: dict[str, int] = {}
    for s in web_sources:
        st = s.get("source_type", "unknown")
        type_counts[st] = type_counts.get(st, 0) + 1
    result.sources_by_type = type_counts

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
    ctx = {
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
        # Phase 2 fields
        "founder_context": result.founder_background or "",
        "hiring_reason": result.hiring_urgency or result.role_reason or "",
        "culture_fit_signals": result.culture_keywords[:5] if result.culture_keywords else [],
        "interview_prep_hints": result.interview_questions_likely[:3] if result.interview_questions_likely else [],
        "glassdoor_signal": result.glassdoor_signal or "",
        "reddit_signal": result.reddit_signal or "",
        "recruiter_info": result.recruiter_info or {},
    }
    return ctx


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
