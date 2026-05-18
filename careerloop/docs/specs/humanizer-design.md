# CareerLoop — Humanizer Layer Design Spec

**Status:** Spec — implementation pending  
**Target file:** `careerloop/council/humanizer.py`  
**PRD Reference:** §12 — Humanizer Layer  
**Priority:** P0 — blocks Resume Council quality

---

## 1. Purpose

The Humanizer transforms AI-generated career communication into text that reads as if a thoughtful, competent human wrote it. It is a **post-processing pass** that runs after Council output and before the renderer.

This is a monetizable wedge. The difference between "AI wrote this" and "a human wrote this" is the difference between a ignored application and an interview.

---

## 2. What It Operates On

| Input | Source | Output |
|-------|--------|--------|
| `resume_markdown` | Council `assembly_node` | Humanized resume text |
| `cover_note` | Council `assembly_node` | Humanized cover note |
| `recruiter_message` | Council `assembly_node` | Humanized outreach |
| `follow_up_message` | Future: follow-up scheduler | Humanized follow-up |

Humanizer does NOT touch:
- `positioning_strategy` (internal, never user-facing)
- `quality_report` (internal audit artifact)
- `preservation_contract` (internal constraint artifact)

---

## 3. Core Rules (The Immutable List)

### 3.1 Banned Words

These words and their variants must never appear in humanized output:

```
passionate, leverage (verb), spearheaded, synergize/synergy,
revolutionize, disrupt/disruptive, game-changer, best-in-class,
cutting-edge, state-of-the-art, thought leader, ninja/guru/wizard,
rockstar, hustle, grind, deep dive (noun), unlock (metaphorical),
supercharge, empower (generic), innovative (standalone)
```

Detection: exact + lemma match (e.g., "leveraged" → flag, "leveraging" → flag).

### 3.2 Banned Phrases

```
"in this essay I will", "it is important to note",
"I am writing to express my interest", "as a highly motivated",
"with a proven track record", "results-driven professional",
"I believe I am the ideal candidate", "I am confident that",
"thank you for taking the time", "I look forward to hearing"
```

Detection: substring match case-insensitive.

### 3.3 Structural Rules

1. **No sentence starts with "I" more than 2 times consecutively.**
2. **Paragraphs max 4 sentences.**
3. **Sentences max 35 words.** (Split longer ones.)
4. **No rhetorical questions in cover notes or recruiter messages.**
5. **Bullet points must start with action verbs** (past tense for experience, present for current role).
6. **No exclamation marks** in professional communication (resume, cover note, recruiter message).
7. **Numbers under 10 spelled out** in prose (not bullet points).

---

## 4. Tone Profiles

The Humanizer adapts tone based on the `PositioningStrategy.tone_guidance` and company type.

### 4.1 Default (unknown company)

- Direct, confident, specific
- No filler adjectives
- Every sentence carries information

### 4.2 Startup (<50 employees)

- Leaner sentences
- More action-oriented
- "Built" over "responsible for"
- "Shipped" over "delivered"
- Less formal salutations

### 4.3 Enterprise (500+ employees)

- Slightly more formal (but not stiff)
- Full sentences preferred over fragments
- Standard salutations ("Dear Hiring Team,")
- Quantified achievements emphasized

### 4.4 Recruiter DM

- 2 sentences max, under 250 characters
- Sentence 1: what caught attention about the role/company
- Sentence 2: one specific qualification
- No "Hi I'm X and I'm interested in Y" — skip straight to value
- Must feel like a DM, not an email

---

## 5. Architecture

```
┌──────────────────────────┐
│   Council assembly_node  │
│   produces raw text      │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│   Humanizer.humanize()   │
│                          │
│  Phase 1: Strip banned   │
│  Phase 2: Structural fix │
│  Phase 3: Tone adapt     │
│  Phase 4: Final polish   │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│   compiler.py /          │
│   generate-pdf.mjs       │
└──────────────────────────┘
```

### 5.1 Interface

