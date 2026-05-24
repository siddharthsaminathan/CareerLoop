"""
CareerLoop Data Models — JobPosting, fingerprinting, normalization.

Every discovered job becomes a JobPosting with a unique fingerprint.
Fingerprint = normalized_company + normalized_role + canonical_domain
"""

import re
import hashlib
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Optional
from enum import Enum
from urllib.parse import urlparse


class Decision(str, Enum):
    APPLY = "APPLY"
    SKIP = "SKIP"
    MAYBE = "MAYBE"

class Recommendation(str, Enum):
    APPLY = "APPLY"
    MAYBE = "MAYBE"
    SKIP = "SKIP"

class SourceType(str, Enum):
    LINKEDIN = "linkedin"
    NAUKRI = "naukri"
    INSTAHYRE = "instahyre"
    CUTSHORT = "cutshort"
    HIRIST = "hirist"
    IIMJOBS = "iimjobs"
    FOUNDIT = "foundit"
    WELLFOUND = "wellfound"
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    ASHBY = "ashby"
    WORKDAY = "workday"
    COMPANY_CAREERS = "company_careers"
    MANUAL_URL = "manual_url"
    CSV_IMPORT = "csv_import"
    REFERRAL = "referral"
    RECRUITER = "recruiter"
    UNKNOWN = "unknown"


class URLType(str, Enum):
    INDIVIDUAL_JOB = "INDIVIDUAL_JOB"
    SEARCH_PAGE = "SEARCH_PAGE"
    COMPANY_CAREERS_PAGE = "COMPANY_CAREERS_PAGE"
    BLOG_ARTICLE = "BLOG_ARTICLE"
    CATEGORY_PAGE = "CATEGORY_PAGE"
    UNKNOWN = "UNKNOWN"


class VerificationOutcome(str, Enum):
    VERIFIED_STRONG = "VERIFIED_STRONG"
    VERIFIED_MAYBE = "VERIFIED_MAYBE"
    NEEDS_MORE_DATA = "NEEDS_MORE_DATA"
    REJECTED = "REJECTED"
    NOISE = "NOISE"


@dataclass
class SearchResult:
    url: str
    title: str = ""
    snippet: str = ""
    source_query: str = ""
    source_role: str = ""
    source_city: str = ""
    source_site: str = ""
    search_engine: str = "unknown"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CandidateURL:
    url: str
    url_type: str
    title: str = ""
    snippet: str = ""
    source_query: str = ""
    source_role: str = ""
    source_city: str = ""
    source_site: str = ""
    search_engine: str = "unknown"
    verification_outcome: str = VerificationOutcome.NEEDS_MORE_DATA.value
    reason: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ExtractedJob:
    title: str
    company: str
    location: str
    jd_text: str
    apply_url: str
    source_url: str
    url_type: str = URLType.INDIVIDUAL_JOB.value
    source: str = "unknown"
    work_mode: str = ""
    salary_range: str = ""
    skills_required: list[str] = field(default_factory=list)
    posted_at: str = ""
    verification_outcome: str = VerificationOutcome.NEEDS_MORE_DATA.value

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class VerifiedJob:
    job: "JobPosting"
    verification_outcome: str
    verification_reason: str = ""

    def to_dict(self) -> dict:
        d = self.job.to_dict()
        d["verification_outcome"] = self.verification_outcome
        d["verification_reason"] = self.verification_reason
        return d


@dataclass
class ScoredJob:
    job: "JobPosting"
    heuristic_score: float
    fit_score: Optional[float] = None
    fit_result: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = self.job.to_dict()
        d["heuristic_score"] = self.heuristic_score
        d["fit_score"] = self.fit_score
        d["fit_result"] = self.fit_result
        return d


