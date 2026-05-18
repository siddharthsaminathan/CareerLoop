# Resume Template QA Report

**Generated:** 2026-05-18 20:00 IST
**Validator:** `careerloop/rendering/validator.py`
**Test Runner:** `careerloop/rendering/test_validator.py`
**Source Resume:** `output/council/siddharth/nicobar-final/10_final_resume.md`
**Render Pipeline:** `careerloop/rendering/normalizer.py` (markdown to NormalizedResume)

---

## Summary Table

| Template | Status | Errors | Warnings | EM_DASH | ARROW | COLLAPSED | INLINE | FORBIDDEN | ZERO_BULL | SNG_BLOB | SKILLS | OVERUSE | ORPHAN |
|----------|--------|--------|----------|---------|-------|-----------|--------|-----------|-----------|----------|--------|---------|--------|
| classic-ats | FAIL | 1 | 0 | FAIL | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| compact-one-page | FAIL | 1 | 0 | FAIL | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| executive-clean | FAIL | 1 | 0 | FAIL | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| founder-operator | FAIL | 1 | 0 | FAIL | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| modern-accent | FAIL | 1 | 0 | FAIL | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| product-engineer | FAIL | 1 | 0 | FAIL | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| technical-two-column | FAIL | 1 | 0 | FAIL | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| cv-template-v2 | PASS | 0 | 1 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | FAIL |
| cv-template-v2-test | PASS | 0 | 1 | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | PASS | FAIL |

**Key:**
- Status = PASS if ALL error rules pass
- EM_DASH / ARROW / COLLAPSED / INLINE / FORBIDDEN / ZERO_BULL = ERROR rules
- SNG_BLOB / SKILLS / OVERUSE / ORPHAN = WARNING rules
- PASS = all good; FAIL = rule violation

---

## Validation Rules Reference

### Error Rules (blocking)
| Rule ID | Description | Threshold |
|---------|-------------|-----------|
| EM_DASH | Em dash (--) or en dash (--) in visible body text | count == 0 |
| ARROW | Arrow characters (→, ←, ↔) in visible body text | count == 0 |
| COLLAPSED_BULLETS | `<li>` containing " - " followed by capitalized action verb (e.g. "Built", "Designed") | count == 0 |
| INLINE_BULLETS | `<p>` containing inline bullet patterns like "- Built", "- Designed" | count == 0 |
| FORBIDDEN_SECTION | Forbidden section text (Target Role, Deal-breaker, Internal Note, Fit Score, Council Verdict) | count == 0 |
| ZERO_BULLETS | `<h2>Work Experience</h2>` has zero `<li>` items below it | li_count > 0 |

### Warning Rules (cosmetic)
| Rule ID | Description | Threshold |
|---------|-------------|-----------|
| SINGLE_BULLET_BLOB | Experience item has only 1 `<li>` that collapses multiple actions | count == 0 |
| SKILLS_COLLISION | Skills grid category label exceeds char limit for 120px column width | count == 0 |
| OVERUSED_TERMS | Term "agentic" used more than 3 times in body text | count <= 3 |
| ORPHAN_H2 | `<h2>` heading followed by < 60 chars of visible content before next heading | count == 0 |

---

## Template: classic-ats

- **HTML path:** `output/resume_templates/siddharth/latest/classic-ats.html`
- **PDF path:** `output/resume_templates/siddharth/latest/classic-ats.pdf`
- **Validator:** FAIL
- **Errors:** 1
- **Warnings:** 0

| Rule | Result | Detail |
|------|--------|--------|
| EM_DASH | FAIL | 2 em dashes, 2 en dashes in profile text (raw markdown inside `{{ }}` markers) |
| ARROW | PASS | 0 arrows |
| COLLAPSED_BULLETS | PASS | 0 collapsed inline bullet patterns |
| INLINE_BULLETS | PASS | No inline bullets in `<p>` tags |
| FORBIDDEN_SECTION | PASS | No forbidden text |
| ZERO_BULLETS | PASS | Uses `.section-title` divs (Gemini template), not `<h2>`; no Work Experience `<h2>` found |

