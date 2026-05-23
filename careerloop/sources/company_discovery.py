"""
CareerLoop Company Discovery Engine — Regional employer universe builder.

Given city + sector + function, discovers what companies exist and
enriches them with ATS/career page detection.

Sources (in priority order):
1. Google Maps — real operating businesses, best India coverage
2. LinkedIn Companies — employee count, industry signals
3. Wellfound / AngelList — funded startups, high hiring velocity
4. Crunchbase — funding stage, founding year
5. Inc42 / YourStory — India startup funding lists
6. StartupIndia — registered Indian startups
7. YC Companies — batch-filtered for India presence

Output: List[CompanyRecord] upserted to the company registry.
"""

import logging
import re
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin, urlparse, quote_plus

import requests

from careerloop.company_registry import CompanyRecord, CompanyRegistry, CompanySourceRecord, _normalize_id

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 15

# MECE Sector taxonomy — matches PRD §18 table
SECTOR_KEYWORDS = {
    "Technology & Software": [
        "software", "saas", "tech", "ai", "ml", "machine learning", "data",
        "cloud", "devops", "cybersecurity", "fintech platform", "edtech platform",
        "developer tools", "api", "platform", "b2b software",
    ],
    "Financial Services": [
        "fintech", "payments", "lending", "banking", "insurance", "insurtech",
        "wealthtech", "neobank", "stock broking", "investment", "crypto",
    ],
    "Consulting & Professional Services": [
        "consulting", "advisory", "audit", "tax", "legal", "staffing",
        "recruitment", "management consulting", "strategy consulting",
    ],
    "Retail & Commerce": [
        "retail", "fashion", "apparel", "clothing", "ecommerce", "d2c",
        "fmcg", "consumer goods", "beauty", "lifestyle", "omnichannel",
        "merchandising", "buying", "luxury",
    ],
    "Manufacturing & Industrial": [
        "manufacturing", "automotive", "electronics", "chemicals", "aerospace",
        "textiles", "packaging", "industrial",
    ],
    "Healthcare & Life Sciences": [
        "healthcare", "hospital", "pharma", "biotech", "healthtech", "diagnostics",
        "medical devices", "clinical",
    ],
    "Media & Creative": [
        "media", "advertising", "marketing agency", "pr", "film", "tv",
        "publishing", "creator", "content",
    ],
    "Education": [
        "edtech", "education", "university", "coaching", "e-learning",
        "upskilling", "training",
    ],
    "Logistics & Mobility": [
        "logistics", "supply chain", "shipping", "last-mile", "mobility",
        "aviation", "freight",
    ],
    "Real Estate & Infra": [
        "real estate", "proptech", "construction", "facility management",
        "infrastructure",
    ],
    "Energy & Utilities": [
        "energy", "renewable", "solar", "ev", "electric vehicle", "oil", "gas",
        "utilities", "cleantech",
    ],
    "Hospitality & Travel": [
        "hotel", "hospitality", "tourism", "travel tech", "food service",
        "restaurant",
    ],
    "Agriculture & Food": [
        "agritech", "agriculture", "food processing", "farming",
    ],
    "Government & Public Sector": [
        "government", "psu", "public sector", "smart city", "govtech",
        "defense", "defence", "ministry", "civic", "municipal",
    ],
    "Nonprofit & Social Impact": [
        "nonprofit", "ngo", "foundation", "social impact", "climate",
        "social enterprise", "philanthropy", "advocacy",
    ],
}

INDIA_CITIES = [
    "bangalore", "bengaluru", "mumbai", "delhi", "hyderabad", "chennai",
    "pune", "kolkata", "noida", "gurgaon", "gurugram", "ahmedabad",
    "jaipur", "surat", "lucknow", "kochi", "indore", "chandigarh",
]


def _infer_sector(description: str) -> str:
    desc = description.lower()
    for sector, keywords in SECTOR_KEYWORDS.items():
        if any(kw in desc for kw in keywords):
            return sector
    return "Technology & Software"  # default for unknown


def _clean_domain(url: str) -> str:
    try:
        parsed = urlparse(url if url.startswith("http") else "https://" + url)
        domain = parsed.netloc or parsed.path
        return re.sub(r"^www\.", "", domain.lower().strip("/"))
    except Exception:
        return ""


