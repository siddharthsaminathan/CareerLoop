# Siddharth x Nicobar Rendering Handoff

## What was fixed

- `design-brand-compact.html` now renders the declared resume headline as the subtitle:
  `AI Product Engineer · Systems Architect`
- The renderer no longer underplays the candidate as only `AI Engineer` by using the first experience role as the page subtitle.
- The normalizer preserves phone numbers that start with `+`, so `+91 7299707403` survives rendering.
- Experience metadata parsing now treats `2025 - Present | Chennai, India` as dates/location, not as a description line.
- Parenthetical product/context labels such as `Omnex Systems (AquaPro AI)` are no longer mistaken for dates.
- The design-brand sidebar education block now shows only actual degrees, not thesis/detail bullets.
- The light palette was darkened slightly for stronger contrast.

## Latest verified HTML

- `rendered/design-brand-compact.html`
- `rendered/design-brand-compact-dark.html`
- `rendered/08_normalized_resume.json`

## Verified facts

- Header title: `AI Product Engineer · Systems Architect`
- Phone: `+91 7299707403`
- Sidebar education: only `M.Sc. Statistics and Machine Learning` and `B.Tech Computer Science & Engineering`
- No `Lovable` or `lovable` string appears in the latest rendered design-brand HTML.
- 10 HTML templates render from `10_final_resume.md`.
- `tests/test_stabilization.py`: 26 passed.

## Important remaining issue

The latest saved `03_company_intelligence.json` in this output folder is still:

- `grounding_status`: `JD_ONLY`
- `confidence`: `0.45`
- `source_urls`: `[]`
- `sources_by_type`: `{}`

That means the resume currently rendered here did not use the richer MECE/web company intelligence, even if the code exists. A cache-busted full Council rerun is still needed before judging whether the improved S3 context is flowing into S7.

## Verification limitation

PDF regeneration and screenshot capture failed in this sandbox because Chromium could not launch due to macOS permission denial. The HTML output was regenerated and inspected directly.
