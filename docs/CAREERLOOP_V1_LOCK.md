# CAREERLOOP v1 — MECE VALIDATION & LOCK
## Siddharth Saminathan | May 17, 2026

---

## 1. V1 PIPELINE — WHAT'S BUILT (7 STAGES)

| Stage | Name | LLM | Status | Output |
|-------|------|-----|--------|--------|
| S1 | Company Intelligence | DeepSeek | ✅ LIVE | Nicobar snapshot, culture, red flags, screening filters |
| S2 | Role Decode | DeepSeek | ✅ LIVE | Must-have skills, hidden expectations, Day 1 deliverables |
| S3 | User Truth Check | DeepSeek | ✅ LIVE | Confirmed skills, weak claims, gaps, honest fit score |
| S4 | Fit / Gap Analysis | DeepSeek | ✅ LIVE | Overall fit score, recruiter objections, application stance |
| S5 | Positioning Strategy | DeepSeek | ✅ LIVE | Positioning angle, lead story, headline, what NOT to lead with |
| S6 | Resume Plan | DeepSeek | ✅ LIVE | Bullet rewrites, skills add/remove, risky claims, ATS keywords |
| S7 | Application Pack | DeepSeek | ✅ LIVE | Cover note, recruiter DM, follow-up, quality score, green lights |

**Total: 7 DeepSeek API calls. ~$0.02 per run. 90 seconds end-to-end.**

---

## 2. WHAT'S MISSING (Phase 2 Vision vs v1 Reality)

| Stage | In Vision Doc? | In v1? | Gap |
|-------|---------------|--------|-----|
| Company Intelligence | ✅ | ✅ | — |
| Role Decode | ✅ | ✅ | — |
| User Truth Check | ✅ | ✅ | — |
| Fit + Gap | ✅ | ✅ | — |
| Positioning | ✅ | ✅ | — |
| Resume Plan | ✅ | ✅ | — |
| **Section Writers** | ✅ | ❌ | NOT built. Resume plan suggests changes but doesn't write final resume. |
| **Truth Guard** | ✅ | ⚠️ | Partial. Stage 6 has `risky_claims`. No dedicated guard pass. |
| **HR Reader** | ✅ | ❌ | NOT built. No 10-second recruiter scan simulation. |
| **Humanizer** | ✅ | ⚠️ | Distributed. Stage 5 flags what NOT to lead with. Stage 6 flags risky claims. Stage 7 gives final warnings. But NO dedicated "strip AI-isms" pass. |
| **Final Assembler** | ✅ | ❌ | NOT built. Files are raw JSON. No auto-assembled resume PDF/docx. |
| Application Pack | ✅ | ✅ | — |

---

## 3. HUMANIZER LAYER — VALIDATION

### What EXISTS (distributed across stages):

**Stage 5 — Positioning (`what_NOT_to_lead_with`):**
- ✅ Flags wrong tone: "Reddit DM bot (growth hacking too aggressive)"
- ✅ Flags wrong framing: "Hermes Agent as COO (too experimental)"
- ✅ Flags irrelevant content: "CareerLoop (not relevant to e-commerce)"

**Stage 6 — Resume Plan (`risky_claims`):**
- ✅ "I build AI that automates entire companies" → flagged as too aggressive
- ✅ "Configured Hermes Agent as autonomous COO" → flagged as experimental
- ✅ "Monetizable as SaaS ($199/mo)" → flagged as irrelevant

**Stage 6 — Bullet Rewrites:**
- ✅ Actually softens tone: "growth hacking" → "customer acquisition"
- ✅ Removes jargon: Chrome CDP technical details → business outcome focus
- ✅ Reframes: "autonomous COO" → "autonomous agent for daily operations"

**Stage 7 — Application Pack (`final_warnings`):**
- ✅ "Remove or de-emphasize Reddit DM bot and Hermes Agent as COO"
- ✅ "Practice articulating in business terms, not technical jargon"

### What's MISSING:

| Gap | Impact | Fix |
|-----|--------|-----|
| No dedicated AI-language stripper | Corporate words like "spearheaded", "leveraged", "passionate" may survive | Add Stage 6.5: Humanizer pass |
| No recruiter 10-second scan | Can't validate if resume passes quick-read test | Add Stage 6.8: HR Reader |
| No truth verification pass | Unsupported claims could sneak through | Add Stage 5.5: Truth Guard |

