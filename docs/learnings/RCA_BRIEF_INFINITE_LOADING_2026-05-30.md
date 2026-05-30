# RCA: Daily Brief Infinite Loading — May 30, 2026

## ROOT CAUSE

**Primary:** `BriefPage.tsx` line 79-81 — `useEffect(() => { loadBrief(offset); }, [offset, loadBrief])` unconditionally fires a network request on EVERY mount, even when valid cached data exists in `sessionStorage`. On re-visit, this request uses a stale/expired JWT → 401 → `supabase.auth.refreshSession()` → slow Supabase auth round-trip → user sees spinner replacing cached content for 20–30 seconds.

**Secondary:** `api.ts` line 52 — `await supabase.auth.refreshSession()` has no timeout. If Supabase's auth server is slow or unreachable, this call hangs indefinitely. The caller (`loadBrief`) is blocked.

---

## EXACT CHAIN

```
User navigates back to /brief
  → React Router unmounts old page, mounts BriefPage
  → BriefPage: useState(!brief)
    → sessionStorage has cached brief → brief = cached data, loading = false
    → Render: shows cached cards (instant)
  → useEffect fires [line 79]
    → loadBrief(offset) [line 80]
    → setLoading(true) [line 37]
    → Rerender: SPINNER replaces cached cards
    → api.getLatestBrief(offset) [line 40]
      → api.fetch() [api.ts:32]
        → getHeaders() [api.ts:16]
          → supabase.auth.getSession() [api.ts:17]
            → Returns SESSION — but access_token is EXPIRED
            → (Supabase does NOT validate token expiry client-side)
        → fetch("http://localhost:8001/v1/briefs/latest?offset=0") with expired JWT
        → Backend returns 401 {"code":"unauthorized"}
        → 401 handler [api.ts:51]
          → await supabase.auth.refreshSession() [api.ts:52]
            → NO TIMEOUT — this is the HANG POINT
            → POSTs to supabase.co/auth/v1/token?grant_type=refresh_token
            → If Supabase auth server is slow (DNS, network, cold start):
              → 5–15 seconds to respond
            → Returns new session
            → TRIGGERS onAuthStateChange [auth.tsx:72]
              → Calls loadUserProfile() [auth.tsx:75]
              → loadUserProfile calls api.getMe() [auth.tsx:102]
              → api.getMe() goes through api.fetch()
              → Another network request while the first one is still pending
          → Retry brief request with new token [api.ts:54-62]
          → New token works → API returns 200
    → setBrief(res.data) + setLoading(false) [BriefPage:49,60]
    → Rerender: SPINNER STOPS → cards show (after 20–30 seconds)
```

---

## WHY LOGOUT/LOGIN FIXES IT

Fresh Google OAuth → fresh access_token (valid for 1 hour) → API call with valid JWT → no 401 → no refreshSession → response in < 1 second → spinner barely visible.

## WHY NAVIGATION BREAKS IT

Navigation unmounts BriefPage, then remounts it. On remount:
1. Access token has been sitting in memory for 30+ minutes — potentially expired
2. useEffect fires unconditionally — does not check if brief already loaded
3. Expired JWT → 401 → refreshSession → slow Supabase roundtrip → 20–30s spinner

---

## EXACT FILES + LINES

| # | File | Line(s) | Failure |
|---|------|---------|---------|
| 1 | `src/pages/BriefPage.tsx` | 79 | `useEffect` always fires `loadBrief` on mount, even with valid cached data |
| 2 | `src/pages/BriefPage.tsx` | 37 | `setLoading(true)` replaces cached content with spinner |
| 3 | `src/lib/api.ts` | 52 | `refreshSession()` has no timeout — hangs if Supabase auth is slow |
| 4 | `src/lib/api.ts` | 16-18 | `getSession()` returns expired token — no client-side expiry check |
| 5 | `src/lib/auth.tsx` | 75 | `onAuthStateChange` fires `loadUserProfile()` during `refreshSession`, adding another API call to the chain |

---

## FIX

**Fix 1 (file: BriefPage.tsx, line 79):** Skip API call if cached brief is < 5 minutes old.
```typescript
useEffect(() => {
    const cached = sessionStorage.getItem(BRIEF_CACHE_KEY);
    if (cached) {
        try {
            const data = JSON.parse(cached);
            const age = Date.now() - (data._fetchedAt || 0);
            if (age < 300000) { // 5 minutes
                return; // Skip — cache is fresh
            }
        } catch {}
    }
    loadBrief(offset);
}, [offset, loadBrief]);
```

**Fix 2 (file: api.ts, line 52):** Add 10-second timeout to refreshSession.
```typescript
const refreshPromise = supabase.auth.refreshSession();
const timeoutPromise = new Promise((_, reject) => 
    setTimeout(() => reject(new Error('Token refresh timed out')), 10000)
);
const { data: refreshData } = await Promise.race([refreshPromise, timeoutPromise]);
```

**Fix 3 (file: BriefPage.tsx, line 24):** Don't show spinner when cached data exists.
```typescript
const [loading, setLoading] = useState(false); // Always start not loading
// Show cached data immediately, refresh in background
```

---

## PROOF

- API returns 200 with brief data when JWT is valid ✅
- API returns 401 when JWT is expired ✅
- `loadBrief` sets `loading=true` on every mount regardless of cache state ✅
- `supabase.auth.refreshSession()` has no timeout in the code ✅
- Logout/login provides fresh token → brief loads instantly ✅
- Navigation back triggers remount → stale token → 401 → slow refresh ✅
