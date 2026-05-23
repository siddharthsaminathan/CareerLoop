# Siddharth Search — Bug Registry

> Live audit of issues found across runs. Fix status tracked here.

---

## Run Summary

| Run | City | Candidates | Dedup | Ranked | Elapsed | Phase A | Status |
|-----|------|-----------|-------|--------|---------|---------|--------|
| Run 1 | Bangalore | 151 | 100 | 25 | 343.9s | CRASHED (limit= kwarg) | ❌ DB fallback |
| Run 2 | Bangalore | 138 | 90 | 25 | 327.6s | CRASHED (sector= missing) | ❌ DB fallback |
| Run 3 | — | — | — | — | — | FIX APPLIED (LLM infer) | 🔜 pending |

---

## Active Bugs

### BUG-001 — Phase A never searched internet (early-return guard) ✅ FIXED
- **Symptom**: Phase A appeared to run but always returned DB companies — real internet sources (DDG, Wellfound, Crunchbase, Inc42, YC) never fired
- **Root cause**: `discover()` had an early-return guard: if DB already had ≥ `max_companies//2` entries for that city+sector, it returned DB results immediately without any HTTP calls. DB had 62 companies → threshold always hit.
- **Fix**: Removed early-return guard entirely. `discover()` now always fires all internet sources and upserts new companies on top of existing DB records. DB is the write-through cache, not the escape hatch.
- **Also fixed**: Removed `targeting.top_n()` DB fallback from `on_demand.py` — if Phase A returns 0, we note it and continue (board search still runs). No silent DB substitution.

### BUG-002 — City filter missing: off-city jobs score high ✅ FIXED
- **Symptom**: Hyderabad, Noida, Pune jobs appear in Bangalore search results
  - Run 2: BukuWarung (Hyderabad) at #5, #9; CRED (Hyderabad) at #4; Paytm Noida at #6,#14,#15,#17,#19,#20,#21; Out of the Blue (Pune) at #13
- **Root cause**: No post-scoring city filter. IndiaFitEngine scores job relevance but doesn't penalise wrong city hard enough.
- **Fix needed**: Post-scoring filter — if city search is "bangalore", reject jobs where `location` contains none of `[bangalore, bengaluru, remote, india]`. Or apply hard -20 penalty in scorer.

### BUG-003 — Company flooding: Paytm takes 8/25 slots ✅ FIXED
- **Symptom**: Run 2 top 25 has 8 Paytm jobs (#6, #11, #14, #15, #17, #18, #19, #20, #21)
- **Root cause**: No per-company result cap in ranking
- **Fix needed**: Cap results per company at 2-3 in the final ranked output. Add `max_per_company=3` to `top_n()`.

### BUG-004 — Rejected company types not enforced ✅ FIXED
- **Symptom**: Cognizant (#16 in Run 2) is IT outsourcing — exactly what `rejected_company_types: [it_outsourcing]` should block
- **Root cause**: `rejected_company_types` field in `profile_extended.yml` is loaded but not wired into the scoring or filter pipeline
- **Fix needed**: In `_scrape_targeted_companies()` or `_board_search()`, check company against `rejected_company_types` and skip or penalise.

### BUG-005 — Role filter gaps ✅ PARTIALLY FIXED
- **Symptom**: Engineering Manager (#2,#3,#6,#17), Product Manager (#11,#14,#18,#19,#20), Technical Operations (#21), DevOps (#15) slip through
- **Root cause**: Not in `rejected_roles` list
- **Fix applied**: Added `"Product Manager"` and `"Engineering Manager"` to `profile_extended.yml`
- **Still needed**: `"Technical Operations"`, `"DevOps Engineer"`, `"Data DevOps"` — add if confirmed unwanted

### BUG-006 — Recruiter job postings slip through ✅ FIXED
- **Symptom**: Run 2 #24 "HireGenie | Finance Recruitment Expert hiring AI Product Engineer" — this is a recruiter firm posting a JD, not a direct employer
- **Root cause**: No filter for recruiter/staffing firm posts
- **Fix needed**: Title-level check — if title contains `"Recruitment Expert"`, `"Staffing"`, `"| Hiring"`, `"Expert hiring"` → reject

### BUG-007 — PM-domain keywords inflate PM role scores ✅ FIXED
- **Symptom**: "AI Product Engineer" keyword extraction produces `['roadmap', 'pm', 'user research', 'strategy']` — these are PM terms, so PM job postings score high
- **Root cause**: `IndiaFitEngine` keyword extraction reads "Product" in role title → extracts PM-domain terms. Siddharth is a **builder/engineer**, not a PM.
- **Fix needed**: Keyword seeding should use `confirmed_skills` from `profile_extended.yml` as scoring anchors, not role-name-derived PM terms. Override keywords for engineering roles.

### BUG-008 — Blank company names from generic_http ❌ OPEN
- **Symptom**: Run 2 #8, #10, #22 show `company=?` and `location=` empty — generic_http extraction failed to parse company name
- **Root cause**: `generic_http` tier 3 scraper returning raw text without structured parsing
- **Fix needed**: Extract company name from page `<title>` or OG tags as fallback. At minimum, extract from URL domain.

### BUG-009 — DB fallback hides Phase A failure silently ✅ FIXED
- **Symptom**: Notes field says `'Phase A: running live employer discovery'` even when Phase A crashed
- **Root cause**: Note is written before Phase A runs, not after. Silent fallback to DB companies with no indication in output stats.
- **Fix needed**: Write `'Phase A: FAILED (reason) — using DB fallback'` in notes when Phase A crashes.

---

## Run 2 Quality Audit

**Actual good matches (should apply):**
| # | Job | Company | Notes |
|---|-----|---------|-------|
| 1 | AI/ML Engineer (LLMs, RAG Agent Systems) | IAI solution | Bangalore, LLM+RAG exact fit |
| 5 | Applied AI Engineer - AI/ML | BukuWarung | Hyderabad — off-city but role is perfect |
| 7 | Generative AI Platform Infra Engineer | Cargill | Bangalore — infra-heavy, might be too infra |
| 9 | AI Product Engineer | BukuWarung | Hyderabad — off-city but title is exact |
| 25 | AI Applications Engineer | Oleria | Bangalore, unknown company |

**Noise (should never appear):**
- #2,#3,#6,#17: Engineering Manager — management, not engineering
- #4,#5,#9: Hyderabad (off-city for Bangalore search)
- #11,#14,#18,#19,#20: Paytm Product Management — PM roles
- #13: Pune (off-city)
- #15: DevOps — infra only
- #16: Cognizant — IT outsourcing, rejected company type
- #21: Technical Operations
- #24: HireGenie recruiter posting

**Signal-to-noise Run 2: 5/25 (20%) — needs improvement**

---

## Known Limitations (not bugs, design constraints)
- Glassdoor blocked — returns 403 on scrape; no integration
- Naukri adapter present but rate-limited — adds noise
- `generic_http` tier 3 has no structured extraction — returns titles only, no JD text
- Crawl cache not yet warmed for Run 3 (Phase A will call LLM for sector classification for first time)
