"""
ATS Detection Pass — probes each company's career page, detects provider + slug.

Flow per company:
  1. HEAD-probe known ATS API endpoints derived from domain
  2. If miss: fetch career_page HTML, scan for ATS embed scripts/links
  3. Write (ats_provider, ats_url) to DB

Runs independently. Safe to re-run — skips already-detected companies unless --force.

Usage:
    python3 -m careerloop.detect_ats_pass              # skip already detected
    python3 -m careerloop.detect_ats_pass --force       # re-detect all
    python3 -m careerloop.detect_ats_pass --city Chennai
"""

import logging
import re
import sys
import os
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import requests
from bs4 import BeautifulSoup

from careerloop.company_registry import CompanyRegistry

logging.basicConfig(level=logging.INFO, format="%(levelname)s [%(name)s]: %(message)s")
logger = logging.getLogger("ats_detect")

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/122 Safari/537.36"
})
TIMEOUT = 10

# ── ATS probe patterns ────────────────────────────────────────────────────────
# Each entry: (provider, url_template_from_slug)
# slug = domain minus TLD, e.g. "meesho.com" → "meesho"

def _slug(domain: str) -> str:
    d = domain.lower().strip()
    d = re.sub(r"\.co\.in$", "", d)
    d = re.sub(r"\.(com|in|io|co|net|org|ai|club|money|tech|dev|app|gg|pro|careers)$", "", d)
    return d


ATS_PROBES = [
    # Lever public API — 200 only if company exists AND has a board
    ("lever",       lambda s: f"https://api.lever.co/v0/postings/{s}?mode=json"),
    # Greenhouse embed board — 200 only if token valid
    ("greenhouse",  lambda s: f"https://boards.greenhouse.io/embed/job_board/jobs?for={s}"),
    # Ashby posting API — 200 only if company exists
    ("ashby",       lambda s: f"https://api.ashbyhq.com/posting-api/job-board/{s}"),
    # Workday — probe wd1 through wd5
    ("workday", lambda s: f"https://{s}.wd1.myworkdayjobs.com/en-US/{s}/jobs"),
    ("workday", lambda s: f"https://{s}.wd2.myworkdayjobs.com/en-US/{s}/jobs"),
    ("workday", lambda s: f"https://{s}.wd3.myworkdayjobs.com/en-US/{s}/jobs"),
    ("workday", lambda s: f"https://{s}.wd4.myworkdayjobs.com/en-US/{s}/jobs"),
    ("workday", lambda s: f"https://{s}.wd5.myworkdayjobs.com/en-US/{s}/jobs"),
    # SAP SuccessFactors — probe standard career page path
    ("successfactors", lambda s: f"https://{s}.successfactors.com/careers"),
    # SmartRecruiters — check if it returns actual job listings (not just 200 for any slug)
    ("smartrecruiters", lambda s: f"https://{s}.smartrecruiters.com/api/v1/companies/{s}/postings"),
    # iCIMS — standard career portal URL pattern
    ("icims", lambda s: f"https://careers.{s}.icims.com/jobs"),
    # Taleo — standard career portal URL pattern
    ("taleo", lambda s: f"https://{s}.taleo.net/careersection/2/jobsearch.ftl"),
]

# HTML signals in career page source that identify ATS
ATS_HTML_SIGNALS = [
    (r"greenhouse\.io",           "greenhouse"),
    (r"boards\.greenhouse\.io/([a-z0-9_-]+)", "greenhouse"),
    (r"jobs\.lever\.co/([a-z0-9_-]+)",        "lever"),
    (r"api\.lever\.co/v0/postings/([a-z0-9_-]+)", "lever"),
    (r"jobs\.ashbyhq\.com/([a-z0-9_-]+)",     "ashby"),
    (r"ashbyhq\.com",                          "ashby"),
    (r"myworkdayjobs\.com",                    "workday"),
    (r"smartrecruiters\.com",                  "smartrecruiters"),
    (r"icims\.com",                            "icims"),
    (r"taleo\.net",                            "taleo"),
    (r"successfactors",                        "successfactors"),
    (r"bamboohr\.com",                         "bamboohr"),
    (r"recruitee\.com",                        "recruitee"),
]


def _validate_smartrecruiters(url: str) -> bool:
    """Check if SmartRecruiters API returns actual job postings (non-empty JSON array)."""
    try:
        r = SESSION.get(url, timeout=TIMEOUT)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and len(data) > 0:
                return True
        return False
    except Exception:
        return False


def _probe_api(domain: str) -> tuple[str, str]:
    """HEAD-probe known ATS endpoints. Return (provider, url) or ('', '')."""
    s = _slug(domain)
    for provider, url_fn in ATS_PROBES:
        url = url_fn(s)
        try:
            r = SESSION.head(url, timeout=TIMEOUT, allow_redirects=True)
            if r.status_code == 200:
                if provider == "smartrecruiters" and not _validate_smartrecruiters(url):
                    continue
                logger.info(f"  API hit: {provider} → {url}")
                return provider, url
        except Exception:
            continue
        time.sleep(0.2)
    return "", ""


