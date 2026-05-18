# CareerLoop Master Vision — Proposed Amendments

**Source:** Audit pass on 2026-05-18 (see `CAREERLOOP_REUSE_AUDIT.md`).
**Target document:** `careerloop/docs/PRD.md` v1.0 (Canonical Vision).
**Status:** Proposed. Author approval required before applying.
**Author of amendments:** Product audit pass.

> Each amendment names the PRD section, states the change, cites the audit finding that supports it, names the Career-Ops capability that supports the change, and notes whether the roadmap / phase ordering shifts.

---

## Why amendments at all

The PRD v1.0 is internally consistent and forward-looking. The audit did not surface anything that contradicts the vision. What the audit *did* surface is that several PRD sections have **stronger, more battle-tested implementations already sitting in Career-Ops than the PRD currently acknowledges.** The vision is right; the path is shorter than the PRD suggests, *if* we name the assets we already have.

The amendments below are clarifications and integration points, not direction changes.

---

## Amendment 1 — §6 Opportunity Intelligence: explicitly state the two-layer evaluation model

### What changes

Add a paragraph (or new sub-section) to PRD §6 stating:

> Opportunity Intelligence operates in **two layers**:
> 1. **Pre-filter layer** — `careerloop/india_fit_engine.py` scores every discovered job across 14 India-specific dimensions using heuristics and lookup tables. Zero LLM cost. Runs on all discovered jobs.
> 2. **Deep evaluation layer** — A 7-block evaluation (Role, CV Match, Level & Strategy, Comp, Customization, Interview Plan, Legitimacy) runs **only after the user marks a job INTERESTED**. This is the lazy-loaded deep intelligence (Vision v1.6 §4).
>
> The pre-filter compresses the daily 50+ into a triage shortlist (PRD §7). The deep evaluation prepares the shortlist for application.

### Why

Audit Task 4 found that A–G and the India Fit Engine are **complementary, not redundant**. Without naming both layers, builders will either rebuild A–G inside the Fit Engine (token-heavy) or skip A–G entirely (loses the qualitative archetype + interview plan + customization signal).

### Career-Ops capability that supports it

- `modes/oferta.md` — full 7-block evaluation framework, archetype-aware, gap-aware
- `modes/_shared.md` — scoring rubric, archetypes, NEVER/ALWAYS rules
- `careerloop/india_fit_engine.py` — the cheap pre-filter (already built)

### Roadmap impact

None. Aligns Phase 1 (Fit Engine, built) and Phase 2 (deep evaluation wrapper, to build).

---

## Amendment 2 — §9 Company Intelligence: declare lazy-loaded and structured

### What changes

Add to PRD §9:

> Company Intelligence is **lazy-loaded** — it triggers only after the user expresses interest in a job (ledger transition into `SHORTLISTED` or `APPROVED`). It is **never** generated for every discovered job.
>
> Output is **structured, not narrative**: business_model, hiring_intent_signals, stability_signals, culture_signals, realistic_comp_range_inr, interview_loop_pattern, red_flags, positioning_hint, confidence. Persists to the `company_memory` table (Vision v1.6 §5).
>
> The existing `modes/deep.md` is a prompt template only; it is retained as a manual fallback but is NOT the Company Intelligence layer. The Company Intelligence module is `careerloop/company_intel.py` (Phase 2 build).

### Why

Audit Task 7 found that `modes/deep.md` outputs the user a *question* (a 6-axis Perplexity prompt), not an *answer*. PRD §9 as written does not specify that the output must be structured, persistable, and lazy. Without those constraints, the next builder may replicate the prompt-generator anti-pattern.

### Career-Ops capability that supports it

- `modes/deep.md` — existing 6-axis schema is a fine *starting* prompt for the structured extraction
- `careerloop/profile_extended.yml` (and future `company_memory` table)

### Roadmap impact

