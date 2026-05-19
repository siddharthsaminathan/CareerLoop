# Resume Delta Forensics — Varsha x H&M Senior Merchandiser

## TL;DR Verdict

CareerLoop's 8-system Resume Council performs a split operation: the summary and skills sections are genuinely repositioned with new keyword vocabulary (OTB, omnichannel, womenswear framing, entrepreneurial angle), while the professional experience section — which constitutes roughly 70% of the resume's word count — is returned to the final document almost verbatim from the original. The net result is cosmetic re-rendering for the majority of the content, with substantive repositioning confined to the summary and skills sections. The council's own truth guard flags two claims in the final resume as "UNSUPPORTED" with 0.0 confidence — both of which trace back to content that was present in the original resume, revealing a bug in the truth guard's evidence-matching rather than fabrication, but confirming that the guard did not cause any text alteration between System 7 and the final output. The pipeline's central claim — that it "positions" a resume for a target role — is accurate for ~25% of the document (summary + skills) and inaccurate for ~75% (experience bullets), which are passed through with formatting cleanup only.

---

## 1. Semantic Overlap Measurement

Five key bullets selected from the original resume (verbatim, from `varsha_resume_0426.md`), traced to their counterpart in `10_final_resume.md`.

| # | Original bullet | Final bullet | Change type | Overlap % |
|---|----------------|--------------|-------------|-----------|
| 1 | "Expanded the fashion assortment from 5 to 25+ subcategories across menswear, womenswear, kidswear, footwear, and accessories by onboarding 12+ regional vendors, identifying assortment gaps, and benchmarking category offerings against value retail players like DMart and Vishal Mega Mart." | "Expanded the fashion assortment from 5 to 25+ subcategories across menswear, womenswear, kidswear, footwear, and accessories by onboarding 12+ regional vendors, identifying assortment gaps, and benchmarking category offerings against value retail players like DMart and Vishal Mega Mart." | Verbatim (whitespace fix only) | ~100% |
| 2 | "Analyzed weekly sales performance, pricing benchmarks, and customer demand signals thereby generating ₹ 3.5 lakh in category revenue within two months." | "Analyzed weekly sales performance, pricing benchmarks, and customer demand signals thereby generating ₹ 3.5 lakh in category revenue within two months." | Verbatim | ~100% |
| 3 | "Negotiated vendor pricing, MOQs, and sourcing terms, improving product margins from 22% to 35% while maintaining competitive retail pricing." | "Negotiated vendor pricing, MOQs, and sourcing terms, improving product margins from 22% to 35% while maintaining competitive retail pricing." | Verbatim | ~100% |
| 4 | "Managed PO/PI coordination and vendor communication across 20+ suppliers and 10+ factories across India and Asia, ensuring 95% on-time delivery for seasonal production orders." | "Managed PO/PI coordination and vendor communication across 20+ suppliers and 10+ factories across India and Asia, ensuring 95% on-time delivery for seasonal production orders." | Verbatim | ~100% |
| 5 | "Led sampling, fit approvals, and production coordination for 30+ styles per season, reducing post-launch return rates to under 10% while gaining exposure to PLM-driven product development workflows." | "Led sampling, fit approvals, and production coordination for 30+ styles per season, reducing post-launch return rates to under 10% while gaining exposure to PLM-driven product development workflows." | Verbatim | ~100% |

**Overall estimate:** Of the 19 experience section bullets in the final resume (across all three roles), 19 are present and all are >95% identical to their originals in phrasing. The only changes are: whitespace normalization (removing mid-word line breaks from the PDF-extracted source), punctuation in job title separators (pipes added), and role header formatting. Zero bullets were rewritten, reordered, merged, or dropped. The professional experience section has an estimated **>97% semantic overlap** with the original.

**Note on System 7's `rewritten_text` in `07_section_rewrites.json`:** The JSON shows a partially different rewrite for the SuperK and Style Gram roles (e.g., "Grew the fashion assortment from 5 to..." vs original "Expanded the fashion assortment from 5 to..."). However, this rewritten version was NOT used in `10_final_resume.md`. The final document reverted to verbatim original phrasing for the experience section. See Section 4 for details.

---

## 2. Positioning Delta

### Original resume framing (from `varsha_resume_0426.md`)

