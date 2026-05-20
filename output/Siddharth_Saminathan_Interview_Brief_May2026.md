# Siddharth Saminathan — AI Product Engineer
## Proof Points: End-to-End Systems Built at EmoteNow

> Interview-ready brief — May 20, 2026

---

## 1. Reddit DM Outreach Pipeline — User Acquisition Engine

### What It Is
A fully automated Reddit DM outreach system that finds users in distress, sends human-sounding DMs, tracks replies, analyzes sentiment with DeepSeek, syncs to Supabase CRM, and manages a 5-bucket follow-up engine. Built solo in 3 weeks.

### Scale
- **1,002 DMs sent** across 4 Reddit accounts
- **260 replies** (25.9% reply rate)
- **31 users tried Emote** (3.1% conversion from outreach)
- **490 total users** on Emote (~400 from Reddit)

### How It Works (End-to-End)
```
Reddit → Chrome CDP extraction → DeepSeek analysis → CSV + Supabase CRM → 5-bucket follow-up engine
```

1. **Extraction:** Chrome CDP (`:9222`) connects to Reddit Chat, reads Matrix client's in-memory store, extracts ALL conversation data
2. **Analysis:** DeepSeek API analyzes every reply — sentiment, feedback quality, tried_emote (yes/no/unclear), why/why not
3. **Storage:** CSV (`emote_reddit_dm_audit_v2.csv` — 1002 rows, 16 columns) + Supabase CRM (`crm_conversations` — 6,740 rows)
4. **Follow-up:** 5 user buckets, each with 3-level follow-up sequence at specific intervals (Day 2/5/10 → Day 30/60/90)

### DM Approach Performance
| Approach | Reply Rate | Volume | Use Case |
|----------|-----------|--------|----------|
| direct_pitch | 84% | 19 | Posts asking "what should I do?" |
| shared_struggle | 47% | 34 | Breakups, loss, grief |
| pattern_naming | 27% | 48 | Users stuck in cycles |
| insight_reflection | 24% | 810 | 80% of volume — bread and butter |
| empathy_validation | 20% | 91 | Pure venting posts |

### Best Targeting
- **S-Tier subs (50-60% reply):** r/adhdindia, r/breakups, r/relationships
- **A-Tier subs (35-44%):** r/Vent, r/CPTSD, r/ThirtiesIndia
- **Bottom line:** Same DM, different subreddit = 4x difference in reply rate

### Tech Stack
- **Extraction:** Chrome DevTools Protocol + Playwright
- **Analysis:** DeepSeek API (~$0.08 per full analysis run)
- **CRM:** Supabase (wryyxmegytkggdvlioee) — crm_conversations (6,740), thread_users (5,739), threads (830)
- **Dashboard:** Next.js app (`~/Projects/redditbot/reddit-bot/`) — 8 modules
- **Anti-spam:** 50 DMs/day cap per account, rotation across 4 accounts

### Key Engineering Decisions
- Built Chrome CDP extraction (not Reddit API) — Reddit has no chat API
- DeepSeek for conversation analysis (not regex) — catches sentiment, intent, conversion signals
- CSV as primary truth source for reply rate (CRM undercounts at 6.8% vs CSV at 25.9%)
- VC dashboard API for metrics (not raw SQL) — different activation logic

---

## 2. CareerLoop — AI-Native Career Execution System

### What It Is
A closed-loop career transition operating system for Indian professionals. Not a job board. Not a resume builder. An AI agent that handles the entire pipeline: discover → decide → position → apply → follow up → prepare → learn → improve.

### Scale
- **141 jobs** discovered across Indian job market
- **47 git commits** in 4 days (May 17-20)
- **9 custom systems** built from scratch
- **~41-43% product maturity** (up from 38% last week)

### Resume Council v3 — The Core Engine

An 8+1 stage LangGraph state machine:
```
Raw CV + Job Description
  → S1: Document Parser (deterministic, mistune AST)
  → S2: Preservation Contract (deterministic)
  → S3: Company Intelligence (DeepSeek + DuckDuckGo web search, 10s timeout)
  → S4: Role Decoder (DeepSeek)
  → S5: User Truth (DeepSeek, evidence mapping)
  → S6: Positioning Strategy (DeepSeek, narrative generation)
  → S7: Section Rewrites (DeepSeek, parallelized, per-section)
  → S7.5: Truth Guard (deterministic, regex + Jaccard claim validation)
  → S8: Assembly + Humanizer → Application Pack
```

**Performance:** ~$0.02 per run, ~3 minutes end-to-end, 10 HTML + 10 PDF templates rendered

### Tailoring Delta Breakthrough (May 20)
The S7 Section Rewriter was the bottleneck — 3.6% tailoring delta (19/19 bullets verbatim). Root cause: passive prompt ("replace weak verbs") had the LLM saying "already strong → KEEP." Rewrote to prescriptive: "You MUST rewrite every section, inject role-specific language, reframe for this role." Result: 9/9 sections REWRITE, 0 skipped, delta now SUBSTANTIAL.