```python
class Humanizer:
    def humanize(self, text: str, mode: str, context: dict = None) -> str:
        """
        Humanize text for a specific mode.

        Args:
            text: Raw AI-generated text
            mode: "resume" | "cover_note" | "recruiter_message" | "follow_up"
            context: {
                "tone": "startup" | "enterprise" | "default",
                "writing_style_notes": str (from _profile.md),
                "company_name": str,
                "role_title": str
            }

        Returns:
            Humanized text
        """
```

### 5.2 Internal Pipeline

```python
def humanize(self, text, mode, context):
    text = self._strip_banned(text)
    text = self._structural_fix(text, mode)
    text = self._tone_adapt(text, context)
    text = self._final_polish(text, mode)
    return text
```

---

## 6. Phase-by-Phase Detail

### Phase 1: Strip Banned

- Scan for all banned words (3.1) and banned phrases (3.2)
- Replace with context-appropriate alternatives:
  - "passionate about" → "focused on" / "experienced in" / nothing
  - "spearheaded" → "led" / "built" / "ran"
  - "leverage" → "use" / "apply" / "draw on"
  - "innovative" → remove (the thing either is or isn't, the reader decides)
- If a banned phrase is structural ("I am writing to express..."), remove it entirely and start with the actual content

### Phase 2: Structural Fix

- Count consecutive "I"-starting sentences → rewrite every 3rd
- Split sentences >35 words
- Merge fragments if 2+ consecutive sentences <5 words
- Remove exclamation marks
- Check bullet points start with action verbs (past tense for past roles)

### Phase 3: Tone Adapt

- If `tone == "startup"`: shorten sentences, prefer active voice, relax salutation formality
- If `tone == "enterprise"`: ensure full sentences, standard salutations, quantified metrics prominent
- If `writing_style_notes` provided: apply user-specific preferences (e.g., "I use contractions", "I never use semicolons")

### Phase 4: Final Polish

- Read the text top-to-bottom and check:
  - Does every sentence carry information? (Delete those that don't.)
  - Is the confidence level appropriate? (No fake confidence, no false humility.)
  - Would this pass as written by a human colleague? (If not, iterate.)

---

## 7. LLM vs Deterministic

The Humanizer runs with minimal LLM cost. Phases 1 and 2 are purely deterministic (regex + string operations). Phase 3 uses a small LLM call with a strict prompt. Phase 4 is deterministic.

| Phase | Method | LLM Cost |
|-------|--------|----------|
| 1. Strip | Regex | $0 |
| 2. Structure | Regex + rules | $0 |
| 3. Tone | Small LLM call (1 per text) | ~$0.001 |
| 4. Polish | Deterministic quality check | $0 |

Total: ~$0.003 per application pack.

---

## 8. Integration Points

| Integration | Where | When |
|-------------|-------|------|
| Council output | `assembly_node` in `graph.py` | After assembly, before file write |
| Resume text | `assembly_node` → humanize `resume_markdown` | Before HTML template fill |
| Cover note | `assembly_node` → humanize `cover_note` | Before final pack |
| Recruiter DM | `assembly_node` → humanize `recruiter_message` | Before final pack |
| Follow-ups | `followup-cadence.mjs` → future | After draft generation |
| LinkedIn outreach | `modes/contacto.md` → future | After message generation |

---

## 9. Non-Goals (What Humanizer Does NOT Do)

- Does NOT check factual accuracy (Truth Guard's job)
- Does NOT validate against resume (User Truth's job)
- Does NOT rewrite for ATS keywords (Role Decode's job)
- Does NOT change the positioning angle (Positioning Strategy's job)
- Does NOT add content — only transforms existing content

---

## 10. Success Criteria

1. **Blind test:** Human reader cannot distinguish Humanizer output from a thoughtful human's writing.
2. **Zero banned words in output** (100% mechanical enforcement).
3. **<5% LLM-rejection rate** (Phases 1-2 should handle 95% of issues deterministically).
4. **<0.5s latency** for full pipeline (deterministic phases are instant, LLM tone pass is fast).

---

*Spec written 2026-05-18. Implementation target: this sprint (P0).*
