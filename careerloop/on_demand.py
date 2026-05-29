"""
On-Demand Search — synchronous "find jobs for this role in this city, NOW".

Replaces the cron-only batch model. User types a role + city, gets top results
in under ~60 seconds. Uses:
1. RoleKeywordCache for query generation
2. CompanyTargeting for portal-side targeted scrape
3. SearchAdapter + JobSpyAdapter for board-side discovery
4. IndiaFitEngine for fast scoring
5. deduplicate_canonical for cross-source merge

Returns a small ranked list with full breakdown.
"""

import logging
import os
from dataclasses import dataclass, field
from typing import Optional

from careerloop.apply_route import deduplicate_canonical, resolve_apply_route
from careerloop.india_filter import filter_india_jobs
from careerloop.india_fit_engine import IndiaFitEngine
from careerloop.role_keywords import RoleKeywordCache
from careerloop.company_targeting import CompanyTargeting
from careerloop.role_similarity import RoleSimilarityFilter
from careerloop.sources.search_adapter import SearchAdapter
from careerloop.sources.jobspy_adapter import JobSpyAdapter
from careerloop.sources.scrapegraph_adapter import ScrapeGraphAdapter
from careerloop.sources.indeed_scraper import IndeedScraper
from careerloop.sources.api_interceptor import APIInterceptor
from careerloop.sources.portal_scraper import PortalScraper
from careerloop.sources.role_archetype import RoleArchetypeEngine
from careerloop.models import URLType, classify_url_type
from careerloop.profile_manager import ProfileManager

logger = logging.getLogger(__name__)


def _tag_jobs_with_ontology(jobs: list[dict], archetype: "RoleArchetype", seniority_signals: dict) -> None:
    """Tag each job dict with ontology dimensions in-place.
    Tags stored under job['_ontology']. All signals from profile config — zero hardcoding."""
    for job in jobs:
        title_lc = (job.get("title") or "").lower()
        desc_lc = (job.get("description") or "").lower()[:2000]
        combined = title_lc + " " + desc_lc

        # Seniority — signals come from profile_extended.yml seniority_signals
        seniority = "unknown"
        for level, signals in seniority_signals.items():
            if any(s.lower() in title_lc for s in signals):
                seniority = level
                break

        # Role archetype match score — stem-aware: "buying" matches "buyer", "merchandising" matches "merchandiser"
        must = archetype.must_have or []
        def _token_present(token: str, text: str) -> bool:
            t = token.lower()
            if t in text:
                return True
            # stem: strip trailing -ing/-er/-ment/-ion suffixes for fuzzy match
            for suffix in ("ing", "er", "ment", "ion", "ise", "ize", "al"):
                if t.endswith(suffix) and t[:-len(suffix)] and t[:-len(suffix)] in text:
                    return True
            return False
        archetype_match = (
            sum(1 for m in must if _token_present(m, combined)) / len(must)
            if must else 0.5
        )

        # Business model signal — inferred from JD text tokens (generic, not domain-specific)
        biz_b2b_tokens = archetype.preferred_company_types or []
        biz_model = "unknown"
        if any(t.lower() in desc_lc for t in biz_b2b_tokens + ["enterprise", "b2b", "saas", "api platform"]):
            biz_model = "b2b"
        elif any(t.lower() in desc_lc for t in ["consumer", "b2c", "retail", "end user"]):
            biz_model = "b2c"

        job["_ontology"] = {
            "seniority": seniority,
            "archetype_match": round(archetype_match, 2),
            "biz_model": biz_model,
            "preferred_company_match": any(
                p.lower() in combined for p in archetype.preferred_company_types
            ),
        }


def _fetch_missing_jds(jobs: list[dict]) -> None:
    """Attempt to fetch full JD text for jobs with thin descriptions (e.g. jobspy).
    Mutates jobs in-place. Uses requests + BeautifulSoup; silently skips on failure."""
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError:
        return

    for job in jobs:
        if len(job.get("description") or "") >= 200:
            continue
        url = job.get("apply_url") or job.get("url") or ""
        if not url or not url.startswith("http"):
            continue
        try:
            resp = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "nav", "header", "footer"]):
                tag.decompose()
            text = soup.get_text(separator=" ", strip=True)
            if len(text) > len(job.get("description") or ""):
                job["description"] = text[:8000]
        except Exception:
            continue


@dataclass
class OnDemandResult:
    role: str
    city: str
    keywords_used: list = field(default_factory=list)
    targeted_companies: list = field(default_factory=list)
    candidate_count: int = 0
    after_dedup_count: int = 0
    ranked_jobs: list = field(default_factory=list)
    elapsed_seconds: float = 0.0
    notes: list = field(default_factory=list)


