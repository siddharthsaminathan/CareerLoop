# CareerLoop UX: First Principles Architecture

## Core Principle: Daily Briefing = READ, Copilot = ACT

The product has **two modes** with clear separation:

### Daily Briefing (The TAL - Today's Action List)
- **Purpose**: Show today's scored job matches in a readable, actionable list
- **State**: READ-ONLY. Never scans, never mutates.
- **What it does**: `GET /v1/briefs/latest` → render cards
- **Empty state**: "No brief yet. Go to Copilot to scan."
- **Navigation**: Tapping a card → Job Detail page
- **Data lifecycle**: Loaded once, cached in sessionStorage. Navigating away and back = instant render.

### Copilot (The action hub)
- **Purpose**: Onboarding, scanning, chat, Q&A, everything interactive
- **State**: Full interactivity. Scans, chats, asks questions.
- **Scan flow**: User types "/scan" → async POST /v1/scans → SSE stream displayed as chat bubbles → on DONE, show "Brief ready! [View Daily Briefing]"
- **Onboarding**: First-time users land here, go through flow, on PROFILE_READY navigate to /brief

### User Journeys (MECE)

1. **New user**: Landing → Login → OAuth → onAuthStateChange → ProtectedRoute detects onboarding_complete=false → redirect to /onboarding → onboarding chat → PROFILE_READY → refreshUser() → navigate /brief
2. **Returning user (has brief)**: Login → ProtectedRoute → brief loads from cache → instant render
3. **Returning user (needs scan)**: Login → "No brief yet" → tap "Go to Copilot" → type "/scan" → async scan with progress → "Brief ready!" → tap link → /brief
4. **Existing user (wants re-scan)**: Copilot → "/scan" → scan → brief updates
5. **Daily check**: Opens app → /brief loads cached → reviews cards → skips/approves → done
