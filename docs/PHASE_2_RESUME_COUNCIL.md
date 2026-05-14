# Phase 2: Resume Council + Company Intelligence

## Status

Phase 2 begins after Phase 1 discovery has produced a `VerifiedJob` / scored ledger entry and the user explicitly expresses interest.

This phase must never run for every discovered job.

## Core purpose

Resume Council answers one question:

> For this specific job, how should this specific user present themselves so they look credible, relevant, and worth interviewing?

This is application intelligence, not generic tailoring, keyword stuffing, or fake polish.

## Correct lifecycle

```text
VerifiedJob
→ User says interested / apply
→ Company Intelligence
→ Role Decode
→ User Truth Check
→ Fit + Gap Analysis
→ Positioning Strategy
→ Resume Plan
→ Section Writers
→ Truth Guard
→ HR Reader
→ Humanizer
→ Final Assembler
→ Application Pack
→ User Review
→ Apply Assist
```

## Hard gates

- Company intelligence runs only after explicit user interest.
- Resume Council runs only after explicit apply/prepare intent.
- One job per council run.
- No batching 20 jobs into one council run.
- No unsupported claims.
- No application is submitted without user review.

## Inputs for one job

- User profile from `config/profile.yml` and `careerloop/profile_extended.yml`
- Master career profile / CV if available
- Confirmed skills
- Weak skills
- Preferences and rejected categories
- Verified ledger job object
- Job description / extracted JD text
- Apply route
- India Fit score and LLM fit result
- Previous resume variants if available
- Previous user feedback from memory

## Company Intelligence

Purpose:

- What does this company actually care about?
- Should this user want this company?
- How should the user position themselves here?

Research dimensions:

- Company product
- Business model
- Company stage
- Funding/stability
- India presence
- Hiring urgency
- Role context
- Culture signals
- Glassdoor themes
- LinkedIn employee signals
- Interview style
- Red flags
- Compensation signals

Output contract:

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

## Role Decoder

Reads the JD and extracts what the role really needs:

- Must-have skills
- Nice-to-have skills
- Hidden expectations
- Seniority level
- Stakeholder load
- Technical depth
- Likely screening keywords
- Likely interview topics
- Application risks

Examples:

- `fast-paced environment` means ambiguity tolerance.
- `cross-functional` means stakeholder communication.
- `GenAI` means practical LLM implementation, not research-heavy ML by default.

## User Truth Layer

Prevents bullshit.

Questions:

- What can the user honestly claim?
- What is strong?
- What is weak?
- What should not be emphasized?
- What would fail in interview?

Outputs:

- Confirmed skills
- Weak skills
- Unverified skills
- Evidence bank
- Strong proof points
- Claims not allowed
- Claims to soften

Hard rule:

> If the resume/profile does not support it, do not add it.

## Fit + Gap Analysis

Compares company needs + role needs + user truth.

Outputs:

- Strongest matches
- Missing requirements
- Risky claims
- Interview risks
- Gaps to soften
- Gaps to avoid mentioning
- Likely recruiter objections
- Application stance: `STRONG_PUSH`, `CAREFUL_POSITIONING`, `STRETCH_APPLICATION`, or `SKIP_AFTER_INTEREST`

## Positioning Strategist

Creates the narrative:

> Why this user, for this role, at this company, right now?

Decides:

- What to lead with
- What to downplay
- Tone
- Story arc
- Company-specific angle
- Recruiter 10-second takeaway

Output contract:

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

## Resume Plan

Before writing, the council creates a plan:

- Sections that change
- Sections that stay
- Skills reorder
- Bullets needing rewrite
- Risky claims
- Company keywords that matter
- What not to touch

This prevents random full-resume rewrites.

## Section Writers

Each section writer receives only:

- Original section
- Relevant evidence
- Positioning strategy
- Role requirements
- Risk warnings

Each output includes:

- Rewritten text
- Change reason
- Claims added
- Claims removed
- Confidence
- Risks

## Truth Guard

Mandatory review stage.

Flags:

- Unsupported claims
- Fake metrics
- Exaggerated ownership
- Skills not evidenced
- Overstrong language
- Claims likely to backfire

If issues exist, the guard rewrites safer.

## HR Reader

Simulates a recruiter’s 10-second scan.

Checks:

- Role fit appears immediately
- Opening is strong
- Bullets are readable
- Resume is not too dense
- Strongest signals are visible
- Likely objection
- Human feel

## Humanizer

Anti-AI layer. Removes:

- Generic corporate wording
- Fake confidence
- `passionate`
- `results-driven`
- Unnatural phrasing
- Excessive metrics
- Keyword stuffing
- Robotic transitions

Tone:

- Grounded
- Clear
- Specific
- Human
- Confident but not inflated

## Application Pack

For every approved job, output:

- Final resume/profile
- Cover note
- Why this company
- Why this role
- Relevant experience answer
- Notice period answer
- Salary expectation placeholder
- Recruiter message
- Follow-up message
- Quality report

Quality report includes:

- Positioning
- Main risk
- User must review
- Confidence

## User Review UX

Do not dump files by default.

Chat format:

```text
Application pack ready.
Role: Applied AI Engineer — Company X

Positioning:
Practical AI builder who has shipped LLM workflows, not research-heavy ML.

Changed:
- summary
- 3 experience bullets
- skills order

Risks:
- Kubernetes is weak; I softened it.
- Salary not disclosed; kept flexible.

Reply:
approve
show summary
show changes
make safer
make stronger
```

## Memory loop

Every user edit becomes memory:

- “Don’t make me sound too senior.” → tone preference
- “I can’t defend Kubernetes.” → weak skill
- “This sounds too AI-generated.” → stronger humanizer rules
- “I like this version.” → successful positioning pattern

## Cost control

- Discovery fit score: cheap and broad
- Company intelligence: only after interest
- Resume Council: only after apply/prepare
- Deep company research: only high-value roles
- Interview prep: only after interview stage

Use smaller models for:

- JD extraction
- Section rewrite
- Humanizer

Use stronger models for:

- Positioning strategy
- Truth/risk review
- Final quality review

## North star

The final output should make the user feel:

> This is exactly how I would present myself if I had 6 hours, a great recruiter, and zero anxiety.
