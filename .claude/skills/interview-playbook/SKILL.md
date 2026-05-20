---
name: interview-playbook
description: Auto-detects when CareerLoop user is venting about interviews and incrementally updates the interview playbook with learnings, blunders, and patterns. Load when user talks about interview experience.
---

# CareerLoop Interview Playbook Updater

## When This Triggers

Detect ANY of these signals in the user's messages:
- "I had an interview at..."
- "The interviewer asked me..."
- "I just finished a round with..."
- "I messed up when they asked..."
- "The interview went well/bad..."
- Venting about interview experience
- Describing questions asked, answers given, blunders made

## Step 1: Extract Structured Data

From the conversation, extract:

```json
{
  "company": "Company name",
  "role": "Job title they interviewed for",
  "date": "YYYY-MM-DD of interview",
  "round": "Screening / Technical 1 / Technical 2 / Final / Unknown",
  "outcome": "Pending / Advanced / Rejected / Offer / Unknown",
  "questions_asked": [
    "Question 1 — exact or paraphrased",
    "Question 2"
  ],
  "what_went_well": [
    "Topic they handled confidently",
    "Good answer they gave"
  ],
  "blunders": [
    {
      "question": "What was asked",
      "what_happened": "What went wrong",
      "root_cause": "Why it went wrong",
      "fix_for_next_time": "How to handle it next time"
    }
  ],
  "learnings": [
    "Key insight for future interviews"
  ],
  "follow_up_actions": [
    "Send thank-you email by date",
    "Prepare X for next round"
  ]
}
```

## Step 2: Append to Playbook

Read `interview-prep/interview-playbook.md`. Append a new entry under `## Interview Log` at the TOP (most recent first):

```markdown
## Company: {company} — {role}
**Date:** {date} | **Round:** {round} | **Outcome:** {outcome}

### Questions Asked
- Question 1
- Question 2

### What Went Well
- Their strength area
- Another strength

### Blunders
#### "{question_asked}"
**What happened:** {description}
**Root cause:** {why}
**Fix:** {how to handle next time}

### Learnings
- Key takeaway 1
- Key takeaway 2

### Follow-Up
- [ ] Action item with deadline
- [ ] Action item with deadline

---
```

## Step 3: Recalculate Patterns

After 2+ interviews in the playbook, update the `## Patterns Across All Interviews` section:

### Recurring Blunders
Scan all blunders. Group by root cause. List top 3-5 with counts:

```markdown
### Your Recurring Blunders
- **"{blunder_type}"** — {count} of {total} interviews
  - Example: Company A, Company B
```

### Most Common Question Types
Categorize questions: System Design, Framework Trivia, Behavioral, ML Theory, Tool Calling, Architecture, DSA, Culture Fit, Compensation.

```markdown
### Most Common Question Types
- **{category}** — asked in {count} interviews
```

### Your Strengths
Scan what_went_well. Group by theme.

```markdown
### Your Strengths
- **{strength_area}** — consistently strong across {count} interviews
```

### Companies & Outcomes
```markdown
| Company | Role | Date | Outcome |
|---------|------|------|---------|
```

## Step 4: Generate Prep Recommendations

At the bottom, add:

```markdown
## Recommended Prep for Next Interview
<!-- Auto-generated from patterns -->

Based on your {N} interviews so far:
1. **Weak area to drill:** {most_recurring_blunder_category}
2. **Most common question to prep:** {most_common_question_type}
3. **Strength to lead with:** {strongest_area}
```

## Step 5: Tell the User

Confirm what was added:
- "Logged your {company} interview. {N} questions, {M} blunders, {K} learnings captured."
- If patterns emerged: "New pattern detected — {blunder_type} has come up in {N} interviews now. Want me to prep you specific drills for that?"

## CRITICAL RULES

1. **Never overwrite.** Always APPEND to the playbook. Every interview is preserved.
2. **Be specific.** Don't write "they asked technical questions." Write "they asked about LangGraph checkpointing — specifically 'how do you persist state?'"
3. **Blunders are honest.** Don't sugarcoat. "Said I don't know 5 times" is more useful than "needs improvement on framework knowledge."
4. **Extract from venting.** Users won't structure their thoughts. You do the structuring. Pick out company names, questions, emotional cues.
5. **Patterns need 2+ data points.** Don't claim a "pattern" from one interview.
6. **Update the playbook file directly.** Use `patch` to insert at the right location. Don't rewrite the whole file.
