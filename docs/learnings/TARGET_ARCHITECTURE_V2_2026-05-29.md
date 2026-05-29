# CareerLoop Target Architecture V2 — May 29, 2026

**Three Architectural Laws.** No exceptions.

---

## LAW 1 — SINGLE SOURCE OF TRUTH

> Database is the only persistence layer. Filesystem is migration-only.

## LAW 2 — SINGLE WRITER OWNERSHIP

> Each entity has exactly one owner service. No other writes.

## LAW 3 — CANONICAL IDENTITY

> One canonical UUID per job, surviving the entire lifecycle.

---

# PART 1: TARGET ARCHITECTURE

## 1. Service Ownership Matrix

| Entity | Owner Service | Read Access | Write Rule |
|--------|-------------|-------------|------------|
| `careerloop.users` | `UserService` | Any service may read | Only `UserService` writes |
| `careerloop.sessions` | `SessionService` | Any service may read | Only `SessionService` writes |
| `careerloop.jobs` | `JobService` | Any service may read | Only `JobService` writes |
| `careerloop.daily_briefs` | `BriefService` | Any service may read | Only `BriefService` writes |
| `careerloop.daily_brief_items` | `BriefService` | Any service may read | Only `BriefService` writes |
| `careerloop.application_packs` | `ApplicationService` | Any service may read | Only `ApplicationService` writes |
| `careerloop.user_job_relationships` | `ApplicationService` | Any service may read | Only `ApplicationService` writes |
| `careerloop.messages` | `ChatService` | Any service may read | Only `ChatService` writes |
| `careerloop.conversations` | `ChatService` | Any service may read | Only `ChatService` writes |
| `careerloop.background_runs` | `BackgroundRunService` | Any service may read | Only `BackgroundRunService` writes |
| `careerloop.run_events` | `BackgroundRunService` | Any service may read | Only `BackgroundRunService` writes |
| `careerloop.company_memory` | `CompanyIntelService` | Any service may read | Only `CompanyIntelService` writes |
| `careerloop.companies` | `CompanyIntelService` | Any service may read | Only `CompanyIntelService` writes |

## 2. API Boundary (Layer 1)

```
FastAPI ::8001
├── POST /v1/auth/me              → UserService.provision()
├── POST /v1/chat/message         → ChatService.message()
├── GET  /v1/chat/history         → ChatService.get_history()
├── POST /v1/scans                → ScanService.initiate()
├── GET  /v1/scans/{run_id}/events → ScanService.stream_events()
├── GET  /v1/briefs/latest        → BriefService.get_latest()
├── POST /v1/briefs/{id}/items/{idx}/select → BriefService.select_item()
├── GET  /v1/jobs/{job_id}        → JobService.get_detail()
├── POST /v1/jobs/{job_id}/save   → ApplicationService.save()
├── POST /v1/jobs/{job_id}/skip   → ApplicationService.skip()
└── GET  /v1/me/preferences       → UserService.get_preferences()
```

Every endpoint delegates to exactly ONE owner service. No raw SQL in routers.

## 3. Service Layer (Layer 2)

```
UserService
├── provision(user_id, email, full_name, provider)
├── get_profile(user_id)
├── update_profile(user_id, data)         ← THE ONLY ONBOARDING WRITER
└── get_preferences(user_id)

JobService
├── persist_job(job_data) → canonical_id  ← THE ONLY JOB WRITER
├── get_by_id(job_id)
├── get_by_fingerprint(fingerprint)        ← dedup gate
└── search(filters, limit)

ScanService
├── initiate(user_id, mode) → run_id
├── stream_events(run_id) → SSE generator
├── _execute(run_id)                       ← internal: calls JobService + BriefService
└── _execute_more(run_id)                  ← internal: calls JobService + BriefService

BriefService
├── get_latest(user_id, offset) → BriefResponse
├── select_item(user_id, brief_id, idx)
├── create_brief(user_id, job_ids, run_id) ← THE ONLY BRIEF WRITER
└── add_item(brief_id, job_id, score, reasoning)

ApplicationService
├── save_job(user_id, job_id)              ← writes user_job_relationships
├── skip_job(user_id, job_id)
├── prepare_pack(user_id, job_id) → pack_id
├── edit_pack(user_id, pack_id, instruction)
└── get_pack(pack_id)

ChatService
├── message(user_id, text) → reply
├── get_history(user_id) → messages[]
├── _persist_message(user_id, conv_id, role, content)  ← THE ONLY MESSAGE WRITER
└── _load_history(user_id, conv_id) → HumanMessage[]

SessionService
├── get(user_id) → Session
├── save(session)                        ← THE ONLY SESSION WRITER
└── update_state(user_id, state)

BackgroundRunService
├── create(user_id, run_type)
├── emit_event(run_id, event_type, message)
├── complete(run_id)
├── fail(run_id, error)
└── stream_events(run_id) → SSE

CompanyIntelService
├── get(company_name) → cache hit
├── research(company_name) → fresh intel
├── discover_leads(company_name) → recruiter[]
└── persist(company_name, intel_data)     ← THE ONLY COMPANY MEMORY WRITER
```

