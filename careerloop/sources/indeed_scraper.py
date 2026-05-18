"""
CareerLoop Indeed Scraper — Free JD extraction from Indeed India job pages.

Lightweight requests+bs4 scraper. No Selenium, no API keys.
Returns structured job data matching the ScrapeGraphAdapter output shape.

Targets in.indeed.com and indeed.com India job pages.
"""

import logging
import re
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 15

INDEED_URL_PATTERNS = [
    r"in\.indeed\.com/viewjob\?jk=",
    r"indeed\.com/viewjob\?jk=",
    r"in\.indeed\.com/jobs\?",
    r"indeed\.com/jobs\?",
    r"in\.indeed\.com/rc/clk\?jk=",
    r"indeed\.com/rc/clk\?jk=",
    r"in\.indeed\.com/cmp/",
    r"indeed\.com/cmp/.*/jobs\?jk=",
]


class IndeedScraper:
    """Extract structured job data from Indeed India job pages.

    Uses multiple selector strategies to handle Indeed's periodically
    changing DOM structure. Falls back gracefully through modern
    data-testid selectors, legacy class/ID selectors, and generic
    heuristics.
    """

    def __init__(self):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        )

    @classmethod
    def can_handle(cls, url: str) -> bool:
        """Return True if this scraper can extract from the URL."""
        if not url:
            return False
        url_lower = url.lower()
        return any(
            re.search(pattern, url_lower) for pattern in INDEED_URL_PATTERNS
        )

    def extract(self, url: str) -> Optional[dict]:
        """Extract job details from an Indeed job page URL.

        Returns dict matching ScrapeGraphAdapter output shape, or None
        on any failure. Never raises.
        """
        if not self.can_handle(url):
            logger.debug(f"[IndeedScraper] URL not supported: {url}")
            return None

        try:
            resp = self.session.get(url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
        except requests.Timeout:
            logger.warning(f"[IndeedScraper] Timeout fetching {url}")
            return None
        except requests.RequestException as e:
            logger.warning(f"[IndeedScraper] Request failed for {url}: {e}")
            return None
        except Exception as e:
            logger.warning(f"[IndeedScraper] Unexpected error fetching {url}: {e}")
            return None

        try:
            title = self._extract_title(soup) or ""
            company = self._extract_company(soup) or ""
            location = self._extract_location(soup) or ""
            description = self._extract_description(soup) or ""
            skills = self._extract_skills(description) if description else []
            salary = self._extract_salary(description) if description else ""
            work_mode = self._detect_work_mode(description) if description else ""

            # If we got nothing useful, bail
            if not title and not description:
                logger.warning(f"[IndeedScraper] No content extracted from {url}")
                return None

            return {
                "title": title,
                "company": company,
                "location": location,
                "apply_url": url,
                "description": description,
                "skills": skills,
                "salary": salary,
                "work_mode": work_mode,
                "_source_url": url,
                "_extraction_method": "indeed_direct",
            }

        except Exception as e:
            logger.warning(f"[IndeedScraper] Parse error for {url}: {e}")
            return None

    # ---- Title extraction ----

    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        selectors = [
            # Modern data-testid
            {"data-testid": "jobDetailTitle"},
            {"data-testid": "jobsearch-JobInfoHeader-title"},
            # Legacy class-based
            {"class": "jobsearch-JobInfoHeader-title"},
            {"class": "icl-u-xs-mb--xs icl-u-xs-mt--none jobsearch-JobInfoHeader-title"},
            # Generic fallback: h1
        ]
        for sel in selectors:
            el = soup.find(sel.get("tag", True), sel) if isinstance(sel, dict) else soup.find("h1")
            if el is None and isinstance(sel, dict):
                el = soup.find(attrs=sel)
            if el:
                text = el.get_text(" ", strip=True)
                if text and len(text) > 2:
                    return text

        # Last resort: any h1
        h1 = soup.find("h1")
        if h1:
            text = h1.get_text(" ", strip=True)
            if len(text) > 2:
                return text
        return None

    # ---- Company extraction ----

    def _extract_company(self, soup: BeautifulSoup) -> Optional[str]:
        selectors = [
            {"data-testid": "inlineHeader-companyName"},
            {"data-testid": "jobsearch-CompanyInfoContainer"},
            {"class": "icl-u-lg-mr--sm icl-u-xs-mr--xs"},
            {"class": "jobsearch-InlineCompanyRating"},
        ]
        for sel in selectors:
            el = soup.find(attrs=sel)
            if el:
                # Try nested company name link first
                link = el.find("a")
                if link:
                    text = link.get_text(" ", strip=True)
                    if text and len(text) > 1:
                        return text
                text = el.get_text(" ", strip=True)
                # Strip rating numbers that might come along
                text = re.sub(r"\d+\.?\d*\s*(out of 5|reviews?)", "", text, flags=re.IGNORECASE).strip()
                if text and len(text) > 1:
                    return text

        # Generic fallback: any element with "company" in data-testid
        for el in soup.find_all(attrs={"data-testid": True}):
            if "company" in el.get("data-testid", "").lower():
                text = el.get_text(" ", strip=True)
                text = re.sub(r"\d+\.?\d*\s*(out of 5|reviews?)", "", text, flags=re.IGNORECASE).strip()
                if text:
                    return text
        return None

    # ---- Location extraction ----

    def _extract_location(self, soup: BeautifulSoup) -> Optional[str]:
        selectors = [
            {"data-testid": "inlineHeader-companyLocation"},
            {"data-testid": "jobsearch-JobInfoHeader-companyLocation"},
            {"class": "icl-u-xs-mt--xs icl-u-textColor--secondary"},
        ]
        for sel in selectors:
            el = soup.find(attrs=sel)
            if el:
                text = el.get_text(" ", strip=True)
                if text and len(text) > 2:
                    return text

        # Generic fallback: look for location-like text patterns
        # Common Indeed location format: "City, State" or "City, State PIN"
        location_pattern = re.compile(
            r"([A-Z][a-z]+(?: [A-Z][a-z]+)?(?:, [A-Z]{2}(?: \d{5,6})?)?)",
        )
        for el in soup.find_all(["div", "span"]):
            text = el.get_text(" ", strip=True)
            if location_pattern.fullmatch(text):
                return text
        return None

    # ---- Description extraction ----

    def _extract_description(self, soup: BeautifulSoup) -> Optional[str]:
        # Primary: Indeed's standard JD container
        desc_div = soup.find("div", id="jobDescriptionText")
        if desc_div:
            text = desc_div.get_text("\n", strip=True)
            if text and len(text) > 50:
                return text

        # Fallback selectors
        fallback_selectors = [
            {"data-testid": "jobDescriptionText"},
            {"class": "jobsearch-jobDescriptionText"},
            {"class": "job-description"},
            {"id": "jobDescriptionText"},
        ]
        for sel in fallback_selectors:
            el = soup.find(attrs=sel)
            if el:
                text = el.get_text("\n", strip=True)
                if text and len(text) > 50:
                    return text

        # Generic fallback: largest text block on the page
        largest = ""
        for el in soup.find_all(["div", "section", "article"]):
            text = el.get_text("\n", strip=True)
            if len(text) > len(largest) and len(text) > 100:
                # Skip elements that are clearly navigation or metadata
                if not self._is_noise_block(el, text):
                    largest = text

        return largest if largest else None

    def _is_noise_block(self, el, text: str) -> bool:
        """Heuristic: detect blocks that are navigation, footer, or metadata."""
        tag = el.name or ""
        cls = " ".join(el.get("class", []))
        attrs = f"{tag} {cls}".lower()

        noise_terms = [
            "nav", "footer", "header", "sidebar", "related", "similar",
            "breadcrumb", "menu", "signin", "login", "register",
        ]
        if any(t in attrs for t in noise_terms):
            return True

        # Very short text even in a large container is probably not JD
        text_len = len(text)
        html_len = len(el.get_text("", strip=False))
        if text_len < 200 and html_len > 5000:
            return True

        return False

    # ---- Skill extraction ----

    def _extract_skills(self, description: str) -> list[str]:
        """Extract likely technical skills from description text.

        Looks for bullet-point lists and known technical terms.
        """
        skills = set()

        # Common technical skills to scan for
        skill_patterns = [
            # Languages
            r"\b(Python|Java|JavaScript|TypeScript|Go|Rust|C\+\+|C#|Ruby|PHP|Kotlin|Swift|Scala|R|MATLAB|Perl|Shell|Bash)\b",
            # Frameworks / libraries
            r"\b(React|Angular|Vue|Node\.js|Django|Flask|FastAPI|Spring|Rails|Laravel|Express|Next\.js|Nuxt|Svelte|PyTorch|TensorFlow|Keras|Spark|Hadoop|Kafka|RabbitMQ|Redis|MongoDB|PostgreSQL|MySQL|DynamoDB|Elasticsearch)\b",
            # Cloud / DevOps
            r"\b(AWS|Azure|GCP|Google Cloud|Kubernetes|Docker|Terraform|Ansible|Jenkins|GitLab CI|GitHub Actions|Helm|Istio|Prometheus|Grafana|Datadog|Splunk)\b",
            # Data / AI
            r"\b(Machine Learning|Deep Learning|NLP|Computer Vision|LLM|Generative AI|Data Engineering|ETL|Data Pipeline|Snowflake|BigQuery|Redshift|Airflow|dbt|Databricks)\b",
            # Soft / general
            r"\b(Agile|Scrum|Kanban|CI/CD|Microservices|REST|GraphQL|gRPC|OAuth|JWT|TDD|BDD)\b",
        ]

        # Scan full description for known skills
        for pattern in skill_patterns:
            matches = re.findall(pattern, description, re.IGNORECASE)
            for m in matches:
                skills.add(m.strip())

        # Extract bullet-point items that look like skill/requirement lists
        bullet_lines = re.findall(
            r"(?:^|\n)\s*(?:[-•*]|\d+[.)])\s*(.+?)(?:\n|$)",
            description,
        )
        for line in bullet_lines:
            line = line.strip().rstrip(".;,")
            # Short bullet with technical terms likely a skill
            words = line.split()
            if 1 <= len(words) <= 8 and not line.startswith(("http", "www")):
                # Look for capitalized proper nouns that could be skills
                caps = re.findall(r"\b([A-Z][A-Za-z0-9+#.]{2,})\b", line)
                for c in caps:
                    if c not in skills and not c.startswith(("The ", "We ", "Our ", "You ", "As ")):
                        skills.add(c)

        return sorted(skills)

    # ---- Salary extraction ----

    def _extract_salary(self, description: str) -> str:
        """Extract salary information from description text."""
        # Patterns for Indian salary formats
        patterns = [
            # "15-20 LPA" or "15 LPA - 20 LPA"
            r"(\d{1,3}(?:[,.]\d{1,2})?\s*(?:-|to)\s*\d{1,3}(?:[,.]\d{1,2})?\s*(?:LPA|Lakhs?|Lacs?|Crores?|Cr))",
            # "upto 20 LPA"
            r"(?:upto|up to|up-to)\s*(\d{1,3}(?:[,.]\d{1,2})?\s*(?:LPA|Lakhs?|Lacs?|Crores?|Cr))",
            # "salary: 15 LPA" or "CTC: 15 LPA"
            r"(?:salary|ctc|compensation|package)[:\s]*(\d{1,3}(?:[,.]\d{1,2})?\s*(?:-|to)\s*\d{1,3}(?:[,.]\d{1,2})?\s*(?:LPA|Lakhs?|Lacs?|Crores?|Cr|INR))",
            # "Rs. 15,00,000" or "INR 15,00,000"
            r"(?:Rs\.?|INR|₹)\s*(\d{1,3}(?:,\d{2,3})*(?:\s*(?:-|to)\s*\d{1,3}(?:,\d{2,3})*)?)",
            # "15,00,000 - 20,00,000"
            r"(\d{1,3}(?:,\d{2,3})+\s*(?:-|to)\s*\d{1,3}(?:,\d{2,3})+)",
            # USD salaries for remote roles
            r"(\$\d{1,3}(?:,\d{3})*(?:\s*(?:-|to)\s*\$?\d{1,3}(?:,\d{3})*)?(?:\s*(?:k|K|USD|USD/yr|per year|/year|/yr|annually)))",
        ]

        for pattern in patterns:
            match = re.search(pattern, description, re.IGNORECASE)
            if match:
                return match.group(0).strip()

        return ""

    # ---- Work mode detection ----

    def _detect_work_mode(self, description: str) -> str:
        """Detect work mode from description text."""
        desc_lower = description.lower()

        # Check for explicit mode statements
        remote_strong = [
            "permanently remote", "fully remote", "100% remote",
            "work from anywhere", "remote first", "remote-first",
            "anywhere in india", "work from home",
        ]
        hybrid_strong = [
            "hybrid", "hybrid model", "hybrid mode",
            "2 days", "3 days", "few days", "x days a week",
            "flexible work", "work from office.*home", "home.*office",
        ]
        onsite_strong = [
            "work from office", "on-site", "onsite",
            "in-office", "in office", "office based", "office-based",
            "5 days", "all 5 days", "daily commute",
        ]

        if any(phrase in desc_lower for phrase in remote_strong):
            return "remote"
        if any(phrase in desc_lower for phrase in onsite_strong):
            return "onsite"
        if any(phrase in desc_lower for phrase in hybrid_strong):
            return "hybrid"

        # Looser signals
        remote_count = sum(
            desc_lower.count(w) for w in ["remote", "wfh", "work from home"]
        )
        onsite_count = sum(
            desc_lower.count(w) for w in ["on-site", "onsite", "work from office", "in-office"]
        )

        if remote_count > onsite_count and remote_count > 0:
            return "remote"
        if onsite_count > remote_count and onsite_count > 0:
            return "onsite"

        return ""


def extract_indeed_job(url: str) -> Optional[dict]:
    """Entry point: extract job data from an Indeed URL.

    Returns dict with title, company, location, description, skills,
    salary, work_mode or None on failure.
    """
    scraper = IndeedScraper()
    return scraper.extract(url)
