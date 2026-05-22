# Dev Blog — 2026-05-22: S7 Final Quality — Job-Aware Chunking + DeepSeek Prose Fallback

## What Was Done

- **`_split_by_job_boundaries()`**: New function that detects employer start boundaries by finding uppercase non-bullet lines that (a) contain no dates themselves and (b) are followed within 3 lines by a date/tenure pattern. Returns one chunk per employer. Falls back to paragraph splitting or single-section if detection fails.
- **False-positive fix**: Role/date lines like "Category Manager – Fashion Nov 2025 – Present" were triggering as job starts (they start uppercase, aren't bullets). Fixed by adding `if _date_pat.search(stripped): continue` — these lines contain dates, company-name lines don't.
- **Prose-paragraph fallback**: DeepSeek non-deterministically returns either `tailored_bullets` (list) or `rewritten_text` (string). The string can be bullet-formatted (`- bullet`) or plain prose paragraphs. Old code: if no `- ` markers found, `return direct` (raw prose). New code: split on blank lines, skip structural header paragraphs (first line contains date), skip short preambles (<60 chars), treat remaining paragraphs as bullets and run scaffold reconstruction on them.
- **5 new `TestJobBoundaryChunking` tests**: 42/42 total pass.
- **E2E confirmed**: Varsha → 3 chunks, Hayagreev → 2 chunks, zero cross-job attribution.

## Key Decisions

- **One chunk per employer, not per paragraph**: Paragraph boundaries are arbitrary (some jobs have 1 paragraph, some have 5). Employer boundaries are semantic. The only correct split unit is the job entry.
- **Date-skip heuristic for boundary detection**: Company-name lines ("SuperK Bangalore, India") never contain dates. Role/date lines ("Category Manager – Fashion Nov 2025 – Present") always do. This one rule correctly separates the two in every test case seen so far.
- **60-char floor for prose fallback**: Short paragraphs in `rewritten_text` are usually company description preamble ("An AI system for emotional sense-making..."). These are ~50-80 chars and should NOT become bullets — they belong in the company description block, handled by the preamble injection. The 60-char floor cuts most of them.
- **Don't hardcode employer names**: All detection is structural (date patterns, bullet patterns, uppercase starts). No entity recognition, no LLM calls. Pure regex. Deterministic, fast, testable.

## Issues Encountered

- **test_three_employers_splits_into_three_chunks FAILING (5 chunks instead of 3)**: Caused by role/date lines being detected as job starts. Fix: date-skip check. Resolved.
- **DeepSeek non-determinism confirmed on Hayagreev**: Same prompt, two different output formats across runs. Prose fallback now makes both paths produce correct bullet output.
- **Education header stripping (Hayagreev)**: LLM removed "Stoa School", "CentraleSupelec", "SSN College" from education section output, leaving only achievement bullets. This is a quality issue, not a structural bug — education doesn't have a scaffold reconstruction path (no company/date header to preserve). Not fixed this session; noted for future.

## Files Changed

- `careerloop/council/graph.py` — `_split_by_job_boundaries()` added; chunking decision updated; prose-paragraph fallback in `_payload_to_rewritten_text()`
- `tests/test_stabilization.py` — `TestJobBoundaryChunking` class (5 tests)
- `docs/tech-backlog/8-PIPELINE-CHECKLIST.md` — S7 bug #10 added as ✅ DONE
- `docs/tech-backlog/TRACKER.md` — session log + system status updated
- `docs/product/PRD.md` — §17 table updated

## Next Session

- **Don't fix more stuff.** Council is at the quality ceiling (93%).
- **Build Recruiter DM Generator** (PRD §19): Use existing company intel (S3) + positioning (S6) to generate a personalized cold LinkedIn DM to a specific hiring manager. Council already generates a `recruiter_message` — this extends it to a named person at a company.
- **Build Follow-Up Intelligence** (PRD §13): Ledger already tracks application state. Add: after 7 days no response → generate follow-up ping; after interview → generate thank-you + check-in. One LLM call each, context from ledger.
- **Multi-user onboarding** (unblocks monetization): `add_person` CLI — CV path + profile YAML → PERSON_CONFIG. Currently 3 hardcoded users. Need this before any real user can onboard.