## 4. Scan → Brief → Pack Pipeline (Target)

```
1. User triggers: POST /v1/scans
   ↓
2. ScanService.initiate()
   ├── BackgroundRunService.create(user_id, "scan") → run_id
   ├── BackgroundRunService.emit_event(run_id, "SCAN_STARTED")
   └── daemon thread: _execute(run_id)

3. ScanService._execute(run_id)
   ├── DailyRunner.discover() → raw_jobs[]
   ├── for each raw_job:
   │   └── JobService.persist_job(job) → canonical_job_id
   │       (INSERT ON CONFLICT DO UPDATE)
   │       (fingerprint dedup BEFORE insert)
   ├── IndiaFitEngine.score_batch(canonical_job_ids) → scored[]
   ├── filter_india_jobs + company_cap + role_filter
   ├── BackgroundRunService.emit_event(STARTED, FOUND, SCORED, FILTERED)
   └── BriefService.create_brief(user_id, top_job_ids, run_id)
       ├── INSERT careerloop.daily_briefs
       └── INSERT careerloop.daily_brief_items (one per job)

4. Brief returned:
   GET /v1/briefs/latest
   ├── BriefService.get_latest(user_id)
   ├── SELECT brief + items
   └── Serialize → frontend cards

5. User inspects:
   GET /v1/jobs/{job_id}
   ├── JobService.get_detail(job_id)
   ├── LEFT JOIN user_job_relationships for status
   └── Serialize → full JD + match + company intel

6. User approves:
   POST /v1/jobs/{job_id}/save
   ├── ApplicationService.save(user_id, job_id)
   ├── INSERT ON CONFLICT user_job_relationships
   └── return { status: "saved" }

7. User generates pack:
   POST /v1/chat/message "prepare pack for this job"
   ├── ActionResolver → PREPARE_APPLICATION_PACK
   ├── ApplicationService.prepare_pack(user_id, job_id)
   │   ├── JobService.get_detail(job_id) → JD data
   │   ├── UserService.get_profile(user_id) → CV
   │   ├── CompanyIntelService.get(company) → intel
   │   ├── PackageAssembler.assemble(...) → files
   │   ├── INSERT application_packs (status=COMPLETED)
   │   └── return pack_id
   └── User sees: "Pack ready! Resume, cover note, and recruiter message generated."

TRACEABILITY: scan run_id → job canonical_id → brief_id → application_pack pack_id
Single chain. One query. Deterministic.
```

## 5. Canonical Job Identity

```
Job creation:
  fingerprint = SHA256(company_name + title + source_normalized)
  
  JobService.persist_job():
    1. Check careerloop.jobs WHERE content_fingerprint = fingerprint
    2. If found → return existing canonical_job_id
    3. If not → INSERT new row, return new canonical_job_id
    4. canonical_job_id = UUIDv4, generated INSIDE JobService
    5. Source-specific ID stored in source_external_id (NOT used as primary key)
    
  NO MORE:
    ❌ loop-XXXX IDs
    ❌ uuid.uuid4().hex[:8] (partial UUID)
    ❌ pack_XXXX IDs
    ❌ client-generated IDs
    ❌ IDs from external scrapers used as primary keys
```

---

# PART 2: CURRENT VIOLATIONS

## Violations of LAW 1 — Filesystem Persistence

| # | Location | File | What It Does | Severity |
|---|----------|------|-------------|----------|
| V1-1 | `daily_runner.py:233` | `output/daily_briefs/{date}.md` | Writes brief summary to markdown file | P0 — DB already has daily_briefs table |
| V1-2 | `daily_runner.py:252` | `careerloop/.last_brief_date` | Sentinel file to skip re-runs | P0 — use background_runs status instead |
| V1-3 | `application_ledger.py` | `ledger.json` | 1,268 job entries on filesystem | P0 — migrate to careerloop.jobs |
| V1-4 | `application_ledger.py` | `ledger.json` | 19 SQLite entries diverged from 1,268 JSON | P0 — single source |
| V1-5 | `company_intel.py` | `cache/*.json` | Company intel cached as filesystem JSON | P1 — DB has company_memory table |
| V1-6 | `discovery.py` | `data/pipeline.md` | Pending scan URLs on filesystem | P1 — use background_runs + run_events |
| V1-7 | `daily_runner.py` | `test data/output/` | Pack assembly writes to filesystem dirs | P1 — DB stores metadata, files are export |

