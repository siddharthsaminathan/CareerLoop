"""
CareerLoop ATS Extended Adapters — 10 additional ATS platforms.

Coverage added:
  P0: SmartRecruiters, SAP SuccessFactors, Oracle Taleo, iCIMS, TalentRecruit, Darwinbox
  P1: Workable, Teamtailor
  P2: Recruitee, BambooHR

Architecture: all adapters follow same pattern as ats_adapter.py —
  _slug_from_url() → fetch() → list[ATSJob]

Each adapter tries the cheapest extraction first (public REST) then degrades:
  REST JSON → XHR intercept → Playwright DOM
"""

import json
import logging
import re
import time
from typing import Optional
from urllib.parse import urlparse, urlencode

import requests

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 15

# Hard India cities/identifiers — a bare match here is sufficient.
INDIA_CITIES = [
    "india", "bangalore", "bengaluru", "mumbai", "delhi", "hyderabad",
    "chennai", "pune", "kolkata", "noida", "gurgaon", "gurugram",
    "ahmedabad", "jaipur", "surat", "lucknow", "kanpur", "nagpur",
    "coimbatore", "kochi", "thiruvananthapuram", "vizag", "visakhapatnam",
]
# Work modes only count as India when an India city/"india" is also present.
INDIA_WORK_MODES = ["remote", "hybrid"]

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "en-US,en;q=0.9",
}


def _is_india(location: str) -> bool:
    """Return True if location string suggests India.

    Bare 'remote'/'hybrid' do NOT pass — they only count when an India city
    (or 'india') is also present in the string.
    """
    if not location:
        return False  # empty location — cannot assume India
    loc = location.lower()
    if any(city in loc for city in INDIA_CITIES):
        return True
    if any(mode in loc for mode in INDIA_WORK_MODES):
        return any(city in loc for city in INDIA_CITIES) or "india" in loc
    return False