def _probe_html(career_page_url: str) -> tuple[str, str]:
    """Fetch career page HTML, scan for ATS embed signals. Return (provider, ats_url)."""
    if not career_page_url:
        return "", ""
    try:
        r = SESSION.get(career_page_url, timeout=TIMEOUT, allow_redirects=True)
        if r.status_code != 200:
            return "", ""
        html = r.text
    except Exception as e:
        logger.debug(f"  HTML fetch failed: {e}")
        return "", ""

    for pattern, provider in ATS_HTML_SIGNALS:
        m = re.search(pattern, html, re.IGNORECASE)
        if m:
            # Try to extract slug from capture group if present
            slug_captured = m.group(1) if m.lastindex else ""
            if provider == "lever" and slug_captured:
                ats_url = f"https://api.lever.co/v0/postings/{slug_captured}?mode=json"
            elif provider == "greenhouse" and slug_captured:
                ats_url = f"https://boards.greenhouse.io/embed/job_board/jobs?for={slug_captured}"
            elif provider == "ashby" and slug_captured:
                ats_url = f"https://api.ashbyhq.com/posting-api/job-board/{slug_captured}"
            else:
                ats_url = ""
            logger.info(f"  HTML signal: {provider} (slug={slug_captured or '?'})")
            return provider, ats_url

    return "", ""


def _probe_playwright(career_page_url: str) -> tuple[str, str]:
    """Render JS-heavy career page with headless Chromium, scan for ATS signals."""
    if not career_page_url:
        return "", ""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(career_page_url, wait_until="networkidle", timeout=20000)
            html = page.content()
            browser.close()
    except Exception as e:
        logger.debug(f"  Playwright probe failed: {e}")
        return "", ""

    for pattern, provider in ATS_HTML_SIGNALS:
        m = re.search(pattern, html, re.IGNORECASE)
        if m:
            slug_captured = m.group(1) if m.lastindex else ""
            if provider == "lever" and slug_captured:
                ats_url = f"https://api.lever.co/v0/postings/{slug_captured}?mode=json"
            elif provider == "greenhouse" and slug_captured:
                ats_url = f"https://boards.greenhouse.io/embed/job_board/jobs?for={slug_captured}"
            elif provider == "ashby" and slug_captured:
                ats_url = f"https://api.ashbyhq.com/posting-api/job-board/{slug_captured}"
            else:
                ats_url = ""
            logger.info(f"  Playwright HTML signal: {provider} (slug={slug_captured or '?'})")
            return provider, ats_url

    return "", ""


def detect_company(company) -> tuple[str, str]:
    """Return (ats_provider, ats_url) for one company. '' if none found."""
    logger.info(f"[{company.name}] probing {company.domain}")

    # Step 1: API probe from domain slug
    provider, url = _probe_api(company.domain)
    if provider:
        return provider, url

    # Step 2: HTML scan of career page
    provider, url = _probe_html(company.career_page_url)
    if provider:
        if not url:
            s = _slug(company.domain)
            for p, url_fn in ATS_PROBES:
                if p == provider:
                    url = url_fn(s)
                    break
        return provider, url

    # Step 3: Playwright render for JS-heavy career pages
    provider, url = _probe_playwright(company.career_page_url)
    if provider:
        if not url:
            s = _slug(company.domain)
            for p, url_fn in ATS_PROBES:
                if p == provider:
                    url = url_fn(s)
                    break
        return provider, url

    logger.info(f"  → no ATS detected, marking custom/unknown")
    return "none", ""


def run(root: str = None, force: bool = False, city: str = ""):
    reg = CompanyRegistry(root)
    companies = reg.list_by_city_sector(city=city, limit=500)

    targets = [
        c for c in companies
        if force or c.ats_provider in ("unknown", "", None)
    ]

    logger.info(f"ATS detection pass: {len(targets)} companies to probe")
    detected = 0
    failed = 0

    for i, company in enumerate(targets, 1):
        logger.info(f"[{i}/{len(targets)}] {company.name}")
        try:
            provider, url = detect_company(company)
            company.ats_provider = provider or "none"
            company.ats_url = url
            reg.upsert(company)
            if provider:
                detected += 1
                logger.info(f"  ✓ {provider} → {url[:60]}")
            else:
                failed += 1
                logger.info(f"  ✗ no ATS found")
        except Exception as e:
            logger.warning(f"  ERROR: {e}")
            failed += 1
        time.sleep(0.5)

    print(f"\nDone. {detected}/{len(targets)} ATS detected. {failed} no-ATS/failed.")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--force", action="store_true", help="re-detect already-detected companies")
    p.add_argument("--city", default="", help="filter by city")
    p.add_argument("root", nargs="?", default=ROOT)
    args = p.parse_args()
    run(root=args.root, force=args.force, city=args.city)
