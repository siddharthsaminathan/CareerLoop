# CareerLoop Deployment Strategy

**Status:** Draft v1 — 2026-05-29  
**Author:** Product Engineering Lead  
**Priority:** P0 — blocking all user-facing delivery

---

## 1. Vision

CareerLoop will deploy as a **web application first**, with native iOS and Android clients following once the product loop is validated at scale.

```
Phase 1 (NOW):   Web App (PWA-capable) → REST API
Phase 2 (Q3):    iOS App → SwiftUI + Supabase SDK
Phase 3 (Q3/Q4): Android App → Kotlin + Supabase SDK
```

**Key insight:** A web app ships in minutes, not weeks. App store reviews kill iteration speed. We validate the loop on web, then wrap it in native shells.

---

## 2. Why Web-First (Not Telegram/WhatsApp)

| Channel | Verdict | Why |
|---------|---------|-----|
| **Web App** | ✅ **PRIMARY** | Fastest iteration, no approval, full UI control, PWA-capable |
| iOS/Android | 🟡 Phase 2-3 | App store friction, but required for push notifications + offline |
| Telegram | 🔴 **PERMANENTLY DELAYED** | Bot API limitations on rich UI, no control over user experience |
| WhatsApp | 🔴 **PERMANENTLY DELAYED** | Meta API approval process, 24hr messaging window, no structured cards |

All references to Telegram webhook, WhatsApp webhook, and transport abstraction layer as a **P0 dependency** are now superseded by this document.

---

## 3. Architecture

```
┌─────────────┐     ┌──────────────┐     ┌──────────┐
│  Frontend   │────▶│  REST API    │────▶│ Supabase │
│  (React/TS) │◀────│  (FastAPI)   │◀────│ (PG)     │
└─────────────┘     └──────┬───────┘     └──────────┘
                           │
                    ┌──────▼───────┐
                    │  Background  │
                    │  Workers     │
                    │  (threads)   │
                    └──────────────┘
```

### Components

| Component | Tech | Notes |
|-----------|------|-------|
| **Frontend** | React + TypeScript + Tailwind | PWA wrapper (manifest + service worker) |
| **API** | FastAPI + uvicorn | Single process, Gunicorn for multi-worker in prod |
| **DB** | Supabase (PostgreSQL) | Managed Postgres with auth + realtime |
| **Background** | Python threading | Scan workers run in-process threads. Replaceable with Celery/ARQ later |
| **Storage** | Supabase Storage | For PDFs, resumes, company logos |
| **Auth** | Supabase Auth | Google OAuth (web), ASWebAuthenticationSession (iOS), Custom Tabs (Android) |

---

## 4. Deployment Targets (Ranked)

| Target | Cost | Complexity | Best For | Verdict |
|--------|------|-----------|----------|---------|
| **Fly.io** | $0-5/mo (free tier) | Low | FastAPI apps, global regions, auto-scaling | ✅ **Recommended** |
| Railway | $0-5/mo | Low | Easy deploys from GitHub | 🟡 Good alternative |
| Render | $0/mo (free tier) | Low | Simple web services | 🟡 Good for MVP |
| Vercel | $0/mo | High for backend | Serverless functions only | ❌ Not for long-running API |
| AWS/GCP | $10-50/mo | High | Full control | ❌ Too early |

### Recommendation: **Fly.io** (Primary) + **Supabase** (DB + Auth)

**Why Fly.io:**
- First 3 VMs on free tier (shared-cpu-1x @ $0)
- Built-in global load balancing
- Work with long-running connections (SSE scan streaming)
- Auto-scaling from 0 to N
- `fly.toml` config is simple
- Supports docker or raw `Dockerfile`

---

## 5. Infrastructure Setup

### Required Environment Variables (Production)

```bash
# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=eyJ...                  # public, safe in client
SUPABASE_SERVICE_KEY=eyJ...               # private, server-only
SUPABASE_JWT_SECRET=your-jwt-secret       # from Supabase dashboard

# API
DATABASE_URL=postgresql://postgres:pass@host:5432/postgres
CAREERLOOP_DB_SCHEMA=careerloop
CAREERLOOP_API_CORS=https://your-frontend.vercel.app
LOG_LEVEL=info

# Portal API Keys (for scanning)
SERPAPI_KEY=...
NOKRI_KEY=...
LINKEDIN_COOKIE=...
```

### CI/CD Pipeline (GitHub Actions)

```yaml
# .github/workflows/deploy.yml
name: Deploy
on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: superfly/flyctl-actions/setup-flyctl@master
      - run: flyctl deploy --remote-only
```

---

## 6. Database Strategy

### Supabase Schema Management

Current state: Migrations are manual SQL files applied via `supabase migration` or direct SQL.

**Recommended approach for MVP:**
1. Keep `careerloop` schema migrations in `db/migrations/` as numbered SQL files
2. Use Supabase Studio for schema inspection (no migration tool needed yet)
3. Run critical migrations manually after verifying on staging

### Schema Security

