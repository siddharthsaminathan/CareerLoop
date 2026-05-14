# CareerLoop — Phase-by-Phase Feature Tracker & Implementation Roadmap

**Date:** May 14, 2026  
**Status:** Phase 1 Complete; Actively Deploying Phase 1.5 (Decision Layer) & Phase 1.6 (Universal Persistent Memory Layer)  
**Based on:** `docs/careerloop-vision.md` (v1.6)

---

## Executive Architectural Summary

```text
┌────────────────────────┐     ┌────────────────────────┐     ┌────────────────────────┐
│        PHASE 1         │     │     PHASE 1.5 & 1.6    │     │     PHASE 2 & 3        │
│    Discovery Base      │ ──> │    Memory & Decision   │ ──> │   Application & Pack   │
│      (Completed)       │     │   (Active Deployment)  │     │   (Vision Aligned)     │
└────────────────────────┘     └────────────────────────┘     └────────────────────────┘
```

---

## Phase 1 — Discovery Base & Liveness Validation [COMPLETED ✅]

Phase 1 established an unblocked, high-throughput discovery foundation capable of parsing and scoring regional job opportunities autonomously.

### Core Modules Delivered
- `[x]` **Search Interface Adapters**: Direct organic Google Search scraping with DuckDuckGo failover (`sources/search_adapter.py`).
- `[x]` **LLM Extraction Wrappers**: Automated structural parsing per URL via ScrapeGraphAI interfaces (`sources/scrapegraph_adapter.py`).
- `[x]` **Multi-Board Aggregators**: Sourced external bulk aggregators safely (`sources/jobspy_adapter.py`).
- `[x]` **Regional Gatekeeping Logic**: Token parsing and validation matching single-token Indian state codes (`india_filter.py`).
- `[x]` **Liveness Probing**: Active HTTP response tracking filtering stale/expired URLs (`verification.py`).
- `[x]` **Deduplication Normalization**: Initial mapping routines preventing noisy URL re-indexing (`models.py`).
- `[x]` **14-Dimension Fit Scorer**: Evaluates baseline job match quality against user credentials (`india_fit_engine.py`).

---

## Phase 1.5 & 1.6 — Decision Design & Universal Persistent Memory Layer [ACTIVE DEPLOYMENT 🏗️]

Raw discovery creates extreme decision paralysis. Phase 1.5 and 1.6 implement persistent storage logic to map feeds into strategic tracks and regulate review pacing.

### 1. Persistent Storage Infrastructure (`careerloop/memory/`) [DELIVERED ✅]
- `[x]` **Schema Definitions**: Local relational table DDL mapping `users`, `strategic_tracks`, `application_ledger`, `company_memory`, `positioning_memory`, and `event_timeline` (`schema.sql`).
- `[x]` **Connection Lifecycle Manager**: Context manager managing directory creation and SQLite pragmatic bounds (`connection.py`).
- `[x]` **Domain Serialization Models**: Dataclass properties automatically handling nested JSON arrays (`models.py`).
- `[x]` **Uniform Persistence Repository**: Bindings abstracting CRUD statements with idempotent update boundaries (`repository.py`).
- `[x]` **Context Synthesis Services**: Interrogation wrappers outputting Daily Standup summaries and Chat Card properties (`retrieval.py`).
- `[x]` **Bootstrap Historical Ingestion**: Migration module translating legacy flat file JSON ledgers into persistent records without data loss (`migrate_to_sqlite.py`).

### 2. Decision Formatting & Regulation (`careerloop/decision/`) [NEXT ACTIONS]
- `[ ]` **Search Mode Architecture (`search_mode.py`)**: Implement behavioral boundaries for `HUNT`, `UPGRADE`, `EXPLORE`, and `EMERGENCY` parameters.
- `[ ]` **Aggression Level Slider (`aggression_slider.py`)**: Dialable volume bounds regulating daily shortlist queue thresholds dynamically.
- `[ ]` **Strategic Track Clustering (`track_clustering.py`)**: Cluster discovered fingerprinted jobs into coherent macro-trajectories to prepare drop-in variant packaging.
- `[ ]` **Daily Triage Standup Formatter (`triage_board.py`)**: Format ultra-concise multi-bucket chat responses optimized for 2-minute decision sessions.
- `[ ]` **Conversational Memory Cards (`job_memory_card.py`)**: Bind local SQLite history rows directly to conversational argument templates.

---

## Phase 2 — Application Automation & Preference Learning [VISION ALIGNED]

Phase 2 builds directly upon finalized strategic tracks to prepare application assets natively, avoiding brute-force automation loops.

Detailed Phase 2 documents:
- `docs/PHASE_2_RESUME_COUNCIL.md`
- `docs/PHASE_2_IMPLEMENTATION_PLAN.md`
- `docs/PHASE_1_GAP_TRACKER.md`

### Deliverables Roadmap
- `[ ]` **Multi-Agent Resume Council Integration**: Expose pre-compiled, highly optimized **Shared Resume Variants** mapped strictly to high-level tracks rather than generating redundant single-job documents.
- `[ ]` **Drop-In Pack Formatter**: Package customized framing narratives, cover letter structures, and screening parameters directly into isolated staging elements.
- `[ ]` **Continuous Seeker Learning Loop**: Listen to board skipped/approval flags to automatically adjust profile parameters and re-tune fit engine weights implicitly.
- `[ ]` **Browser Autofill Protocol Specification**: Define communication schemas for the external companion browser extension to securely inject prepared application packs directly into third-party portal DOM structures upon user review.

---

## Phase 3 — Interview Lifecycle & Longitudinal Optimization [VISION ALIGNED]

Phase 3 tracks post-application performance to measure empirical framing conversion rates over multi-month lifecycles.

### Deliverables Roadmap
- `[ ]` **Firm-Targeted Story Interrogation**: Map user portfolio assignments to known target interview loops safely.
- `[ ]` **Conversion Metric Tracking**: Read down-funnel status transitions to identify highly converting positioning themes stored within `positioning_memory`.
- `[ ]` **Exhaustion Pacing Safeguards**: Monitor macro event timelines over sliding operational windows to suggest sanctuary operational pauses automatically upon threshold alerts.