## Violations of LAW 2 — Direct Writes (Raw SQL Outside Owner)

| # | Entity | Violator | File + Line |
|---|--------|----------|-------------|
| V2-1 | `careerloop.jobs` | `daily_runner.py` | Raw INSERT in scan thread |
| V2-2 | `careerloop.jobs` | `tool_registry.py:prepare_application_pack` | SELECT job data via raw SQL |
| V2-3 | `careerloop.sessions` | `session_store.py:save_session` | OK — this IS the owner |
| V2-4 | `careerloop.sessions` | `brief_service.py:43-49` | `SessionStore(self.db).save_session()` — cross-service write |
| V2-5 | `careerloop.daily_brief_items` | `scan_service.py:_execute_scan_more` | Direct INSERT bypassing BriefService |
| V2-6 | `careerloop.user_job_relationships` | `tool_registry.py:save_job` | Direct INSERT bypassing ApplicationService |
| V2-7 | `careerloop.background_runs` | `tool_registry.py` | prepare/edit/create — 3 different places create runs |
| V2-8 | `careerloop.background_runs` | `scan_service.py` | Yet another run creation path |
| V2-9 | `careerloop.run_events` | `scan_service.py:_emit` | OK — this IS the run event owner (for scan) |
| V2-10 | `careerloop.run_events` | `tool_registry.py` | pack/resume events — should go through BackgroundRunService |

## Violations of LAW 3 — Multiple ID Systems

| # | ID Type | Location | Problem |
|---|---------|----------|---------|
| V3-1 | `loop-XXXX` | `application_ledger.py:78` | 4-digit sequential, non-unique, collision risk |
| V3-2 | `pack_XXXXXXXX` (8 hex) | `tool_registry.py:912` | Partial UUID, no collision guarantee |
| V3-3 | `uuid.uuid4().hex[:12]` | `tool_registry.py:913,953` | Run IDs generated outside BackgroundRunService |
| V3-4 | `uuid.uuid4().hex[:8]` | Multiple | Multiple places generate partial IDs |
| V3-5 | `company_name` as slug | `package_assembly.py` | String-based ID, not stable across scrapes |
| V3-6 | `fingerprint divergence` | `migrate_to_sqlite.py` vs `models.py` | Two different fingerprinting algorithms |

## Silent Exception Swallowing (Observability Blockers)

| # | File | Line | Pattern |
|---|------|------|---------|
| S1 | `company_intel.py` | 4 locations | `except Exception: pass` |
| S2 | `india_fit_engine.py` | 80-108 | `except Exception: return {}` |
| S3 | `session_store.py` | Every method | `logger.error(...)` only, never re-raises |
| S4 | `daily_runner.py` | Job persist block | `try/except: logger.warning` silently skips failed jobs |
| S5 | `tool_registry.py` | Pack thread | `except Exception: logger.error` in daemon — user never sees |

---

# PART 3: MIGRATION PLAN

## Phase 0 — Emergency (This Week)

### 0.1: JobService.create() — canonical job persistence

```python
class JobService:
    def persist_job(self, job_data: dict) -> str:
        """Single entry point for creating or updating a job. Returns canonical UUID."""
        fingerprint = self._compute_fingerprint(
            job_data.get("company_name", ""),
            job_data.get("title", ""),
            job_data.get("source_url", ""),
        )
        
        # Check existing
        existing = self.repo.get_by_fingerprint(fingerprint)
        if existing:
            return existing["id"]
        
        canonical_id = str(uuid.uuid4())
        self.repo.insert({
            "id": canonical_id,
            "content_fingerprint": fingerprint,
            "title": job_data.get("title", "")[:500],
            "company_name": job_data.get("company_name", "")[:255],
            "location": job_data.get("location", "")[:255],
            "source": job_data.get("source", "")[:50],
            "source_url": job_data.get("source_url", "")[:2048],
            "apply_url": job_data.get("apply_url", "")[:2048],
            "raw_jd_text": job_data.get("description", "")[:10000],
            "source_external_id": job_data.get("external_id"),  # NOT primary key
        })
        return canonical_id
```

**Migration:** Replace ALL raw INSERTs into `careerloop.jobs` with `JobService.persist_job()`. Affected files: `daily_runner.py`, `scan_service.py`, `discovery.py`.

### 0.2: BriefService — consolidate brief creation

Move ALL brief + brief_item creation logic from `daily_runner.py` and `scan_service.py` into `BriefService`. Single `create_brief(user_id, job_ids, run_id)` method.

### 0.3: BackgroundRunService — single run lifecycle

```python
class BackgroundRunService:
    def create(self, user_id: str, run_type: str) -> str: ...
    def emit(self, run_id: str, event_type: str, message: str) -> None: ...
    def complete(self, run_id: str) -> None: ...
    def fail(self, run_id: str, error: str) -> None: ...
```

