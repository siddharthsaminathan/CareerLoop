# Brief Lifecycle Correctness — Architecture Verification

**Date:** 2026-05-30
**Auditor:** Sub-Agent B
**Result:** PASS -- No violations found

## Architecture Boundary

```
Daily Briefing (BriefPage)          Copilot (ChatPage)
        |                                  |
   READ ONLY                          ACTION HUB
        |                                  |
  GET /v1/briefs/latest            POST /v1/scans (SSE)
  POST /v1/briefs/:id/select       POST /v1/chat/message
  POST /v1/jobs/:id/save           GET /v1/chat/history
  POST /v1/jobs/:id/skip
        |                                  |
  BriefService.latest()            runScanInChat()
  (DB read, no side effects)       (async scan + SSE stream)
```

## Verification Results

### 1. Backend Endpoints

| File | Endpoints | Role | Violations |
|------|-----------|------|------------|
| `careerloop_api/routers/briefs.py` | `GET /latest`, `POST /{id}/items/{idx}/select` | Read-only brief + selection | None |
| `careerloop_api/routers/scans.py` | `POST`, `GET /latest`, `GET /{id}`, `GET /{id}/events` | Scan lifecycle + SSE | None |
| `careerloop_api/routers/chat.py` | `POST /message`, `GET /history` | Chat only | None |

**Grep verification:**
- `briefs.py` + `brief_service.py`: zero occurrences of "scan" -- no scan logic leaked into brief layer.
- `scans.py` + `chat.py`: the only "brief" mentions in scans.py are in descriptive comments (documenting the `BRIEF_CREATED` SSE event). Zero brief router logic in scans or chat routers.

### 2. BriefService -- No Side Effects

`BriefService.latest()`:
- Calls `BriefsRepo.get_latest_brief()` -- database read only
- Calls `BriefsRepo.get_items()` -- database read only
- Calls `serializers.brief()` -- pure data transformation
- **No scan triggers, no mutations, no SSE, no background jobs.**

`BriefService.select_item()`:
- Reads brief + item from DB
- Persists active context to SessionStore (non-destructive context update)
- **No scan triggers.**

### 3. Frontend -- BriefPage

| Concern | Status | Detail |
|---------|--------|--------|
| Scan API calls | PASS | Zero `startScan()` or `POST /scans` calls |
| SSE / EventSource | PASS | Zero `fetchEventSource` or `EventSource` usage |
| Brief cache | PASS | `sessionStorage` cache with 5-min TTL, purely client-side |
| "Scan More" button | PASS | Navigates to `/chat?prefill=scan_more` -- navigation only, no API call |
| "Go to Copilot" button | PASS | Navigates to `/chat?prefill=/scan` -- navigation only |
| Empty state "Run a Scan" | PASS | Navigates to `/chat?prefill=scan_more` |
| Empty state "Adjust Preferences" | PASS | Navigates to `/chat?prefill=/scan` |

**Grep verification:** The only matches for "scan" in BriefPage.tsx are `navigate("/chat?prefill=/scan")` calls -- all are routing, not API calls. Zero hits for `startScan`, `/scans`, `fetchEventSource`, `EventSource`, or `SSE`.

### 4. Frontend -- ChatPage

| Concern | Status | Detail |
|---------|--------|--------|
| Scan initiation | PASS | `api.startScan(mode)` -- correct POST to `/scans` |
| SSE streaming | PASS | `fetchEventSource` to `/scans/${runId}/events` |
| Prefill handling | PASS | URL `?prefill=/scan` or `?prefill=scan_more` triggers scan |
| Chat fallback | PASS | Non-scan prefill delegated to `handleUserSubmit()` |
| `/brief` action | PASS | Navigates to `/brief` -- no brief logic implemented in ChatPage |
| Brief cache clear | PASS | `sessionStorage.removeItem("cl_brief_cache")` before scan |

**Grep verification:** Zero hits in ChatPage.tsx for `getLatestBrief`, `/briefs/latest`, `selectBriefItem`, `skipJob`, `saveJob`. No brief-only logic leaked.

### 5. API Client Endpoint Mapping

| Client Method | HTTP Call | Backend Route | Boundary |
|---------------|-----------|---------------|----------|
| `api.getLatestBrief()` | `GET /briefs/latest` | `briefs.py:latest()` | BriefPage only |
| `api.startScan()` | `POST /scans` | `scans.py:start_scan()` | ChatPage only |
| `api.selectBriefItem()` | `POST /briefs/:id/items/:idx/select` | `briefs.py:select_item()` | BriefPage only |
| `api.saveJob()` | `POST /jobs/:id/save` | jobs router | Shared (both pages) |
| `api.skipJob()` | `POST /jobs/:id/skip` | jobs router | Shared (both pages) |
| `api.sendChatMessage()` | `POST /chat/message` | `chat.py:message()` | ChatPage only |
| `api.getChatHistory()` | `GET /chat/history` | `chat.py:history()` | ChatPage only |

### 6. Scan More Button Flow

```
BriefPage "Scan More" button click
  → navigate("/chat?prefill=scan_more")
    → ChatPage mounts, reads prefill param
      → ChatPage effect: runScanInChat("scan_more")
        → api.startScan("scan_more") → POST /v1/scans {"mode":"scan_more"}
          → SSE stream → fetchEventSource to /v1/scans/{runId}/events
            → on DONE → user navigates back to /brief to see results
```

**No direct POST /v1/scans from BriefPage.** The scan is initiated entirely within ChatPage.

## Conclusion

All architecture boundaries are respected:

1. **BriefPage is READ ONLY** -- fetches briefs, handles skip/save, navigates to Copilot for scans.
2. **ChatPage is ACTION HUB** -- initiates scans, streams SSE, handles chat, navigates to BriefPage for viewing.
3. **BriefService has no side effects** -- pure database reads + session context persistence.
4. **No endpoint mixing** -- briefs router only serves briefs, scans router only serves scans, chat router only serves chat.
5. **Scan More flow is correct** -- BriefPage navigates to ChatPage with prefill, ChatPage initiates the scan.

**Zero violations. Zero code changes required.**