class OnDemandSearch:
    """Run a synchronous targeted discovery for one (role, city)."""

    def __init__(self, career_ops_root: str, profile_path: str = None,
                 extended_profile_path: str = None):
        self.root = career_ops_root
        self.profile = ProfileManager(career_ops_root, profile_path=profile_path,
                                      extended_profile_path=extended_profile_path)
        self.fit_engine = IndiaFitEngine(self.profile)
        self.keywords = RoleKeywordCache(career_ops_root)
        self.targeting = CompanyTargeting(career_ops_root)
        self.search = SearchAdapter()
        self.jobspy = JobSpyAdapter()
        self.scraper = ScrapeGraphAdapter()
        self._indeed = IndeedScraper()
        self._interceptor = APIInterceptor()   # kept for backward compat
        self._portal_scraper = PortalScraper()  # 3-layer replacement
        self._role_filter = RoleSimilarityFilter()
        self._archetype_engine = RoleArchetypeEngine(self.profile)
        self._ats = None
        self._portal = None

    def _get_ats(self):
        if self._ats is None:
            from careerloop.sources.ats_adapter import ATSAdapter
            self._ats = ATSAdapter()
        return self._ats

    def _get_portal(self):
        if self._portal is None:
            from careerloop.sources.company_portal_scraper import (
                CareerPageCrawler, JDSectionExtractor,
            )
            self._portal = (CareerPageCrawler(), JDSectionExtractor())
        return self._portal

    # ── Public API ────────────────────────────────────────────────────

    def run(
        self,
        role: str,
        city: str = "",
        max_results: int = 10,
        portal_companies: int = 20,
        include_boards: bool = True,
        force_refresh: bool = False,
        include_phase_a: bool = True,
    ) -> OnDemandResult:
        """Run a targeted discovery pass. Returns top-N ranked jobs."""
        import time
        t0 = time.time()
        city = city or self.profile.location_city
        self._current_role = role  # used by post-ATS filter
        result = OnDemandResult(role=role, city=city)

        # Check shared crawl cache first (skip when force_refresh=True)
        try:
            from careerloop.sources.crawl_cache import CrawlCache
            _cache = CrawlCache(self.root)
            cached = None if force_refresh else _cache.get(role, city)
            if cached is not None:
                result.notes.append(f"crawl cache hit: {len(cached)} jobs (skipping pipeline)")
                result.candidate_count = len(cached)
                deduped = cached
                scored = self.fit_engine.score_jobs_batch(deduped)
                # City filter (was previously skipped in cache path)
                _city_lc = city.lower().strip()
                _city_aliases = {
                    "bangalore": {"bangalore", "bengaluru", "blr"},
                    "bengaluru": {"bangalore", "bengaluru", "blr"},
                    "mumbai": {"mumbai", "bombay"},
                    "delhi": {"delhi", "new delhi", "ncr", "gurgaon", "gurugram", "noida"},
                    "hyderabad": {"hyderabad", "hyd"},
                    "chennai": {"chennai", "madras"},
                    "remote": {"remote"},
                }
                _allowed = _city_aliases.get(_city_lc, {_city_lc})
                _allowed |= {"remote", "india", "pan india", "pan-india", "anywhere"}
                def _city_ok_cached(jd: dict) -> bool:
                    loc = (jd.get("job", jd).get("location") or "").lower()
                    if not loc:
                        return True
                    return any(a in loc for a in _allowed)
                scored = [j for j in scored if _city_ok_cached(j)]
                # Company cap (was previously skipped in cache path)
                _cc: dict[str, int] = {}
                _capped = []
                for j in scored:
                    _comp = (j.get("job", j).get("company_name") or j.get("job", j).get("company") or "unknown").lower().strip()
                    _cc[_comp] = _cc.get(_comp, 0) + 1
                    if _cc[_comp] <= 3:
                        _capped.append(j)
                result.ranked_jobs = _capped[:max_results]
                result.after_dedup_count = len(deduped)
                result.elapsed_seconds = round(time.time() - t0, 2)
                return result
        except Exception:
            _cache = None

        # 1. Dynamic keywords for this role
        kw_data = self.keywords.get(role, city)
        result.keywords_used = kw_data.get("keywords", [])[:10]
        queries = kw_data.get("search_queries", [])

        # Compute archetype once — used for query enrichment, Phase A hint, Phase B filter
        archetype = self._archetype_engine.get_archetype(role)
        print(f"  [Archetype] role='{role}' | function={archetype.function_type!r} | market={archetype.market_type!r}", flush=True)
        print(f"  [Archetype] must_have={archetype.must_have}", flush=True)
        print(f"  [Archetype] avoid={archetype.avoid[:8]}", flush=True)

        # Prepend archetype-enriched queries to strengthen board retrieval signal
        arch_constraint = archetype.to_query_constraint()
        if arch_constraint:
            archetype_queries = [
                f'{arch_constraint} {city} jobs',
                f'{arch_constraint} hiring {city} 2025',
            ]
            queries = archetype_queries + queries
        print(f"  [Queries] {len(queries)} board queries: {queries[:4]}", flush=True)

        all_jobs: list[dict] = []

        # 2. Phase A — Employer discovery (primary) + portal scrape
        #    Controlled by include_phase_a flag. Set False to run Phase B→G only
        #    (recommended until Company Identity Layer is built — see SEARCH_VISION.md Sprint 7+)
        if include_phase_a:
            try:
                print(f"  [Phase A] discovering companies for '{role}' in {city}...", flush=True)
                ranked_companies = self._discover_and_rank(role, city, portal_companies)
                if ranked_companies:
                    result.notes.append(f"Phase A: live discovery OK — {len(ranked_companies)} companies")
                    print(f"  [Phase A] found {len(ranked_companies)} companies. scraping portals...", flush=True)
                else:
                    result.notes.append("Phase A: live discovery returned 0 companies — skipping portal layer")
                    print(f"  [Phase A] 0 companies found.", flush=True)
                result.targeted_companies = [rc.company.name for rc in ranked_companies]
                portal_jobs = self._scrape_targeted_companies(ranked_companies)
                for j in portal_jobs:
                    j.setdefault("_phase", "A")
                print(f"  [Phase A] portal scrape done — {len(portal_jobs)} jobs", flush=True)
                all_jobs.extend(portal_jobs)
            except Exception as e:
                result.notes.append(f"Phase A FAILED: {e}")
                logger.warning(f"[OnDemand] Phase A failed: {e}")
        else:
            print(f"  [Phase A] DETACHED — skipping employer discovery (Phase B→G mode)", flush=True)
            result.notes.append("Phase A: detached (include_phase_a=False)")

        # 3. Job boards (DDG + JobSpy) — bounded
        if include_boards and queries:
            try:
                print(f"  [Phase B] searching job boards (parallel)...", flush=True)
                board_jobs = self._board_search(queries[:6], role=role, city=city)
                # Archetype filter: reject titles that match the user's avoided role signals
                for j in board_jobs:
                    j.setdefault("_phase", "B")
                pre_arch = len(board_jobs)
                board_jobs = [j for j in board_jobs if not archetype.reject_title(j.get("title", ""))]
                arch_dropped = pre_arch - len(board_jobs)
                # M2: report per-source health immediately
                if hasattr(self, "_last_board_health"):
                    health_str = " | ".join(f"{k}:{v}" for k, v in sorted(self._last_board_health.items()))
                    print(f"  [Phase B] per-source: {health_str}", flush=True)
                    result.notes.append(f"board health: {health_str}")
                print(f"  [Phase B] boards done — {len(board_jobs)} jobs (archetype title-rejected {arch_dropped})", flush=True)
                all_jobs.extend(board_jobs)
            except Exception as e:
                result.notes.append(f"board search error: {e}")
                logger.warning(f"[OnDemand] Board search failed: {e}")

        result.candidate_count = len(all_jobs)
        print(f"  [Pipeline] total raw candidates: {len(all_jobs)} (A:{sum(1 for j in all_jobs if j.get('_phase')=='A')} + B:{sum(1 for j in all_jobs if j.get('_phase')=='B')})", flush=True)

        # Tag all jobs with ontology dimensions (function, market, archetype, seniority)
        _tag_jobs_with_ontology(all_jobs, archetype, self.profile.seniority_signals)

        # 4. India filter
        india_filtered, _ = filter_india_jobs(all_jobs)
        print(f"  [Filter] India filter: {len(all_jobs)} → {len(india_filtered)}", flush=True)

        # BUG-006: Drop recruiter/staffing agency postings before role filter
        _RECRUITER_PATTERNS = [
            "recruitment expert", "staffing", "| hiring", "expert hiring",
            "talent solutions", "executive search", "placement agency",
        ]
        non_recruiter = []
        recruiter_dropped = 0
        for j in india_filtered:
            title_lc = (j.get("title") or "").lower()
            if any(p in title_lc for p in _RECRUITER_PATTERNS):
                recruiter_dropped += 1
            else:
                non_recruiter.append(j)
        if recruiter_dropped:
            result.notes.append(f"recruiter filter: dropped {recruiter_dropped} agency postings")

        # BUG-004: Drop jobs from rejected company types
        rejected_company_types = self.profile.rejected_company_types or []
        _COMPANY_TYPE_SIGNALS = {
            "it_outsourcing": ["tcs", "infosys", "wipro", "hcl", "accenture", "cognizant",
                               "hexaware", "mphasis", "capgemini", "tech mahindra", "ltimindtree",
                               "mindtree", "persistent systems", "niit", "mastech"],
            "body_shop": ["teamlease", "quess corp", "manpower", "adecco", "randstad",
                          "ikya", "careernet"],
            "consulting": ["deloitte", "kpmg", "ey ", "ernst & young", "mckinsey", "bain ",
                           "bcg", "grant thornton", "pwc", "pricewaterhousecoopers"],
            "mass_recruiter": ["hiregenie", "naukri fast forward", "foundit premium",
                               "monster hiring", "recruitment expert"],
        }
        active_reject_signals = []
        for rtype in rejected_company_types:
            active_reject_signals.extend(_COMPANY_TYPE_SIGNALS.get(rtype, []))

        company_type_filtered = []
        company_type_dropped = 0
        for j in non_recruiter:
            company_lc = (j.get("company_name") or j.get("company") or "").lower()
            if active_reject_signals and any(s in company_lc for s in active_reject_signals):
                company_type_dropped += 1
            else:
                company_type_filtered.append(j)
        if company_type_dropped:
            result.notes.append(f"company-type filter: dropped {company_type_dropped} rejected-type companies")

        # Phase E — Ontology pre-filter (fast, zero-cost, before embedding similarity)
        arch_gate = self.profile.archetype_gate
        pre_ontology = len(company_type_filtered)
        ontology_filtered = [
            j for j in company_type_filtered
            if j.get("_ontology", {}).get("archetype_match", 0.5) >= arch_gate
        ]
        ont_dropped = pre_ontology - len(ontology_filtered)
        print(f"  [Phase E] ontology gate (archetype_match>={arch_gate}): {pre_ontology} → {len(ontology_filtered)} ({ont_dropped} dropped)", flush=True)
        if ont_dropped:
            result.notes.append(f"ontology gate: dropped {ont_dropped} jobs (archetype_match<{arch_gate})")

        # Phase E — Role relevance filter (embedding similarity + profile rejection)
        print(f"  [Phase E] role similarity filter: {len(ontology_filtered)} candidates...", flush=True)
        relevant, rejected_count = self._role_filter.filter_jobs(
            ontology_filtered,
            target_role=role,
            target_functions=self.profile.target_functions or [],
            rejected_roles=self.profile.rejected_roles or [],
        )
        print(f"  [Phase E] role filter done: {len(ontology_filtered)} → {len(relevant)} relevant ({rejected_count} rejected)", flush=True)
        result.notes.append(f"role filter: {len(ontology_filtered)} → {len(relevant)} relevant ({rejected_count} rejected)")

        # 5. Canonical dedup
        deduped = deduplicate_canonical(relevant)
        for job in deduped:
            job["apply_route"] = resolve_apply_route(job)
        result.after_dedup_count = len(deduped)

        # Attempt full JD fetch for jobs with thin descriptions (jobspy/foundit typically)
        _fetch_missing_jds(deduped)

        # Hard gate: reject jobs still under min_description_chars after fetch attempt
        min_desc = self.profile.min_description_chars
        pre_gate = len(deduped)
        deduped = [j for j in deduped if len(j.get("description") or "") >= min_desc]
        gate_dropped = pre_gate - len(deduped)
        if gate_dropped:
            result.notes.append(f"min-desc gate: dropped {gate_dropped} jobs (<{min_desc}c)")

        # 6. Score with IndiaFitEngine
        scored = self.fit_engine.score_jobs_batch(deduped)

        # 7. Save to crawl cache for future reuse
        try:
            if _cache is not None:
                _cache.set(role, city, deduped)
        except Exception:
            pass

        # 7. City filter — reject jobs in wrong city (keep remote/India-wide)
        #    Runs BEFORE LLM validation (FREE filter) to avoid wasting tokens on wrong-city jobs.
        city_lc = city.lower().strip()
        city_aliases = {
            "bangalore": {"bangalore", "bengaluru", "blr"},
            "bengaluru": {"bangalore", "bengaluru", "blr"},
            "mumbai": {"mumbai", "bombay"},
            "delhi": {"delhi", "new delhi", "ncr", "gurgaon", "gurugram", "noida"},
            "hyderabad": {"hyderabad", "hyd"},
            "chennai": {"chennai", "madras"},
            "remote": {"remote"},
        }
        allowed = city_aliases.get(city_lc, {city_lc})
        allowed |= {"remote", "india", "pan india", "pan-india", "anywhere"}

        def _city_ok(job_dict: dict) -> bool:
            loc = (job_dict.get("job", job_dict).get("location") or "").lower()
            if not loc:
                return True  # unknown location → allow (can't reject blind)
            return any(a in loc for a in allowed)

        city_filtered = [j for j in scored if _city_ok(j)]
        off_city = len(scored) - len(city_filtered)
        if off_city:
            result.notes.append(f"city filter ({city}): {len(scored)} → {len(city_filtered)} ({off_city} off-city removed)")

        # 8. Per-company cap — prevent one company flooding the ranked list
        #    Runs BEFORE LLM validation (FREE filter) to avoid wasting tokens on capped jobs.
        company_counts: dict[str, int] = {}
        capped = []
        for j in city_filtered:
            company = (j.get("job", j).get("company_name") or j.get("job", j).get("company") or "unknown").lower().strip()
            company_counts[company] = company_counts.get(company, 0) + 1
            if company_counts[company] <= 3:
                capped.append(j)
        if len(capped) < len(city_filtered):
            result.notes.append(f"company cap (max 3): {len(city_filtered)} → {len(capped)}")

        # 9. FIX 20: LLM validator — DeepSeek pass to reject hardware/intern/bodyshop jobs
        #    that slipped past embedding filter. Runs on pre-filtered top-60 to save tokens.
        print(f"  [Phase F] LLM validator (DeepSeek): validating top-{min(60, len(capped))} jobs...", flush=True)
        pre_llm = len(capped)
        try:
            capped = self._llm_validate(capped[:60], role=role) + capped[60:]
            print(f"  [Phase F] LLM validator done: {pre_llm} → {len(capped)}", flush=True)
        except Exception as e:
            print(f"  [Phase F] LLM validator skipped: {e}", flush=True)
            logger.debug(f"[OnDemand] LLM validator skipped: {e}")

        # 10. Trim to max_results
        result.ranked_jobs = capped[:max_results]
        result.elapsed_seconds = round(time.time() - t0, 2)
        return result

    # ── Internals ─────────────────────────────────────────────────────

    _PORTAL_WORKERS = 6  # P2: concurrent browser sessions

    def _llm_validate(self, scored_jobs: list[dict], role: str) -> list[dict]:
        """
        FIX 20: DeepSeek pass — batch-validate top scored jobs.
        Catches hardware roles, interns, bodyshop companies that pass embedding filter.
        Input: list of scored dicts (each has 'job' key + 'score').
        Returns: filtered list (rejects removed, order preserved).
        """
        import os, json, requests as req

        api_key = os.getenv("DEEPSEEK_API_KEY", "")
        base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
        if not api_key or not scored_jobs:
            return scored_jobs

        rejected_roles = self.profile.rejected_roles or []
        rejected_types = self.profile.rejected_company_types or []

        items = []
        for i, item in enumerate(scored_jobs):
            job = item.get("job", item)
            items.append({
                "id": i,
                "title": job.get("title", ""),
                "company": job.get("company_name") or job.get("company", ""),
                "description_snippet": (job.get("description") or "")[:300],
            })

        prompt = (
            f"You are a job relevance validator. Target role: '{role}'.\n"
            f"Rejected role patterns: {rejected_roles[:20]}\n"
            f"Rejected company types: {rejected_types}\n\n"
            "For each job below, decide KEEP or REJECT. "
            "REJECT if: title matches rejected patterns, company is IT outsourcing/bodyshop/staffing, "
            "or role is clearly not '{role}' (hardware, sales, admin, intern, etc.).\n\n"
            "Jobs:\n"
            + json.dumps(items, ensure_ascii=False)
            + "\n\nReturn ONLY a JSON array: [{\"id\": 0, \"verdict\": \"KEEP\"}, ...] for ALL items."
        )

        try:
            resp = req.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0,
                    "max_tokens": len(scored_jobs) * 25,
                },
                timeout=30,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
            import re
            arr_match = re.search(r"\[.*\]", content, re.DOTALL)
            if not arr_match:
                return scored_jobs
            verdicts = {v["id"]: v["verdict"] for v in json.loads(arr_match.group())}
            kept = [item for i, item in enumerate(scored_jobs) if verdicts.get(i, "KEEP") == "KEEP"]
            rejected_count = len(scored_jobs) - len(kept)
            if rejected_count:
                logger.info(f"[OnDemand] LLM validator: {len(scored_jobs)} → {len(kept)} ({rejected_count} rejected)")
            return kept
        except Exception as e:
            logger.debug(f"[OnDemand] LLM validator error: {e}")
            return scored_jobs

    def _scrape_targeted_companies(self, ranked) -> list[dict]:
        """P2: Parallel company scraping — 6 concurrent workers."""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        from careerloop.sources.spireai_adapter import discover_workspace_id, fetch_jobs as spire_fetch

        ats = self._get_ats()
        crawler, extractor = self._get_portal()

        def _scrape_one(rc) -> list[dict]:
            company = rc.company
            try:
                if company.ats_provider not in ("unknown", "none", ""):
                    ats_jobs = ats.fetch_jobs(
                        company.id, company.name,
                        company.ats_provider, company.ats_url,
                    )
                    source_tag = company.ats_provider
                    # Core adapters return ATSJob objects; extended return plain dicts
                    raw_dicts = [
                        aj.to_dict() if hasattr(aj, "to_dict") else aj
                        for aj in ats_jobs
                    ]
                    for d in raw_dicts:
                        d.setdefault("_source_type", source_tag)
                    filtered, rejected = self._role_filter.filter_jobs(
                        raw_dicts,
                        target_role=self._current_role,
                        target_functions=self.profile.target_functions or [],
                        rejected_roles=self.profile.rejected_roles or [],
                    )
                    logger.info(f"[OnDemand] {company.name} ATS: {len(raw_dicts)} raw → {len(filtered)} after role filter ({rejected} rejected)")
                    return filtered

                elif company.career_page_url:
                    career_url = company.career_page_url

                    ws_id = discover_workspace_id(career_url)
                    if ws_id:
                        spire_jobs = spire_fetch(ws_id, company.name, career_url)
                        logger.info(f"[OnDemand] {company.name}: {len(spire_jobs)} via SpireAI")
                        return spire_jobs

                    portal_result = self._portal_scraper.scrape(career_url)

                    if portal_result.intercepted_apis:
                        discovered = self._resolve_intercepted_apis(portal_result, company, ats)
                        if discovered:
                            platform = portal_result.intercepted_apis[0].platform
                            logger.info(f"[OnDemand] {company.name}: {len(discovered)} via L1 API ({platform})")
                            return discovered

                    if portal_result.has_jobs:
                        all_dom = portal_result.all_jobs
                        for j in all_dom:
                            j.setdefault("company", company.name)
                        logger.info(
                            f"[OnDemand] {company.name}: {len(all_dom)} via "
                            f"L{'2+3' if portal_result.agentive_jobs else '2'} DOM"
                        )
                        return all_dom

                    # Static HTML fallback
                    result = []
                    urls = crawler.crawl(career_url)
                    for url in urls[:10]:
                        try:
                            jd = extractor.extract(url)
                            if jd.extraction_confidence >= 0.6:
                                result.append({
                                    "title": jd.job_title,
                                    "company": company.name,
                                    "location": jd.location,
                                    "url": url,
                                    "apply_url": url,
                                    "url_type": URLType.INDIVIDUAL_JOB.value,
                                    "description": jd.raw_text,
                                    "role_summary": jd.role_summary,
                                    "responsibilities": jd.responsibilities,
                                    "requirements": jd.requirements,
                                    "benefits": jd.benefits,
                                    "extraction_confidence": jd.extraction_confidence,
                                    "_source_type": "company_portal",
                                })
                        except Exception:
                            pass
                    return result
            except Exception as e:
                logger.debug(f"[OnDemand] {company.name}: {e}")
            return []

        jobs: list[dict] = []
        with ThreadPoolExecutor(max_workers=self._PORTAL_WORKERS) as pool:
            # M1: wrap each company scrape with retry(1) — browser timeouts are transient
            futures = {
                pool.submit(self._retry, lambda rc=rc: _scrape_one(rc), 1, rc.company.name): rc
                for rc in ranked
            }
            for fut in as_completed(futures):
                try:
                    jobs.extend(fut.result() or [])
                except Exception as e:
                    rc = futures[fut]
                    logger.debug(f"[OnDemand] worker error {rc.company.name}: {e}")
        return jobs

    def _resolve_intercepted_apis(self, interception, company, ats) -> list[dict]:
        """Phase C+D: given intercepted APIs, fetch jobs via the right adapter."""
        jobs = []
        # PortalScraperResult uses .intercepted_apis; InterceptionResult uses .apis
        api_list = getattr(interception, "intercepted_apis", None) or getattr(interception, "apis", [])
        for api in api_list:
            try:
                if api.platform in ("lever", "greenhouse", "ashby", "workday"):
                    # Build canonical ATS URL and fetch
                    ats_url = self._build_ats_url(api)
                    if ats_url:
                        ats_jobs = ats.fetch_jobs(company.id, company.name, api.platform, ats_url)
                        for aj in ats_jobs:
                            d = aj.to_dict()
                            d["_source_type"] = aj.source
                            jobs.append(d)
                        # Cache discovery in DB
                        self._update_company_ats(company.id, api.platform, ats_url)
                elif api.platform == "spireai":
                    from careerloop.sources.spireai_adapter import fetch_jobs as spire_fetch
                    ws_id = api.slug or ""
                    if not ws_id and api.sample_data:
                        ws_id = api.sample_data.get("workspaceId", "")
                    if ws_id:
                        jobs.extend(spire_fetch(ws_id, company.name, company.career_page_url or api.url))
                elif api.platform == "custom_json" and api.sample_data:
                    # Direct fetch of the discovered endpoint
                    endpoint = api.sample_data.get("endpoint", "")
                    if endpoint:
                        jobs.extend(self._fetch_custom_json(endpoint, company.name))
            except Exception as e:
                logger.debug(f"[OnDemand] intercept resolve {api.platform}: {e}")
        return jobs

    def _build_ats_url(self, api) -> Optional[str]:
        slug = api.slug
        if not slug:
            return None
        if api.platform == "lever":
            return f"https://api.lever.co/v0/postings/{slug}?mode=json"
        if api.platform == "greenhouse":
            return f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
        if api.platform == "ashby":
            return f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
        return None

    def _update_company_ats(self, company_id: str, provider: str, ats_url: str):
        """FIX 11: Persist discovered ATS endpoint to DB — companies + company_sources tables."""
        try:
            from datetime import datetime, timezone
            from careerloop.memory.connection import get_db_manager
            now = datetime.now(timezone.utc).isoformat()
            db = get_db_manager(self.root)
            with db.get_connection() as conn:
                conn.execute(
                    "UPDATE companies SET ats_provider=?, ats_url=?, updated_at=? WHERE id=?",
                    [provider, ats_url, now, company_id],
                )
                # Upsert into company_sources for full endpoint history
                conn.execute(
                    """INSERT INTO company_sources (company_id, source_type, crawl_url,
                       last_crawled_at, is_active)
                       VALUES (?, ?, ?, ?, 1)
                       ON CONFLICT(company_id, source_type)
                       DO UPDATE SET crawl_url=excluded.crawl_url,
                                     last_crawled_at=excluded.last_crawled_at,
                                     is_active=1""",
                    [company_id, provider, ats_url, now],
                )
            logger.info(f"[OnDemand] Persisted ATS endpoint: {company_id} → {provider} @ {ats_url}")
        except Exception as e:
            logger.debug(f"[OnDemand] ATS cache write failed: {e}")

    def _fetch_custom_json(self, endpoint: str, company_name: str) -> list[dict]:
        import requests
        try:
            r = requests.get(endpoint, timeout=10,
                             headers={"User-Agent": "Mozilla/5.0"})
            if not r.ok:
                return []
            data = r.json()
            items = []
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                for k in ["jobs", "results", "data", "items", "entities", "postings"]:
                    if isinstance(data.get(k), list):
                        items = data[k]
                        break
            jobs = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                title = item.get("title") or item.get("jobTitle") or item.get("name") or ""
                if not title:
                    continue
                locs = item.get("location") or item.get("locations") or ""
                if isinstance(locs, list):
                    locs = locs[0] if locs else ""
                if isinstance(locs, dict):
                    locs = locs.get("city") or locs.get("name") or ""
                jobs.append({
                    "title": title,
                    "company": company_name,
                    "location": str(locs),
                    "url": item.get("url") or item.get("apply_url") or endpoint,
                    "apply_url": item.get("apply_url") or item.get("url") or endpoint,
                    "description": item.get("description") or item.get("content") or "",
                    "_source_type": "custom_api",
                })
            return jobs
        except Exception as e:
            logger.debug(f"[OnDemand] custom JSON fetch failed: {e}")
            return []

    def _infer_sector(self, role: str) -> str:
        """
        Use DeepSeek to classify what industry sector a role belongs to.
        In-session cache: one LLM call per unique role string, not per search.
        At scale: replace _sector_cache with Redis keyed by role.
        """
        import os, requests as req, json as _json

        if not hasattr(self, "_sector_cache"):
            self._sector_cache: dict[str, str] = {}

        role_key = role.lower().strip()
        if role_key in self._sector_cache:
            return self._sector_cache[role_key]

        api_key = os.getenv("DEEPSEEK_API_KEY", "")
        base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")

        if api_key:
            try:
                resp = req.post(
                    f"{base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}",
                             "Content-Type": "application/json"},
                    json={
                        "model": "deepseek-chat",
                        "messages": [{
                            "role": "user",
                            "content": (
                                "What industry sector does this job role belong to? "
                                "Reply with ONLY the sector name, 2-4 words max. "
                                "Examples: 'Technology & Software', 'Financial Services', "
                                "'Healthcare', 'Retail & Commerce', 'Education', "
                                "'Media & Entertainment', 'Manufacturing'.\n\n"
                                f"Role: {role}"
                            ),
                        }],
                        "temperature": 0,
                        "max_tokens": 15,
                    },
                    timeout=10,
                )
                sector = resp.json()["choices"][0]["message"]["content"].strip().strip("'\"")
                logger.info(f"[OnDemand] Phase A: sector inferred → '{sector}' for role '{role}'")
                self._sector_cache[role_key] = sector
                return sector
            except Exception as e:
                logger.debug(f"[OnDemand] sector inference failed: {e}")

        # Only falls here if no API key or LLM call fails
        return "Technology & Software"

    def _discover_and_rank(self, role: str, city: str, n: int):
        """Phase A: live internet company discovery (DDG + Wellfound + YC + Inc42 + Crunchbase)."""
        try:
            from careerloop.sources.company_discovery import CompanyDiscoveryEngine
            engine = CompanyDiscoveryEngine(self.root)
            sector = self._infer_sector(role)
            archetype = self._archetype_engine.get_archetype(role)
            # Use archetype-constrained hint so SerpAPI queries target role type, not just role name
            function_hint = archetype.to_query_constraint()
            src = "SerpAPI" if os.environ.get("SERPAPI_KEY") else "DDG"
            print(f"    sector={sector} — Phase A via {src}+Wellfound+Crunchbase+Inc42+YC...", flush=True)
            engine.discover(city=city, sector=sector, function_hint=function_hint, max_companies=n * 2)
            print(f"    internet discovery done — querying DB for top companies...", flush=True)
            # Targets pulled from DB now enriched by live discovery
            return self.targeting.top_n(
                function=role, city=city, n=0,
                min_function_probability=0.25,
                min_score=50.0,
            )
        except Exception as e:
            logger.warning(f"[OnDemand] Phase A discovery failed: {e}")
            return []

    _GENERIC_JD_SKIP_DOMAINS = frozenset([
        "linkedin.com", "glassdoor.com", "timesjobs.com",
        "shine.com", "foundit.in",
    ])

    def _extract_generic_jd(
        self,
        url: str,
        fallback_title: str = "",
        fallback_snippet: str = "",
    ) -> Optional[dict]:
        """
        P1.3: Generic HTTP + BeautifulSoup JD extraction for URLs not covered
        by ScrapeGraph or IndeedScraper. Gives scoring engine real JD text
        instead of a 20-word snippet, breaking the 47-67 score compression.
        """
        import re
        import requests
        from urllib.parse import urlparse

        if not url:
            return None

        domain = urlparse(url).netloc.lower().lstrip("www.")
        if any(skip in domain for skip in self._GENERIC_JD_SKIP_DOMAINS):
            return None

        try:
            resp = requests.get(
                url,
                timeout=10,
                headers={"User-Agent": "Mozilla/5.0 (compatible; CareerLoopBot/1.0)"},
                allow_redirects=True,
            )
            if not resp.ok or "text/html" not in resp.headers.get("content-type", ""):
                return None
        except Exception:
            return None

        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, "html.parser")

            # Remove boilerplate elements
            for tag in soup(["script", "style", "nav", "header", "footer",
                              "aside", "noscript", "iframe"]):
                tag.decompose()

            # JD container heuristics — ordered by specificity
            CONTAINER_SELECTORS = [
                {"id": re.compile(r"job.?desc|jobDesc|description|content", re.I)},
                {"class": re.compile(r"job.?desc|jobDesc|job.?content|job.?detail", re.I)},
                {"class": re.compile(r"description|content.?body|main.?content", re.I)},
            ]
            text = ""
            for sel in CONTAINER_SELECTORS:
                el = soup.find(attrs=sel)
                if el:
                    candidate = el.get_text("\n", strip=True)
                    if len(candidate) > 200:
                        text = candidate
                        break

            # Fallback: <main> or <article>
            if not text:
                for tag in ("main", "article"):
                    el = soup.find(tag)
                    if el:
                        candidate = el.get_text("\n", strip=True)
                        if len(candidate) > 200:
                            text = candidate
                            break

            # Last resort: largest block
            if not text:
                best = ""
                for el in soup.find_all(["div", "section"]):
                    t = el.get_text("\n", strip=True)
                    if len(t) > len(best) and len(t) > 300:
                        best = t
                text = best

            if not text or len(text) < 150:
                return None

            # Trim to 4000 chars to avoid bloating scorer context
            text = text[:4000]

            # Heuristic title extraction from <h1>
            title = fallback_title
            h1 = soup.find("h1")
            if h1:
                h1_text = h1.get_text(" ", strip=True)
                if 3 < len(h1_text) < 120:
                    title = h1_text

            return {
                "title": title,
                "company": "",
                "location": "",
                "apply_url": url,
                "description": text,
                "skills": [],
                "salary": "",
                "work_mode": "",
                "_extraction_method": "generic_http",
                "_source_url": url,
            }
        except Exception as e:
            logger.debug(f"[OnDemand] generic JD extract failed for {url}: {e}")
            return None

    @staticmethod
    def _retry(fn, retries: int = 2, label: str = ""):
        """M1: Retry wrapper — retries fn up to `retries` times on exception."""
        import time
        for attempt in range(retries + 1):
            try:
                return fn()
            except Exception as e:
                if attempt < retries:
                    logger.debug(f"[OnDemand] {label} attempt {attempt+1} failed ({e}), retrying...")
                    time.sleep(1.5 * (attempt + 1))
                else:
                    logger.debug(f"[OnDemand] {label} all {retries+1} attempts failed: {e}")
        return []

    def _board_search(self, queries: list[str], role: str = "", city: str = "") -> list[dict]:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def _run_ddg_search() -> list[dict]:
            from urllib.parse import urlparse
            search_results = (
                self.search.search_queries(queries)
                if hasattr(self.search, "search_queries")
                else self.search.search_all([{"query": q, "city": "", "site": ""} for q in queries])
            )
            _skip_domains = set(self.profile.jd_extraction_skip_domains)
            _max_scrapes = self.profile.jd_extraction_max_ddg_scrapes
            _scrape_count = 0
            out: list[dict] = []
            for r in search_results:
                url = r.get("url", "")
                if not url:
                    continue
                url_type = classify_url_type(url).value
                if url_type != URLType.INDIVIDUAL_JOB.value:
                    continue
                _domain = urlparse(url).netloc.lower().lstrip("www.")
                _skip = any(s in _domain for s in _skip_domains)
                _can_scrape = self.scraper.available and not _skip and _scrape_count < _max_scrapes
                if _can_scrape:
                    _scrape_count += 1
                data = self.scraper.extract(url) if _can_scrape else None
                if not data and self._indeed.can_handle(url):
                    data = self._indeed.extract(url)
                if not data:
                    data = self._extract_generic_jd(url, fallback_title=r.get("title", ""), fallback_snippet=r.get("snippet", ""))
                if data:
                    extraction_method = data.get("_extraction_method", "scrapegraph")
                    if extraction_method == "scrapegraphai":
                        source_type = "scrapegraph"
                    elif extraction_method == "indeed_direct":
                        source_type = "indeed_direct"
                    else:
                        source_type = "generic_http"
                    out.append({
                        "title": data.get("title", r.get("title", "")),
                        "company": data.get("company", ""),
                        "location": data.get("location", ""),
                        "url": url,
                        "apply_url": data.get("apply_url", url),
                        "url_type": url_type,
                        "description": data.get("description", ""),
                        "skills": data.get("skills", []),
                        "salary": data.get("salary", ""),
                        "work_mode": data.get("work_mode", ""),
                        "_source_type": source_type,
                    })
                else:
                    out.append({
                        "title": r.get("title", ""),
                        "company": "",
                        "location": r.get("source_city", ""),
                        "url": url,
                        "url_type": url_type,
                        "description": r.get("snippet", ""),
                        "_source_type": "search",
                    })
            return out

        def _run_jobspy() -> list[dict]:
            try:
                results = self.jobspy.search_from_queries([
                    {"role": role, "city": city or "India", "query": q} for q in queries[:2]
                ])
                out = [{
                    "title": r.get("title", ""),
                    "company": r.get("company", ""),
                    "location": r.get("location", ""),
                    "url": r.get("url", ""),
                    "apply_url": r.get("url", ""),
                    "url_type": classify_url_type(r.get("url", "")).value,
                    "description": r.get("description", ""),
                    "_source_type": "jobspy",
                } for r in results]
                logger.info(f"[OnDemand] JobSpy: {len(out)} jobs")
                return out
            except Exception as e:
                logger.debug(f"[OnDemand] JobSpy: {e}")
                return []

        def _run_naukri() -> list[dict]:
            try:
                from careerloop.sources.naukri_adapter import search_naukri
                results = search_naukri(role, city, max_results=50)
                logger.info(f"[OnDemand] Naukri: {len(results)} jobs")
                return results
            except Exception as e:
                logger.debug(f"[OnDemand] Naukri: {e}")
                return []

        def _run_monster() -> list[dict]:
            try:
                from careerloop.sources.monster_adapter import search_monster
                results = search_monster(role, city, max_results=50)
                logger.info(f"[OnDemand] Monster/foundit: {len(results)} jobs")
                return results
            except Exception as e:
                logger.debug(f"[OnDemand] Monster: {e}")
                return []

        def _run_glassdoor() -> list[dict]:
            try:
                from careerloop.sources.glassdoor_adapter import search_glassdoor
                results = search_glassdoor(role, city, max_results=30)
                logger.info(f"[OnDemand] Glassdoor: {len(results)} jobs")
                return results
            except Exception as e:
                logger.debug(f"[OnDemand] Glassdoor: {e}")
                return []

        def _run_google_jobs() -> list[dict]:
            try:
                from careerloop.sources.google_jobs_adapter import search_google_jobs
                results = search_google_jobs(role, city, max_results=30)
                logger.info(f"[OnDemand] GoogleJobs: {len(results)} jobs")
                return results
            except Exception as e:
                logger.debug(f"[OnDemand] GoogleJobs: {e}")
                return []

        def _run_cutshort() -> list[dict]:
            try:
                from careerloop.sources.cutshort_adapter import search_cutshort
                results = search_cutshort(role, city, max_results=50)
                logger.info(f"[OnDemand] Cutshort: {len(results)} jobs")
                return results
            except Exception as e:
                logger.debug(f"[OnDemand] Cutshort: {e}")
                return []

        def _run_wellfound() -> list[dict]:
            try:
                from careerloop.sources.wellfound_adapter import search_wellfound
                results = search_wellfound(role, city, max_results=30)
                logger.info(f"[OnDemand] Wellfound: {len(results)} jobs")
                return results
            except Exception as e:
                logger.debug(f"[OnDemand] Wellfound: {e}")
                return []

        def _run_iimjobs() -> list[dict]:
            try:
                from careerloop.sources.iimjobs_adapter import search_iimjobs
                results = search_iimjobs(role, city, max_results=30)
                logger.info(f"[OnDemand] IIMJobs: {len(results)} jobs")
                return results
            except Exception as e:
                logger.debug(f"[OnDemand] IIMJobs: {e}")
                return []

        def _run_instahyre() -> list[dict]:
            try:
                from careerloop.sources.instahyre_adapter import search_instahyre
                results = search_instahyre(role, city, max_results=30)
                logger.info(f"[OnDemand] Instahyre: {len(results)} jobs")
                return results
            except Exception as e:
                logger.debug(f"[OnDemand] Instahyre: {e}")
                return []

        def _run_remoteok() -> list[dict]:
            try:
                from careerloop.sources.remoteok_adapter import search_remoteok
                results = search_remoteok(role, city, max_results=30)
                logger.info(f"[OnDemand] RemoteOK: {len(results)} jobs")
                return results
            except Exception as e:
                logger.debug(f"[OnDemand] RemoteOK: {e}")
                return []

        def _run_remotive() -> list[dict]:
            try:
                from careerloop.sources.remotive_adapter import search_remotive
                results = search_remotive(role, city, max_results=30)
                logger.info(f"[OnDemand] Remotive: {len(results)} jobs")
                return results
            except Exception as e:
                logger.debug(f"[OnDemand] Remotive: {e}")
                return []

        def _run_weworkremotely() -> list[dict]:
            try:
                from careerloop.sources.weworkremotely_adapter import search_weworkremotely
                results = search_weworkremotely(role, city, max_results=30)
                logger.info(f"[OnDemand] WeWorkRemotely: {len(results)} jobs")
                return results
            except Exception as e:
                logger.debug(f"[OnDemand] WeWorkRemotely: {e}")
                return []

        board_fns = [
            ("ddg", _run_ddg_search),
            ("jobspy", _run_jobspy),
            ("naukri", _run_naukri),
            ("monster", _run_monster),
            ("glassdoor", _run_glassdoor),
            ("google_jobs", _run_google_jobs),
            ("cutshort", _run_cutshort),
            ("wellfound", _run_wellfound),
            ("iimjobs", _run_iimjobs),
            ("instahyre", _run_instahyre),
            ("remoteok", _run_remoteok),
            ("remotive", _run_remotive),
            ("weworkremotely", _run_weworkremotely),
        ]

        # M2: track per-source results for health monitoring
        _source_counts: dict[str, int] = {}

        jobs: list[dict] = []
        with ThreadPoolExecutor(max_workers=len(board_fns)) as pool:
            # M1: each board fn wrapped with retry
            futures = {
                pool.submit(self._retry, fn, 2, name): name
                for name, fn in board_fns
            }
            for fut in as_completed(futures):
                name = futures[fut]
                try:
                    results = fut.result() or []
                    _source_counts[name] = len(results)
                    jobs.extend(results)
                except Exception as e:
                    _source_counts[name] = 0
                    logger.debug(f"[OnDemand] board worker {name}: {e}")

        # M2: store health stats on instance for caller access
        if not hasattr(self, "_last_board_health"):
            self._last_board_health: dict[str, int] = {}
        self._last_board_health.update(_source_counts)
        logger.info(f"[OnDemand] Board health: {_source_counts}")

        return jobs