**Verdict:** Humanizer is ~60% implemented. It catches the BIG things (wrong products to lead with, aggressive tone) but misses the small things (corporate language, AI-isms in phrasing).

---

## 4. GO / NO-GO DECISION

### GO ✅ (What works):
- 7-stage pipeline runs end-to-end with zero errors
- Produces actionable output: resume edits, positioning, application pack
- Actual DeepSeek calls, not simulation
- Handles multi-product CVs correctly
- Generates recruiter messages and follow-ups
- Scores are calibrated (85-88 for this role = aggressive apply)

### CONDITIONAL GO ⚠️ (Works but needs attention):
- Humanizer is distributed, not isolated — hard to improve independently
- ATS keyword detection works but doesn't inject them into final text
- Gap mitigation suggestions exist but user must manually implement them

### NO-GO ❌ (Broken or missing):
- No final assembled resume file (only edit suggestions)
- No Section Writers → user must manually apply bullet rewrites
- No PDF/docx generation
- No HR Reader simulation
- No independent Truth Guard pass

**Overall: CONDITIONAL GO.** The pipeline works. It produces real value. But it's an advisor, not an assembler. The user must manually apply the edits.

---

## 5. V1 LOCK — DOCUMENTS & FILES

### Project files:
```
~/Projects/CareerLoop/
├── cv.md                              ← Your CV (updated with Reddit bot, CareerLoop, Hermes)
├── config/profile.yml                 ← Your profile (from career-ops)
├── run_council.py                     ← CLI runner (Nicobar job added)
├── careerloop/council/
│   ├── graph.py                       ← LangGraph state machine (7 stages)
│   ├── stages.py                      ← Deterministic fallbacks
│   ├── llm.py                         ← DeepSeek client
│   ├── models.py                      ← Typed contracts
│   └── orchestrator.py                ← One-job runner
├── output/
│   ├── council-nicobar-ai-pm.json     ← Latest run (42KB JSON)
│   └── test-runs/nicobar/
│       ├── LATEST_RUN_PORTFOLIO_FULL.md    ← Full 7-stage output
│       ├── nicobar_rewritten_resume.md     ← Edits from Stage 6
│       ├── nicobar_outreach_dm.md          ← LinkedIn DM to Raul
│       ├── nicobar_full_application_pack.md← Complete application
│       ├── nicobar_humanizer_notes.md      ← Humanizer findings
│       ├── REDDIT_BOT_PRD_YC_READY.md      ← Reddit bot PRD
│       └── NICOBAR_APPLICATION_PACK_FULL.md← Earlier full pack
└── docs/
    ├── PHASE_1_PIPELINE.md            ← Discovery engine doc
    ├── PHASE_2_RESUME_COUNCIL.md       ← Vision for full council
    └── ARCHITECTURE.md                ← System overview
```

---

## 6. NEXT STEPS — v1.1

1. **Section Writers (S6.5):** Actually assemble the final resume text from the plan
2. **Humanizer (S6.8):** Dedicated pass to strip AI-isms, corporate language
3. **HR Reader (S6.9):** 10-second recruiter scan of final resume
4. **Truth Guard (S5.5):** Independent verification pass between positioning and resume plan
5. **PDF export:** Auto-generate ATS-optimized PDF from final resume

---

## 7. HANDOFF SUMMARY

**What we built:** A 7-stage LangGraph Resume Council that takes a job description + your CV → produces company intelligence, role analysis, fit scoring, positioning strategy, resume edits, and a full application pack. 7 DeepSeek calls, ~$0.02 per run, 90 seconds.

**What we validated:** Ran against real Nicobar AI Product Engineer JD with your full portfolio (Emote, Omnex, Reddit bot, CareerLoop, Hermes). Fit: 85/100. Quality: 88/100. Tech fit: 90/100. Stance: Aggressive apply.

**What's delivered:** Rewritten resume edits, LinkedIn DM to Raul Rai, cover note, follow-up message, humanizer notes, Reddit bot PRD.

**What's next:** v1.1 adds Section Writers, Humanizer, HR Reader, Truth Guard, and PDF export to close the gap between "advisor" and "assembler."

---

*v1 locked May 17, 2026. 11:15 PM IST.*
