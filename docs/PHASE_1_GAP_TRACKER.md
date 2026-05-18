# Phase 1 Gap Tracker

## Purpose

Track known gaps discovered while moving from Phase 1 discovery into Phase 2 application intelligence.

## Current status

Phase 1 can discover, classify, verify, score, and shortlist jobs. Recent live run produced:

- Raw search results: 115
- JobSpy results: 70
- India-verified candidate jobs: 35
- Merged unique jobs: 19
- Verified active jobs: 16
- User-visible opportunities: 4

## Gaps

### GAP-001 — Search package mismatch

- **Observed:** Code imported `ddgs`, while `requirements.txt` listed `duckduckgo-search`.
- **Impact:** Fresh discovery failed in environments where only requirements were installed.
- **Status:** Open until adapter supports both or requirements are updated consistently.
- **Owner:** Phase 1 discovery.

### GAP-002 — Heavy optional dependencies mutate global environment

- **Observed:** Installing `scrapegraphai` upgraded/downgraded LangChain, NumPy, Playwright, and related packages.
- **Impact:** Potential conflicts with unrelated local ML/OpenCV/LangGraph packages.
- **Status:** Open.
- **Recommended fix:** Move Phase 1/2 runtime into a project virtual environment and split optional extras.

### GAP-003 — Cutshort deep extraction is slow/unreliable

- **Observed:** Cutshort pages repeatedly timed out at Playwright 30s page load.
- **Impact:** Live discovery run spent several minutes on low-yield URLs.
- **Status:** Open.
- **Recommended fix:** Deprioritize Cutshort in deep extraction or use metadata-only `NEEDS_MORE_DATA` unless user selects the lead.

### GAP-004 — ScrapeGraph extraction can omit location

- **Observed:** Some Naukri/Instahyre pages extracted with blank or incomplete location even when URL contained Indian city names.
- **Impact:** India filter rejected legitimate India roles.
- **Status:** Partially mitigated with URL location inference.
- **Recommended fix:** Add board-specific extraction normalizers and rejection reason separation.

### GAP-005 — Rejection reason is too broad

- **Observed:** Logs say `Rejected post-extraction (non-India)` even when the real reason may be incomplete title/company/JD/apply URL.
- **Impact:** Debugging is harder and valid jobs may appear incorrectly rejected as geography failures.
- **Status:** Open.
- **Recommended fix:** Split `NOT_INDIA`, `INCOMPLETE_EXTRACTION`, `SEARCH_LEAD`, `NOISE`, and `VERIFICATION_FAILED` counters.

### GAP-006 — Old ledger contains pre-lifecycle noise

- **Observed:** Existing ledger includes old noisy entries such as Foundit career-advice article scored as job.
- **Impact:** Historical top recommendations can include non-jobs unless filtered to fresh runs or cleaned.
- **Status:** Open.
- **Recommended fix:** Run a ledger migration/classification pass to mark old articles as `NOISE` or archive them.

### GAP-007 — Company names missing from some board-derived entries

- **Observed:** Some Instahyre/Hirist entries are title-heavy with blank company fields.
- **Impact:** Fingerprinting, company intelligence, and positioning quality degrade.
- **Status:** Open.
- **Recommended fix:** Board-specific parsing and company-name extraction from title/URL/snippet.

### GAP-008 — Company intelligence is not yet lazy-loaded from memory

- **Observed:** Memory schema has `company_memory`, but discovery/scoring does not yet consult it.
- **Impact:** Phase 1 fit scores use limited company context.
- **Status:** Expected Phase 2 work.
- **Recommended fix:** Trigger company intelligence only after user interest and persist summaries.

### GAP-009 — Master CV source missing in current workspace

- **Observed:** No root `cv.md` found.
- **Impact:** Resume Council cannot safely rewrite resume sections without a canonical source.
- **Status:** Open.
- **Recommended fix:** Add/confirm `cv.md` or use `config/profile.yml` + `profile_extended.yml` as reduced evidence mode.

### GAP-010 — Full council UX not implemented

- **Observed:** Current runner can shortlist jobs but cannot prepare a truth-guarded application pack.
- **Impact:** User must manually bridge from recommendation to application materials.
- **Status:** Phase 2 target.
- **Recommended fix:** Implement `careerloop/council/` one-job orchestration.

### GAP-011 — Google Docs / External JD link scraping

- **Observed:** Discovery engine fails to follow 'full JD' links that point to external docs (Google Docs, Notion, PDF) found in LinkedIn posts or social feeds.
- **Impact:** High-fidelity JDs are missed, resulting in poor fit scores or manual intervention.
- **Status:** Open.
- **Recommended fix:** Add a 'Follow External Lead' stage to the discovery adapter to fetch and scrape linked document content.

## Tracker conventions

- `Open`: Known gap, not solved.
- `Partially mitigated`: Patch exists but needs hardening.
- `Done`: Fixed and validated.
- `Deferred`: Intentionally left for later phase.
