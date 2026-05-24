# Dev Blog — 2026-05-24: E2E Package Assembly & Direct LinkedIn Search Fallbacks

## What Was Done
- **Package Compilation & Rendering:** Implemented `PackageAssembler` to compile tailored resume markdowns, cover letters, and outreach packs. Renders classic-ats and product-engineer PDFs on disk via local headless Playwright.
- **Supervisor Integration:** Hooked package assembly directly into the `pack_generating_node` of `careerloop/session/supervisor_graph.py`, returning immediate absolute file paths to the user.
- **Foolproof LinkedIn Search Fallbacks:** Replaced complex boolean queries on LinkedIn with multiple, hyper-targeted, individual search fallbacks (Recruiter, Talent Acquisition, Engineering Heads).
- **Direct Company Profile Pages:** Pre-computed direct, official company profile page URLs using company slug normalization (e.g. `linkedin.com/company/bukuwarung`).
- **E2E Validation:** Ran `run_assembly_test.py` and `run_council.py` against BukuWarung, generating high-fidelity PDFs, cover letters, and outreach packs with clickable direct links.

## Key Decisions
- **Direct Fallbacks:** Provided multiple individual search buttons instead of a single merged boolean query, stopping LinkedIn search parser crashes.
- **Direct Company Slugs:** Resolved direct company profile links directly using safe normalization slug logic.

## Issues Encountered
- **LinkedIn Boolean Search Failures:** Confirmed that complex queries like `BukuWarung Talent Acquisition OR Head of Engineering` return zero results on LinkedIn. Resolved by splitting into clean, individual, high-probability keywords.
- **DeepSeek Read Timeout:** Witnessed global read timeouts on DeepSeek API endpoint under high load. Handled by fallback configurations in local E2E test runs.

## Files Changed
- [careerloop/package_assembly.py](file:///Users/siddharthsaminathan/projects/CareerLoop/careerloop/package_assembly.py)
- [docs/product/TECH_ROADMAP.md](file:///Users/siddharthsaminathan/projects/CareerLoop/docs/product/TECH_ROADMAP.md)
- [docs/tech-backlog/TRACKER.md](file:///Users/siddharthsaminathan/projects/CareerLoop/docs/tech-backlog/TRACKER.md)
- [docs/product/PRD.md](file:///Users/siddharthsaminathan/projects/CareerLoop/docs/product/PRD.md)

## Next Session
- Fix score compression: fetch full JDs for JobSpy results before scoring.
- Seed Mumbai/Remote company database in SQLite fallback DB.
