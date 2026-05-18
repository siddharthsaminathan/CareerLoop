"""
CareerLoop JobSpy Adapter — Multi-board search via python-jobspy.

Searches LinkedIn, Indeed, Google Jobs, Glassdoor.
Naukri is NOT supported by JobSpy — remains CSV import.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class JobSpyAdapter:
    """Multi-board job search using python-jobspy."""

    def __init__(self):
        self._available = None

    @property
    def available(self) -> bool:
        if self._available is None:
            try:
                from jobspy import scrape_jobs
                self._available = True
            except ImportError:
                self._available = False
        return self._available

    def search(
        self,
        role: str,
        location: str = "India",
        results_wanted: int = 10,
        sites: list[str] = None,
    ) -> list[dict]:
        """
        Search for jobs across boards.
        Returns list of dicts with url, title, company, location, etc.
        """
        if not self.available:
            logger.warning("python-jobspy not installed")
            return []

        from jobspy import scrape_jobs

        if sites is None:
            sites = ["linkedin", "indeed"]

        try:
            jobs_df = scrape_jobs(
                site_name=sites,
                search_term=role,
                location=location,
                results_wanted=results_wanted,
                country_indeed="India",
            )

            results = []
            for _, row in jobs_df.iterrows():
                results.append({
                    "url": str(row.get("job_url", "")),
                    "title": str(row.get("title", "")),
                    "company": str(row.get("company_name", row.get("company", ""))),
                    "location": str(row.get("location", "")),
                    "description": str(row.get("description", ""))[:500],
                    "posted_at": str(row.get("date_posted", "")),
                    "salary": str(row.get("min_amount", "")) + "-" + str(row.get("max_amount", "")) if row.get("min_amount") else "",
                    "source_board": str(row.get("site", "")),
                    "work_mode": str(row.get("is_remote", "")),
                })

            logger.info(f"JobSpy found {len(results)} jobs for '{role}' in {location}")
            return results

        except Exception as e:
            logger.warning(f"JobSpy search failed: {e}")
            return []

    def search_from_queries(self, queries: list[dict]) -> list[dict]:
        """Run JobSpy for unique role+city combos from query list."""
        seen = set()
        all_results = []

        for q in queries:
            role = q.get("role", "")
            city = q.get("city", "India")
            key = f"{role}|{city}"
            if key in seen:
                continue
            seen.add(key)

            results = self.search(role=role, location=city, results_wanted=20)
            all_results.extend(results)

        return all_results