def _strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html or "")
    text = re.sub(r"&[a-z]+;", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _make_job(title, company_id, company_name, source, url, location="", jd="",
              job_id="", posted_at=None):
    """Build a dict compatible with ATSJob.to_dict() output."""
    from datetime import datetime, timezone
    return {
        "title": title,
        "company": company_name,
        "company_id": company_id,
        "source": source,
        "source_url": url,
        "url": url,
        "apply_url": url,
        "location": location,
        "description": jd,
        "role_summary": "",
        "responsibilities": "",
        "requirements": "",
        "benefits": "",
        "jd_confidence": 0.9,
        "posted_at": posted_at,
        "job_id_ats": job_id,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "from_company_portal": True,
        "_source_type": source,
    }


# ── P0: SmartRecruiters ───────────────────────────────────────────────────────

class SmartRecruitersAdapter:
    """
    SmartRecruiters — public REST API, no auth required.
    API: https://api.smartrecruiters.com/v1/companies/{company}/postings?limit=100
    Fingerprints: jobs.smartrecruiters.com/{company}, smartrecruiters.com/jobs/
    """

    def _slug_from_url(self, url: str) -> Optional[str]:
        # jobs.smartrecruiters.com/{slug}
        m = re.search(r"smartrecruiters\.com/([a-zA-Z0-9_.-]+)", url)
        if m:
            return m.group(1)
        # api.smartrecruiters.com/v1/companies/{slug}
        m2 = re.search(r"/companies/([a-zA-Z0-9_.-]+)", url)
        if m2:
            return m2.group(1)
        return None

    def fetch(self, company_id: str, company_name: str, ats_url: str) -> list[dict]:
        slug = self._slug_from_url(ats_url) or company_id
        if not slug:
            return []

        offset = 0
        all_jobs = []
        while True:
            api_url = (
                f"https://api.smartrecruiters.com/v1/companies/{slug}/postings"
                f"?limit=100&offset={offset}"
            )
            try:
                resp = requests.get(api_url, headers=_HEADERS, timeout=REQUEST_TIMEOUT)
                if resp.status_code == 404:
                    logger.debug(f"[SmartRecruiters] 404 for {slug}")
                    break
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.debug(f"[SmartRecruiters] API error for {slug}: {e}")
                break

            postings = data.get("content", [])
            if not postings:
                break

            for p in postings:
                loc = (p.get("location") or {})
                loc_str = ", ".join(filter(None, [
                    loc.get("city"), loc.get("region"), loc.get("country")
                ]))
                if not _is_india(loc_str):
                    continue
                job_url = f"https://jobs.smartrecruiters.com/{slug}/{p.get('id', '')}"
                all_jobs.append(_make_job(
                    title=p.get("name", ""),
                    company_id=company_id,
                    company_name=company_name,
                    source="smartrecruiters",
                    url=job_url,
                    location=loc_str,
                    jd=_strip_html(p.get("jobAd", {}).get("sections", {}).get("jobDescription", {}).get("text", "")),
                    job_id=p.get("id", ""),
                ))

            total = data.get("totalFound", 0)
            offset += len(postings)
            if offset >= total or len(postings) < 100:
                break

        logger.info(f"[SmartRecruiters] {company_name}: {len(all_jobs)} India jobs")
        return all_jobs


# ── P0: SAP SuccessFactors ────────────────────────────────────────────────────

class SuccessFactorsAdapter:
    """
    SAP SuccessFactors — Playwright + XHR intercept.
    Fingerprints: career5.successfactors.com, career.sap.com, jobs2web.com
    Many variants of URL format — detect company_id from URL then call JSON endpoint.
    """

    def _parse_url(self, url: str) -> tuple[str, str]:
        """Returns (host, company_id)."""
        m = re.search(r"company=([A-Za-z0-9_~-]+)", url)
        company_param = m.group(1) if m else ""
        parsed = urlparse(url)
        return parsed.netloc, company_param

    def fetch(self, company_id: str, company_name: str, ats_url: str) -> list[dict]:
        host, sf_company = self._parse_url(ats_url)
        if not sf_company:
            sf_company = company_id

        # Try OData API first — some SuccessFactors instances expose it
        jobs = self._try_odata(host, sf_company, company_id, company_name)
        if jobs:
            return jobs

        # Playwright fallback
        return self._try_playwright(ats_url, company_id, company_name)

    def _try_odata(self, host: str, sf_company: str, company_id: str, company_name: str) -> list[dict]:
        candidates = [
            f"https://{host}/odata/v2/Requisition/RequisitionDetail?"
            f"$filter=companyId eq '{sf_company}'&$format=json&$top=100",
            f"https://{host}/career?career_ns=job_listing&company={sf_company}&format=json",
        ]
        for url in candidates:
            try:
                resp = requests.get(url, headers=_HEADERS, timeout=REQUEST_TIMEOUT)
                if not resp.ok:
                    continue
                data = resp.json()
                results = data.get("d", {}).get("results", []) or data.get("results", [])
                if not results:
                    continue
                jobs = []
                for r in results:
                    loc = str(r.get("primaryLocation", "") or r.get("location", ""))
                    if not _is_india(loc):
                        continue
                    title = r.get("jobTitle", "") or r.get("name", "")
                    job_url = r.get("jobReqUrl", "") or r.get("applyUrl", "") or ats_url
                    jobs.append(_make_job(
                        title=title, company_id=company_id, company_name=company_name,
                        source="successfactors", url=job_url, location=loc,
                        job_id=str(r.get("jobReqId", "") or r.get("id", "")),
                    ))
                if jobs:
                    logger.info(f"[SuccessFactors] {company_name}: {len(jobs)} India jobs (OData)")
                    return jobs
            except Exception as e:
                logger.debug(f"[SuccessFactors] OData failed: {e}")
        return []

    def _try_playwright(self, url: str, company_id: str, company_name: str) -> list[dict]:
        jobs = []
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
                page = browser.new_page()
                intercepted = []

                def _on_response(response):
                    try:
                        if "odata" in response.url or "jobsearch" in response.url:
                            if response.status == 200:
                                intercepted.append(response.json())
                    except Exception:
                        pass

                page.on("response", _on_response)
                page.goto(url, timeout=25000, wait_until="networkidle")
                page.wait_for_timeout(3000)

                for data in intercepted:
                    results = data.get("d", {}).get("results", []) or data.get("results", [])
                    for r in results:
                        loc = str(r.get("primaryLocation", "") or r.get("location", ""))
                        if not _is_india(loc):
                            continue
                        title = r.get("jobTitle", "") or r.get("name", "")
                        job_url = r.get("jobReqUrl", "") or url
                        jobs.append(_make_job(
                            title=title, company_id=company_id, company_name=company_name,
                            source="successfactors", url=job_url, location=loc,
                        ))

                if not jobs:
                    # DOM fallback
                    html = page.content()
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(html, "html.parser")
                    for item in soup.select(".jobTitle, [data-job-title], .job-item"):
                        title_el = item.select_one("a, h2, h3, .title")
                        if title_el:
                            title = title_el.get_text(strip=True)
                            href = title_el.get("href", url)
                            jobs.append(_make_job(
                                title=title, company_id=company_id, company_name=company_name,
                                source="successfactors", url=href or url,
                            ))

                browser.close()
        except Exception as e:
            logger.debug(f"[SuccessFactors] Playwright failed: {e}")

        logger.info(f"[SuccessFactors] {company_name}: {len(jobs)} jobs (Playwright)")
        return jobs


# ── P0: Oracle Taleo ──────────────────────────────────────────────────────────

class TaleoAdapter:
    """
    Oracle Taleo — old enterprise ATS.
    Fingerprints: {slug}.taleo.net, .taleo.net/careersection/
    Tries JSON endpoint first, then DOM extraction.
    """

    def _parse_url(self, url: str) -> tuple[str, str, str]:
        """Returns (base, slug, section)."""
        m = re.search(r"([a-z0-9_-]+)\.taleo\.net/careersection/([^/]+)/", url, re.IGNORECASE)
        if m:
            return f"https://{m.group(1)}.taleo.net", m.group(1), m.group(2)
        m2 = re.search(r"([a-z0-9_-]+)\.taleo\.net", url, re.IGNORECASE)
        if m2:
            return f"https://{m2.group(1)}.taleo.net", m2.group(1), "External"
        return "", "", "External"

    def fetch(self, company_id: str, company_name: str, ats_url: str) -> list[dict]:
        base, slug, section = self._parse_url(ats_url)
        if not base:
            base = ats_url.rstrip("/")
            slug = company_id
            section = "External"

        jobs = self._try_json_api(base, slug, section, company_id, company_name)
        if jobs:
            return jobs
        return self._try_playwright(ats_url, company_id, company_name)

    def _try_json_api(self, base: str, slug: str, section: str,
                      company_id: str, company_name: str) -> list[dict]:
        # Taleo has a hidden JSON endpoint on many instances
        candidates = [
            f"{base}/careersection/{section}/jobsearch.json?multilineEnabled=false&numRows=100",
            f"{base}/careersection/External/jobsearch.json?multilineEnabled=false&numRows=100",
        ]
        for url in candidates:
            try:
                resp = requests.get(url, headers=_HEADERS, timeout=REQUEST_TIMEOUT)
                if not resp.ok:
                    continue
                data = resp.json()
                postings = data.get("requisitionList", [])
                if not postings:
                    continue
                jobs = []
                for p in postings:
                    loc = p.get("locationId", "") or p.get("location", "")
                    if loc and not _is_india(loc):
                        continue
                    title = p.get("jobTitle", "") or p.get("title", "")
                    job_id = str(p.get("contestNo", "") or p.get("id", ""))
                    job_url = f"{base}/careersection/{section}/jobdetail.ftl?lang=en&job={job_id}"
                    jobs.append(_make_job(
                        title=title, company_id=company_id, company_name=company_name,
                        source="taleo", url=job_url, location=str(loc), job_id=job_id,
                    ))
                logger.info(f"[Taleo] {company_name}: {len(jobs)} jobs (JSON)")
                return jobs
            except Exception as e:
                logger.debug(f"[Taleo] JSON API failed: {e}")
        return []

    def _try_playwright(self, url: str, company_id: str, company_name: str) -> list[dict]:
        jobs = []
        try:
            from playwright.sync_api import sync_playwright
            from bs4 import BeautifulSoup
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
                page = browser.new_page()
                page.goto(url, timeout=25000, wait_until="domcontentloaded")
                page.wait_for_timeout(3000)
                html = page.content()
                browser.close()

            soup = BeautifulSoup(html, "html.parser")
            for row in soup.select("tr.data1, tr.data2, .requisitionListItem, [class*='job-row']"):
                cells = row.find_all("td")
                if not cells:
                    continue
                title_el = row.select_one("a, .jobTitle, td:first-child")
                title = title_el.get_text(strip=True) if title_el else ""
                href = title_el.get("href", "") if title_el else ""
                if title:
                    jobs.append(_make_job(
                        title=title, company_id=company_id, company_name=company_name,
                        source="taleo", url=href or url,
                    ))
        except Exception as e:
            logger.debug(f"[Taleo] Playwright failed: {e}")

        logger.info(f"[Taleo] {company_name}: {len(jobs)} jobs (DOM)")
        return jobs


# ── P0: iCIMS ─────────────────────────────────────────────────────────────────

class ICIMSAdapter:
    """
    iCIMS — JSON endpoint + DOM fallback.
    Fingerprints: {slug}.icims.com/jobs/, careers.{company}.com/jobs/{id}
    """

    def _slug_from_url(self, url: str) -> Optional[str]:
        m = re.search(r"([a-z0-9_-]+)\.icims\.com", url, re.IGNORECASE)
        return m.group(1) if m else None

    def _customer_id(self, url: str) -> Optional[str]:
        m = re.search(r"/jobs/(\d+)/", url)
        return m.group(1) if m else None

    def fetch(self, company_id: str, company_name: str, ats_url: str) -> list[dict]:
        slug = self._slug_from_url(ats_url) or company_id

        # Try the icims search JSON endpoint
        jobs = self._try_search_json(slug, company_id, company_name)
        if jobs:
            return jobs

        # Playwright + DOM fallback
        return self._try_playwright(ats_url, company_id, company_name)

    def _try_search_json(self, slug: str, company_id: str, company_name: str) -> list[dict]:
        candidates = [
            f"https://{slug}.icims.com/icims2/servlet/icims2?module=AppInert&action=jobs&iis=search&searchCategory=0&searchLocation=0&searchKeyword=&format=json",
            f"https://{slug}.icims.com/jobs/search?pr=0&searchCategory=0&searchLocation=0&in_iframe=1",
        ]
        for url in candidates:
            try:
                resp = requests.get(url, headers=_HEADERS, timeout=REQUEST_TIMEOUT)
                if not resp.ok:
                    continue
                data = resp.json()
                items = data.get("searchResults", {}).get("items", [])
                if not items:
                    continue
                jobs = []
                for item in items:
                    loc = item.get("formattedLocation", "") or str(item.get("location", ""))
                    if not _is_india(loc):
                        continue
                    title = item.get("title", "")
                    job_url = item.get("url", "") or f"https://{slug}.icims.com/jobs/{item.get('id', '')}/job"
                    jobs.append(_make_job(
                        title=title, company_id=company_id, company_name=company_name,
                        source="icims", url=job_url, location=loc,
                        job_id=str(item.get("id", "")),
                    ))
                logger.info(f"[iCIMS] {company_name}: {len(jobs)} India jobs")
                return jobs
            except Exception as e:
                logger.debug(f"[iCIMS] JSON failed for {slug}: {e}")
        return []

    def _try_playwright(self, url: str, company_id: str, company_name: str) -> list[dict]:
        jobs = []
        try:
            from playwright.sync_api import sync_playwright
            from bs4 import BeautifulSoup
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
                page = browser.new_page()
                page.goto(url, timeout=25000, wait_until="networkidle")
                page.wait_for_timeout(2000)
                html = page.content()
                browser.close()

            soup = BeautifulSoup(html, "html.parser")
            for item in soup.select(".iCIMS_JobsTable tr, .job-listing, [class*='job-title']"):
                title_el = item.select_one("a, .title, h3")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                href = title_el.get("href", url)
                if title:
                    jobs.append(_make_job(
                        title=title, company_id=company_id, company_name=company_name,
                        source="icims", url=href or url,
                    ))
        except Exception as e:
            logger.debug(f"[iCIMS] Playwright failed: {e}")

        logger.info(f"[iCIMS] {company_name}: {len(jobs)} jobs (DOM)")
        return jobs


# ── P0: TalentRecruit (India) ─────────────────────────────────────────────────

class TalentRecruitAdapter:
    """
    TalentRecruit — India ATS used by Grant Thornton, mid-market firms.
    Fingerprints: talentrecruit.com, gtprod.talentrecruit.com, /career-page
    API: https://gtprod.talentrecruit.com/career-page/api/jobs?company={company_id}
    """

    def _company_id_from_url(self, url: str) -> Optional[str]:
        # https://gtprod.talentrecruit.com/career-page?company_id=XXXX
        m = re.search(r"company[_-]?id=([A-Za-z0-9_-]+)", url, re.IGNORECASE)
        if m:
            return m.group(1)
        # https://{company}.talentrecruit.com/career-page
        m2 = re.search(r"([a-z0-9_-]+)\.talentrecruit\.com", url, re.IGNORECASE)
        if m2 and m2.group(1) not in ("gtprod", "www", "api"):
            return m2.group(1)
        return None

    def fetch(self, company_id: str, company_name: str, ats_url: str) -> list[dict]:
        tr_id = self._company_id_from_url(ats_url) or company_id

        # Try public API
        jobs = self._try_api(tr_id, company_id, company_name)
        if jobs:
            return jobs

        # XHR intercept via Playwright
        return self._try_playwright(ats_url, company_id, company_name)

    def _try_api(self, tr_id: str, company_id: str, company_name: str) -> list[dict]:
        candidates = [
            f"https://gtprod.talentrecruit.com/career-page/api/jobs?company_id={tr_id}&page=1&limit=100",
            f"https://gtprod.talentrecruit.com/career-page/api/v2/jobs?company_id={tr_id}",
            f"https://{tr_id}.talentrecruit.com/career-page/api/jobs?page=1&limit=100",
        ]
        for url in candidates:
            try:
                resp = requests.get(url, headers=_HEADERS, timeout=REQUEST_TIMEOUT)
                if not resp.ok:
                    continue
                data = resp.json()
                items = (data.get("data") or data.get("jobs") or
                         data.get("result") or (data if isinstance(data, list) else []))
                if not items:
                    continue
                jobs = []
                for item in items:
                    loc = item.get("location", "") or item.get("job_location", "")
                    if isinstance(loc, list):
                        loc = ", ".join(loc)
                    if loc and not _is_india(loc):
                        continue
                    title = item.get("job_title", "") or item.get("title", "")
                    job_url = (item.get("apply_url") or item.get("job_url") or
                               f"https://gtprod.talentrecruit.com/career-page?company_id={tr_id}&job_id={item.get('id', '')}")
                    jobs.append(_make_job(
                        title=title, company_id=company_id, company_name=company_name,
                        source="talentrecruit", url=job_url, location=str(loc),
                        job_id=str(item.get("id", "") or item.get("job_id", "")),
                    ))
                logger.info(f"[TalentRecruit] {company_name}: {len(jobs)} jobs (API)")
                return jobs
            except Exception as e:
                logger.debug(f"[TalentRecruit] API failed: {e}")
        return []

    def _try_playwright(self, url: str, company_id: str, company_name: str) -> list[dict]:
        jobs = []
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
                page = browser.new_page()
                intercepted = []

                def _on_response(response):
                    try:
                        if "api" in response.url and "job" in response.url and response.status == 200:
                            try:
                                intercepted.append((response.url, response.json()))
                            except Exception:
                                pass
                    except Exception:
                        pass

                page.on("response", _on_response)
                page.goto(url, timeout=25000, wait_until="networkidle")
                page.wait_for_timeout(3000)
                browser.close()

                for api_url, data in intercepted:
                    items = (data.get("data") or data.get("jobs") or
                             (data if isinstance(data, list) else []))
                    for item in items:
                        title = item.get("job_title") or item.get("title", "")
                        loc = item.get("location") or item.get("job_location", "")
                        if isinstance(loc, list):
                            loc = ", ".join(loc)
                        if loc and not _is_india(loc):
                            continue
                        job_url = item.get("apply_url") or item.get("job_url") or api_url
                        if title:
                            jobs.append(_make_job(
                                title=title, company_id=company_id, company_name=company_name,
                                source="talentrecruit", url=job_url, location=str(loc),
                            ))
        except Exception as e:
            logger.debug(f"[TalentRecruit] Playwright failed: {e}")

        logger.info(f"[TalentRecruit] {company_name}: {len(jobs)} jobs (XHR)")
        return jobs


# ── P0/P1: Darwinbox ──────────────────────────────────────────────────────────

class DarwinboxAdapter:
    """
    Darwinbox — India enterprise HR/ATS. SPA React app.
    Fingerprints: {company}.darwinbox.com, darwinbox.com/careers
    """

    def _slug_from_url(self, url: str) -> Optional[str]:
        m = re.search(r"([a-z0-9_-]+)\.darwinbox\.com", url, re.IGNORECASE)
        return m.group(1) if m else None

    def fetch(self, company_id: str, company_name: str, ats_url: str) -> list[dict]:
        slug = self._slug_from_url(ats_url) or company_id
        return self._try_playwright(ats_url, slug, company_id, company_name)

    def _try_playwright(self, url: str, slug: str, company_id: str, company_name: str) -> list[dict]:
        jobs = []
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
                page = browser.new_page()
                intercepted = []

                def _on_response(response):
                    try:
                        resp_url = response.url
                        if (("careers" in resp_url or "vacancy" in resp_url or "job" in resp_url)
                                and response.status == 200
                                and "application/json" in response.headers.get("content-type", "")):
                            try:
                                intercepted.append(response.json())
                            except Exception:
                                pass
                    except Exception:
                        pass

                page.on("response", _on_response)
                career_url = url if "darwinbox" in url else f"https://{slug}.darwinbox.com/ms/candidate/careers"
                page.goto(career_url, timeout=25000, wait_until="networkidle")
                page.wait_for_timeout(4000)

                for data in intercepted:
                    items = (data.get("data") or data.get("jobs") or data.get("vacancies") or
                             (data if isinstance(data, list) else []))
                    for item in items:
                        title = (item.get("designation") or item.get("job_title") or
                                 item.get("title") or item.get("name", ""))
                        loc = str(item.get("location") or item.get("city") or "")
                        if loc and not _is_india(loc):
                            continue
                        job_id = str(item.get("id") or item.get("job_id") or item.get("vacancy_id", ""))
                        job_url = item.get("apply_url") or item.get("url") or career_url
                        if title:
                            jobs.append(_make_job(
                                title=title, company_id=company_id, company_name=company_name,
                                source="darwinbox", url=job_url, location=loc, job_id=job_id,
                            ))

                if not jobs:
                    # DOM fallback
                    from bs4 import BeautifulSoup
                    html = page.content()
                    soup = BeautifulSoup(html, "html.parser")
                    for card in soup.select("[class*='job-card'], [class*='vacancy'], [class*='position']"):
                        title_el = card.select_one("h2, h3, .title, [class*='job-title']")
                        if title_el:
                            title = title_el.get_text(strip=True)
                            href = title_el.get("href") or card.select_one("a", href=True)
                            jobs.append(_make_job(
                                title=title, company_id=company_id, company_name=company_name,
                                source="darwinbox", url=str(href) if href else career_url,
                            ))

                browser.close()
        except Exception as e:
            logger.debug(f"[Darwinbox] Playwright failed for {company_name}: {e}")

        logger.info(f"[Darwinbox] {company_name}: {len(jobs)} jobs")
        return jobs


# ── P1: Workable ──────────────────────────────────────────────────────────────

class WorkableAdapter:
    """
    Workable — clean public JSON API.
    API: https://apply.workable.com/api/v1/widget/accounts/{slug}/jobs
    Fingerprints: jobs.workable.com/{slug}, apply.workable.com/{slug}
    """

    def _slug_from_url(self, url: str) -> Optional[str]:
        m = re.search(r"workable\.com/([a-zA-Z0-9_-]+)", url)
        return m.group(1) if m and m.group(1) not in ("api", "jobs", "apply", "j") else None

    def fetch(self, company_id: str, company_name: str, ats_url: str) -> list[dict]:
        slug = self._slug_from_url(ats_url) or company_id
        if not slug:
            return []

        api_url = f"https://apply.workable.com/api/v1/widget/accounts/{slug}/jobs"
        try:
            resp = requests.post(
                api_url,
                headers={**_HEADERS, "Content-Type": "application/json"},
                json={"query": "", "location": [], "department": [], "worktype": [], "remote": []},
                timeout=REQUEST_TIMEOUT,
            )
            if not resp.ok:
                # Try GET variant
                resp = requests.get(api_url, headers=_HEADERS, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.debug(f"[Workable] API failed for {slug}: {e}")
            return []

        results = data.get("results", [])
        jobs = []
        for r in results:
            loc_parts = [r.get("city", ""), r.get("state", ""), r.get("country", "")]
            loc = ", ".join(p for p in loc_parts if p)
            if not _is_india(loc):
                continue
            shortcode = r.get("shortcode", "")
            job_url = f"https://apply.workable.com/{slug}/j/{shortcode}"
            jobs.append(_make_job(
                title=r.get("title", ""),
                company_id=company_id,
                company_name=company_name,
                source="workable",
                url=job_url,
                location=loc,
                job_id=shortcode,
            ))

        logger.info(f"[Workable] {company_name}: {len(jobs)} India jobs")
        return jobs


# ── P1: Teamtailor ────────────────────────────────────────────────────────────

class TeamtailorAdapter:
    """
    Teamtailor — clean JSON API with API version header.
    API: https://{slug}.teamtailor.com/api/v1/jobs
    Fingerprints: teamtailor.com, {company}.teamtailor.com
    """

    def _slug_from_url(self, url: str) -> Optional[str]:
        m = re.search(r"([a-z0-9_-]+)\.teamtailor\.com", url, re.IGNORECASE)
        return m.group(1) if m else None

    def fetch(self, company_id: str, company_name: str, ats_url: str) -> list[dict]:
        slug = self._slug_from_url(ats_url) or company_id
        if not slug:
            return []

        api_url = f"https://{slug}.teamtailor.com/api/v1/jobs"
        headers = {**_HEADERS, "X-Api-Version": "20210218", "Accept": "application/vnd.api+json"}
        page_num = 1
        all_jobs = []

        while True:
            try:
                resp = requests.get(
                    f"{api_url}?page[size]=100&page[number]={page_num}",
                    headers=headers,
                    timeout=REQUEST_TIMEOUT,
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.debug(f"[Teamtailor] API failed for {slug}: {e}")
                break

            records = data.get("data", [])
            if not records:
                break

            for r in records:
                attrs = r.get("attributes", {})
                links = r.get("links", {})
                loc = attrs.get("city", "") or ""
                if loc and not _is_india(loc):
                    continue
                title = attrs.get("title", "")
                job_url = links.get("careersite-job-url", "") or f"https://{slug}.teamtailor.com/jobs/{r.get('id', '')}"
                all_jobs.append(_make_job(
                    title=title, company_id=company_id, company_name=company_name,
                    source="teamtailor", url=job_url, location=loc,
                    job_id=str(r.get("id", "")),
                ))

            meta = data.get("meta", {})
            if page_num >= meta.get("page-count", 1):
                break
            page_num += 1

        logger.info(f"[Teamtailor] {company_name}: {len(all_jobs)} jobs")
        return all_jobs


# ── P2: Recruitee ─────────────────────────────────────────────────────────────

class RecruiteeAdapter:
    """
    Recruitee — public JSON API.
    API: https://{slug}.recruitee.com/api/offers
    Fingerprints: {slug}.recruitee.com
    """

    def _slug_from_url(self, url: str) -> Optional[str]:
        m = re.search(r"([a-z0-9_-]+)\.recruitee\.com", url, re.IGNORECASE)
        return m.group(1) if m else None

    def fetch(self, company_id: str, company_name: str, ats_url: str) -> list[dict]:
        slug = self._slug_from_url(ats_url) or company_id
        if not slug:
            return []

        api_url = f"https://{slug}.recruitee.com/api/offers"
        try:
            resp = requests.get(api_url, headers=_HEADERS, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.debug(f"[Recruitee] API failed for {slug}: {e}")
            return []

        offers = data.get("offers", [])
        jobs = []
        for o in offers:
            loc = o.get("city", "") or o.get("location", "")
            if not _is_india(loc):
                continue
            job_url = o.get("careers_url", "") or f"https://{slug}.recruitee.com/o/{o.get('slug', '')}"
            jobs.append(_make_job(
                title=o.get("title", ""),
                company_id=company_id, company_name=company_name,
                source="recruitee", url=job_url, location=loc,
                jd=_strip_html(o.get("description", "")),
                job_id=str(o.get("id", "")),
            ))

        logger.info(f"[Recruitee] {company_name}: {len(jobs)} India jobs")
        return jobs


# ── P2: BambooHR ──────────────────────────────────────────────────────────────

class BambooHRAdapter:
    """
    BambooHR — public JSON list endpoint.
    API: https://{slug}.bamboohr.com/careers/list
    Fingerprints: {slug}.bamboohr.com/careers
    """

    def _slug_from_url(self, url: str) -> Optional[str]:
        m = re.search(r"([a-z0-9_-]+)\.bamboohr\.com", url, re.IGNORECASE)
        return m.group(1) if m else None

    def fetch(self, company_id: str, company_name: str, ats_url: str) -> list[dict]:
        slug = self._slug_from_url(ats_url) or company_id
        if not slug:
            return []

        api_url = f"https://{slug}.bamboohr.com/careers/list"
        try:
            resp = requests.get(
                api_url,
                headers={**_HEADERS, "Accept": "application/json"},
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.debug(f"[BambooHR] API failed for {slug}: {e}")
            return []

        items = data.get("result", [])
        jobs = []
        for item in items:
            loc_parts = item.get("location", {})
            if isinstance(loc_parts, dict):
                loc = ", ".join(filter(None, [
                    loc_parts.get("city", ""), loc_parts.get("state", ""),
                    loc_parts.get("country", ""),
                ]))
            else:
                loc = str(loc_parts)
            if not _is_india(loc):
                continue
            job_id = str(item.get("id", ""))
            job_url = f"https://{slug}.bamboohr.com/careers/{job_id}"
            title_obj = item.get("title", {})
            title = title_obj.get("label", "") if isinstance(title_obj, dict) else str(title_obj)
            jobs.append(_make_job(
                title=title, company_id=company_id, company_name=company_name,
                source="bamboohr", url=job_url, location=loc, job_id=job_id,
            ))

        logger.info(f"[BambooHR] {company_name}: {len(jobs)} India jobs")
        return jobs


# ── ATS Fingerprint Engine ────────────────────────────────────────────────────

# URL/domain-level fingerprints — cheapest check (no HTTP call)
URL_FINGERPRINTS: dict[str, list[str]] = {
    "greenhouse": ["greenhouse.io", "grnh.se", "boards.greenhouse.io"],
    "lever": ["jobs.lever.co", "lever.co/", "api.lever.co"],
    "ashby": ["ashbyhq.com", "app.ashbyhq.com"],
    "workday": ["myworkdayjobs.com", ".wd1.", ".wd3.", ".wd5."],
    "smartrecruiters": ["jobs.smartrecruiters.com", "smartrecruiters.com/jobs", "api.smartrecruiters.com"],
    "successfactors": ["successfactors.com", "career5.successfactors", "jobs2web.com", "sap.com/careers"],
    "taleo": ["taleo.net", ".taleo.net/careersection"],
    "icims": [".icims.com/jobs", "icims.com/careers", ".icims.com"],
    "talentrecruit": ["talentrecruit.com", "gtprod.talentrecruit"],
    "darwinbox": [".darwinbox.com"],
    "workable": ["jobs.workable.com", "apply.workable.com", "workable.com/j/"],
    "teamtailor": [".teamtailor.com", "teamtailor.com/jobs"],
    "recruitee": [".recruitee.com"],
    "bamboohr": [".bamboohr.com/careers", "bamboohr.com/careers"],
    "spireai": ["app.spireai.com", "career.spire.ai"],
}

# HTML/script-level fingerprints for when we have page content
HTML_FINGERPRINTS: dict[str, list[str]] = {
    "greenhouse": ["greenhouse.io/embed", "window.Grnhse", "grnhse_app"],
    "lever": ["jobs.lever.co", "lever-job-listing"],
    "ashby": ["ashbyhq.com", "ashby-application-form"],
    "workday": ["workday.com", "wday-field-wrapper", "WDAY.HCM"],
    "smartrecruiters": ["smartrecruiters.com", "sr-job-ad"],
    "successfactors": ["successfactors.com", "sapcdn.com", "jobs2web"],
    "taleo": ["taleo.net", "tbe.taleo.net"],
    "icims": ["icims.com", "iCIMS_JobsTable"],
    "talentrecruit": ["talentrecruit.com", "career-page", "tr-career"],
    "darwinbox": ["darwinbox.com", "darwin-careers"],
    "workable": ["workable.com", "__NEXT_DATA__", "workable-job"],
    "teamtailor": ["teamtailor.com", "teamtailor-theme"],
    "recruitee": ["recruitee.com", "recruitee-widget"],
    "bamboohr": ["bamboohr.com", "bamboohr-jobs"],
}


def fingerprint_ats(url: str, html: str = "") -> Optional[str]:
    """
    Detect ATS platform from URL and optional HTML content.
    Returns platform name or None.
    Fastest check first: URL patterns → HTML patterns.
    """
    url_lc = url.lower()

    for platform, patterns in URL_FINGERPRINTS.items():
        if any(p in url_lc for p in patterns):
            return platform

    if html:
        html_lc = html[:20000].lower()
        for platform, patterns in HTML_FINGERPRINTS.items():
            if any(p in html_lc for p in patterns):
                return platform

    return None


def build_ats_url(platform: str, slug: str, url: str = "") -> str:
    """Build canonical ATS API URL for known platform + slug."""
    if platform == "greenhouse":
        return f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
    if platform == "lever":
        return f"https://api.lever.co/v0/postings/{slug}?mode=json"
    if platform == "ashby":
        return f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
    if platform == "workday":
        return url  # Workday URL must come from discovery
    if platform == "smartrecruiters":
        return f"https://jobs.smartrecruiters.com/{slug}"
    if platform == "workable":
        return f"https://apply.workable.com/{slug}"
    if platform == "teamtailor":
        return f"https://{slug}.teamtailor.com/jobs"
    if platform == "recruitee":
        return f"https://{slug}.recruitee.com"
    if platform == "bamboohr":
        return f"https://{slug}.bamboohr.com/careers"
    if platform == "talentrecruit":
        return url or f"https://gtprod.talentrecruit.com/career-page?company_id={slug}"
    if platform == "darwinbox":
        return f"https://{slug}.darwinbox.com/ms/candidate/careers"
    if platform == "taleo":
        return url or f"https://{slug}.taleo.net/careersection/External/jobsearch.ftl"
    if platform == "icims":
        return url or f"https://{slug}.icims.com/jobs/search"
    if platform == "successfactors":
        return url
    return url
