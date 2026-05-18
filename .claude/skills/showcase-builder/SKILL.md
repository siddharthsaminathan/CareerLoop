---
name: showcase-builder
description: >
  Build premium editorial portfolio/showcase HTML pages for career applications,
  founder-office artifacts, and personal brand pages. When the user wants a
  polished one-page website for a job application, investor update, portfolio,
  or personal showcase — use frontend-design skill to create a tasteful,
  animated, PDF-exportable HTML page from their profile data.
triggers:
  - "build me a showcase page"
  - "create a portfolio page for me"
  - "make a founder-office application artifact"
  - "I want a personal brand page"
  - "build a page for my job application"
  - "create a polished HTML page like the Nicobar one"
  - "make me a one-page website for my profile"
  - any request matching: "build a [company/role] application page"
platforms:
  - claude-code
  - gemini-cli
---

# Showcase Builder Skill

You build premium editorial HTML showcase pages for career applications, portfolios, and founder-office artifacts.

## WHAT YOU BUILD

A single standalone HTML file that:
- Communicates the person's thesis and evidence in 5-7 sections
- Uses premium editorial design (not dashboard cards, not generic SaaS)
- Has tasteful scroll animations and metric count-ups
- Exports cleanly to PDF
- Works as a shareable link or upload

## TEMPLATE REFERENCE

Use this structure. Adapt the content to the person, company, and role.

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <!-- Google Fonts: Cormorant Garamond (display) + Inter (body) -->
  <!-- Warm ivory/charcoal/clay palette -->
  <!-- CSS: grain texture, scroll reveal, count-up, print -->
</head>
<body>
  <div class="page">
    <!-- HERO: thesis headline + identity -->
    <!-- SECTION 1: Evidence/metrics grid (4-col, large numerals) -->
    <!-- SECTION 2: Lessons/learning cards (3x2 grid) -->
    <!-- SECTION 3: Growth/acquisition story (pipeline visual) -->
    <!-- SECTION 4: Why this maps to [target company] (2x2 cards) -->
    <!-- SECTION 5: Working style principles (4-col numbered) -->
    <!-- CLOSING: short, human, tasteful -->
  </div>
  <!-- JS: IntersectionObserver reveal + count-up animation -->
</body>
</html>
```

## DESIGN SYSTEM

### Aesthetic
Refined editorial. Warm, restrained, wabi-sabi precision. Think Stripe annual letter meets Muji catalog.

### Palette (light mode only, no dark mode)
```
Background: #faf8f4 (warm ivory)
Text:       #1f2933 (charcoal)
Secondary:  #5e6b78 (slate)
Muted:      #9b8e84 (warm gray)
Accent:     #b07d62 (muted clay/terracotta)
Dividers:   #e5ded4 (warm gray)
```

### Typography
- Display/Headlines: Cormorant Garamond (serif, 300-600 weight)
- Body: Inter (sans, 400-600)
- Metric numerals: Cormorant Garamond, 48px, 300 weight
- Labels: Inter, 9px, 700 weight, uppercase, letter-spaced

### Layout
- 920px max-width, generous 100px section spacing
- 4-column asymmetric metric grid with 1px dividers
- 1px separator grid (not card shadows) for a refined look
- Grain texture overlay (SVG CSS filter, opacity 0.03)

### Animations (tasteful, not gimmicky)
- Scroll reveal: IntersectionObserver, opacity 0→1, translateY 28px→0
- Metric count-up: requestAnimationFrame, cubic ease-out, 1.4s
- Hover lift: transform translateY(-3px), subtle box-shadow
- Pipeline dots: hover fills solid, scales 1.15
- Reduced-motion media query disables all animations

### Print
- @media print with clean page breaks
- Disable animations, grain texture
- A4 margins via @page

## WHAT YOU NEED FROM THE USER

Ask for (or extract from existing data):
1. **Name, role, location, links** (GitHub, portfolio, email, phone)
2. **Target company + role** (who is this for?)
3. **Thesis** — one strong headline summarizing what they do
4. **Evidence metrics** — 6-8 numbers with labels and meanings (retention, users, growth, cost, etc.)
5. **Key lessons** — 4-6 things they learned building their product
6. **Acquisition/growth story** — how they got users (pipeline steps + metrics)
7. **Why this maps to target** — 4 domain cards mapping their experience to target company's JD
8. **Working style** — 4 principles of how they build
9. **Closing statement** — short, humble, human

If the user doesn't have all of these, build with what they give you. NEVER invent metrics.

## THEME VARIANTS

Adapt colors and typography per context:

| Context | Palette | Fonts |
|---------|---------|-------|
| Design brand (Nicobar) | Warm ivory + clay terracotta | Cormorant Garamond + Inter |
| Startup / Founder | Off-white + deep indigo | DM Serif Display + Inter |
| Enterprise / Consulting | White + navy slate | Georgia + system sans |
| Technical / Engineering | Cool white + steel blue | JetBrains Mono headers + Inter |

Default: warm ivory editorial (works for most contexts).

## OUTPUT

Always produce:
1. HTML file → `output/showcase-{slug}.html`
2. PDF file → `output/showcase-{slug}.pdf` (via `node generate-pdf.mjs`)
3. Copy both to `~/Desktop/{Name}_{Company}_Application.*`

Always report absolute paths.

## RULES

- NEVER invent metrics. Only use what the user provides.
- NEVER use dark mode for application pages. Light mode only.
- NEVER use "not demos", "not POCs", "I've already built what you're looking for" language.
- NEVER use generic SaaS dashboard card aesthetics.
- NEVER skip the frontend-design skill invocation — it guides the aesthetic direction.
- ALWAYS validate PDF exports (PyPDF2: 0 **, 0 em dashes, 0 arrows).
- ALWAYS report absolute paths to the user.

## EXISTING REFERENCE

The canonical showcase page is at:
```
/Users/siddharthsaminathan/Projects/CareerLoop/output/nicobar-ai-product-showcase.html
```
Use it as the structural and design reference for all future showcase pages.