Replace all direct INSERTs into `background_runs` and `run_events` with this service.

### 0.4: Kill `ledger.json` write path

Stop writing to `ApplicationLedger` JSON. Read from `careerloop.jobs` + `careerloop.user_job_relationships`. Migrate existing 1,268 entries.

### 0.5: Full canonical IDs

Replace all `uuid.uuid4().hex[:N]` with `str(uuid.uuid4())`. Generate IDs ONLY inside owner services.

## Phase 1 — Consolidation (Week 2)

### 1.1: Filesystem purge

Remove: `.last_brief_date` → check `background_runs` table.
Remove: `output/daily_briefs/*.md` → DB is the source.
Remove: `cache/*.json` → use `company_memory` table.

### 1.2: Ownership enforcement

Add assertion decorator or comment header to every write method:
```python
# OWNER: BriefService — ONLY service allowed to write careerloop.daily_briefs
```

### 1.3: Exception propagation

Replace all `except Exception: pass` with:
```python
except Exception as e:
    logger.error(f"SYSTEM: operation_name FAILED | user_id={user_id} | error={e}", exc_info=True)
    raise  # Let the caller handle it
```

Only catch exceptions at API boundary (routers) to convert to safe user-facing errors.

### 1.4: End-to-end traceability

Add `run_id` column to `daily_brief_items` so every item traces back to its scan.
Add `pack_id` + `job_id` + `run_id` linking in `application_packs`.

```sql
-- Trace a job's full journey:
SELECT 
    br.run_id,
    j.id as job_id,
    j.title,
    db.id as brief_id,
    dbi.item_index,
    ap.pack_id,
    ap.status as pack_status
FROM careerloop.background_runs br
JOIN careerloop.daily_brief_items dbi ON dbi.brief_run_id = br.run_id
JOIN careerloop.jobs j ON j.id = dbi.job_id
JOIN careerloop.daily_briefs db ON db.id = dbi.brief_id
LEFT JOIN careerloop.application_packs ap ON ap.job_id = j.id AND ap.user_id = br.user_id
WHERE br.run_id = %s
ORDER BY dbi.item_index;
```

## Phase 2 — Clean Architecture (Week 3)

### 2.1: Repository layer enforcement
All DB access through `careerloop/memory/repository_v2.py` or service-specific repos. No raw SQL in tool_registry, daily_runner, or scan_service.

### 2.2: Remove direct DB from chat tools
`tool_registry.py` currently has 15+ raw SQL queries. Move each to its owner service.

### 2.3: Single DB manager instance
`DatabaseManager` singleton already exists (`_get_db()`). Enforce it everywhere. No `DatabaseManager(os.getenv("DATABASE_URL"))` in any service.

---

# PART 4: BEFORE/AFTER

| Dimension | Before | After |
|-----------|--------|-------|
| Job IDs | `loop-XXXX`, `uuid4.hex[:8]`, `pack_XX` | One `UUIDv4` per job, generated in `JobService` |
| Job persistence | 4 files write directly to `careerloop.jobs` | Only `JobService.persist_job()` |
| Brief persistence | `daily_runner.py` + `scan_service.py` + raw SQL | Only `BriefService` |
| Session writes | `session_store.py` + `brief_service.py` + `chat_service.py` | Only `SessionService` |
| Run lifecycle | Scattered across 5+ files | Only `BackgroundRunService` |
| Filesystem deps | 7 active filesystem paths | 0 (filesystem = export/migration only) |
| Exception handling | `pass`, `return {}`, `return None` | Log + propagate. Catch only at API boundary. |
| Tracing a job | Impossible — IDs don't link | One SQL query traces scan→job→brief→pack |
| Application packs | QUEUED row, never generated | Generated via `ApplicationService` with real files |

---

# PART 5: SUCCESS CRITERIA

```
✅ ledger.json is never written by any production workflow
✅ No raw SQL in tool_registry.py, daily_runner.py, scan_service.py
✅ Every careerloop.* table has exactly one writer service
✅ Every job has a canonical UUID surviving its entire lifecycle
✅ A single SQL query traces: scan run_id → job_id → brief_id → pack_id
✅ Zero `except Exception: pass` in production code paths
✅ Zero filesystem reads in the Scan → Brief → Inspect → Approve → Pack path
```

---

This is the target. Phase 0 is the emergency migration — 5 changes that can ship this week. Phase 1 consolidates. Phase 2 enforces. The architecture audit (SYSTEMS_ARCHITECTURE_AUDIT_2026-05-29.md) maps exactly what is where today. The data lineage audit (DATA_LINEAGE_AUDIT_2026-05-29.md) traces exactly what data flows where. This document describes where everything must go.