@dataclass
class UserVisibleOpportunity:
    company: str
    role_title: str
    location: str
    source_url: str
    apply_url: str
    overall_score: float
    recommendation: str
    why_user_might_like_it: str = ""
    risks: list[str] = field(default_factory=list)
    confidence: float = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class JobPosting:
    """Canonical job posting model."""

    # Identity
    id: str = ""                      # loop-XXXX (assigned by ledger)
    fingerprint: str = ""             # SHA256 of normalized identity
    source: str = "unknown"           # SourceType value
    source_url: str = ""

    # Normalized fields
    company: str = ""
    company_normalized: str = ""
    role_title: str = ""
    role_normalized: str = ""
    location: str = ""
    location_normalized: str = ""

    # Details
    work_mode: str = ""               # remote / hybrid / onsite
    salary_range: str = ""
    experience_required: str = ""
    skills_required: list[str] = field(default_factory=list)
    responsibilities: str = ""
    company_type: str = ""            # startup / mnc / gcc / saas / fintech / etc
    application_url: str = ""

    # Timestamps
    posted_at: Optional[str] = None
    first_seen_at: str = ""
    last_seen_at: str = ""

    # Extraction metadata
    raw_description: str = ""
    extraction_confidence: float = 1.0  # 1.0 = manual, <1.0 = automated extraction

    # Source merging
    alternate_sources: list[str] = field(default_factory=list)
    is_repost: bool = False

    def __post_init__(self):
        if not self.first_seen_at:
            self.first_seen_at = datetime.now(timezone.utc).isoformat()
        if not self.last_seen_at:
            self.last_seen_at = self.first_seen_at
        if not self.company_normalized:
            self.company_normalized = normalize_company(self.company)
        if not self.role_normalized:
            self.role_normalized = normalize_role(self.role_title)
        if not self.location_normalized:
            self.location_normalized = normalize_location(self.location)
        if not self.fingerprint:
            self.fingerprint = make_fingerprint(
                self.company_normalized, self.role_normalized,
                self.location_normalized, self._extract_domain()
            )

    def _extract_domain(self) -> str:
        if self.source_url:
            m = re.search(r'https?://([^/]+)', self.source_url)
            if m:
                return m.group(1).replace('boards.', '').replace('job-boards.', '').replace('jobs.', '').replace('careers.', '')
        if self.application_url:
            m = re.search(r'https?://([^/]+)', self.application_url)
            if m:
                return m.group(1)
        return ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d['source'] = self.source
        return d


# ── Normalization ────────────────────────────────────────────────────

COMMON_WORDS = re.compile(
    r'\b(inc|llc|ltd|limited|corp|corporation|pvt|private|technologies|technology|'
    r'solutions|services|software|systems|group|holdings|international|global|'
    r'consulting|digital|tech|ai|labs|venture|studios|capital|partners)\.?\b',
    re.IGNORECASE
)

def normalize_company(name: str) -> str:
    """Normalize company name for fingerprinting."""
    if not name:
        return ""
    n = name.lower().strip()
    n = re.sub(r'[^\w\s]', '', n)       # remove punctuation
    n = COMMON_WORDS.sub('', n)          # remove common legal suffixes
    n = re.sub(r'\s+', ' ', n).strip()   # collapse whitespace
    # Common mappings
    mappings = {
        'tcs': 'tata consultancy services',
        'hcl': 'hcl technologies',
        'ibm': 'ibm',
        'amazon web services': 'aws',
        'google cloud': 'google',
        'microsoft azure': 'microsoft',
    }
    return mappings.get(n, n)

def normalize_role(title: str) -> str:
    """Normalize role title for fingerprinting."""
    if not title:
        return ""
    t = title.lower().strip()
    t = re.sub(r'[^\w\s]', '', t)
    t = re.sub(r'\s+', ' ', t).strip()
    # Strip seniority prefixes for matching
    seniority = ['senior', 'staff', 'principal', 'lead', 'head', 'director',
                 'vp', 'associate', 'junior', 'trainee', 'intern', 'sr', 'jr']
    words = t.split()
    while words and words[0] in seniority:
        words.pop(0)
    t = ' '.join(words)
    # Common normalizations
    mappings = {
        'software development engineer': 'software engineer',
        'sde': 'software engineer',
        'member of technical staff': 'software engineer',
        'mts': 'software engineer',
        'product analyst': 'product analyst',
        'applied ai': 'applied ai engineer',
        'machine learning': 'ml engineer',
    }
    for k, v in mappings.items():
        if k in t:
            t = t.replace(k, v, 1)
            break
    return t

def normalize_location(loc: str) -> str:
    """Normalize location for fingerprinting."""
    if not loc:
        return ""
    l = loc.lower().strip()
    l = re.sub(r'[^\w\s,]', '', l)
    l = re.sub(r'\s+', ' ', l).strip()
    # Map common variations
    mappings = {
        'bengaluru': 'bangalore',
        'blr': 'bangalore',
        'gurgaon': 'gurugram',
        'gurugram': 'gurugram',
        'ncr': 'delhi ncr',
        'new delhi': 'delhi',
        'bombay': 'mumbai',
        'navi mumbai': 'mumbai',
        'madras': 'chennai',
        'pune': 'pune',
        'hyderabad': 'hyderabad',
        'hyd': 'hyderabad',
        'secunderabad': 'hyderabad',
        'calcutta': 'kolkata',
        'remote': 'remote',
        'work from home': 'remote',
        'wfh': 'remote',
    }
    for k, v in mappings.items():
        if k in l:
            return v
    # If "india" is in location, return canonical city if found
    for city in ['bangalore', 'mumbai', 'delhi', 'gurugram', 'chennai', 'hyderabad',
                 'pune', 'kolkata', 'ahmedabad', 'kochi', 'jaipur']:
        if city in l:
            return city
    if 'india' in l:
        return 'india'
    return l.split(',')[0].strip()

