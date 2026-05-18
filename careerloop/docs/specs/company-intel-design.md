# CareerLoop — Company Intelligence Engine Design Spec

**Status:** Spec — implementation pending  
**Target file:** `careerloop/company_intel.py`  
**PRD Reference:** §9 — Company Intelligence  
**Priority:** P1 — replaces placeholder node in Council, enables lazy-loaded deep intel

---

## 1. Purpose

`company_intel.py` is the structured company intelligence engine for CareerLoop. It replaces the current Council `company_intelligence_node` (which asks an LLM to recall company facts from training data — unreliable) and supersedes `modes/deep.md` (which generates a prompt for the user to take elsewhere — not intelligence).

The module must answer one question for every company the user expresses interest in:

> **"Should this specific user want this specific company, and how should they position for it?"**

---

## 2. Trigger: Lazy-Loaded Only

Company Intelligence runs **only after the user marks a job INTERESTED** (ledger transition `DISCOVERED → SHORTLISTED → INTERESTED`). It is never run on all discovered jobs.

| Trigger | Ledger Transition | Who Initiates |
|---------|-------------------|---------------|
| User marks job INTERESTED | `SHORTLISTED → INTERESTED` | User action |
| User clicks "Tell me about this company" | Any status | User explicit request |
| Council run initiated | `INTERESTED → APPLY` or `PREPARE_APPLICATION` | Council orchestrator |

---

## 3. Output Contract

Must produce a populated `CompanyIntelligence` dataclass (already defined in `careerloop/council/models.py`):

```python
@dataclass
class CompanyIntelligence:
    summary: str                    # 2-3 sentence company overview
    business_model: str            # How they make money, B2B/B2C, revenue model
    india_presence: str            # Office locations, team size in India, remote policy for India
    maturity: str                  # "startup" | "growth" | "enterprise" | "unknown"
    hiring_urgency: str            # "HIGH" | "MEDIUM" | "LOW" | "UNKNOWN" — are they actively building?
    culture_signals: List[str]     # Glassdoor themes, eng blog tone, public statements
    red_flags: List[str]           # Layoffs, funding issues, toxic signals, high churn
    positioning_implications: str  # 1-2 sentences: what THIS user should lead with
    interview_implications: str    # 1-2 sentences: likely interview style + preparation focus
    confidence: float              # 0.0-1.0 — how confident is this intelligence?
    missing_data: List[str]        # What we couldn't determine
```

---

## 4. Research Sources (Priority Order)

### 4.1 Primary (web-scraped, per-invocation)

| Source | What It Provides | Method |
|--------|-----------------|--------|
| Company career page | Open roles count, hiring velocity, office locations | WebFetch or ScrapeGraphAI |
| Crunchbase / Tracxn | Funding stage, total raised, recent round date | WebSearch |
| Glassdoor (public) | Employee reviews summary, CEO approval, recommend-to-friend % | WebSearch |
| LinkedIn company page | Employee count, growth rate, recent hires | WebSearch or API |
| Levels.fyi (public) | Compensation bands for India roles | WebSearch |
| News / TechCrunch / ET | Recent funding, layoffs, strategy shifts | WebSearch |

### 4.2 Secondary (cached, cross-invocation)

| Source | Cache Location | TTL |
|--------|---------------|-----|
| `company_memory` table | SQLite `company_memory` | 30 days for facts, 7 days for hiring signals |
| Prior Council runs | `positioning_memory` | Perpetual (accumulating) |
| `application_ledger` | `ledger.json` | Real-time (status + recruiter feedback) |

---

## 5. Architecture

```
┌─────────────────────────────────┐
│  User marks job INTERESTED      │
│  (ledger transition)            │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│  company_intel.research()       │
│                                 │
│  1. Check company_memory cache  │
│     → cache hit + fresh? return │
│  2. WebSearch across sources    │
│  3. Structured extraction (LLM) │
│  4. Populate CompanyIntelligence│
│  5. Cache to company_memory     │
│  6. Return                      │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│  Council graph.py receives      │
│  pre-computed CompanyIntelligence│
│  (no raw LLM call in graph)     │
└─────────────────────────────────┘
```

### 5.1 Interface