### Humanizer — The "Cope-Killer"
5-phase anti-AI-slop pipeline:
1. Slop Detection (banned words: leverage, spearheaded, synergy)
2. Tone Adaptation (paragraph-aware, preserves structure)
3. LLM Surgical Rewrite (aggressive: "Lead with concrete outcomes")
4. Structure Validation (markdown safety gate — rejects if bullets lost)
5. Post-Verify Scan (catches surviving slop)

Catches 70+ slop flags per run. Status: 60% complete.

### Truth Guard — Deterministic Claim Validation
Zero-LLM validation of all rewritten claims:
- 5 claim types: Year Experience, Percentage, Skill Assertion, Ownership, Quantified Achievement
- 4 risk levels: VERIFIED, WEAK, UNSUPPORTED, EXAGGERATED, FABRICATED
- Surgical repair for EXAGGERATED/FABRICATED (e.g. "5+ years" → "3+ years")
- Known gap: year-inflation cross-check against parsed dates (B9)

### India Discovery Engine
Multi-source job discovery with India-first filtering:
- Sources: LinkedIn, Naukri, Instahyre, Cutshort, Foundit, SpireAI (Myntra), JobSpy
- 14-dimension heuristic scoring (no LLM cost)
- Search-page rejection filter (blocks Naukri category pages, blog spam)
- ATS detection: Greenhouse, Lever, Ashby, Workday
- 15-sector MECE map for employer discovery

### Rendering System
- **10 HTML templates** (classic-ats, executive-clean, design-brand-compact, founder-operator, etc.)
- **NormalizedResume** — single data contract for ALL renderers
- **36 regression tests**, 94.4% pass rate
- **Hard fail** on `**`, `—`, `→` in rendered output
- PDF via Chrome headless (not weasyprint — avoids system dependency issues)

### Architecture Decisions (11 LOCKED Rules)
- Single source of truth: `ledger.json`
- NormalizedResume = data contract for all renderers
- Strategy model: `deepseek-v4-pro`, Writer: `deepseek-chat`
- Humanizer on every user-facing output
- No auto-submit — manual review required
- Post-render validation FAILS HARD on artifacts

### Fuckups Log (9 documented mistakes)
Transparent engineering culture. Most expensive: S3 hung pipeline for 10+ minutes across 6 launches, wasting ~2.1B tokens. Fixed with 10s hard timeout + `CAREERLOOP_SKIP_S3=1` escape hatch.

### Tech Stack
- **Orchestration:** LangGraph (StateGraph)
- **LLM:** DeepSeek API (v4-pro + chat)
- **Parsing:** mistune AST
- **Web Search:** DuckDuckGo (company research, 10s timeout)
- **PDF:** Chrome headless + Playwright
- **Validation:** 36 regression tests, 10-rule validator
- **CRM:** ledger.json + application_ledger.py

---

## 3. How These Systems Connect — The "AI Product Engineer" Identity

Both systems share the same engineering DNA:

| Principle | Reddit DM Pipeline | CareerLoop |
|-----------|-------------------|------------|
| Deterministic core + LLM edges | Chrome CDP extraction (deterministic) + DeepSeek analysis (LLM) | S1/S2/S8 (deterministic) + S3-S7 (LLM) |
| Data contract enforcement | CSV schema (16 columns, strict typing) | NormalizedResume contract (all renderers) |
| Anti-garbage guards | 50 DM/day rate limit, account rotation | Truth Guard, Humanizer, validator hard fails |
| Cost consciousness | ~$0.08 per full analysis | ~$0.02 per council run |
| Honest failure logging | CRM undercounting documented | Fuckups.md (9 entries) |
| Multi-source truth | CSV + CRM cross-referenced | Ledger + company_memory cache |

**The thread:** I build systems where AI does the heavy lifting, but deterministic guards ensure correctness. Every system has a "what could go wrong" checklist and a "here's what actually went wrong" log.

---

## 4. Key Numbers for the Interview

- **Emote users:** 490 (400 from Reddit)
- **Reddit reply rate:** 25.9% (260/1002)
- **Emote conversion:** 3.1% from cold DM
- **CareerLoop maturity:** 41-43%
- **Resume Council cost:** $0.02/run, ~3 min
- **Templates rendered:** 10 HTML + 10 PDF per run
- **Regression tests:** 36, 94.4% pass
- **Git commits:** 47 in 4 days (May 17-20)
- **Custom systems built:** 9 (Council, Humanizer, Truth Guard, Rendering, Discovery, Company Intel, People Graph, Quality Auditor, Reddit DM Pipeline)

---

*Built by Siddharth Saminathan, Co-Founder & AI Product Engineer, EmoteNow.*
*M.Sc. Statistics & Machine Learning, Linköping University, Sweden (2020-2022)*
*B.Tech Computer Science, SRM University, Chennai (2016-2020)*