def make_fingerprint(company: str, role: str, location: str, domain: str) -> str:
    """Create a deterministic fingerprint for deduplication."""
    key = f"{company}|{role}|{location}|{domain}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def classify_url_type(url: str) -> URLType:
    if not url:
        return URLType.UNKNOWN

    parsed = urlparse(url.lower())
    netloc = parsed.netloc.replace("www.", "")
    path = parsed.path.rstrip("/")
    query = parsed.query
    blog_tokens = (
        "/blog", "/blogs", "/article", "/articles", "/news", "/press",
        "/insights", "/resources", "/stories", "/learn"
    )
    if any(token in path for token in blog_tokens) or any(d in netloc for d in ("medium.com", "substack.com")):
        return URLType.BLOG_ARTICLE

    if "linkedin.com" in netloc:
        if path.startswith("/jobs/search"):
            return URLType.SEARCH_PAGE
        if re.search(r"^/jobs/view/\d+", path):
            return URLType.INDIVIDUAL_JOB
        if path.startswith("/jobs/collections") or path == "/jobs":
            return URLType.SEARCH_PAGE
        return URLType.UNKNOWN

    if "naukri.com" in netloc:
        if path.startswith("/job-listings-") or "/job-listings-" in path:
            return URLType.INDIVIDUAL_JOB
        if "jobs-in-" in path or path.endswith("-jobs") or path in ("", "/") or any(k in query for k in ("keyword=", "k=", "location=", "l=", "experience=")):
            return URLType.SEARCH_PAGE
        if any(token in path for token in ("/browse-jobs", "/top-jobs", "/jobsearch")):
            return URLType.CATEGORY_PAGE
        return URLType.UNKNOWN

    if "cutshort.io" in netloc:
        if path.startswith("/job/"):
            return URLType.INDIVIDUAL_JOB
        if path.startswith("/jobs"):
            return URLType.CATEGORY_PAGE
        return URLType.UNKNOWN

    if "instahyre.com" in netloc:
        if re.search(r"/job-\d+", path):
            return URLType.INDIVIDUAL_JOB
        return URLType.SEARCH_PAGE if path.startswith("/jobs") else URLType.UNKNOWN

    if "hirist.tech" in netloc:
        if path.startswith("/j/"):
            return URLType.INDIVIDUAL_JOB
        return URLType.SEARCH_PAGE if "jobs" in path else URLType.UNKNOWN

    if "foundit.in" in netloc:
        if path.startswith("/career-advice") or path.startswith("/career-advice/"):
            return URLType.BLOG_ARTICLE
        if "job" in path and re.search(r"\d+", path):
            return URLType.INDIVIDUAL_JOB
        return URLType.SEARCH_PAGE if "job" in path else URLType.UNKNOWN

    if any(token in path for token in ("/category", "/categories", "/browse", "/tag/", "/tags/", "/roles")):
        return URLType.CATEGORY_PAGE

    if any(token in path for token in ("/careers", "/career", "/jobs", "/openings", "/positions")):
        if re.search(r"(/jobs?|/openings|/positions)/[^/]*\d", path) or re.search(r"/(gh_jid|jobs?)/", path):
            return URLType.INDIVIDUAL_JOB
        return URLType.COMPANY_CAREERS_PAGE

    if re.search(r"/job[-/]?([a-z0-9-]*\d+|details|view)", path) or "jobid=" in query or "job_id=" in query:
        return URLType.INDIVIDUAL_JOB

    return URLType.UNKNOWN


# ── Pipeline Observability ────────────────────────────────────────────


@dataclass
class RunMetrics:
    """Per-pipeline-run tracking. Standardizes what we measure across runs."""

    run_id: str
    started_at: str
    completed_at: str = ""
    jobs_discovered: int = 0
    jobs_deduped: int = 0
    jobs_scored: int = 0
    jobs_shortlisted: int = 0
    llm_calls: int = 0
    llm_prompt_tokens: int = 0
    llm_completion_tokens: int = 0
    errors: list[str] = field(default_factory=list)
    source_breakdown: dict = field(default_factory=dict)
