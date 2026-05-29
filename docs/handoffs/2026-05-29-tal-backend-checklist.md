# Tal Inspiration — Backend Checklist
**Date:** 2026-05-29
**Source:** `docs/Tal Inspiration/tal_ux_inspiration.md` + `chat_stabilization_mece.md`

Status of every backend-side capability the Tal vision requires. ✅ done · 🟡 partial · ⬜ not started.

---

## A. Interactive Chat Onboarding (Tal §2)

| # | Tal requirement | Status | Evidence / Notes |
|---|-----------------|--------|------------------|
| A1 | Conversational onboarding (not a form) | ✅ | `onboarding_flow.py` — full chat state machine, proven 7/7 E2E |
| A2 | "What's your full name?" identity hook | ✅ | `_handle_idle` asks for name when Proxycurl configured |
| A3 | LinkedIn identity search by name | ✅ | `identity_provider.py::LinkedInIdentityProvider.search_candidates` — SerpAPI Google search (`SERPAPI_KEY`, no paid per-profile API). **Needs `SERPAPI_KEY`.** |
| A4 | "Is this you?" rich profile card | ✅ | `_handle_identifying` builds card; surfaced via `chat/message` `cards[0].type=="identity_confirmation"` |
| A5 | Confirm → auto-hydrate profile | ✅ | `_handle_profile_confirmation` hydrates from candidate; CV step fills proof points |
| A6 | "Search again / enter manually" fallback | ✅ | NO → CV path; no match → CV path (graceful) |
| A7 | Resume capture after identity | ✅ | After confirm, asks for CV (or "skip") |
| A8 | Gap-fill remaining fields | ✅ | `STEP_COLLECTING` via `OnboardingAgent` |
| A9 | Remove hardcoded mock LinkedIn data | ✅ | Old mock `linkedin_scraper.py` replaced with real SerpAPI delegate; no fabricated profiles |
| A10 | **Filter search to verify it's actually the user** | ✅ | `_name_matches` — first name must match + ≥60% token overlap, else filtered (falls back to CV; never claims a stranger is them) |

**Onboarding verdict:** LinkedIn-first is **built and wired** on SerpAPI Google search with a name-match filter, dormant until `SERPAPI_KEY` is added. CV-first is live and proven. No mocks remain. No new paid service.

---

## B. Tinder-Swipe Job Cards (Tal §3, §4)

| # | Tal requirement | Status | Evidence / Notes |
|---|-----------------|--------|------------------|
| B1 | Company logo on card | 🟡 | `logo_url` always returned (`serializers.company_logo`): real logo if domain known, else initials avatar. **Real logos need `companies.logo_url`/`domain` backfill (all NULL today).** |
| B2 | Job title | ✅ | `BriefItem.title` |
| B3 | Company name | ✅ | `BriefItem.company` (falls back to `jobs.company_name`) |
| B4 | Location | ✅ | `BriefItem.location` |
| B5 | Fit score + color tier | ✅ | `fit_score` + `fit_tier` (strong/good/weak) |
| B6 | Salary range | 🟡 | `salary_min/max/currency` returned; **NULL for 5 real jobs (scraper doesn't extract salary yet)** |
| B7 | Description snippet | 🟡 | `description` returned (≤280 char); **empty for 5 real jobs (no jd_text scraped)** |
| B8 | Swipe right → shortlist + queue pack | ✅ | `POST /jobs/{id}/save` → `match_status=saved` |
| B9 | Swipe left → skip/discard | ✅ | `POST /jobs/{id}/skip` → `match_status=skipped` |
| B10 | Swipe up → deep-inspect company | 🟡 | Via `POST /chat/message` "company intel" (supervisor path); no dedicated endpoint yet |
| B11 | Verified job link (liveness) | 🟡 | `apply_url`/`source_url` + `verified_active` flag returned; live re-check not run per-request |
| B12 | Outreach pack (recruiter name + DM) | ⬜ | `/jobs/{id}/people` + packs endpoints not built yet (deferred MVP) |
| B13 | Dynamic deep-inspect Q&A | ✅ | `POST /chat/message` → supervisor → company intel |

**Job-card verdict:** All card **fields are wired into the API**. The gaps are **data population** (logos, salary, descriptions for scraped jobs) — not API gaps. Cards render today with initials avatars + fit color.

---

## C. Conversational Intelligence (chat_stabilization_mece.md)

| # | Issue from MECE doc | Status | Notes |
|---|---------------------|--------|-------|
| C1 | State machine cages users | ✅ resolved | New 3-node supervisor + ActionResolver (not the old 5-bucket router) |
| C2 | "find me on LinkedIn" misrouted to SCAN_JOBS | ✅ N/A | Old `ChatIntentAgent` not used by supervisor; ActionResolver has ~17 intents |
| C3 | Hardcoded brief-ready chokepoint overwrite | ✅ resolved | Not present in current `supervisor_graph.py` |
| C4 | No UPDATE_PROFILE intent (re-onboard from chat) | ⬜ | `UPDATE_PROFILE` action not in `ActionType`/`ToolRegistry`. To let a PROFILE_READY user say "update my LinkedIn", add an `UPDATE_PROFILE` action that re-enters onboarding. **Not built.** |

---

## Remaining backend work (prioritized, post-MVP)
1. **Add `SERPAPI_KEY`** → flips LinkedIn-first onboarding live (A3–A5, A10).
2. **Company logo + domain backfill** → real logos (B1). Clearbit enrichment or crawler fix to populate `companies.domain`/`logo_url`.
3. **Scraper: populate `jd_text` + `salary_min/max`** on real jobs → descriptions + salary on cards (B6, B7).
4. **`UPDATE_PROFILE` intent** → conversational re-onboarding / "find me on LinkedIn" from an active session (C4).
5. **Outreach/people + packs endpoints** (B12) and per-request liveness (B11) — deferred MVP scope.

Nothing in 1–5 blocks the first frontend: auth, onboarding, TAL list, job detail, save/skip, and chat all work today.
