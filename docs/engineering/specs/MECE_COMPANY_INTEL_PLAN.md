# MECE Company Intelligence: Implementation Plan

**Status:** Implementation In-Progress  
**PRD Reference:** §9 — Company Intelligence  
**Objective:** Realize the Mutually Exclusive, Collectively Exhaustive (MECE) vision for company research.

---

## 1. The MECE Vectors (D1–D5)

We must populate these 5 distinct data vectors for every interested job to ensure the Resume Council has high-fidelity grounding.

| Vector | Dimension | Primary Source | Tooling |
| :--- | :--- | :--- | :--- |
| **D1** | **Identity & Product** | Company Website / Wiki | `DuckDuckGo` + `WebFetch` |
| **D2** | **Culture & Red Flags** | Glassdoor / Reddit | `scrapegraph_adapter.py` / `Playwright` |
| **D3** | **People & Recruiters** | LinkedIn Job Page / Team | `portal_scraper.py` (Stealth) |
| **D4** | **Role Context** | Job Description (JD) | Native Parser |
| **D5** | **Market & Growth** | Crunchbase / News / PR | `DuckDuckGo` News API |

---

## 2. Methodology & Tooling

### 2.1 Multi-Adapter Research
Instead of a single `requests.get` call, `company_intel.py` will act as an orchestrator for specialized adapters:
- **Stealth Scraper:** Use `careerloop/sources/portal_scraper.py` for LinkedIn Job URLs to extract "Posted by" (Recruiter) data.
- **Structured Scraper:** Use `careerloop/sources/scrapegraph_adapter.py` for Glassdoor/Reddit sentiment extraction.
- **Lightweight Harvester:** DuckDuckGo + standard `WebFetch` for general identity/news.

### 2.2 Concurrency & Stability
- **Asynchronous Execution:** Use `asyncio.gather` or `ThreadPoolExecutor` with a strict **12-second ceiling**.
- **Incremental Harvesting:** Keep any vector that finishes within the timeout; never fallback to `JD_ONLY` if *some* web data exists.
- **Domain Isolation:** Automatically route URLs to the correct adapter (e.g., if domain is `linkedin.com`, use `portal_scraper`).

---

## 3. Implementation Roadmap

### Phase 1: Core Refactor (Current)
- Update `CompanyIntelligenceResult` dataclass to include `recruiter_info` and `red_flags_detail`.
- Refactor `_gather_web_sources` to support multiple concurrent queries.

### Phase 2: LinkedIn & People Extraction
- Wire `portal_scraper.py` to navigate to LinkedIn Job URLs.
- Extract recruiter name, link, and company "About" metadata.

### Phase 3: Culture & Red Flag Layer
- Wire `scrapegraph_adapter.py` to hit Glassdoor public review summaries.
- Extract "Pros/Cons" and "Hiring Status" (layoffs/growth).

---

## 4. Success Metrics
- **Recruiter Link Presence:** >60% on LinkedIn-sourced jobs.
- **Grounded Status:** 100% of runs must achieve at least `PARTIAL` grounding (no `JD_ONLY`).
- **Zero Hallucination:** 0 fabricated funding rounds; `UNKNOWN` is the enforced default.

---

## 5. Risk Mitigations
- **Anti-Bot Gating:** Use stealth Playwright headers for LinkedIn/Glassdoor.
- **Cost Control:** ScrapeGraph is only used for high-value cultural extraction, not general news.
- **Latency:** Strict timeouts per source to prevent a single hang from blocking the Council.