Promotes Company Intelligence to a named Phase 2 build (PRD §17 currently shows 15% completion with "Research direction exists; not automated"). Amendment makes the work scope concrete.

---

## Amendment 3 — §11 Resume Council: name the final renderer

### What changes

Add to PRD §11:

> The Council's `application_pack.resume_markdown` is rendered to PDF through the **canonical renderer**: `careerloop/council/compiler.py` fills `templates/cv-template.html`, which `generate-pdf.mjs` (Playwright + Chromium) converts to a clean, ATS-compatible PDF with Unicode normalization (em-dash → hyphen, smart quotes → ASCII, zero-width strip).
>
> The Council never invents content. The renderer never invents content. Content generation is fully owned by the Council graph.

### Why

Audit Task 8 found that `generate-pdf.mjs` is a 5★ pure renderer with no coupling. It should be named as the rendering tail of the Council pipeline so future builders don't duplicate PDF generation. It also disambiguates the `modes/pdf.md` flow, which conflates content generation with rendering and should be retired (content half), kept (rendering half).

### Career-Ops capability that supports it

- `generate-pdf.mjs` (renderer, 5★)
- `templates/cv-template.html` + `fonts/` (template + self-hosted fonts)
- `careerloop/council/compiler.py` (compiler step already exists)

### Roadmap impact

None — pure clarification. Removes implicit duplication risk.

---

## Amendment 4 — §13 Application Execution Layer: name the existing prototype

### What changes

Add to PRD §13:

> `modes/apply.md` is the **functional prototype** of the future CareerLoop Chrome extension (Vision v1.6 §12). The workflow is already validated end-to-end with Playwright: detect active Chrome tab → match to existing report → identify form questions → draft per-question answers → user reviews and submits manually. The Chrome extension will execute the same workflow with native DOM hooks instead of an external browser process.
>
> Backend support: the Council's `application_pack` plus a per-question Q&A bank are cached in the `positioning_memory` table (Vision v1.6 §5) when the user marks a job `APPROVED`, so the extension can return cached answers instantly.

### Why

Audit Task 9 found `modes/apply.md` is a 4★ workflow that already enforces the "never submit, user in control" rule. The PRD §13 phrasing ("Future execution: Chrome extension for assisted autofill") under-states what already exists. Naming the prototype lets the Phase 3 extension build inherit a tested workflow instead of reinventing it.

### Career-Ops capability that supports it

- `modes/apply.md` — workflow blueprint
- Playwright integration already used in `modes/auto-pipeline.md` and `modes/scan.md`
- Ledger `APPROVED` status (already in `LEDGER_STATUSES`)

### Roadmap impact

None — clarifies Phase 3 entry point.

---

## Amendment 5 — §14 Learning Loop: reuse the pattern miner

### What changes

Add to PRD §14:

> The Learning Loop is seeded by `analyze-patterns.mjs` (Career-Ops asset), which produces structured analyses across:
> - **Archetype performance** — conversion rates per archetype
> - **Blocker frequency** — geo-restriction, stack-mismatch, seniority, onsite
> - **Remote policy patterns** — conversion by remote/hybrid/onsite bucket
> - **Score-threshold recommendation** — the empirical "no positive outcomes below X" floor
>
> The miner will be ported to Python and repointed at the ledger (`careerloop/learning.py`, Phase 2). Its outputs persist to the `event_timeline` entity (Vision v1.6 §5) and surface in the daily standup ("this week's learning: stop evaluating geo-restricted roles, 0% conversion").

### Why

Audit Task 10 found that `analyze-patterns.mjs` is 4★ and shaped exactly like the Learning Loop PRD §14 demands. The PRD currently describes the Learning Loop abstractly ("what mattered, what should we improve, what should we ignore"); naming the existing analyzer turns it into work that's 70% done.

### Career-Ops capability that supports it

- `analyze-patterns.mjs` (the pattern miner)
- `modes/patterns.md` (the rendering layer)
- `careerloop/application_ledger.py` (the data source, post-migration)

