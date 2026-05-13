# CareerLoop — Internal Product Vision

**Author:** Siddharth Saminathan  
**Date:** May 14, 2026  
**Status:** Vision v1.6 — Phase 1 Discovery Complete; Integrating Phase 1.6 Universal Persistent Career Memory Layer

---

## 1. Definition

CareerLoop is a WhatsApp-first autonomous career operating system for Indian professionals.

It moves beyond basic job discovery to act as an intelligent **decision design layer** powered by a **Universal Persistent Career Memory Layer**. It processes high-volume market opportunities, clusters them into actionable strategy buckets, respects user job-search intensity, prepares reusable application packs, and maintains an ACID-compliant local database tracking longitudinal career execution history.

CareerLoop does not dump long feeds of jobs. It presents **strategy**, allowing the user to review directions rather than individual listings.

---

## 2. The Core Problem: Decision Overload

Through highly optimized discovery (Google Search scraping, JobSpy aggregation, ScrapeGraphAI deep extraction, and rigorous local filtering), CareerLoop reliably finds **50+ active, high-fidelity India jobs** daily. 

However, raw discovery volume creates intense cognitive overload. Users do not want "57 jobs dumped on their head." 

To solve this, the product transforms high-throughput discovery into a **low-cognitive-load decision process** rooted in permanent operational continuity. The user reviews strategic clusters and action plans in a 2-minute daily standup driven directly by persistent embedded data stores.

---

## 3. Core Promise

The user asks:

**"What should I do today?"**

CareerLoop answers not with a list, but with a highly synthesized **Triage Strategy**:
*"Found 57 jobs. Only 8 clear your personal threshold. Apply to these 5 today. Save 3. Ignore the rest."*

---

## 4. Product Principles

### WhatsApp First
The primary interface remains simple, chat-based, and highly conversational. 

### Review Strategy, Not Listings
Jobs are grouped into decision buckets (*Strong Fits*, *Decent Fits*, *Stretch Roles*, *Noisy*, *Preference Violations*). The user commands strategic moves (*"apply to all strong fits"*, *"tighten filters"*) rather than manually evaluating dozens of job descriptions.

### Intensity-Aware (Search Modes)
The system fundamentally adapts its filters, volume, and urgency based on the user's operational state—differentiating between passive exploration and high-pressure hunting.

### Memory Is the Moat
Centralized local embedded database models track dynamic execution history across six synchronized entities. The companion answers user questions directly from structured memory tables instantly.

### Lazy-Loaded Deep Intelligence
To prevent computational waste and extreme token expenditure, **Company Intelligence, dynamic candidate framing, and multi-agent document packaging are strictly lazy-loaded**, triggering only *after* the user confirms strategic interest via triage interactions.

### Batch but Safe Workflow
Instead of generating 57 separate resumes, discovered jobs are clustered into **Role Tracks** mapping to **4–6 highly tailored Resume Variants**, massively reducing token costs and repetitive cognitive load.

---

## 5. The Universal Persistent Memory Layer (SQLite Schema)

Operational state resides permanently within an embedded local SQLite engine across 6 unified entities:
1. **Users Entity**: Tracks active search posture, absolute urgency/burnout limits, expected CTC floors, and structural boundary configurations.
2. **Strategic Tracks Entity**: Maps individual opportunities into targeted role trajectories to share optimized positioning variants cleanly.
3. **Application Ledger Entity**: Sourced repository tracking distinct opportunity validation hashes, audit histories, personal notes, and recruiter check-in timelines.
4. **Company Memory Entity**: Lazy-loaded tables accumulating Glassdoor synthesis, parsed compensation signals, and structural org trends over time.
5. **Positioning Memory Entity**: Logs generated narrative structures to build an empirical understanding of highly converting cover letter/resume text.
6. **Event Timeline Entity**: Append-only log recording systemic transitions to dynamically calculate application pacing and prevent seeker exhaustion.

---

## 6. The Missing UX Layer: Search Modes

After onboarding, every user configures an operational mode defining their job-search intensity:

### 1. Hunt Mode
- **Target**: Unemployed / active full-time job seekers.
- **Goal**: Maximize qualified application surface area.
- **Behavior**: Shows higher job volume, allows batch application tracking, aggressively pre-generates resume variants/application packs, and maintains an active daily queue.

### 2. Upgrade Mode
- **Target**: Employed but dissatisfied professionals looking for significant upside.
- **Goal**: Apply only to roles worth switching for.
- **Behavior**: Shows fewer jobs, enforces highly rigorous filtering, raises the company brand/stability bar, filters out lateral moves, and emphasizes compensation/role trajectory upside.

### 3. Explore Mode
- **Target**: Passive browsers curious about market value.
- **Goal**: Market mapping and long-term opportunity discovery.
- **Behavior**: Zero application pressure, weekly digests, high-level company insights, and persistent "Maybe Later" saving mechanisms.

### 4. Emergency Mode
- **Target**: Users under tight timelines or severe pressure.
- **Goal**: Daily execution velocity and strict accountability.
- **Behavior**: Aggressive daily shortlists, automated follow-up nudges, structured momentum tracking, and deep interview readiness support.

