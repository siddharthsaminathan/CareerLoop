# Phase 2 Implementation Plan — Resume Council + Company Intelligence

## Objective

Build the one-job application intelligence layer that starts only after user interest and produces a truth-preserving application pack for user review.

## Non-goals

- Do not run company intelligence during daily discovery.
- Do not generate resumes for every shortlisted job.
- Do not auto-submit applications.
- Do not rewrite full resumes without section plans.
- Do not invent skills, metrics, employers, seniority, or ownership.

## Phase 2 architecture

```text
careerloop/council/
  models.py                # Typed contracts for council stages
  context.py               # Load one ledger job + profile + CV/evidence
  llm.py                   # DeepSeek client + JSON-safe calls
  company_intelligence.py  # Lazy company research synthesis
  role_decoder.py          # JD decoding
  truth_layer.py           # User truth and evidence guardrails
  positioning.py           # Narrative and application stance
  resume_plan.py           # Section-level plan before writing
  application_pack.py      # Final pack assembly and review summary
  orchestrator.py          # One-job council runner
```

## Trigger model

Council runner requires:

- `job_id`
- `user_intent` in `INTERESTED`, `APPLY`, or `PREPARE_APPLICATION`

If intent is absent, the runner returns a blocked result and does no research.

## Model routing

Use `config/models.yml`:

- `fit_engine`: existing fast scoring model
- `scrape_engine`: existing extraction model
- `resume_council.strategy_model`: stronger reasoning model for positioning/truth review
- `resume_council.writer_model`: cheaper model for section rewrites/humanizer

Environment overrides:

- `CAREERLOOP_COUNCIL_STRATEGY_MODEL`
- `CAREERLOOP_COUNCIL_WRITER_MODEL`

Both use the same `DEEPSEEK_API_KEY` and `DEEPSEEK_BASE_URL`.

## Data contracts

### CompanyIntelligence

```json
{
  "company_summary": "",
  "why_this_role_exists": "",
  "company_maturity": "",
  "hiring_urgency": "",
  "likely_screening_filters": [],
  "culture_signals": [],
  "red_flags": [],
  "positioning_implications": [],
  "interview_implications": []
}
```

### RoleDecode

```json
{
  "must_have_skills": [],
  "nice_to_have_skills": [],
  "hidden_expectations": [],
  "seniority_level": "",
  "stakeholder_load": "",
  "technical_depth": "",
  "likely_screening_keywords": [],
  "likely_interview_topics": [],
  "application_risks": []
}
```

### UserTruth

```json
{
  "confirmed_skills": [],
  "weak_skills": [],
  "unverified_skills": [],
  "evidence_bank": [],
  "strong_proof_points": [],
  "claims_not_allowed": [],
  "claims_to_soften": []
}
```

### FitGapAnalysis

```json
{
  "strongest_matches": [],
  "missing_requirements": [],
  "risky_claims": [],
  "interview_risks": [],
  "gaps_to_soften": [],
  "gaps_to_avoid": [],
  "likely_recruiter_objections": [],
  "application_stance": "CAREFUL_POSITIONING"
}
```

### PositioningStrategy

```json
{
  "one_line_positioning": "",
  "narrative_angle": "",
  "lead_strengths": [],
  "downplay": [],
  "tone": "",
  "recruiter_first_impression": "",
  "company_specific_angle": ""
}
```

### ApplicationPack

```json
{
  "job_id": "",
  "company": "",
  "role": "",
  "positioning": "",
  "cover_note": "",
  "why_this_company": "",
  "why_this_role": "",
  "relevant_experience_answer": "",
  "notice_period_answer": "",
  "salary_expectation_placeholder": "",
  "recruiter_message": "",
  "follow_up_message": "",
  "quality_report": {},
  "whatsapp_review_summary": ""
}
```

## Implementation milestones

### M1 — Documentation and contracts

- `[x]` Create Phase 2 vision doc.
- `[x]` Create Phase 2 implementation plan.
- `[x]` Create Phase 1 gap tracker.
- `[ ]` Add typed council data contracts.

### M2 — One-job council skeleton

- `[ ]` Load one ledger job by ID.
- `[ ]` Require explicit user intent.
- `[ ]` Load profile and optional CV/evidence.
- `[ ]` Build deterministic role decode fallback.
- `[ ]` Build deterministic truth layer fallback.
- `[ ]` Build deterministic positioning fallback.
- `[ ]` Assemble review summary.

### M3 — LLM-backed stage execution

- `[ ]` Add DeepSeek JSON client.
- `[ ]` Add company intelligence prompt.
- `[ ]` Add role decoder prompt.
- `[ ]` Add positioning strategy prompt.
- `[ ]` Add truth guard prompt.
- `[ ]` Persist company memory and positioning memory.

### M4 — Resume section writing

- `[ ]` Parse master CV/profile into sections.
- `[ ]` Generate resume plan.
- `[ ]` Rewrite selected sections only.
- `[ ]` Run truth guard.
- `[ ]` Run HR reader.
- `[ ]` Run humanizer.

### M5 — User review and apply assist

- `[ ]` Add chat commands: `prepare`, `show changes`, `make safer`, `make stronger`, `approve`.
- `[ ]` Save user edits as positioning memory.
- `[ ]` Generate application pack files only after user requests details.
- `[ ]` Integrate with apply assistant without auto-submit.

## Immediate build target

The first implementation target is a non-destructive council preview:

```powershell
python -m careerloop.council.orchestrator --job-id loop-0135 --intent INTERESTED
```

It should output:

- Company intelligence placeholder/synthesis
- Role decode
- User truth check
- Fit/gap analysis
- Positioning strategy
- Application pack review summary

It should not create final resume files yet.