@dataclass
class RawCompany:
    """Raw company data before enrichment."""
    name: str
    domain: str = ""
    city: str = ""
    sector: str = ""
    subsector: str = ""
    employee_estimate: int = 0
    source: str = ""
    linkedin_url: str = ""
    description: str = ""


class GoogleMapsDiscovery:
    """
    Discover companies via Google Maps search.
    Uses Google search scraping (no API key) with Maps-specific queries.
    Best for: physical offices, regional businesses, India coverage.
    """

    def __init__(self):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )

    def search(self, city: str, sector: str, function_hint: str = "") -> list[RawCompany]:
        queries = self._build_queries(city, sector, function_hint)
        results = []
        seen = set()

        for query in queries:
            companies = self._search_ddg(query, city, sector)
            for c in companies:
                key = _normalize_id(c.domain or c.name)
                if key not in seen:
                    seen.add(key)
                    results.append(c)
            time.sleep(1.5)

        logger.info(f"[GoogleMaps] {city}/{sector}: {len(results)} companies")
        return results

    def _build_queries(self, city: str, sector: str, function_hint: str) -> list[str]:
        sector_short = sector.split("&")[0].strip().lower()
        queries = [
            f"{sector_short} companies in {city} India",
            f"top {sector_short} startups in {city}",
            f"best {sector_short} firms {city} India",
        ]
        if function_hint:
            queries.append(f"companies hiring {function_hint} in {city} India")
        return queries

    def _search_ddg(self, query: str, city: str, sector: str) -> list[RawCompany]:
        try:
            from ddgs import DDGS
            with DDGS() as ddgs:
                raw = list(ddgs.text(query, max_results=15, region="in-en"))
        except Exception as e:
            logger.debug(f"[GoogleMaps] DDG search failed: {e}")
            return []

        results = []
        for r in raw:
            url = r.get("href", "")
            title = r.get("title", "")
            snippet = r.get("body", "")
            if not url or not title:
                continue

            domain = _clean_domain(url)
            if not domain or any(skip in domain for skip in [
                "naukri", "linkedin", "glassdoor", "indeed", "wikipedia",
                "youtube", "twitter", "facebook", "instagram", "quora",
                "reddit", "medium", "ambitionbox", "crunchbase", "startupindia",
            ]):
                continue

            # Quick India city check
            combined = (title + " " + snippet).lower()
            if city.lower() not in combined and not any(c in combined for c in INDIA_CITIES):
                continue

            results.append(RawCompany(
                name=self._clean_company_name(title),
                domain=domain,
                city=city,
                sector=_infer_sector(snippet + " " + sector),
                description=snippet[:300],
                source="google_maps_ddg",
            ))

        return results

    def _clean_company_name(self, title: str) -> str:
        """Extract company name from a search result title."""
        # Remove common suffixes like "- Jobs", "| Careers", etc.
        name = re.sub(r"\s*[-|–]\s*(jobs|careers|hiring|about|official|india).*$", "", title, flags=re.IGNORECASE)
        return name.strip()[:100]


