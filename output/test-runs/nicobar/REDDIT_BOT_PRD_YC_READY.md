# 🚀 REDDIT DM BOT — YC-READY PRD
## Product: Emote Reddit Outreach Engine (EROS)
### Founder: Siddharth Saminathan | May 2026

---

## 1. EXECUTIVE SUMMARY

EROS is a fully automated Reddit DM outreach engine that turns subreddit communities into customer acquisition funnels. It scrapes Reddit threads, classifies users by segment, generates personalized DMs through AI, handles replies, and manages 3-level follow-ups — all without Reddit's API (anti-ban design).

**Traction:** 5,619 DMs sent across 5 Reddit accounts. 25.9% reply rate on manual DMs. 31 confirmed conversions. 490+ total Emote users, ~80% from Reddit.

**Monetizable as:** SaaS for D2C brands, agencies, and startups doing community-led growth. $199/mo per account. TAM: 50M+ Reddit daily active users. Every D2C brand needs this.

---

## 2. PROBLEM

Reddit has 50M+ daily active users across 100K+ active communities. Every subreddit is a room full of your exact target customer — but reaching them is near-impossible:
- Reddit API bans automated DMs
- Manual outreach doesn't scale
- No tool exists for Reddit-native community-led growth

The existing playbook is "post in subreddits and hope." That's not a strategy.

---

## 3. SOLUTION

EROS automates the entire Reddit outreach funnel:

```
SCRAPE → SEGMENT → GENERATE → SEND → REPLY → FOLLOW-UP → CONVERT
```

**Key innovation:** Bypasses Reddit's API entirely. Uses Chrome CDP (DevTools Protocol) to interact with Reddit Chat directly — same as a human would. Undetectable at the browser level.

---

## 4. ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────┐
│                    EROS — SYSTEM ARCHITECTURE                 │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  LAYER 1: DISCOVERY                                           │
│  ┌──────────┐    ┌──────────────┐    ┌──────────────────┐   │
│  │ Reddit   │ →  │ Thread        │ →  │ Segment Matrix   │   │
│  │ Scraper  │    │ Classifier    │    │ (A-I scoring)    │   │
│  │(keyword) │    │ (DeepSeek AI) │    │                  │   │
│  └──────────┘    └──────────────┘    └──────────────────┘   │
│                                                               │
│  LAYER 2: OUTREACH                                            │
│  ┌──────────┐    ┌──────────────┐    ┌──────────────────┐   │
│  │ DM       │ →  │ Humanizer     │ →  │ Chrome CDP       │   │
│  │ Generator│    │ (de-AI layer) │    │ (send via chat)  │   │
│  │(5 styles)│    │               │    │                  │   │
│  └──────────┘    └──────────────┘    └──────────────────┘   │
│                                                               │
│  LAYER 3: ENGAGEMENT                                          │
│  ┌──────────┐    ┌──────────────┐    ┌──────────────────┐   │
│  │ Matrix   │ →  │ Reply        │ →  │ Follow-Up        │   │
│  │ Extractor│    │ Classifier   │    │ Engine (L1/L2/L3)│   │
│  │(CDP)     │    │ (7 types)    │    │                  │   │
│  └──────────┘    └──────────────┘    └──────────────────┘   │
│                                                               │
│  LAYER 4: ANALYTICS                                           │
│  ┌──────────┐    ┌──────────────┐    ┌──────────────────┐   │
│  │ Supabase │ →  │ Dashboard    │ →  │ Hermes Agent     │   │
│  │ CRM      │    │ (Next.js)    │    │ (autonomous ops) │   │
│  └──────────┘    └──────────────┘    └──────────────────┘   │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. TECH STACK

| Layer | Technology | Why |
|-------|-----------|-----|
| Browser Automation | Playwright + Chrome CDP | Bypasses Reddit API bans |
| AI/LLM | DeepSeek v4 | DM generation, thread classification, reply analysis |
| Backend | Python, FastAPI | Pipeline orchestration |
| Database | Supabase (PostgreSQL) | CRM, thread tracking, analytics |
| Dashboard | Next.js 14, Tailwind | Real-time funnel visualization |
| Agent | Hermes Agent (Nous Research) | Autonomous operations, multi-agent orchestration |
| Cost | $0.08 per 1,000 DMs analyzed | DeepSeek is 50x cheaper than GPT-4 |

---

## 6. KEY METRICS (LIVE DATA)

| Metric | Value |
|--------|-------|
| Total DMs sent | 5,619 (5 accounts) |
| Reply rate (manual) | 25.9% |
| Reply rate (bot) | 6.8% (improving) |
| Confirmed conversions | 31 |
| Users acquired via Reddit | ~400 (80% of 490) |
| Best subreddit | r/BreakUps (100% reply) |
| Best approach | shared_struggle (47% reply) |
| DeepSeek cost | <$0.01/day incremental |
| Multi-account support | 5 accounts, rotating |

---

## 7. MONETIZATION MODEL

**SaaS Pricing:**
- Starter: $99/mo (1 account, 50 DMs/day)
- Growth: $199/mo (3 accounts, 150 DMs/day)
- Agency: $499/mo (10 accounts, 500 DMs/day)

**TAM:** 50M+ Reddit DAU × 10% are potential D2C/startup targets = 5M businesses. At 0.1% penetration = 5,000 customers. At $199/mo avg = $12M ARR.

**Competitive moat:** Chrome CDP approach is hard to replicate. Matrix client extraction is undocumented. Anti-ban design took months to perfect.

---

## 8. WHAT THIS PROVES I CAN BUILD

- **Full-stack AI products** from zero to production (Emote: 490 users)
- **Browser automation** at scale (5,600+ DMs via Playwright/CDP)
- **Multi-agent AI systems** (Hermes agent orchestration)
- **Production pipelines** with observability, retry logic, cost optimization
- **Growth engineering** — turning communities into conversion funnels
- **Rapid domain adaptation** — I built this for wellness. Works for ANY vertical.

---

## 9. FOR NICOBAR — WHAT THIS MEANS

Nicobar needs: Personalisation, Store Clienteling, Conversational BI, Design Workflows.

I've already built:
- **Personalisation engine** → Emote learns from user behavior across sessions (same pattern for customer personalisation)
- **Store clienteling** → The CRM tracks every DM interaction with context (same pattern for store associates knowing customers)
- **Conversational BI** → The dashboard queries Supabase in natural language via Hermes agent
- **Design workflows** → Full pipeline automation — scrape → generate → humanize → deliver

**I can build Nicobar's entire AI stack. I've already built 80% of it.**

---

*PRD v1.0 | Built and battle-tested on 5,600+ real DMs*