---

## 7. Simplified Onboarding (3 Questions)

Onboarding takes 2 minutes immediately following resume upload:

1. **Why are you looking?**
   - Need job urgently / Want better pay / Hate current role / Want stable company / Want career switch / Just exploring
2. **What should I avoid?**
   - Startups / Sales / Night shifts / Low salary / Relocation / Long take-home assignments / Toxic or chaotic environments
3. **How aggressive should I be?**
   - Apply only to best 5 / Apply to good fits / Apply broadly / Just show options

*Optional Voice Note*: *"Tell me what you hate about your current job."* 
*(Grounds personalization natively without excessive long-form intake)*

---

## 8. The Apply Strategy Slider (Aggression Levels 1–5)

Users can dynamically dial their discovery and application surface area using a simple integer scale:

- **Level 1 — Picky**: Only absolute dream roles matching pristine criteria.
- **Level 2 — Quality**: Strong role fit + highly validated company stability.
- **Level 3 — Balanced**: Good volume with structured filter guards.
- **Level 4 — Active Hunt**: Broad application matching plausible role families.
- **Level 5 — Maximum Surface Area**: Apply to everything defensible.

*Example Throughput on 57 Discovered Jobs*:
- Level 2: Recommends applying to **6**
- Level 3: Recommends applying to **14**
- Level 4: Recommends applying to **29**
- Level 5: Recommends applying to **42**

---

## 9. Presentation & The Daily Decision Ritual

### Decision Buckets
Discovered jobs are categorized cleanly:
- Strong Fits
- Decent Fits
- Stretch Roles
- Low-Quality / Noisy
- Rejected (Preference Violations)

### The Daily Standup Message
```text
Morning.

Found 57 jobs.
Only 8 clear your personal threshold.

My recommendation:
Apply to 5 today.
Save 3.
Ignore the rest.

Why:
The rest are too sales-heavy, startup-chaotic, or exhibit weak salary signals.

Reply:
go = prepare 5 applications
review = show one by one
more = loosen filters
```

### Collaborative Triage Board Interaction
Users can interrogate the board dynamically via chat:
- *"Why did you reject Infosys?"*
- *"Show me only stable companies."*
- *"Remove sales-ish roles."*
- *"Why am I a good fit for job 2?"*

---

## 10. Conversational Job Memory Cards

To support native collaborative Q&A, every shortlisted job holds a structured memory block pulled instantly from persistent storage:
- **Company & Role**
- **Fit Score & Grounded Arguments** (*Why fit / Why not*)
- **Apply Route & Application Track Mapping**
- **Assigned Resume Variant**
- **Company Summary & Core Skills Required**
- **Screening Risks & Recommended Positioning**

---

## 11. The Decision Session Override

Adapting to immediate user constraints, the bot asks:
**"Do you have 2 minutes or 20 minutes?"**

- **2 Minutes**: Autonomous fast path (*"I'll make the call. Apply to these 5. Skip 38. Save 14."*)
- **20 Minutes**: Granular review path (*"Let's review one by one."*)

---

## 12. Real-World Portal Execution (Browser Extension)

To bridge the gap between application generation and submission without resorting to risky complete auto-apply loops:
1. CareerLoop generates the full customized application pack (resume variant, cover letter arguments, screening answers).
2. The user clicks the job link, navigating natively to the target portal (Greenhouse, Lever, Workday, LinkedIn).
3. The **CareerLoop Chrome Extension** detects the active form and securely presents drop-in auto-fill options:
   - *Fill tailored resume*
   - *Fill "Why this company"*
   - *Fill notice period & expected CTC*
4. The user reviews inputs and clicks submit manually, retaining ultimate control.

---

## 13. Realigned Product Roadmap

### Phase 1 — Discovery Base (Completed)
- Multi-source aggregation (JobSpy, ScrapeGraphAI deep extract, Direct Google Search scraping).
- Geographic hard filter passing validated India opportunities.
- Liveness verification and core capability evaluation.

### Phase 1.5 & 1.6 — Decision Design & Universal Persistent Memory Layer (Current Focus)
- **Universal Embedded SQLite Database** deployment tracking unified records across `users`, `strategic_tracks`, `application_ledger`, `company_memory`, `positioning_memory`, and `event_timeline` entities.
- Lazy-loaded architectural hooks protecting token optimization bounds.
- **Daily Triage Board** implementation.
- Search Modes (*Hunt*, *Upgrade*, *Explore*, *Emergency*) + Aggression Slider.
- Track Clustering (grouping jobs into targeted role tracks).
- Conversational Job Memory Cards supporting real-time chat interrogation.

### Phase 2 — Decision + Application Layer
- Application Pack Generator orchestrating reusable Resume Variants.
- Preference learning loop driving continuous scoring adjustments based on skips/approvals.
- Integration specification for the companion browser autofill extension.
- Multi-agent Resume Council operating as an internal subsystem of the pack generator.

### Phase 3 — Interview & Feedback Loop
- Company-specific interview prep bots, outcome tracing, and long-term strategy self-correction.

---

*Vision document v1.6 · May 14, 2026 · CareerLoop Internal*