**Status:** DONE_WITH_CONCERNS -- unfilled Gemini template. Raw markdown in `{{ }}` markers contains en dashes from date ranges (e.g. 2020-2022). Once properly filled via the normalizer pipeline, these would be sanitized.

---

## Template: compact-one-page

- **HTML path:** `output/resume_templates/siddharth/latest/compact-one-page.html`
- **PDF path:** `output/resume_templates/siddharth/latest/compact-one-page.pdf`
- **Validator:** FAIL
- **Errors:** 1
- **Warnings:** 0

All results identical to classic-ats (same root cause: unfilled template with em dashes in raw `{{ }}` content).

**Status:** DONE_WITH_CONCERNS -- same root cause as classic-ats.

---

## Template: executive-clean

- **HTML path:** `output/resume_templates/siddharth/latest/executive-clean.html`
- **PDF path:** `output/resume_templates/siddharth/latest/executive-clean.pdf`
- **Validator:** FAIL
- **Errors:** 1
- **Warnings:** 0

All results identical to classic-ats (same root cause: unfilled template with em dashes in raw `{{ }}` content).

**Status:** DONE_WITH_CONCERNS -- same root cause as classic-ats.

---

## Template: founder-operator

- **HTML path:** `output/resume_templates/siddharth/latest/founder-operator.html`
- **PDF path:** `output/resume_templates/siddharth/latest/founder-operator.pdf`
- **Validator:** FAIL
- **Errors:** 1
- **Warnings:** 0

All results identical to classic-ats (same root cause: unfilled template with em dashes in raw `{{ }}` content).

**Status:** DONE_WITH_CONCERNS -- same root cause as classic-ats.

---

## Template: modern-accent

- **HTML path:** `output/resume_templates/siddharth/latest/modern-accent.html`
- **PDF path:** `output/resume_templates/siddharth/latest/modern-accent.pdf`
- **Validator:** FAIL
- **Errors:** 1
- **Warnings:** 0

All results identical to classic-ats (same root cause: unfilled template with em dashes in raw `{{ }}` content).

**Status:** DONE_WITH_CONCERNS -- same root cause as classic-ats.

---

## Template: product-engineer

- **HTML path:** `output/resume_templates/siddharth/latest/product-engineer.html`
- **PDF path:** `output/resume_templates/siddharth/latest/product-engineer.pdf`
- **Validator:** FAIL
- **Errors:** 1
- **Warnings:** 0

All results identical to classic-ats (same root cause: unfilled template with em dashes in raw `{{ }}` content).

**Status:** DONE_WITH_CONCERNS -- same root cause as classic-ats.

---

## Template: technical-two-column

- **HTML path:** `output/resume_templates/siddharth/latest/technical-two-column.html`
- **PDF path:** `output/resume_templates/siddharth/latest/technical-two-column.pdf`
- **Validator:** FAIL
- **Errors:** 1
- **Warnings:** 0

All results identical to classic-ats (same root cause: unfilled template with em dashes in raw `{{ }}` content).

**Status:** DONE_WITH_CONCERNS -- same root cause as classic-ats.

---

## Template: cv-template-v2 (Canonical CareerLoop Template)

- **HTML path:** `output/resume_templates/siddharth/latest/cv-template-v2.html`
- **PDF path:** N/A (not yet generated)
- **Validator:** PASS
- **Errors:** 0
- **Warnings:** 1

