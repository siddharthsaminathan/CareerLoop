# CareerLoop — Master Landing Page Vision

**Author:** Siddharth Saminathan + LLM Council (Haiku / Sonnet / Opus 4.7)  
**Date:** 2026-05-21  
**Status:** Canonical Landing Page Source of Truth  
**Purpose:** Every word on the landing page must trace back to a claim in this document. Every claim must be defensible by the product as it exists today.

---

## 0. The One Sentence

> **You're too good to be spraying 100 applications into the void. CareerLoop finds the 5 that actually fit — and makes you impossible to ignore.**

*Supporting subhead: "Found 57 jobs today. Only 8 clear your personal threshold. Apply to 5. Save 3. Ignore the rest."*

---

## 1. What CareerLoop Is

**CareerLoop is a career decision engine for Indian professionals.**

It does one thing no other product does: compresses 100 noisy job opportunities into 5 intelligent decisions, then executes on them.

The full loop:

```
Discover → Verify → Score → Compress → Research → Position → Tailor → Humanize → Apply → Learn
```

Every step feeds the next. Every outcome feeds back. The system gets smarter with every application.

### What CareerLoop Is NOT

- ❌ **Not a job board.** We don't host listings. We pull from everywhere and filter ruthlessly.
- ❌ **Not a resume builder.** We don't ask you to drag-and-drop sections. We surgically adapt your real experience.
- ❌ **Not a chatbot.** You don't chat with your career. The system executes; you decide.
- ❌ **Not an ATS spray tool.** We don't help you blast 500 applications. We help you send 5 that actually land.

### Core Philosophy

> *"The user should make decisions. The system should handle the chaos."*

---

## 2. Who This Is For

**Primary ICP:** Indian professionals trying to improve their career situation.

This includes freshers, employed switchers, AI/tech workers, analysts, consultants, burned-out employees, and people escaping toxic jobs.

**Their emotional state when they find us:** anxious, overwhelmed, tired, uncertain, overprompting ChatGPT, manually managing chaos across 8+ browser tabs.

**The job we're really doing:** Reducing psychological load. The user should feel: *"I am no longer handling my career transition alone."*

---

## 3. The Pain — Why This Exists

### Pain 1: Platform Fragmentation

The Indian job seeker lives across Naukri, LinkedIn, Instahyre, Wellfound, CutShort, Hirist, IIMJobs, Foundit, company career pages, and 15 WhatsApp groups. Each has its own UI, saved-search logic, and notification spam. They are not overwhelmed by one platform — they are overwhelmed by the *fragmentation* of ten.

**What CareerLoop does:** Discovery layer collapses this into a single, verified, scored, deduplicated queue. India-first geographic hard filter. Only verified opportunities survive.

### Pain 2: AI Slop Is Making Applications Worse

Indian professionals have discovered ChatGPT writes resumes. What they haven't discovered is that ChatGPT writes *obviously AI-generated resumes* — full of "spearheaded," "leveraged," "orchestrated," and other tells that recruiters now filter on sight. AI-generated applications are becoming a negative signal. The more people use ChatGPT for resumes, the worse the problem gets for everyone.

**What CareerLoop does:** The Humanizer layer removes AI slop, corporate filler, fake confidence, unnatural phrasing, and keyword spam. **The bar:** *"Looks like a thoughtful human wrote this."* The Truth Guard prevents hallucinated skills and invented experience. Every claim is grounded in the user's actual CV.

### Pain 3: Application Fatigue With Zero Signal

Indian professionals apply to 100+ jobs. They get 90 ghosts, 7 rejections, maybe 3 callbacks. None of the rejections tell them *why*. There is no learning loop. Every application is starting from scratch. Every rejection is wasted information.

**What CareerLoop does:** The Persistent Career Memory Graph captures what worked, what didn't, which companies responded, which positioning angles converted. Every rejection becomes training data for the next application. The system compounds. The hit rate improves with every cycle.

### Pain 4: Weak Positioning