# ── CLI entry ────────────────────────────────────────────────────────────

def main():
    """Usage: python -m careerloop.on_demand "fashion buyer" "Mumbai" 10"""
    import sys
    if len(sys.argv) < 2:
        print('Usage: python -m careerloop.on_demand "<role>" [city] [max_results]')
        sys.exit(1)
    role = sys.argv[1]
    city = sys.argv[2] if len(sys.argv) > 2 else ""
    max_results = int(sys.argv[3]) if len(sys.argv) > 3 else 10
    root = os.getcwd()
    od = OnDemandSearch(root)
    result = od.run(role, city, max_results=max_results)

    print(f"\nOn-demand search: {role} / {city}")
    print(f"Elapsed: {result.elapsed_seconds}s")
    print(f"Keywords: {', '.join(result.keywords_used)}")
    print(f"Targeted companies: {len(result.targeted_companies)} — {', '.join(result.targeted_companies[:5])}{'...' if len(result.targeted_companies) > 5 else ''}")
    print(f"Candidates: {result.candidate_count} → after dedup: {result.after_dedup_count}")
    if result.notes:
        for n in result.notes:
            print(f"  note: {n}")
    print(f"\nTop {len(result.ranked_jobs)} jobs:")
    for i, item in enumerate(result.ranked_jobs, 1):
        job = item["job"]
        print(f"  {i}. [{item['score']}/100] {job.get('company', '')} — {job.get('title', '')}")
        print(f"     {job.get('location', '')} | {job.get('apply_url') or job.get('url', '')}")


if __name__ == "__main__":
    main()