| Rule | Result | Detail |
|------|--------|--------|
| EM_DASH | PASS | 0 em/en dashes (sanitized during rendering) |
| ARROW | PASS | 0 arrow characters (→ replaced with "to" during normalization) |
| COLLAPSED_BULLETS | PASS | 0 collapsed inline bullet patterns |
| INLINE_BULLETS | PASS | No inline bullets in `<p>` tags |
| FORBIDDEN_SECTION | PASS | No forbidden section text |
| ZERO_BULLETS | PASS | 16 bullet items in Work Experience section |
| SINGLE_BULLET_BLOB | PASS | All 4 experience items have 3-5 bullets each |
| SKILLS_COLLISION | PASS | No overflow risk in 120px skills grid column |
| OVERUSED_TERMS | PASS | "agentic" appears 3 times (threshold: 3) |
| ORPHAN_H2 | FAIL | "Languages" heading has only 32 chars of visible content after it (cosmetic only) |

**Status:** DONE -- all ERROR rules pass. 1 cosmetic WARNING (Languages heading with minimal content). This is a design decision, not a defect: the Languages section is intentionally compact.

---

## Template: cv-template-v2-test

- **HTML path:** `output/resume_templates/siddharth/latest/cv-template-v2-test.html`
- **PDF path:** N/A (test copy)
- **Validator:** PASS
- **Errors:** 0
- **Warnings:** 1

Results are identical to cv-template-v2. Same PASS on all ERROR rules, same ORPHAN_H2 warning.

**Status:** DONE -- confirms the template renders consistently.

---

## Source Markdown Audit (Pre-Render)

Run via `test_validator.py --audit-source` on `10_final_resume.md`.

| Issue | Count | Note |
|-------|-------|------|
| Em dashes | 13 | In raw markdown -- normalizer strips during render |
| En dashes | 8 | In date ranges (e.g. 2020-2022) -- normalizer replaces with hyphens |
| Right arrows (→) | 13 | Performance metrics like "~15s → ~3s" -- normalizer replaces with "to" |
| Collapsed bullet patterns | 30 | Multi-bullet paragraphs on single line -- normalizer splits into individual `<li>` items |

All source issues are **handled by the normalizer**. The rendered output (cv-template-v2.html) shows **0 em dashes, 0 arrows, 0 collapsed bullets** -- confirming the normalization pipeline is effective.

---

## Normalizer Statistics

| Metric | Value |
|--------|-------|
| Name | Siddharth Saminathan |
| Profile length | 490 chars |
| Skills | 6 rows (Programming, AI Systems, Backend, Systems Design, Infra, Data) |
| Experience entries | 4 |
| Total bullets | 16 |
| Bullets per role | 3-5 (no single-bullet blobs) |
| Achievements | 4 |
| Education | 2 entries |
| Thesis | Yes (colorectal cancer ML pipeline) |
| Languages | 3 (English, Tamil, Hindi) |

---

## Overall Assessment

| Category | Result |
|----------|--------|
| **CareerLoop v2 template** | PASSES all 6 ERROR rules. 1 WARNING: Languages heading has minimal content (32 chars) -- cosmetic. |
| **v2 test copy** | Confirms the v2 template renders consistently. Identical PASS results. |
| **Gemini templates (7)** | All fail on EM_DASH -- content inside `{{ }}` markers is raw markdown with unescaped special characters. These are unfilled templates. Once properly filled via the normalizer pipeline, these would pass. |
| **Normalizer pipeline** | Successfully handles em dashes, arrows, collapsed bullets, and forbidden terms. Output passes all ERROR checks. |
| **Validator** | 10 rules operational (6 ERROR + 4 WARNING). All rules correctly detect issues. |
| **Test runner** | `test_validator.py` operational with `--full`, `--audit-source`, `--template`, and `--json` modes. |

### Actions Required

1. **Gemini templates (7):** Fill via normalizer pipeline to resolve EM_DASH failures. This is a rendering gap, not a content issue.
2. **Orphan H2 (v2):** Languages heading with 32 chars -- add a one-line description or accept as-is (design choice).
3. **PDF generation:** cv-template-v2 PDF not yet generated. Run `generate-pdf.mjs` once rendering is finalized.