```python
class CompanyIntelligenceEngine:
    def __init__(self, root: str):
        self.root = root
        self.cache = CompanyMemoryRepo(root)   # SQLite company_memory table
        self.llm = CouncilLLMClient("strategy")

    def research(self, company: str, role_title: str = None,
                 jd_text: str = None, user_profile: dict = None) -> CompanyIntelligence:
        """
        Produce structured company intelligence for one company.

        Args:
            company: Company name
            role_title: Optional — job title for role-specific positioning
            jd_text: Optional — full JD text for hiring-intent signal extraction
            user_profile: Optional — user profile for personalized positioning_implications

        Returns:
            Populated CompanyIntelligence with confidence score
        """

    def _from_cache(self, company: str) -> Optional[CompanyIntelligence]:
        """Check company_memory table. Return None if stale or missing."""

    def _to_cache(self, company: str, intel: CompanyIntelligence) -> None:
        """Write to company_memory table with timestamp."""

    def _gather_signals(self, company: str) -> dict:
        """WebSearch across 6+ sources. Return raw signals dict."""

    def _synthesize(self, raw_signals: dict, role_title: str,
                    jd_text: str, user_profile: dict) -> CompanyIntelligence:
        """LLM: convert raw signals into structured intelligence. ONE call."""
```

---

## 6. The LLM Synthesis Prompt (Key Design)

The synthesis prompt is the core of this module. It must:

1. **Accept raw signals** (search results from 6+ sources, deduplicated and summarized)
2. **Accept user context** (role target, preferences, deal-breakers from `_profile.md`)
3. **Accept role context** (JD text, title)
4. **Produce structured CompanyIntelligence JSON**

### Prompt Structure

```
You are a company intelligence analyst for an Indian professional's career search.

RAW RESEARCH:
{business_model_signal}
{funding_signal}
{glassdoor_signal}
{hiring_signal}
{culture_signal}
{news_signal}

USER CONTEXT:
- Target roles: {roles}
- Deal-breakers: {deal_breakers}
- Preferred company stage: {preferred_stage}
- Minimum salary floor: {salary_floor} INR

ROLE CONTEXT:
- Title: {role_title}
- JD Summary: {jd_summary}

TASK:
Synthesize structured intelligence. Be specific. If a signal is missing, use UNKNOWN.

RULES:
1. Do NOT invent facts not present in the research above.
2. "UNKNOWN" is better than a guess.
3. Position the company relative to THIS user's goals — not generic praise.
4. Red flags must be evidence-backed (cite source).
5. Confidence reflects signal quality, not your certainty about guesses.

OUTPUT (valid JSON only):
{the CompanyIntelligence schema}
```

---

## 7. Caching Strategy

| Signal Type | TTL | Rationale |
|-------------|-----|-----------|
| `business_model` | 90 days | Rarely changes |
| `india_presence` | 30 days | Office changes infrequent |
| `maturity` | 90 days | Funding stage changes slow |
| `hiring_urgency` | 7 days | Can change week-to-week |
| `culture_signals` | 30 days | Slow-moving |
| `red_flags` | 7 days | Layoff news is time-sensitive |
| `positioning_implications` | Per-invocation | Role-specific, depends on JD + user |
| `interview_implications` | 7 days | Interview patterns change slowly |
| `confidence` | Per-invocation | Always recompute |

Cache key: normalized(company_name). Check on every invocation. Return cached if all requested signals are fresh. Otherwise, re-gather stale signals only.

---

## 8. Integration with Council

### Before (current graph.py:89-93):

```python
def company_intelligence_node(state):
    prompt = f"Company: {state['company']}\nJD: {state['jd_text']}"
    result = _call(_S3_SYSTEM, prompt)  # LLM recalls from memory → unreliable
    return {**state, "company_intelligence": result}
```

### After:

```python
def company_intelligence_node(state):
    engine = CompanyIntelligenceEngine(root)
    intel = engine.research(
        company=state["company"],
        role_title=state["job_title"],
        jd_text=state["jd_text"],
        user_profile=state["profile"]
    )
    return {**state, "company_intelligence": intel.to_dict()}
```

The Council graph node becomes a thin wrapper. All intelligence gathering lives in `company_intel.py`.

---

## 9. Non-Goals

- Does NOT scrape company internal wikis or private pages
- Does NOT contact recruiters or employees
- Does NOT guarantee accuracy — confidence score communicates uncertainty
- Does NOT replace the user's judgment — it informs it

---

## 10. Success Criteria

1. **>80% confidence on top-100 Indian tech companies** (enough public signal).
2. **<3s latency** (cache hit) / **<15s latency** (cache miss, web search).
3. **Zero hallucinated funding amounts or employee counts** (confidence drops instead).
4. **Positioning implications are company+user-specific**, not generic ("lead with AI experience" is generic; "lead with observability work — their eng blog signals monitoring pain" is specific).

---

*Spec written 2026-05-18. Implementation target: Phase 2 (P1). Prerequisite: company_memory SQLite table.*