class WellfoundDiscovery:
    """
    Discover startups from Wellfound (AngelList) company directory.
    Targets funded startups with active hiring — high signal quality.
    """

    BASE = "https://wellfound.com/companies"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; CareerLoopBot/1.0)",
            "Accept": "application/json, text/html",
        })

    def search(self, city: str, sector: str) -> list[RawCompany]:
        # Wellfound location slugs for Indian cities
        city_slug_map = {
            "bangalore": "bangalore", "bengaluru": "bangalore",
            "mumbai": "mumbai", "delhi": "delhi", "hyderabad": "hyderabad",
            "chennai": "chennai", "pune": "pune",
        }
        city_slug = city_slug_map.get(city.lower(), city.lower())
        market_map = {
            "Technology & Software": "saas",
            "Financial Services": "fintech",
            "Retail & Commerce": "e-commerce",
            "Healthcare & Life Sciences": "healthcare",
            "Education": "edtech",
        }
        market = market_map.get(sector, "software")

        url = f"{self.BASE}?locations[]={city_slug}&markets[]={market}"
        results = self._scrape(url, city, sector)
        logger.info(f"[Wellfound] {city}/{sector}: {len(results)} companies")
        return results

    def _scrape(self, url: str, city: str, sector: str) -> list[RawCompany]:
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
                page = browser.new_page()
                page.goto(url, wait_until="networkidle", timeout=25000)
                time.sleep(3)

                try:
                    from bs4 import BeautifulSoup
                    html = page.content()
                    browser.close()
                    return self._parse_html(html, city, sector)
                except Exception:
                    browser.close()
        except Exception as e:
            logger.debug(f"[Wellfound] Playwright failed: {e}. Trying requests...")

        # Fallback: DDG search for Wellfound company listings
        return self._ddg_fallback(city, sector)

    def _parse_html(self, html: str, city: str, sector: str) -> list[RawCompany]:
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            return []

        soup = BeautifulSoup(html, "html.parser")
        results = []

        for card in soup.select('[data-test="StartupResult"], .styles_component__2Lx8j, .startup'):
            name_tag = card.find("h2") or card.find("h3") or card.find("a")
            if not name_tag:
                continue
            name = name_tag.get_text(strip=True)
            if not name:
                continue

            link = card.find("a", href=True)
            domain = ""
            linkedin = ""
            if link:
                href = link["href"]
                if "wellfound.com/company/" in href:
                    slug = href.split("/company/")[-1].split("/")[0].split("?")[0]
                    domain = f"{slug}.com"

            desc_tag = card.find("p") or card.find("[class*='description']")
            desc = desc_tag.get_text(strip=True) if desc_tag else ""

            emp_tag = card.find(string=re.compile(r"\d+[-–]\d+ employees", re.IGNORECASE))
            emp = 0
            if emp_tag:
                m = re.search(r"(\d+)", str(emp_tag))
                if m:
                    emp = int(m.group(1))

            results.append(RawCompany(
                name=name,
                domain=domain,
                city=city,
                sector=_infer_sector(desc + " " + sector),
                employee_estimate=emp,
                description=desc[:300],
                source="wellfound",
            ))

        return results

    def _ddg_fallback(self, city: str, sector: str) -> list[RawCompany]:
        try:
            from ddgs import DDGS
            sector_short = sector.split("&")[0].strip()
            query = f"site:wellfound.com/company {sector_short.lower()} {city.lower()}"
            with DDGS() as ddgs:
                raw = list(ddgs.text(query, max_results=20, region="in-en"))
        except Exception:
            return []

        results = []
        seen = set()
        for r in raw:
            url = r.get("href", "")
            if "wellfound.com/company/" not in url:
                continue
            slug = re.search(r"wellfound\.com/company/([a-z0-9-]+)", url)
            if not slug:
                continue
            name_slug = slug.group(1)
            if name_slug in seen:
                continue
            seen.add(name_slug)
            name = r.get("title", name_slug).split(" - ")[0].strip()
            results.append(RawCompany(
                name=name,
                domain=f"{name_slug}.com",
                city=city,
                sector=sector,
                source="wellfound_ddg",
                linkedin_url=url,
            ))

        return results


class CrunchbaseDiscovery:
    """
    Discover funded companies from Crunchbase via DDG search.
    No API key required — searches DDG for Crunchbase company pages.
    Targets: funded startups, MNCs with India offices.
    """

    def search(self, city: str, sector: str) -> list[RawCompany]:
        sector_short = sector.split("&")[0].strip().lower()
        queries = [
            f"site:crunchbase.com/organization {sector_short} {city.lower()} india",
            f"crunchbase {sector_short} company {city.lower()} india funding",
        ]
        results = []
        seen = set()

        for query in queries:
            try:
                from ddgs import DDGS
                with DDGS() as ddgs:
                    raw = list(ddgs.text(query, max_results=15, region="in-en"))
            except Exception:
                continue

            for r in raw:
                url = r.get("href", "")
                if "crunchbase.com/organization/" not in url:
                    continue
                slug = re.search(r"crunchbase\.com/organization/([a-z0-9-]+)", url)
                if not slug:
                    continue
                name_slug = slug.group(1)
                if name_slug in seen:
                    continue
                seen.add(name_slug)
                title = r.get("title", name_slug)
                name = re.sub(r"\s*[-|–].*$", "", title).strip()
                snippet = r.get("body", "")
                combined = (name + " " + snippet).lower()
                if city.lower() not in combined and not any(c in combined for c in INDIA_CITIES):
                    continue

                results.append(RawCompany(
                    name=name,
                    domain="",
                    city=city,
                    sector=_infer_sector(snippet + " " + sector),
                    description=snippet[:300],
                    source="crunchbase",
                ))
            time.sleep(1)

        logger.info(f"[Crunchbase] {city}/{sector}: {len(results)} companies")
        return results