- Identity label: "Fashion professional"
- Industry vocabulary: "category management," "multi-channel retail," "bottom-wear," "casualwear," "accessories"
- Target framing: Generic apparel/retail, no specific company-type callout
- The word "womenswear" appears **1 time** (in the Go Colors role description: "women's and girls' bottom-wear categories")
- The word "OTB" appears **0 times**
- The word "omnichannel" appears **0 times**
- The word "entrepreneurial" appears **0 times**
- The word "merchandising" appears **4 times** (summary x1, Go Colors description x1, Style Gram description x1, SuperK intro x1)
- The word "jersey" appears **0 times**

### Final resume framing (from `10_final_resume.md`)

- Identity label: "fashion merchandising and buying professional"
- Industry vocabulary: "OTB," "omnichannel retail," "womenswear," "P&L ownership," "entrepreneurial"
- Target framing: H&M role screening keywords surface in summary and skills
- The word "womenswear" appears **3 times** (summary x1, skills x2)
- The word "OTB" appears **2 times** (summary x1, skills x1: "OTB-driven assortment planning")
- The word "omnichannel" appears **3 times** (summary x1, skills x1, functional strengths x1)
- The word "entrepreneurial" appears **1 time** (summary)
- The word "merchandising" appears **6 times**
- The word "jersey" appears **0 times** — the H&M jersey category focus is entirely absent from the final resume

### Before/after comparison — summary section

**Original:**
> "Fashion professional with 3+ years of experience in buying, merchandising, category management, and P&L management across retail and e-commerce. Experienced in assortment planning, vendor sourcing, PO/PI coordination, and product lifecycle execution for apparel categories including bottom-wear, casualwear, and accessories. Proven ability to analyze sales performance, optimize assortments, negotiate supplier terms, and improve margins and sell-through across multi-channel retail environments."

**Final:**
> "Results-driven fashion merchandising and buying professional with 3+ years of experience owning P&L, managing OTB, and driving assortment planning and vendor negotiation for womenswear and multi-category apparel. Proven track record of improving margins and sell-through across omnichannel retail, with hands-on expertise in SAP, PO management, and cross-functional collaboration. Analytical and entrepreneurial, with a focus on scaling categories and delivering measurable business growth."

