"""
WeWorkRemotely adapter — RSS feeds (static XML, no JS needed).
Feeds: /categories/remote-programming-jobs.rss, /categories/remote-product-jobs.rss,
       /categories/remote-management-jobs.rss, /categories/remote-design-jobs.rss
"""
import logging
import re
import xml.etree.ElementTree as ET

import requests

logger = logging.getLogger(__name__)

_BASE = "https://weworkremotely.com"
_FEEDS = [
    "/categories/remote-programming-jobs.rss",
    "/categories/remote-product-jobs.rss",
    "/categories/remote-management-jobs.rss",
    "/categories/remote-data-science-jobs.rss",
]
_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; CareerLoopBot/1.0)"}


def search_weworkremotely(role: str, city: str = "", max_results: int = 30) -> list[dict]:
    """Search WeWorkRemotely RSS feeds for matching jobs."""
    keywords = {t.lower() for t in re.split(r"[\s/\-]+", role) if len(t) > 2}
    out: list[dict] = []

    for feed_path in _FEEDS:
        if len(out) >= max_results:
            break
        try:
            resp = requests.get(_BASE + feed_path, headers=_HEADERS, timeout=12)
            if not resp.ok:
                continue
            root = ET.fromstring(resp.content)
        except Exception as e:
            logger.debug(f"[WWR] feed {feed_path} failed: {e}")
            continue

        ns = {"atom": "https://www.w3.org/2005/Atom"}
        for item in root.iter("item"):
            title_el = item.find("title")
            link_el = item.find("link")
            desc_el = item.find("description")
            region_el = item.find("region")

            title = title_el.text.strip() if title_el is not None and title_el.text else ""
            url = link_el.text.strip() if link_el is not None and link_el.text else ""
            description = _strip_html(desc_el.text or "") if desc_el is not None else ""
            region = region_el.text.strip() if region_el is not None and region_el.text else "remote"

            combined = (title + " " + description[:300]).lower()
            if not any(kw in combined for kw in keywords):
                continue

            # WWR title format varies: "Company: Title" or "Company | Title" or just "Title"
            if ": " in title:
                company, job_title = title.split(": ", 1)
            elif " | " in title:
                company, job_title = title.split(" | ", 1)
            else:
                company, job_title = "", title

            out.append({
                "title": job_title,
                "company": company,
                "location": region or "remote",
                "url": url,
                "apply_url": url,
                "description": description,
                "skills": [],
                "work_mode": "remote",
                "_source_type": "weworkremotely",
            })
            if len(out) >= max_results:
                break

    logger.info(f"[WWR] {len(out)} jobs for '{role}'")
    return out


def _strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", re.sub(r"&\w+;", " ", html)).strip()