### Roadmap impact

Upgrades PRD §17 row "Persistent memory graph: 10%" — the analysis half is much further along than the row suggests, once the ledger migration is done.

---

## Amendment 6 — §15 Persistent Career Memory: declare one source of truth

### What changes

Add to PRD §15 (or a new sub-section "Single Source of Truth"):

> All job lifecycle state, application history, follow-ups, recruiter contacts, and per-job audit trails live in **one** store: `careerloop/application_ledger.py` (JSON today, SQLite per Vision v1.6 §5 next).
>
> The legacy Career-Ops Markdown stores (`data/applications.md`, `data/pipeline.md`, `data/follow-ups.md`, `data/scan-history.tsv`) are either:
> - **Retired as writers** (`applications.md`, `pipeline.md`, `follow-ups.md`) — replaced by ledger entries
> - **Kept as a generated view** (Markdown tracker) — rendered from the ledger for human readability
> - **Kept as a flat log** (`scan-history.tsv`) — fine for dedup history
>
> `scan.mjs`, the future India portal adapters, the Council, follow-up scheduling, and the Chrome extension all read/write through the ledger. No system maintains a parallel application list.

### Why

Audit Task 3 + Task 10 found dual-write between Markdown trackers and the ledger. The PRD does not currently forbid this. Naming a single source of truth blocks the dual-write problem from getting worse and accelerates Vision v1.6 §5's 6-entity SQLite plan.

### Career-Ops capability that supports it

- `careerloop/application_ledger.py` (the canonical store)
- `templates/states.yml` (canonical-status taxonomy, mappable to LEDGER_STATUSES)
- `modes/tracker.md` (becomes a view, not a writer)

### Roadmap impact

Tightens Phase 1.5 / 1.6 scope. The migration is small (rewire `scan.mjs` output, generate Markdown view) but high-leverage.

---

## Amendment 7 — §17 Tracker: adjust completion estimates based on audit findings

### What changes

Audit-corrected completion estimates for PRD §17:

| System | PRD §17 today | Audit-corrected | Rationale |
|---|---|---|---|
| India-first discovery | 70% | 70% (no change) | ATS slice via `scan.mjs` solid. Naukri/Instahyre/etc. still the gap. |
| Verification & filtering | 60% | 60% (no change) | `verification.py` + India Fit pre-filter ok. Block G hoist pending. |
| Opportunity scoring (14-dim) | 55% | 60% | Heuristic engine is more complete than 55% suggests; LLM hybrid layer next. |
| Decision compression / triage | 25% | 25% | Triage UX still ahead; `modes/ofertas.md` schema reusable. |
| Career state system (modes) | 10% | 10% | Conceptual only. |
| Company intelligence | 15% | 10% | The 15% mostly references `modes/deep.md` which is a prompt template, not intelligence. Honest grade lower. |
| Positioning engine | 5% | 15% | Council `positioning_node` exists and is wired into the graph. Not full, but not 5%. |
| Resume Council (v3) | 40% | 45% | Truth Guard already present (`truth_guard_node`). Humanizer + cover_note/recruiter_message still missing. |
| Humanizer layer | 10% | 5% | The "distributed across stages" framing overstates it. There is no dedicated pass; cliché list exists in `_shared.md` only as a prompt rule. |
| Application execution | 5% | 15% | `modes/apply.md` workflow is a working prototype. The extension is 0%, but the workflow blueprint is real. |
| Chrome extension | 0% | 0% | No change. |
| Follow-up system | 10% | 25% | `application_ledger.transition()` already auto-schedules `follow_up_dates` per `FOLLOW_UP_SCHEDULE`. The miner and drafts (`followup-cadence.mjs`, `modes/followup.md`) exist. Surfacing & UI missing. |
| Interview memory | 0% | 10% | `modes/interview-prep.md` is a 4★ working mode with 7-step framework, question taxonomy, source-attribution rules, and story-bank mapping (`interview-prep/story-bank.md`). No structured DB persistence yet. |
| Persistent memory graph | 10% | 20% | Ledger is functional JSON with full lifecycle + history + 13 statuses + auto-schedules. The 6-entity SQLite is the bigger jump, but the foundation is more than 10%. |
| WhatsApp/transport UX | 20% | 20% | No change. |
| Monetization logic | 30% | 30% | No change. |