Most resumes are generic — same bullet structures, same vague verbs, same positioning regardless of the company or role. They don't answer the question: *"Why this person for this role right now?"*

**What CareerLoop does:** The Positioning Engine + Resume Council surgically adapts a professional identity to resonate with a specific company's needs — without compromising truth, seniority, or privacy. 8-stage structured compiler. Not freeform generation. Not keyword stuffing. Strategic representation.

### Pain 5: Decision Paralysis

100+ open tabs. 57 jobs found. No way to know which 5 matter. The user doesn't need more jobs — they need fewer, better decisions.

**What CareerLoop does:** Decision Compression — the core wedge. 100 jobs scored across 14 dimensions against the user's actual profile. Compressed to 5 actionable decisions. Not a dump of listings. A decision framework.

---

## 4. How It Works — The Architecture

### The Full Pipeline

```
cv.md (your real experience, never hallucinated)
    ↓
S1: Parse → Structured canonical resume
S2: Preservation Contract → Lock what cannot change
    ↓
S3: Company Intelligence → MECE 5-vector research on target company
    - Identity & Product (company website, Wiki)
    - Culture & Red Flags (Glassdoor, Reddit)
    - People & Recruiters (LinkedIn, team pages)
    - Role Context (JD parsing)
    - Market & Growth (Crunchbase, news, PR)
    ↓
S4: Role Decode → Extract the "Hidden JD" — what they actually want
S5: User Truth → Map your evidence to role requirements
    - Strips private constraints (salary, location) before any LLM sees them
    ↓
S6: Positioning Strategy → Narrative angle + stance (PUSH / STRETCH / HOLD / SKIP)
    Answers: "Why this person for this role right now?"
    ↓
S7: Section Rewrites → Surgical per-section tailoring
    - Returns structured bullet arrays, not markdown blobs
    - 3-worker parallel execution with retry on rate limits
    ↓
S8: Truth Guard → Semantic claim validation
    - Flags unsupported, exaggerated, or fabricated claims
    - Repairs only within evidence bounds
    ↓
Humanizer → 5-phase tone adaptation
    - Removes AI slop, corporate filler, fake confidence
    - Structure validation pre/post — rejects rewrites that lose bullets
    ↓
Compiler → Deterministic assembly (Python, not LLM generation)
    - Zero hallucination risk at assembly stage
    ↓
Renderer → 10 HTML templates + PDFs
    - Post-render validator: hard fail on structure loss
    - 70 stabilization tests passing
    ↓
Delta Report → Tailoring depth + humanization delta + cope detection
```

### What Makes This Different From Every Competitor

| Competitor | What They Do | What They Don't Do |
|-----------|-------------|-------------------|
| Teal | Resume builder + job tracker | No discovery, no verification, no scoring, no positioning, no memory graph |
| Simplify | Application autofill | No discovery, no tailoring, no research, no learning loop |
| Kickresume | Resume templates | No pipeline, no intelligence, no humanization |
| Rezi | ATS keyword optimization | No discovery, no decision compression, no truth guard |
| Jobscan | ATS match scoring | Single JD vs resume only. No discovery, no positioning, no memory |
| **CareerLoop** | **Full-loop career decision engine** | **Does everything above, end to end, with compounding memory** |

Every competitor is a point solution (one step in the pipeline). CareerLoop is the full loop. Individual features can be copied. The feedback loop cannot — it requires the whole system to exist.

---

## 5. The Moats — Why This Is Defensible

### Moat 1: Persistent Career Memory Graph (Strongest)

**What it is:** SQLite-based memory system with 6 entities (Users, Strategic Tracks, Application Ledger, Company Memory, Positioning Memory, Event Timeline). Every application, rejection, interview, and recruiter interaction feeds back in.

**Why it's defensible:** This is a compounding data asset that gets better with every session. Like Spotify's Discover Weekly — the data *is* the product, and you cannot bootstrap it with funding. A competitor cannot replicate your career history. Switching cost increases with every cycle.

**Proof it exists:** Ledger + company_registry + SQLite schema live. Application ledger tracks 13 status states. Company memory persists per-company research. Positioning memory tracks what angles converted.

