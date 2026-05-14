# Phase 1: India Job Discovery & Evaluation Pipeline

## 1. Executive Summary
The Phase 1 pipeline is the "Discovery Engine" of CareerLoop. Its mission is to find, verify, and score every relevant AI/ML role in India with zero international leakage. It transforms raw, messy internet data into a high-fidelity, structured ledger of opportunities.

---

## 2. The Source of Truth: `ledger.json`
Everything starts and ends with the **Ledger**. 
- **Role:** The persistent, deduplicated database of every job the system has ever seen.
- **Integrity:** No job is added twice. Every entry tracks its own history (from Discovery to Evaluation).
- **Location:** `careerloop/ledger.json`

---

## 3. The Discovery Workflow (The "Search" Layer)
We don't wait for APIs; we hunt for data. The system uses a **Mutually Exclusive, Collectively Exhaustive (MECE)** strategy across four primary channels:

### A. Dynamic Search Queries
The engine generates 20+ specialized search strings targeting:
- **Major Portals:** LinkedIn, Naukri, Cutshort, IIMJobs, FoundIt.
- **Niche Keywords:** "Applied AI Engineer", "Generative AI", "LLM Architect".
- **Geo-Tags:** "Chennai", "Bengaluru", "Hyderabad", "Remote India".

### B. Multi-Engine Fallback
If one search provider (like Google or Brave) rate-limits us, the system automatically falls back to DuckDuckGo, Yandex, or Yahoo to ensure the daily discovery never stops.

---

## 4. The Extraction Layer (Deep Scraping)
Discovered URLs are just "leads." The **ScrapeGraphAI** layer performs deep extraction:
1. **Rendering:** Uses Playwright to render Javascript-heavy job boards.
2. **Structure:** Converts raw HTML into clean JSON containing Title, Company, Location, and JD text.
3. **Efficiency:** Only the top-tier candidates undergo this deep extraction to save time and API costs.

---

## 5. The "India-Lock" Filter (Geographic Hardening)
To eliminate international "leakage" (e.g., jobs in Paris/USA), the pipeline applies a strict **Geographic Verification** script:
- **Inclusion List:** Only roles explicitly mentioning major Indian cities (Chennai, Bengaluru, Hyderabad, Pune, etc.) or "Remote India" are allowed.
- **State Code Check:** Validates against Indian state abbreviations (TN, KA, MH, etc.).
- **Automatic Rejection:** Any role that cannot be definitively placed in India is discarded before hitting the LLM.

---

## 6. The Evaluation Engine (High-Fidelity Scoring)
This is where the **DeepSeek AI** makes decisions based on your specific profile.

### A. The Scoring Pillars
Every job is scored on a 0-100 scale across these dimensions:
- **Role Fit:** Does it match "Senior/Lead AI Product Engineer"? (Rejects frontend/support).
- **Salary Floor:** Does it meet the ₹25L minimum? (Inferred or extracted).
- **Company Type:** Is it a Product/SaaS company? (Rejects Consulting/Body-shops).
- **Skill Alignment:** Does it need PyTorch, LLMs, or RAG?

### B. The Recommendation Logic
- **80-100 (GO):** High-priority application.
- **50-79 (MAYBE):** Needs human review.
- **0-49 (SKIP):** Automatically archived; user never sees it.

---

## 7. Optimization & Guardrails
- **Batching:** The system only "verifies" the top 10-15 jobs in detail to keep the run under 5 minutes.
- **Env Control:** API keys and fit models are centralized in the `.env` file.
- **Unicode Resilience:** Final reports are stripped of problematic emojis to ensure compatibility with all terminals/CSVs.

---

## 8. Final Output
The pipeline produces a **Daily Shortlist** in the `reports/` folder, which is a CSV representation of the top-scored jobs from the Ledger, ready for the "Apply Phase."