**Overall product maturity: ~25–30% of vision** (up from 20–25%, on more accurate accounting).

### Why

The audit revealed several "secretly already built" capabilities (see Reuse Audit §TL;DR). The current §17 numbers under-count them. Higher accuracy = better planning.

### Career-Ops capability that supports it

All of `careerloop/*.py`, especially `application_ledger.py`, `india_fit_engine.py`, `council/`, `apply_route.py`, `verification.py`.

### Roadmap impact

None on direction. Improves visibility on where the build actually is.

---

## Amendment 8 — Phase ordering: A–G evaluation moves from "Phase 2" implicit to "Phase 1.5/2 hinge"

### What changes

Add to PRD §17 phase notes or to a new section "Roadmap clarifications":

> The Career-Ops 7-block A–G evaluation (`modes/oferta.md` + `modes/_shared.md`) is **not** a Phase 2 build. It is a Phase 1.5/2 hinge:
> - In Phase 1.5 it is exposed as a per-job command (user triggers explicitly after expressing interest).
> - In Phase 2 it is automatically invoked between `INTERESTED → APPROVED` ledger transitions and its outputs feed Resume Council's `role_decode_node`, `user_truth_node`, and (eventually) `positioning_node` to reduce LLM cost via cross-feed.

### Why

Audit Task 4 found that A–G output overlaps strongly with three existing Council nodes. Treating A–G as a "later, separate" build risks rebuilding the same analysis inside Council. Naming the cross-feed prevents this.

### Career-Ops capability that supports it

- `modes/oferta.md` (block-by-block evaluation)
- `careerloop/council/graph.py` (role_decode_node, user_truth_node)

### Roadmap impact

Minor reordering only. Both Phase 1.5 and Phase 2 already exist in Vision v1.6 §13.

---

## Amendments NOT proposed (intentionally)

The audit did **not** find reasons to amend:

- §1 What CareerLoop Is / Is Not — accurate.
- §2 Core Problem — accurate.
- §3 User We Are Building For — accurate.
- §4 Core Product Loop — accurate.
- §5 Discovery Engine — accurate (the implementation gaps are tracker work, not vision work).
- §7 Decision Compression — accurate (the implementation will reuse `modes/ofertas.md`, naming this is optional polish).
- §8 Career State Awareness — accurate.
- §10 Positioning Engine — accurate.
- §12 Humanizer Layer — accurate (this is the §17 blocker B2, not a vision problem).
- §16 End-State Vision — accurate.

---

## Summary

Eight amendments proposed. All are **clarifying integrations**, not direction changes. They:

1. Name the two-layer evaluation (pre-filter + deep) explicitly (§6)
2. Lock Company Intelligence as lazy + structured (§9)
3. Name the canonical renderer (§11)
4. Name the live application prototype (§13)
5. Seed the Learning Loop with the existing pattern miner (§14)
6. Declare one source of truth — the ledger (§15)
7. Recalibrate tracker percentages on audit-grade evidence (§17)
8. Lock A–G as a Phase 1.5/2 hinge with cross-feed to Council (§17 / phasing)

The vision holds as-is on direction. The amendments shorten the path between vision and execution by naming the assets we already have.

**Recommendation:** Apply Amendments 1, 3, 5, 6 immediately (lowest risk, highest clarity). Apply Amendments 2, 4, 7, 8 after author review.

---

*End of amendments. No code or canonical-vision file was modified during this pass.*