### Moat 2: Resume Council 8-System Architecture

**What it is:** Not a single LLM call with a big prompt. Eight specialized systems with cross-validation, each independently testable. Truth Guard validates claims against evidence. Humanizer removes slop without destroying structure. Compiler is deterministic Python, not generative.

**Why it's defensible:** Single-pass LLM generation (what every competitor does) is fundamentally undefendable — any competitor can call an LLM with a prompt. The Council's architecture is a process moat. A competitor cannot clone this by reading the PRD; they would need to build the same multi-stage validation pipeline, which is months of engineering.

**Proof it exists:** 1245-line graph.py implementing LangGraph StateGraph. 8 nodes. 6 JSON schema-validated LLM calls. 70 stabilization tests passing. 52% tailoring delta on real runs.

### Moat 3: Humanizer + Truth Guard as Anti-Slop Antibodies

**What it is:** A 5-phase tone adaptation pipeline that removes AI language, corporate filler, fake confidence, and unnatural phrasing. Truth Guard does semantic claim validation — flags fabricated, exaggerated, and unsupported claims.

**Why it's defensible:** This moat gets *stronger* as AI saturation increases. Every new ChatGPT user makes CareerLoop's value more apparent. The anti-slop signal compounds with market adoption of AI writing tools. This is a timing moat — it appreciates over time.

**Proof it exists:** 30K-line humanizer.py. 33K-line truth_guard.py. Banned word lists. Structure validation pre/post. 29/29 humanizer unit tests passing. Cope detection in delta reports.

### Moat 4: Open-Source + Data Contract as Trust Moat