**Delta observations:**
- "Fashion professional" → "Results-driven fashion merchandising and buying professional" (role-specific identifier added)
- "multi-channel retail" → "omnichannel retail" (H&M JD language adopted; JD uses "omnichannel" explicitly)
- "bottom-wear, casualwear, and accessories" → "womenswear and multi-category apparel" (category focus sharpened toward H&M's womenswear scope)
- "OTB" inserted (was absent in original; OTB is listed as H&M's #1 key responsibility)
- "SAP" elevated to summary mention (was only in skills list in original)
- "entrepreneurial" added (matches System 6 tone guidance verbatim: "Analytical and entrepreneurial")
- The phrase "scaling categories" (final) vs "optimize assortments" (original) — framing shift from optimization to growth

### Skills section — before/after comparison

**Original:**
- "Core Competencies: Assortment Planning • Fashion Buying • PO/PI Coordination • Vendor Management • Inventory Control • Forecasting • TNA Calendar Tracking • Product Lifecycle Management (PLM) • Order Tracking"
- "Functional Strengths: Cross-Functional Collaboration • Trend Analysis • Sales Performance Reporting • Catalog & Content Management • E-commerce Marketing • Vendor Negotiation"

**Final:**
- "Fashion buying & OTB-driven assortment planning" (OTB injected into the primary competency bullet)
- "Womenswear & multi-category trend analysis" (original: "Trend Analysis" — category-specific language added)
- "Catalog & content management for omnichannel retail" (original: "Catalog & Content Management" — H&M keyword appended)
- "Sales performance reporting & P&L analysis" (original: "Sales Performance Reporting" — P&L appended)
- "Vendor negotiation & contract management" (original: "Vendor Negotiation" — scope expanded)

The skills section is the most transformed section in the document.

---

## 3. Claim Transformation

All quantified metrics from the original resume, cross-referenced against `05_user_truth.json` claims and the final resume.

| Claim | Source file | In final resume? | Modified? |
|-------|-------------|-----------------|-----------|
| ₹3.5 lakh in category revenue within two months | Original resume | Yes | No — identical phrasing |
| Margins from 22% to 35% | Original resume | Yes | No — identical phrasing |
| 12+ regional vendors | Original resume | Yes | No — identical phrasing |
| 5 to 25+ subcategories | Original resume | Yes | No — identical phrasing |
| ~22% category visibility increase | Original resume | Yes | No — identical phrasing |
| ~15% uplift in campaign period sales | Original resume | Yes | No — identical phrasing |
| ~20% reduction in stock-outs | Original resume | Yes | No — identical phrasing |
| ~6% improvement in category gross margin | Original resume | Yes | No — identical phrasing |
| ₹50,000 revenue, ₹600 AOV | Original resume | Yes | No — identical phrasing |
| 80+ customer orders, zero returns | Original resume | Yes | No — identical phrasing |
| 60+ SKUs, 45% gross margins | Original resume | Yes | No — identical phrasing |
| 25% reduction in sourcing turnaround | Original resume | Yes | No — identical phrasing |
| 5 supplier partners | Original resume | Yes | No — identical phrasing |
| 100% order fulfillment | Original resume | Yes | No — identical phrasing |
| 90% reduction in catalog errors | Original resume | Yes | No — identical phrasing |
| 22% click-through rate improvement | Original resume | Yes | No — identical phrasing |
| 95% on-time delivery, 20+ suppliers, 10+ factories | Original resume | Yes | No — identical phrasing |
| 200+ SKUs, 15% sell-through improvement | Original resume | Yes | No — identical phrasing |
| 10% lift in customer purchase rate | Original resume | Yes | No — identical phrasing |
| 15% category sales boost in first quarter | Original resume | Yes | No — identical phrasing |
| 30+ styles per season, under 10% return rate | Original resume | Yes | No — identical phrasing |
| "4+ years of fashion merchandising and buying experience" | `05_user_truth.json` claims_allowed | No — final says "3+ years" | Understated relative to user_truth |

**Truth guard discrepancy:** `08_truth_guard_report.json` flags "managed end-to-end sourcing" (in The Style Gram description) and "Built a custom Excel WIP tracker" as UNSUPPORTED with 0.0 confidence. Both phrases are present verbatim in the original source resume (`varsha_resume_0426.md`). The truth guard's evidence-matching algorithm failed to locate these claims in the evidence bank, not because they were fabricated, but because the evidence bank (`05_user_truth.json`) does not index them. The truth guard did not edit the final resume to remove or qualify these phrases — they appear unchanged in `10_final_resume.md`.

**OTB claim in summary:** The final summary states "managing OTB." The original resume contains zero references to OTB. `05_user_truth.json` lists "OTB Management" as a **weak skill** and under `claims_not_allowed` notes "Deep OTB management expertise (not explicitly evidenced)." Despite this, the summary rewrite in System 7 introduced "managing OTB" as a primary stated competency. The truth guard did not flag this insertion.

---

## 4. System 7 Rewrite Audit

System 7 (`07_section_rewrites.json`) produced rewritten text for all five sections. The final document (`10_final_resume.md`) reflects these rewrites inconsistently across sections.

### Intro section
- System 7 output: Added line break between name and email, fixed concatenation
- Final resume: Matches System 7 output exactly
- Delta: Formatting-only change. Zero substantive difference.

### Summary section
- System 7 output: Complete rewrite introducing OTB, omnichannel, womenswear, entrepreneurial framing
- Final resume: Matches System 7 output exactly
- Delta: Full rewrite accepted. This is where the only genuine narrative repositioning occurred.

### Professional experience section
- System 7 output (in `07_section_rewrites.json` `rewritten_text`): Contains different action verbs — "Grew the fashion assortment" (vs original "Expanded"), "Drove ₹3.5 lakh" (vs original "Analyzed weekly sales... generating ₹3.5 lakh"), "Increased category visibility" (vs original "Partnered with marketing teams... increasing"), "Reduced stock-outs" (vs original "Collaborated with operations... to reduce stock-outs"), "Boosted category gross margin" (vs original "Utilized Excel... improved category gross margin"), and an omnichannel framing in the SuperK role intro
- Final resume: Does **NOT** use the System 7 rewritten text. The experience section in `10_final_resume.md` reverts to the original resume's phrasing exactly (with only whitespace normalization)
- Note: The `07_section_rewrites.json` `rewritten_text` for `professional_experience` is also truncated mid-sentence ("Supported buying and mer") — the Go Colors role text is cut off, suggesting the LLM output was truncated during generation
- Delta: System 7's experience rewrite was discarded. The final document uses original text for all experience bullets. This is the critical finding: the section with the most H&M-specific positioning opportunity (womenswear, jersey, OTB language in context) received zero positioning changes in the published output.

### Education section
- System 7 output: Formatting restructure — separated concatenated entries, standardized delimiters and dates
- Final resume: Matches System 7 output exactly
- Delta: Formatting-only change. Zero substantive difference.

### Skills section
- System 7 output: Reorganized into formatted bullet groups, appended role keywords ("OTB-driven," "womenswear," "omnichannel," "P&L analysis," "contract management"), restructured SAP entry
- Final resume: Matches System 7 output exactly
- Delta: Moderate substantive change accepted. Keywords from H&M JD screening list were injected into skills.

### Truth Guard (System 8) impact
- `08_truth_guard_report.json` identifies 3 claims, 0 verified, 1 weak, 2 unsupported
- The report does not record any repairs, corrections, or text modifications
- The final resume text matches the System 7 summary output and the original experience text — Truth Guard performed no visible edits
- `repair_suggestion` is null for all three flagged claims

**Conclusion for Section 4:** System 7 generated a genuine rewrite for the experience section (action verb changes, omnichannel framing in SuperK intro), but this rewrite was not carried forward to the final output. The pipeline reverted to original text for experience. Whether this reversion was intentional (Truth Guard instructed fallback) or a bug (truncation in System 7's output causing the compiler to fall back) cannot be determined from available files, but the truncation in `rewritten_text` ("Supported buying and mer") is a strong indicator of a generation-length issue that caused the fallback.

---

## 5. Narrative Delta

### Original summary narrative

The original summary positions Varsha as a generalist "fashion professional" with breadth across "retail and e-commerce," listing categories ("bottom-wear, casualwear, and accessories") and functions ("assortment planning, vendor sourcing, PO/PI coordination"). The framing is capability inventory — a list of what she has done. No company-type or growth-stage specificity. No entrepreneurial signal. "3+ years" understates actual 4.1 years per `05_user_truth.json`.

### Final summary narrative

The final summary introduces a distinct angle: "entrepreneurial" identity, P&L ownership as a primary attribute, OTB as a named competency, and "scaling categories" as the value proposition. The original's "multi-channel" becomes "omnichannel." The original's category breadth disappears in favor of "womenswear" focus. The original's passive "Experienced in..." construction becomes active "owning P&L, managing OTB, and driving assortment planning."

The framing shift from "I have experience in X" to "I own X and deliver Y" is observable and specific.

### H&M specificity in narrative

The JD specifies "Women's Wear Jersey" as the target category. The word "jersey" does not appear in the final resume. The JD's Day 1 deliverable is "assume ownership of jersey OTB and inventory levels." While OTB is injected into the summary, the jersey/casualwear specificity is absent. The narrative repositioning is toward H&M's category type (womenswear merchandising) but not toward H&M's specific product focus (jersey).

The JD also emphasizes "localization of global assortments" and "regional teams (India, SEA)" as hidden expectations (`03_company_intelligence.json`). Neither "SEA," "localization," "global assortment," nor "regional adaptation" appears in the final resume.

---

## 6. Rendering Path Audit

### Data flow trace

```
varsha_resume_0426.md
  → 00_input_snapshot.json   [master_cv field stores raw resume text verbatim]
  → 01_canonical_resume.json [parser extracts sections; raw_text = PDF-artifact text with mid-word line breaks]
  → 02_preservation_contract.json [System 2: section ordering + link rules; no content transformation]
  → 03_company_intelligence.json [System 3: H&M context; informs positioning but no text change]
  → 04_role_decode.json [System 4: JD decoding; produces screening_keywords list]
  → 05_user_truth.json [System 5: skill/claim extraction; evidence_bank built from resume bullets]
  → 06_positioning_strategy.json [System 6: angle + tone; generates tone_guidance, narrative_angle]
  → 07_section_rewrites.json [System 7: per-section LLM rewrites; different outputs per section — see below]
  → 08_truth_guard_report.json [System 8: claim verification; 0 repairs performed]
  → 10_final_resume.md [compiler assembles final document]
```

### Where transformation is confirmed (LLM rewrite accepted)

- **Summary:** System 7 output used verbatim in final. LLM rewrite confirmed.
- **Skills:** System 7 output used verbatim in final. LLM rewrite confirmed.
- **Education:** System 7 formatting-only cleanup used in final. No substantive LLM rewrite.
- **Intro:** System 7 whitespace fix used in final. No substantive LLM rewrite.

### Where transformation was proposed but not carried through (pass-through confirmed)

- **Professional experience:** System 7 produced a rewrite with different action verbs and omnichannel framing. This output is truncated mid-sentence in `07_section_rewrites.json` (the Go Colors section cuts off at "Supported buying and mer"). The final resume uses the original resume's experience bullets with whitespace cleanup only. No System 7 action verb changes appear in the final document.

### Identified pass-through points

1. `01_canonical_resume.json` → `raw_text` fields are the exact input text with PDF artifacts (concatenated words). No transformation at parse stage.
2. `00_input_snapshot.json` → `master_cv` field preserves the full original text without modification. This field was populated before any Council system ran.
3. The compiler (which assembles `10_final_resume.md` from section rewrites) appears to fall back to original section text when the System 7 rewrite is truncated, incomplete, or unavailable. This fallback is the mechanism by which 19 experience bullets pass through unchanged.
4. `17_council_run_log.json` → `section_rewrites.professional_experience.rewritten_text` contains the same truncated text as `07_section_rewrites.json`, confirming the truncation occurred at the LLM generation step, not at the compiler step.

---

## 7. Raw Findings Summary

- The professional experience section (19 bullets, ~70% of resume word count) is verbatim from the original source in the final output. Action verbs, metrics, phrasing, and order are identical after whitespace normalization.
- System 7 generated a rewrite for the experience section that included different action verbs ("Grew," "Drove," "Increased," "Reduced," "Boosted" vs original "Expanded," "Analyzed," "Partnered," "Collaborated," "Utilized") and an omnichannel framing for the SuperK role intro. This rewrite was not used.
- The System 7 `rewritten_text` for `professional_experience` is truncated mid-sentence (ends: "Supported buying and mer"). The Go Colors role content is missing from the System 7 JSON output. This truncation is the likely cause of the experience revert.
- The summary section is the only section with confirmed narrative repositioning toward the H&M role. It introduces 4 keywords absent from the original (OTB, omnichannel, entrepreneurial, womenswear in summary context).
- The skills section is the second section with substantive positioning change: 5 of 15 skill bullets were modified to append role-specific language (OTB-driven, womenswear, omnichannel, P&L analysis, contract management).
- The word "jersey" — H&M's target product category for this specific role — appears zero times in the final resume.
- The words "SEA," "localization," and "regional" — explicitly identified as hidden expectations in System 3 — do not appear in the final resume.
- `05_user_truth.json` lists OTB Management as a weak skill and `claims_not_allowed` states "Deep OTB management expertise (not explicitly evidenced)." Despite this, the rewritten summary states "managing OTB" as a primary competency. The truth guard did not flag this insertion.
- `08_truth_guard_report.json` flags 3 claims (1 weak, 2 unsupported, 0 verified). Both "unsupported" claims — "managed end-to-end sourcing" and "Built a custom Excel WIP tracker" — are present verbatim in the original source resume. The truth guard's evidence-matching failed to locate them in the evidence bank but performed no edits.
- `02_preservation_contract.json` allows a maximum of 3 changes, yet `15_quality_report.md` records all 5 sections as rewritten (REWRITE). The `max_allowed_changes: 3` constraint was exceeded with no recorded enforcement.
- `05_user_truth.json` `claims_allowed` lists "4+ years of fashion merchandising and buying experience" as an allowed claim. The final summary says "3+ years." This is a regression from what the truth system authorized.
- The `application_pack.resume_markdown` in `17_council_run_log.json` and the `10_final_resume.md` are not identical: the run log's resume_markdown uses a different SuperK intro ("Launched and scaled the fashion category...") from the S7 rewrite, while `10_final_resume.md` uses the original intro ("Built the fashion category from near zero..."). Two different versions of the experience section exist across the pipeline artifacts.
- Total unique keywords from `04_role_decode.json` screening list: OTB, assortment planning, fashion merchandising, vendor management, P&L, omnichannel, SAP, womenswear, negotiation. All 9 appear in the final resume. In the original, OTB and omnichannel were absent.