All `careerloop.*` tables are **server-side only**. The API manages all reads/writes.
- Row Level Security (RLS) is enabled on Supabase
- API uses `SUPABASE_SERVICE_KEY` for database operations
- Frontend never queries Supabase directly (except for auth)

---

## 7. Performance Considerations

### Current Bottlenecks

| Bottleneck | Impact | Mitigation |
|-----------|--------|------------|
| **Thread-based scan workers** | No horizontal scaling, in-process memory | Phase 2: replace with Celery/ARQ + Redis |
| **Polling SSE** | 1s poll = N queries per connection | Phase 2: replace with LISTEN/NOTIFY or pg_notify |
| **In-process provision cache** | Per-worker cache miss on multi-worker | Phase 2: Redis cache layer |
| **No connection pooling** | DB connections per thread | Add `psycopg2.pool.ThreadedConnectionPool` or use `pgbouncer` |

### SSE Architecture Note

The current SSE implementation polls `run_events` every 1s. For <50 concurrent scan viewers this is fine. For scale:
- Replace polling with `LISTEN/NOTIFY` + `asyncpg`
- Or use WebSocket (Supabase Realtime) instead of SSE

For MVP: **SSE is correct.** It's simple, works through proxies, and has native browser support.

---

## 8. Scaling Plan

```
Phase 1 (1-100 users):    Fly.io single VM + Supabase free tier
Phase 2 (100-1000 users): Fly.io auto-scale (2-4 VMs) + Supabase Pro
Phase 3 (1000+ users):    Fly.io global + Celery workers + Redis + CDN
```

### Phase 1 Requirements
- [x] REST API (7 MVP endpoints)
- [x] Auth (Supabase Google OAuth)
- [x] Async scan with SSE streaming
- [ ] Dockerfile
- [ ] fly.toml
- [ ] GitHub Actions deploy workflow
- [ ] Production env vars in Fly.io secrets
- [ ] Health check endpoint (/health)
- [ ] CORS configuration for frontend domain

---

## 9. Monitoring & Observability

### MVP Monitoring (Phase 1)
- **Health endpoint:** `/health` → `{"status": "ok"}`
- **Logs:** Fly.io logs via `fly logs`
- **Error tracking:** Sentry (free tier) for API exceptions
- **Uptime:** Better Stack (free) pings `/health` every 5min

### Phase 2
- Prometheus metrics on FastAPI
- Grafana dashboard for scan latency, error rates, user counts
- Alerting on scan failure rate > 5%

---

## 10. Rollback Strategy

```bash
# Fly.io — rollback to previous release
flyctl releases list
flyctl deploy --image registry.fly.io/careerloop:prev-release-id
```

### Database rollback
- **No destructive migrations in MVP** — all migrations are additive (CREATE TABLE, ADD COLUMN)
- For destructive changes: manual SQL reverse-migration script
- Daily Supabase backups (automatic on Pro tier)

---

## 11. Domain & DNS

- **API:** `api.careerloop.app` → Fly.io
- **Frontend:** `app.careerloop.app` → Vercel (or Fly.io static)
- **Landing:** `careerloop.app` → Vercel landing page

### SSL
- Fly.io auto-provisions Let's Encrypt certificates
- Vercel auto-provisions SSL
- No custom cert management needed

---

## 12. Cost Projection (Phase 1)

| Service | Cost/mo | Notes |
|---------|---------|-------|
| Fly.io (1 VM) | $0 | Free tier: 3 shared-cpu-1x VMs |
| Supabase (free) | $0 | 500MB DB, 50K users, 2GB bandwidth |
| Sentry | $0 | Free tier: 5K events/mo |
| Better Stack | $0 | Free: 3 monitors, 10min checks |
| GitHub Actions | $0 | Free: 2000 min/mo |
| Domain (careerloop.app) | ~$12/yr | Namecheap or Cloudflare Registrar |
| **Total** | **~$1/mo** | |

---

## 13. Timeline

| When | What |
|------|------|
| **2026-05-29** | API deployed to Fly.io staging |
| **2026-05-30** | Frontend connected to production API |
| **2026-06-01** | Internal beta (5 users) on web app |
| **2026-06-15** | Public beta |
| **2026-Q3** | iOS app build |
| **2026-Q3/Q4** | Android app build |

---

## 14. Telegram/WhatsApp — Permanently Delayed

**Decision (2026-05-29):** All Telegram webhook, WhatsApp webhook, and transport abstraction layer work is permanently delayed until further notice.

**Rationale:**
1. A web app provides richer UI (TAL-style cards, swipe, color-coded fit scores)
2. No platform approval process (Telegram Bot API limits, WhatsApp 24hr window)
3. Unified auth via Supabase (Google OAuth works everywhere)
4. Same API serves web, iOS, Android — transport abstraction is the API itself
5. Faster iteration: deploy in minutes, not days

**What this means for existing code:**
- `careerloop/transport/` directory is archived but not deleted
- `webhook_server.py` is deprecated for user-facing use (kept as reference)
- All PRD references to Telegram/WhatsApp as delivery channels are marked as delayed
- The API IS the transport layer now

---