**What it is:** The system is open source. The Data Contract explicitly separates User Layer (never auto-updated, personalization goes here) from System Layer (auto-updatable, don't put user data here). The rule: *"NEVER hardcode metrics — read them from the user's files at evaluation time."*

**Why it's defensible:** In an era of AI data ethics concerns and "we train on your data" terms of service, the Data Contract is a positioning wedge that closed competitors cannot claim. Trust is the hardest thing to compete on. Open-source means the user can audit the pipeline.

**Proof it exists:** CLAUDE.md §Data Contract. AGENTS.md §Data Contract. DATA_CONTRACT.md. Public GitHub repo. Ethical use guidelines: no auto-submit, quality over quantity, respect recruiters' time.

---

## 6. What Is True Today (Product Maturity)

| System | Completion | What Exists |
|--------|-----------|-------------|
| India-first Discovery | 75% | ATS adapter, Spire AI adapter, portal scraper, JobSpy (LinkedIn/Indeed/Glassdoor), on-demand search, role keywords, 15-sector MECE taxonomy |
| Verification & Filtering | 60% | detect_ats_pass.py, liveness checker, search page rejection, stale job detection |
| Opportunity Scoring (14-dim) | 55% | function_probability.py + metrics.py, 14 weighted dimensions, heuristic scoring (no LLM cost per job), 141 jobs scored, avg 62.8/100 |
| Decision Compression | 20% | Modes defined, logic exists in pipeline. UX NOT built. This is the P0 gap. |
| Career State System | 10% | 4 modes conceptualized (Hunt/Upgrade/Explore/Emergency). NOT implemented. |
| **Company Intelligence** | **60%** | MECE 5-vector research engine live. 5 parallel queries. DuckDuckGo + Playwright + ScrapeGraph. PARTIAL grounding achieved on real runs. Hallucination inhibition via grounded synthesis. |
| Positioning Engine | 30% | S6 wired with JSON schema validation. Narrative angle + stance + proof point selection. Tailoring delta substantial post-S7 fix. |
| **Resume Council (v3)** | **80%** | Full 8-system pipeline. 3-worker parallel S7. Structured bullet contract. Truth Guard semantic validation. Deterministic compiler. 52% tailoring delta on real runs. |
| Humanizer Layer | 60% | 5-phase pipeline. Anti-slop word lists. Structure validation pre/post. Markdown safety gate. Currently producing near-zero actual edits (0.21% delta on last run) — prompt assertiveness needs tuning. |
| **Resume Rendering** | **80%** | 10 HTML templates. PDF generation. NormalizedResume single data contract. Post-render validator (10 rules). Hard fail on structure loss. 70 stabilization tests. |
| Validator / QA | 70% | 10/10 rules pass. collapsed_bullet_marker fixed. possible_truncation de-fanged. 64 tests. |
| Application Execution | 15% | modes/apply.md prototype. Chrome extension NOT started. |
| Interview Memory | 25% | interview-playbook skill auto-extracts learnings. Patterns after 2+ interviews. |
| Persistent Memory Graph | 25% | Ledger + company_registry + SQLite schema live. 6 entities mapped. |
| Monetization Logic | 30% | Strategic understanding solid. Target: $9/mo individual, $29/mo pro. No payment infrastructure built. |

**Overall product maturity: ~45-48% of the 16-part PRD vision.**

---

## 7. What Is NOT True (Honest Gaps)

These are claims we CANNOT make on the landing page because the product doesn't do them yet:

- ❌ **"WhatsApp-first"** — Transport at 15% conceptual. Not built. Don't mention WhatsApp on the landing page.
- ❌ **"Autonomous"** — The system requires user review and approval at every decision point. This is by design (ethical use), not a bug. Don't claim autonomy.
- ❌ **"Chrome extension"** — 0%. Not started. Don't mention it.
- ❌ **"Apply with one click"** — Application execution at 15%. The system prepares packs; the user submits manually.
- ❌ **"AI career coach"** — Interview memory at 25%. Patterns after 2+ interviews only. Not a coaching product yet.
- ❌ **"500+ jobs discovered"** — Target, not reality. Current: 141 jobs, 33 GO (70+).
- ❌ **Any specific salary/comp numbers** — Monetization at 30%. Pricing not validated.

---

## 8. The Vision — Where We're Going (North Star)

> This section belongs BELOW THE FOLD on the landing page. "Where we're going." Not "what we are today."

**End-state:** CareerLoop feels like a recruiter + a strategist + a researcher + a career coach + an execution operator + a brutally honest editor + a memory system — working together, 24/7, for one user.

**The daily experience (v2.0):**

```
Morning.
Found 57 jobs.
Only 8 clear your personal threshold.
My recommendation:
Apply to 5 today.
Save 3.
Ignore the rest.
Why: The rest are too sales-heavy, startup-chaotic, or exhibit weak salary signals.
Reply: go = prepare 5 applications | review = show one by one | more = loosen filters
```

**The four application paths (v2.0):**
1. Direct Application (ATS or career portal) — fully covered
2. Recruiter Inbound — evaluate, prep positioning, draft reply, fast-track Council
3. Warm Referral — find employees at target company, identify connectors, draft outreach
4. Cold Outreach — find hiring manager, draft cold DM/email, personalize per company

**The People Graph (v3.0):** Every recruiter who replied, every hiring manager who responded, every referral that converted — these compound into a people graph. The system learns which outreach patterns work per sector, which companies are referral-friendly, which recruiters are responsive. *This is the real long-term moat. Not scraped job counts. Career transition conversion rate.*

---

## 9. Competitive Positioning Map

```
                    DISCOVERY LAYER
                         │
          Job boards     │     CareerLoop
          (Naukri,       │     (full loop:
          LinkedIn)      │     discover→verify
                         │     →score→compress
                         │     →research→position
                         │     →tailor→humanize
                         │     →apply→learn)
                         │
    ─────────────────────┼──────────────────────
                         │
          Spreadsheets   │     Resume builders
          + ChatGPT      │     (Teal, Rezi,
          (manual)       │     Kickresume,
                         │     Jobscan)
                         │
                    EXECUTION LAYER
```

CareerLoop is the only product in the top-right quadrant: both discovers AND executes.

---

## 10. The User's Proof Points (Siddharth Saminathan)

> These are the metrics and achievements that make the product credible. Feature on the landing page as social proof — "built by someone who actually does this."

- **Emote (emotenow.app):** Built AI companion from 0 to 450+ users, 40+ power users, 13-15% weekly retention. Reduced inference cost from $1.20 to $0.023 per conversation (**50x**). Improved latency from 15s to 3s (**5x**). Built Reddit bot reducing outreach from 6-8 hours to 30-40 minutes, improving activation from ~20% to ~75%.
- **Omnex Systems (AquaPro AI):** Built production multi-agent AI for manufacturing quality workflows (DFMEA, PFMEA, Control Plans, 8D). Reduced response latency from 12.5s to 8s. Built observability infrastructure.
- **Akkodis AB (Ericsson client):** Led Azure to on-prem PostgreSQL migration. Owned data pipeline redesign for enterprise reporting. Improved reporting accuracy by 5%.
- **Education:** M.Sc. Statistics and Machine Learning, Linköping University, Sweden. Thesis: ML pipeline for colorectal cancer metastasis prediction from RNA sequencing data.

---

## 11. Landing Page Structure (Recommended)

### Above the Fold
- **Hero sentence:** "You're too good to be spraying 100 applications into the void. CareerLoop finds the 5 that actually fit — and makes you impossible to ignore."
- **Supporting subhead:** "Found 57 jobs today. Only 8 clear your personal threshold. Apply to 5. Save 3. Ignore the rest."
- **CTA:** "See how it works" or "Join the waitlist"
- **Visual:** Single ranked list vs. 10 scattered browser tabs (before/after contrast)

### Section 1: The Problem
- Headline: "You weren't supposed to do this alone."
- 5 pain points with supporting copy
- Emotional hook: validated, not blamed

### Section 2: What CareerLoop Does
- Headline: "From 100 tabs to 5 decisions."
- The full loop visual (10 steps, compressed to 1 flow)
- "Not a job board. Not a resume builder. Not a chatbot."

### Section 3: How It's Different
- Headline: "Every other tool helps you apply. We help you decide."
- Comparison table (Teal, Simplify, Rezi, Jobscan vs. CareerLoop)
- The moat: "Gets smarter every time you use it."

### Section 4: Proof
- Headline: "Built by someone in the arena."
- Siddharth's metrics (50x cost reduction, 5x latency, 0→450 users)
- 52% tailoring delta, 70 tests passing, 10 templates
- Open source. Data contract. No training on your data.

### Section 5: The Vision (North Star)
- Headline: "Where we're going."
- The daily standup message (57→8→5)
- Four application paths
- The People Graph
- "I am no longer handling my career transition alone."

### Footer
- Open source (GitHub link)
- Data Contract
- Ethical use commitment
- Waitlist / early access CTA

---

## 12. Council Verdict (2026-05-21)

**Council composition:** Haiku, Sonnet, Opus 4.7 — 3 independent responses + 3 anonymous peer reviews.

**Unanimous verdict:** Response C (Opus) ranked #1 by all three reviewers. Response B (Sonnet) ranked #2. Response A (Haiku) ranked #3.

**Key alignments:**
- Positioning: "Career Decision Engine" — most differentiated, most ownable, maps to the actual wedge
- Above-the-fold: Emotional validation + specific promise + transformation arc
- Pain points: Platform fragmentation (India-specific), AI slop as negative signal (timing wedge), rejection without learning loop (retention hook)
- Moat: Memory Graph as the true moat (like Spotify Discover Weekly), not the features
- Risk: Gap between landing page promise and product delivery. Sell what exists. Tease the vision.

**Council minority report:** Response B's moat analysis (4 named layers with maturity notes) is the strongest internal strategy document. Use B's moat framework for investor/pitch conversations. Use C's positioning for public-facing landing page.

---

*This document is the single source of truth for all landing page copy. Every claim must be defensible by the product as it exists at ~45-48% maturity. No WhatsApp. No autonomy. No Chrome extension. No one-click apply. Decision compression. Humanized output. Compounding memory. Those three. Everything else is "where we're going."*
