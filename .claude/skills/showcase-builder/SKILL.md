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
  - any request matching: "build a [company/role] application page"
platforms:
  - claude-code
  - gemini-cli
---

# Showcase Builder Skill

You build premium editorial HTML showcase pages for career applications, portfolios, and founder-office artifacts.

## CANONICAL TEMPLATE

The template at `templates/showcase-template.html` is the source of truth. ALWAYS start from this template. It defines:
- Typography scale (Playfair Display 66px hero → DM Sans 17px body)
- Component library (hero, metrics-grid, lessons-grid, pipeline, mapping-grid, principles-row, closing, contact-card, float-cta)
- Animation system (reveal, reveal-left, stagger with 80ms delays, orbFloat, count-up)
- Grain texture overlay (SVG filter, 0.025 opacity)
- Print CSS (@media print, A4)
- Responsive breakpoints (780px)
- Reduced motion support

## DESIGN SYSTEM

### Typography
```
Display: Playfair Display (serif) — 400, 500, 700 weight + italic
Body:    DM Sans (sans) — 300, 400, 500 weight
Hero:    66px / 500 / -0.025em
H2:      40px / 500 / -0.015em
Body:    17px / 300 / 1.7 line-height
Metrics: 48px / 400 / -0.025em
Labels:  10px / 500 / uppercase / 0.12em letter-spacing
```

### Layout
```
max-width: 960px
section margin: 100px
hero padding: 88px top
page padding: 0 52px 120px
```

### Components
```
.hero            — overline-with-line + h1 + subhead + cta buttons + identity
.metrics-grid    — 4-col, 1px gap, accent hover bg
.lessons-grid    — 3-col, 1px gap, italic lesson numbers
.pipeline-wrap   — border-left accent, 7 dots with connecting lines
.mapping-grid    — 2×2, domain label + title + body
.principles-row  — 4-col, large italic numbers that brighten on hover
.closing         — centered italic quote with curly quotes, contact-card
.float-cta       — fixed bottom-right floating buttons (appear on scroll)
.bg-orbs         — 3 floating blurred gradient orbs (optional, decorative)
```

### Animations
```
.reveal         — opacity 0→1, translateY 36px→0, 0.9s ease
.reveal-left    — opacity 0→1, translateX -24px→0, 0.8s ease
.stagger        — children reveal with 80ms delays (8 children max)
.count-up       — requestAnimationFrame, cubic ease-out
.hover          — translateY(-3px), box-shadow, bg transition
.float-cta      — appears after hero scrolls past
```

---

## COLOR VARIANTS

Choose based on context. Replace CSS variables in `:root`.

### 1. Warm Earth (default — design brands, lifestyle, D2C)
```
--paper: #f9f6f1;
--surface: #f2ede5;
--ink: #18130e;
--ink-mid: #3d3128;
--slate: #4a3f35;
--muted: #8a7a6a;
--rule: #ddd5c8;
--accent: #9c6b3c;
--accent-deep: #7a5228;
--accent-mid: #b8834e;
--accent-soft: #f0e4d4;
--accent-softer: #f7f0e8;
```
Use for: Nicobar, design brands, lifestyle, D2C, consumer, hospitality

### 2. Deep Ocean (enterprise, SaaS, AI platforms, fintech)
```
--paper: #f7f9fb;
--surface: #edf1f7;
--ink: #0f1729;
--ink-mid: #1e3148;
--slate: #3b5068;
--muted: #6b8299;
--rule: #d4dde8;
--accent: #2c5f8a;
--accent-deep: #1d3f5e;
--accent-mid: #4a7fad;
--accent-soft: #e4edf5;
--accent-softer: #f0f4f9;
```
Use for: enterprise SaaS, fintech, data platforms, security, B2B

### 3. Forest (climate, health, biotech, wellness, education)
```
--paper: #f8faf6;
--surface: #eef2ea;
--ink: #1a2218;
--ink-mid: #354030;
--slate: #4a5a44;
--muted: #6d8066;
--rule: #d2dbcc;
--accent: #5a7844;
--accent-deep: #3f562f;
--accent-mid: #7a9a62;
--accent-soft: #e8f0e0;
--accent-softer: #f2f7ee;
```
Use for: climate tech, health, biotech, wellness, education, sustainability

### 4. Merlot (creative, media, publishing, luxury, fashion)
```
--paper: #faf7f6;
--surface: #f4eeec;
--ink: #1f1518;
--ink-mid: #423035;
--slate: #5a4348;
--muted: #8a7075;
--rule: #dbcccf;
--accent: #8b3a4a;
--accent-deep: #622a36;
--accent-mid: #ad5a6a;
--accent-soft: #f2e0e4;
--accent-softer: #f8eff1;
```
Use for: creative agencies, media, publishing, luxury, fashion, art

### 5. Slate (consulting, legal, finance, government, traditional)
```
--paper: #fafaf9;
--surface: #f2f2f0;
--ink: #1a1c1e;
--ink-mid: #3a3e42;
--slate: #52585e;
--muted: #7d8389;
--rule: #d6d8db;
--accent: #4a5568;
--accent-deep: #2d3343;
--accent-mid: #6b7a94;
--accent-soft: #e6e9ee;
--accent-softer: #f2f4f6;
```
Use for: consulting, legal, finance, government, traditional enterprise

---

## WHAT YOU NEED FROM THE USER

Ask for (or extract from existing data):
1. **Name, role, location, links** (GitHub, portfolio, email, phone)
2. **Target company + role** — who is this for?
3. **Color variant** — pick from the 5 above based on company context
4. **Thesis headline** — one strong statement (supports italic emphasis on key word)
5. **Evidence metrics** — 6-8 numbers with labels, meanings, and periods
6. **Key lessons** — 4-6 things learned (numbered, 1-2 sentences each)
7. **Acquisition/growth story** — pipeline steps + 4 metrics
8. **Company mapping** — 4 domain cards translating experience to target role
9. **Working principles** — 4 principles of how they build
10. **Closing statement** — short, humble, 1-2 sentences

If the user doesn't have all of these, build with what they give you. NEVER invent metrics.

## OUTPUT

Always produce:
1. HTML → `output/showcase-{slug}.html`
2. PDF → `output/showcase-{slug}.pdf`  
3. Desktop copy → `~/Desktop/{Name}_{Company}_Application.*`

Always report absolute paths.

## RULES

- ALWAYS start from `templates/showcase-template.html`
- NEVER invent metrics. Only use what the user provides.
- NEVER use dark mode for application pages. Light mode only.
- NEVER use "not demos", "not POCs", "I've already built what you're looking for" language.
- NEVER skip the frontend-design skill for design direction.
- ALWAYS validate PDF exports.
- ALWAYS report absolute paths to the user.
- PICK the right color variant for the company context.