class Inc42Discovery:
    """
    Discover India startups from Inc42 funding lists and YourStory.
    Targets: India-specific funded startups that may not appear on Western databases.
    """

    def search(self, city: str, sector: str) -> list[RawCompany]:
        sector_short = sector.split("&")[0].strip().lower()
        queries = [
            f"site:inc42.com {sector_short} startup {city.lower()} india",
            f"site:yourstory.com {sector_short} company {city.lower()} india",
            f"startupindia.gov.in {sector_short} {city.lower()} registered startup",
        ]
        results = []
        seen = set()

        for query in queries:
            try:
                from ddgs import DDGS
                with DDGS() as ddgs:
                    raw = list(ddgs.text(query, max_results=10, region="in-en"))
            except Exception:
                continue

            for r in raw:
                title = r.get("title", "")
                snippet = r.get("body", "")
                url = r.get("href", "")
                if not title:
                    continue
                name = re.sub(r"\s*[-|–:]\s*(inc42|yourstory|startupindia|funding|raises|crore).*$",
                              "", title, flags=re.IGNORECASE).strip()
                if not name or len(name) < 3:
                    continue
                key = _normalize_id(name)
                if key in seen:
                    continue
                seen.add(key)

                results.append(RawCompany(
                    name=name,
                    domain="",
                    city=city,
                    sector=_infer_sector(snippet + " " + sector),
                    description=snippet[:300],
                    source="inc42_yourstory",
                ))
            time.sleep(1)

        logger.info(f"[Inc42/YourStory] {city}/{sector}: {len(results)} companies")
        return results


class YCDiscovery:
    """
    Discover Y Combinator alumni with India presence.
    Uses YC company directory filtered by country.
    """

    YC_API = "https://api.ycombinator.com/v0.1/companies?country=India&batch=&page={page}"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "Mozilla/5.0 (compatible; CareerLoopBot/1.0)"

    def search(self, sector: str) -> list[RawCompany]:
        results = []
        page = 1
        while page <= 5:  # max 5 pages
            try:
                resp = self.session.get(self.YC_API.format(page=page), timeout=REQUEST_TIMEOUT)
                if resp.status_code != 200:
                    break
                data = resp.json()
                companies = data.get("companies", [])
                if not companies:
                    break
                for c in companies:
                    desc = c.get("one_liner", "") + " " + c.get("long_description", "")
                    if not _infer_sector(desc) == sector and sector not in desc:
                        continue
                    domain = _clean_domain(c.get("website", ""))
                    results.append(RawCompany(
                        name=c.get("name", ""),
                        domain=domain,
                        city=c.get("city", ""),
                        sector=_infer_sector(desc),
                        employee_estimate=int(c.get("team_size", 0) or 0),
                        description=c.get("one_liner", "")[:300],
                        source="yc",
                        linkedin_url=c.get("linkedin_url", ""),
                    ))
                page += 1
                time.sleep(0.5)
            except Exception as e:
                logger.debug(f"[YC] API error: {e}")
                break

        logger.info(f"[YC] India/{sector}: {len(results)} companies")
        return results


class CompanyEnricher:
    """
    Stage 2: Enrich a raw company with ATS provider + career page URL.
    """

    def __init__(self):
        from careerloop.sources.ats_adapter import ATSAdapter
        from careerloop.sources.company_portal_scraper import CareerPageCrawler
        self.ats = ATSAdapter()
        self.crawler = CareerPageCrawler()

    def enrich(self, raw: RawCompany) -> CompanyRecord:
        """
        Detect ATS and career page for a company.
        Returns an enriched CompanyRecord ready for registry upsert.
        """
        company_id = _normalize_id(raw.domain or raw.name)
        record = CompanyRecord(
            id=company_id,
            name=raw.name,
            domain=raw.domain,
            city=raw.city,
            sector=raw.sector,
            subsector=raw.subsector,
            linkedin_url=raw.linkedin_url,
            employee_estimate=raw.employee_estimate,
            source=raw.source,
            crawl_status="pending",
        )

        if not raw.domain:
            return record

        # Probe ATS
        ats_provider, ats_url = self.ats.detect_ats(raw.domain)
        if ats_provider != "none":
            record.ats_provider = ats_provider
            record.ats_url = ats_url
            record.crawl_status = "active"
            return record

        # No ATS found — look for career page
        career_url = self.crawler.find_career_page(raw.domain)
        if career_url:
            record.career_page_url = career_url
            record.ats_provider = "custom"
            record.crawl_status = "warm"
        else:
            record.ats_provider = "none"
            record.crawl_status = "cold"

        return record


class CompanyDiscoveryEngine:
    """
    Main discovery orchestrator.

    Input:  city + sector + optional function_hint
    Output: ranked list of CompanyRecord upserted to the registry.

    Sources: Google Maps, Wellfound, Crunchbase, Inc42/YourStory, YC.
    Each discovered company is enriched with ATS + career page detection.
    """

    def __init__(self, career_ops_root: str = None):
        self.registry = CompanyRegistry(career_ops_root)
        self.enricher = CompanyEnricher()
        self.google = GoogleMapsDiscovery()
        self.wellfound = WellfoundDiscovery()
        self.crunchbase = CrunchbaseDiscovery()
        self.inc42 = Inc42Discovery()
        self.yc = YCDiscovery()

    def discover(
        self,
        city: str,
        sector: str = "Technology & Software",
        function_hint: str = "",
        max_companies: int = 100,
    ) -> list[CompanyRecord]:
        """
        Discover and enrich companies in a city+sector.
        Returns top-ranked companies upserted to registry.
        """
        logger.info(f"[Discovery] Starting: city={city}, sector={sector}, function={function_hint}")

        # Always search the internet — no early return from DB cache.
        # DB stores previously discovered companies so they get enriched/updated,
        # but it never replaces a live search.
        raw_companies: list[RawCompany] = []

        raw_companies += self.google.search(city, sector, function_hint)
        raw_companies += self.wellfound.search(city, sector)
        raw_companies += self.crunchbase.search(city, sector)
        raw_companies += self.inc42.search(city, sector)
        if sector in ("Technology & Software", "Financial Services"):
            raw_companies += self.yc.search(sector)

        # Deduplicate by domain/name
        deduped = self._dedup(raw_companies)
        logger.info(f"[Discovery] {len(raw_companies)} raw → {len(deduped)} deduped")

        # Enrich and store top N (enrichment probes ATS/career pages — rate-limited)
        records = []
        for i, raw in enumerate(deduped[:max_companies]):
            try:
                record = self.enricher.enrich(raw)
                self.registry.upsert(record)
                if record.ats_url or record.career_page_url:
                    self.registry.upsert_source(CompanySourceRecord(
                        company_id=record.id,
                        source_type=record.ats_provider,
                        crawl_url=record.ats_url or record.career_page_url,
                        is_active=True,
                    ))
                records.append(record)
                if (i + 1) % 10 == 0:
                    logger.info(f"[Discovery] Enriched {i+1}/{min(len(deduped), max_companies)}")
                time.sleep(0.5)
            except Exception as e:
                logger.warning(f"[Discovery] Enrichment failed for {raw.name}: {e}")

        ranked = self._rank(records)
        logger.info(f"[Discovery] Done: {len(ranked)} companies enriched and stored")
        return ranked

    def _dedup(self, companies: list[RawCompany]) -> list[RawCompany]:
        seen = {}
        for c in companies:
            key = _normalize_id(c.domain or c.name)
            if key not in seen:
                seen[key] = c
            else:
                # Merge: prefer record with more data
                existing = seen[key]
                if not existing.domain and c.domain:
                    existing.domain = c.domain
                if existing.employee_estimate == 0 and c.employee_estimate > 0:
                    existing.employee_estimate = c.employee_estimate
        return list(seen.values())

    def _rank(self, companies: list[CompanyRecord]) -> list[CompanyRecord]:
        """
        Rank companies by hiring signal strength.
        Active ATS > warm career page > cold.
        """
        status_score = {"active": 3, "warm": 2, "pending": 1, "cold": 0, "dead": -1}
        ats_score = {"greenhouse": 3, "lever": 3, "ashby": 3, "workday": 2, "custom": 1, "none": 0, "unknown": 0}

        def score(c: CompanyRecord) -> int:
            return (
                status_score.get(c.crawl_status, 0) * 10
                + ats_score.get(c.ats_provider, 0) * 5
                + min(c.employee_estimate // 100, 10)
                + (5 if c.last_job_count and c.last_job_count > 0 else 0)
            )

        return sorted(companies, key=score, reverse=True)
