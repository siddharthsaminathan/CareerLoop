# Career-Ops -- AI Job Search Pipeline

## Origin

This system was built and used by [santifer](https://santifer.io) to evaluate 740+ job offers, generate 100+ tailored CVs, and land a Head of Applied AI role. The archetypes, scoring logic, negotiation scripts, and proof point structure all reflect his specific career search in AI/automation roles.

The portfolio that goes with this system is also open source: [cv-santiago](https://github.com/santifer/cv-santiago).

**It will work out of the box, but it's designed to be made yours.** If the archetypes don't match your career, the modes are in the wrong language, or the scoring doesn't fit your priorities -- just ask. You (AI Agent) can edit the user's files. The user says "change the archetypes to data engineering roles" and you do it. That's the whole point.

## Data Contract (CRITICAL)

There are two layers. Read `DATA_CONTRACT.md` for the full list.

**User Layer (NEVER auto-updated, personalization goes HERE):**
- `cv.md`, `config/profile.yml`, `modes/_profile.md`, `article-digest.md`, `portals.yml`
- `data/*`, `reports/*`, `output/*`, `interview-prep/*`

**System Layer (auto-updatable, DON'T put user data here):**
- `modes/_shared.md`, `modes/oferta.md`, all other modes
- `AGENTS.md`, `CLAUDE.md`, `*.mjs` scripts, `dashboard/*`, `templates/*`, `batch/*`

**THE RULE: When the user asks to customize anything (archetypes, narrative, negotiation scripts, proof points, location policy, comp targets), ALWAYS write to `modes/_profile.md` or `config/profile.yml`. NEVER edit `modes/_shared.md` for user-specific content.** This ensures system updates don't overwrite their customizations.

## CareerLoop Product Lead (Session Start — All Agents)

On the first message of every session, after the update check, run the product engineering lead silently:

1. Read `docs/product/PRD.md`
2. Read `docs/tech-backlog/TRACKER.md`
3. Run `git log --oneline -15`
4. Output **3 bullets max** in this format (no headers, no preamble):

```
[product-lead] Last session: <what was done in 1 line>.
Aligned to: PRD §<N> (<system name>). Status: <system>% → estimated <new>%.
Watch: <one risk or deviation to keep in mind>.
```

Full review instructions are in `.claude/skills/careerloop-product-lead/SKILL.md`.  
On-demand: invoke `/careerloop-product-lead` (Claude Code) or `/careerloop-product-lead` (Gemini CLI) for a full review with tracker update.

**Key docs:**
| File | Purpose |
|------|---------|
| `docs/product/PRD.md` | Canonical product vision — source of truth for all engineering |
| `docs/tech-backlog/TRACKER.md` | Rolling session log + live system status |
| `docs/product/vision_v1.6_historical.md` | Historical vision v1.6 |
| `docs/engineering/breakdown-20-part.md` | Architecture breakdown reference |
| `docs/engineering/resume-council-vision.md` | Resume Council 8-system spec |

---

## Update Check

On the first message of each session, run the update checker silently:

```bash
node update-system.mjs check
```

Parse the JSON output:
- `{"status": "update-available", "local": "1.0.0", "remote": "1.1.0", "changelog": "..."}` → tell the user:
  > "career-ops update available (v{local} → v{remote}). Your data (CV, profile, tracker, reports) will NOT be touched. Want me to update?"
  If yes → run `node update-system.mjs apply`. If no → run `node update-system.mjs dismiss`.
- `{"status": "up-to-date"}` → say nothing
- `{"status": "dismissed"}` → say nothing
- `{"status": "offline"}` → say nothing
- `{"status": "no-remote-version"}` → say nothing (checker reached GitHub but neither VERSION nor the latest release tag parsed as semver — treat as a silent non-failure, same as offline)

The user can also say "check for updates" or "update career-ops" at any time to force a check.
To rollback: `node update-system.mjs rollback`

## What is career-ops

AI-powered, CLI-agnostic job search automation: pipeline tracking, offer evaluation, CV generation, portal scanning, batch processing. Runs on any AI coding CLI that follows the [open agent skill standard](https://agentskills.io) (Claude Code, Codex, Gemini, OpenCode, Qwen, Copilot, Kimi).

### Main Files

| File | Function |
|------|----------|
| `data/applications.md` | Application tracker |
| `data/pipeline.md` | Inbox of pending URLs |
| `data/scan-history.tsv` | Scanner dedup history |
| `portals.yml` | Query and company config |
| `templates/cv-template.html` | HTML template for CVs |
| `templates/cv-template.tex` | LaTeX/Overleaf template for CVs |
| `generate-pdf.mjs` | Playwright: HTML to PDF |
| `generate-latex.mjs` | LaTeX CV validator + pdflatex compiler |
| `article-digest.md` | Compact proof points from portfolio (optional) |
| `interview-prep/story-bank.md` | Accumulated STAR+R stories across evaluations |
| `interview-prep/{company}-{role}.md` | Company-specific interview intel reports |
| `analyze-patterns.mjs` | Pattern analysis script (JSON output) |
| `followup-cadence.mjs` | Follow-up cadence calculator (JSON output) |
| `data/follow-ups.md` | Follow-up history tracker |
| `scan.mjs` | Zero-token portal scanner — hits Greenhouse/Ashby/Lever APIs directly, zero LLM cost |
| `check-liveness.mjs` | Job posting liveness checker |
| `liveness-core.mjs` | Shared liveness logic (expired signals win over generic Apply text) |
| `reports/` | Evaluation reports (format: `{###}-{company-slug}-{YYYY-MM-DD}.md`). Blocks A-F + G (Posting Legitimacy). Header includes `**Legitimacy:** {tier}`. |

### First Run — Onboarding (IMPORTANT)

**Before doing ANYTHING else, check if the system is set up.** Run these checks silently every time a session starts:

1. Does `cv.md` exist?
2. Does `config/profile.yml` exist (not just profile.example.yml)?
3. Does `modes/_profile.md` exist (not just _profile.template.md)?
4. Does `portals.yml` exist (not just templates/portals.example.yml)?

If `modes/_profile.md` is missing, copy from `modes/_profile.template.md` silently. This is the user's customization file — it will never be overwritten by updates.

**If ANY of these is missing, enter onboarding mode.** Do NOT proceed with evaluations, scans, or any other mode until the basics are in place. Guide the user step by step:

#### Step 1: CV (required)
If `cv.md` is missing, ask:
> "I don't have your CV yet. You can either:
> 1. Paste your CV here and I'll convert it to markdown
> 2. Paste your LinkedIn URL and I'll extract the key info
> 3. Tell me about your experience and I'll draft a CV for you
>
> Which do you prefer?"

Create `cv.md` from whatever they provide. Make it clean markdown with standard sections (Summary, Experience, Projects, Education, Skills).

#### Step 2: Profile (required)
If `config/profile.yml` is missing, copy from `config/profile.example.yml` and then ask:
> "I need a few details to personalize the system:
> - Your full name and email
> - Your location and timezone
> - What roles are you targeting? (e.g., 'Senior Backend Engineer', 'AI Product Manager')
> - Your salary target range
>
> I'll set everything up for you."

Fill in `config/profile.yml` with their answers. For archetypes and targeting narrative, store the user-specific mapping in `modes/_profile.md` or `config/profile.yml` rather than editing `modes/_shared.md`.

#### Step 3: Portals (recommended)
If `portals.yml` is missing:
> "I'll set up the job scanner with 45+ pre-configured companies. Want me to customize the search keywords for your target roles?"

Copy `templates/portals.example.yml` → `portals.yml`. If they gave target roles in Step 2, update `title_filter.positive` to match.

#### Step 4: Tracker
If `data/applications.md` doesn't exist, create it:
```markdown
# Applications Tracker

| # | Date | Company | Role | Score | Status | PDF | Report | Notes |
|---|------|---------|------|-------|--------|-----|--------|-------|
```

#### Step 5: Get to know the user (important for quality)

After the basics are set up, proactively ask for more context. The more you know, the better your evaluations will be:

> "The basics are ready. But the system works much better when it knows you well. Can you tell me more about:
> - What makes you unique? What's your 'superpower' that other candidates don't have?
> - What kind of work excites you? What drains you?
> - Any deal-breakers? (e.g., no on-site, no startups under 20 people, no Java shops)
> - Your best professional achievement — the one you'd lead with in an interview
> - Any projects, articles, or case studies you've published?
>
> The more context you give me, the better I filter. Think of it as onboarding a recruiter — the first week I need to learn about you, then I become invaluable."

Store any insights the user shares in `config/profile.yml` (under narrative), `modes/_profile.md`, or in `article-digest.md` if they share proof points. Do not put user-specific archetypes or framing into `modes/_shared.md`.

**After every evaluation, learn.** If the user says "this score is too high, I wouldn't apply here" or "you missed that I have experience in X", update your understanding in `modes/_profile.md`, `config/profile.yml`, or `article-digest.md`. The system should get smarter with every interaction without putting personalization into system-layer files.

#### Step 6: Ready
Once all files exist, confirm:
> "You're all set! You can now:
> - Paste a job URL to evaluate it
> - Run `/career-ops scan` (or `/career-ops-scan` if using OpenCode) to search portals
> - Run `/career-ops` to see all commands
>
> Everything is customizable — just ask me to change anything.
>
> Tip: Having a personal portfolio dramatically improves your job search. If you don't have one yet, the author's portfolio is also open source: github.com/santifer/cv-santiago — feel free to fork it and make it yours."

Then suggest automation:
> "Want me to scan for new offers automatically? I can set up a recurring scan every few days so you don't miss anything. Just say 'scan every 3 days' and I'll configure it."

If the user accepts, use the `/loop` or `/schedule` skill (if available) to set up a recurring `/career-ops scan` (or `/career-ops-scan` if using OpenCode). If those aren't available, suggest adding a cron job or remind them to run `/career-ops scan` (or `/career-ops-scan` if using OpenCode) periodically.

### Personalization

This system is designed to be customized by YOU (AI Agent). When the user asks you to change archetypes, translate modes, adjust scoring, add companies, or modify negotiation scripts -- do it directly. You read the same files you use, so you know exactly what to edit.

**Common customization requests:**
- "Change the archetypes to [backend/frontend/data/devops] roles" → edit `modes/_profile.md` or `config/profile.yml`
- "Translate the modes to English" → edit all files in `modes/`
- "Add these companies to my portals" → edit `portals.yml`
- "Update my profile" → edit `config/profile.yml`
- "Change the CV template design" → edit `templates/cv-template.html`
- "Adjust the scoring weights" → edit `modes/_profile.md` for user-specific weighting, or edit `modes/_shared.md` and `batch/batch-prompt.md` only when changing the shared system defaults for everyone

### Language Modes

Default modes are in `modes/` (English). Additional language-specific modes are available:

- **German (DACH market):** `modes/de/` — native German translations with DACH-specific vocabulary (13. Monatsgehalt, Probezeit, Kündigungsfrist, AGG, Tarifvertrag, etc.). Includes `_shared.md`, `angebot.md` (evaluation), `bewerben.md` (apply), `pipeline.md`.
- **French (Francophone market):** `modes/fr/` — native French translations with France/Belgium/Switzerland/Luxembourg-specific vocabulary (CDI/CDD, convention collective SYNTEC, RTT, mutuelle, prévoyance, 13e mois, intéressement/participation, titres-restaurant, CSE, portage salarial, etc.). Includes `_shared.md`, `offre.md` (evaluation), `postuler.md` (apply), `pipeline.md`.
- **Japanese (Japan market):** `modes/ja/` — native Japanese translations with Japan-specific vocabulary (正社員, 業務委託, 賞与, 退職金, みなし残業, 年俸制, 36協定, 通勤手当, 住宅手当, etc.). Includes `_shared.md`, `kyujin.md` (evaluation), `oubo.md` (apply), `pipeline.md`.
- **Turkish (Turkey market):** `modes/tr/` — native Turkish translations with Turkey-specific vocabulary (SGK, kıdem tazminatı, ihbar süresi, brüt/net maaş, AGİ, BES, yemek kartı, yol yardımı, TÜFE zammı, etc.). Includes `_shared.md`, `is-ilani.md` (evaluation), `basvuru.md` (apply), `pipeline.md`.

**When to use German modes:** If the user is targeting German-language job postings, lives in DACH, or asks for German output. Either:
1. User says "use German modes" → read from `modes/de/` instead of `modes/`
2. User sets `language.modes_dir: modes/de` in `config/profile.yml` → always use German modes
3. You detect a German JD → suggest switching to German modes

**When to use French modes:** If the user is targeting French-language job postings, lives in France/Belgium/Switzerland/Luxembourg/Quebec, or asks for French output. Either:
1. User says "use French modes" → read from `modes/fr/` instead of `modes/`
2. User sets `language.modes_dir: modes/fr` in `config/profile.yml` → always use French modes
3. You detect a French JD → suggest switching to French modes

**When to use Japanese modes:** If the user is targeting Japanese-language job postings, lives in Japan, or asks for Japanese output. Either:
1. User says "use Japanese modes" → read from `modes/ja/` instead of `modes/`
2. User sets `language.modes_dir: modes/ja` in `config/profile.yml` → always use Japanese modes
3. You detect a Japanese JD → suggest switching to Japanese modes

**When to use Turkish modes:** If the user is targeting Turkish-language job postings, lives in Turkey, or asks for Turkish output. Either:
1. User says "use Turkish modes" → read from `modes/tr/` instead of `modes/`
2. User sets `language.modes_dir: modes/tr` in `config/profile.yml` → always use Turkish modes
3. You detect a Turkish JD → suggest switching to Turkish modes

**When NOT to:** If the user applies to English-language roles, even at French, German, Japanese, or Turkish companies, use the default English modes — *unless* the user has explicitly requested another mode in this conversation, or `language.modes_dir` is set in `config/profile.yml` (the explicit user preference always wins over JD-language detection).

### Skill Modes

| If the user... | Mode |
|----------------|------|
| Pastes JD or URL | auto-pipeline (evaluate + report + PDF + tracker) |
| Asks to evaluate offer | `oferta` |
| Asks to compare offers | `ofertas` |
| Wants LinkedIn outreach | `contacto` |
| Asks for company research | `deep` |
| Preps for interview at specific company | `interview-prep` |
| Wants to generate CV/PDF | `pdf` |
| Evaluates a course/cert | `training` |
| Evaluates portfolio project | `project` |
| Asks about application status | `tracker` |
| Fills out application form | `apply` |
| Searches for new offers | `scan` |
| Processes pending URLs | `pipeline` |
| Batch processes offers | `batch` |
| Asks about rejection patterns or wants to improve targeting | `patterns` |
| Asks about follow-ups or application cadence | `followup` |
| Wants to perform a resume/data quality audit | `audit` |

### CV Source of Truth

- `cv.md` in project root is the canonical CV
- `article-digest.md` has detailed proof points (optional)
- **NEVER hardcode metrics** -- read them from these files at evaluation time

---

## Ethical Use -- CRITICAL

**This system is designed for quality, not quantity.** The goal is to help the user find and apply to roles where there is a genuine match -- not to spam companies with mass applications.

- **NEVER submit an application without the user reviewing it first.** Fill forms, draft answers, generate PDFs -- but always STOP before clicking Submit/Send/Apply. The user makes the final call.
- **Strongly discourage low-fit applications.** If a score is below 4.0/5, explicitly recommend against applying. The user's time and the recruiter's time are both valuable. Only proceed if the user has a specific reason to override the score.
- **Quality over speed.** A well-targeted application to 5 companies beats a generic blast to 50. Guide the user toward fewer, better applications.
- **Respect recruiters' time.** Every application a human reads costs someone's attention. Only send what's worth reading.

---

## Offer Verification -- MANDATORY

**NEVER trust WebSearch/WebFetch to verify if an offer is still active.** ALWAYS use Playwright:
1. `browser_navigate` to the URL
2. `browser_snapshot` to read content
3. Only footer/navbar without JD = closed. Title + description + Apply = active.

**Exception for batch workers (headless mode):** Playwright is not available in headless pipe mode. Use WebFetch as fallback and mark the report header with `**Verification:** unconfirmed (batch mode)`. The user can verify manually later.

---

## CI/CD and Quality

- **GitHub Actions** run on every PR: `test-all.mjs` (63+ checks), auto-labeler (risk-based: 🔴 core-architecture, ⚠️ agent-behavior, 📄 docs), welcome bot for first-time contributors
- **Branch protection** on `main`: status checks must pass before merge. No direct pushes to main (except admin bypass).
- **Dependabot** monitors npm, Go modules, and GitHub Actions for security updates
- **Contributing process**: issue first → discussion → PR with linked issue → CI passes → maintainer review → merge

## Community and Governance

- **Code of Conduct**: Contributor Covenant 2.1 with enforcement actions (see `CODE_OF_CONDUCT.md`)
- **Governance**: BDFL model with contributor ladder — Participant → Contributor → Triager → Reviewer → Maintainer (see `GOVERNANCE.md`)
- **Security**: private vulnerability reporting via email (see `SECURITY.md`)
- **Support**: help questions go to Discord/Discussions, not issues (see `SUPPORT.md`)
- **Discord**: https://discord.gg/8pRpHETxa4

## Headless / Batch Mode

When spawning headless workers for batch processing, use the appropriate command for your CLI:

| CLI | Command |
|-----|---------|
| Claude Code | `claude -p "prompt"` |
| Gemini CLI | `gemini -p "prompt"` |
| Copilot CLI | `copilot -p "prompt"` |
| Codex | `codex exec "prompt"` |
| OpenCode | `opencode run "prompt"` |
| Qwen | `qwen -p "prompt"` |

## Stack and Conventions

- Node.js (mjs modules), Playwright (PDF + scraping), YAML (config), HTML/CSS (template), Markdown (data), Canva MCP (optional visual CV)
- Scripts in `.mjs`, configuration in YAML
- Output in `output/` (gitignored), Reports in `reports/`
- JDs in `jds/` (referenced as `local:jds/{file}` in pipeline.md)
- Batch in `batch/` (gitignored except scripts and prompt)
- Report numbering: sequential 3-digit zero-padded, max existing + 1
- **RULE: After each batch of evaluations, run `node merge-tracker.mjs`** to merge tracker additions and avoid duplications.
- **RULE: NEVER create new entries in applications.md if company+role already exists.** Update the existing entry.

### TSV Format for Tracker Additions

Write one TSV file per evaluation to `batch/tracker-additions/{num}-{company-slug}.tsv`. Single line, 9 tab-separated columns:

```
{num}\t{date}\t{company}\t{role}\t{status}\t{score}/5\t{pdf_emoji}\t[{num}](reports/{num}-{slug}-{date}.md)\t{note}
```

**Column order (IMPORTANT -- status BEFORE score):**
1. `num` -- sequential number (integer)
2. `date` -- YYYY-MM-DD
3. `company` -- short company name
4. `role` -- job title
5. `status` -- canonical status (e.g., `Evaluated`)
6. `score` -- format `X.X/5` (e.g., `4.2/5`)
7. `pdf` -- `✅` or `❌`
8. `report` -- markdown link `[num](reports/...)`
9. `notes` -- one-line summary

**Note:** In applications.md, score comes BEFORE status. The merge script handles this column swap automatically.

### Pipeline Integrity

1. **NEVER edit applications.md to ADD new entries** -- Write TSV in `batch/tracker-additions/` and `merge-tracker.mjs` handles the merge.
2. **YES you can edit applications.md to UPDATE status/notes of existing entries.**
3. All reports MUST include `**URL:**` in the header (between Score and PDF). Include `**Legitimacy:** {tier}` (see Block G in `modes/oferta.md`).
4. All statuses MUST be canonical (see `templates/states.yml`).
5. Health check: `node verify-pipeline.mjs`
6. Normalize statuses: `node normalize-statuses.mjs`
7. Dedup: `node dedup-tracker.mjs`

### Canonical States (applications.md)

**Source of truth:** `templates/states.yml`

| State | When to use |
|-------|-------------|
| `Evaluated` | Report completed, pending decision |
| `Applied` | Application sent |
| `Responded` | Company responded |
| `Interview` | In interview process |
| `Offer` | Offer received |
| `Rejected` | Rejected by company |
| `Discarded` | Discarded by candidate or offer closed |
| `SKIP` | Doesn't fit, don't apply |

**RULES:**
- No markdown bold (`**`) in status field
- No dates in status field (use the date column)
- No extra text (use the notes column)


<claude-mem-context>
# Memory Context

# [CareerLoop] recent context, 2026-05-20 11:17pm GMT+5:30

Legend: 🎯session 🔴bugfix 🟣feature 🔄refactor ✅change 🔵discovery ⚖️decision 🚨security_alert 🔐security_note
Format: ID TIME TYPE TITLE
Fetch details: get_observations([IDs]) | Search: mem-search skill

Stats: 50 obs (21,322t read) | 1,772,777t work | 99% savings

### May 18, 2026
S403 Deploy Nicobar AI Product Engineer showcase HTML to GitHub Pages so animated version is shareable (not raw HTML via Google Drive) (May 18 at 7:53 PM)
### May 19, 2026
S404 Deploy Nicobar showcase HTML to GitHub Pages — hit UI issue where /public folder option doesn't appear (May 19 at 12:55 AM)
S405 Fix GitHub Pages deployment — move showcase from /public to /docs folder so branch source selector works (May 19 at 1:00 AM)
S406 Deploy Nicobar showcase to GitHub Pages — session wrap-up with all outputs committed (May 19 at 1:01 AM)
S407 Session wrap-up: codify Nicobar showcase design system into reusable showcase-builder skill (May 19 at 1:04 AM)
S408 Update showcase-builder skill with final Nicobar HTML as canonical template + 5 named color variants (May 19 at 1:06 AM)
S409 CareerLoop pipeline E2E fix: tailoring delta P0 fix, validator bug fixes, full pipeline run for nicobar-ai-pm job, and output quality review (May 19 at 2:02 AM)
988 10:19p 🔵 Pre-existing Test Failure in test_company_intel: _extract_jd_signals Misses "retail" Business Term
989 " 🔵 All 26 Stabilization Tests Pass After Validator Fix
990 " 🔵 CouncilLLMClient Reads DEEPSEEK_API_KEY via os.getenv — No .env Loading in llm.py
991 10:26p 🔵 Git History Confirms S7 Bug Was Introduced in Commit 93cda15 — "Wrong Model, Wrong max_tokens, Rate Limit, Garbage MD Output"
992 10:27p 🔵 Pipeline Entry Points: test_council_v3.py Uses Fixture Files, orchestrator.py Has Special nicobar-test Case
993 " 🔵 Correct Pipeline Invocation: orchestrator.py CLI with --job-id and --person-id Args
994 " 🔵 Orchestrator Context Loading: CouncilContextLoader Reads from Job Ledger, Fixture Mode Is Separate Path
995 " 🔵 ledger.json Does Not Exist — ApplicationLedger Cannot Find "nicobar-test" Job
996 10:28p 🔴 CareerLoop S7 validator fix confirmed working — 9/10 sections rewritten
997 " 🔵 skills section still fails possible_truncation after validator fix
1014 11:36p 🟣 HeaderInfo.title field + _parse_header_title() extracts declared professional headline
1015 " 🔴 _derive_role_subtitle now prefers HeaderInfo.title over first experience role
1016 " 🔴 _contains_date_range now matches year-only ranges like "2025 - Present"
1017 " 🔴 Sidebar education block now filters out thesis/detail entries, caps at 3 items
1018 " ✅ design-brand-compact palette darkened for stronger contrast
1019 " 🔵 Playwright PDF generation broken in this environment due to macOS Chromium permission denial
1020 " ✅ IMPLEMENTATION_HANDOFF.md created documenting all rendering fixes for nicobar-ai-pm run
1021 " 🟣 CareerLoop session handoff: 12-part Senior Engineer summary of today's 0-to-100 execution
### May 20, 2026
998 3:32a 🔵 CareerLoop State of the Union 2026-05-20 — full system audit documented
999 " 🔵 S7 prompt lacks prescriptive rewrite mandate — root cause of 3.6% tailoring delta
1000 " 🔵 _rewrite_one_section signature and contact-section filter logic confirmed
1001 " 🔵 change_type labels in JSON contradict runtime output — KEEP sections show 80-94% char delta
1003 " 🔴 S7 prompt overhauled to mandate aggressive rewriting — fixes 3.6% tailoring delta
1002 3:34a 🔵 LLM self-reported change_type is unreliable — KEEP sections show 88-94% char delta
1004 " 🔴 S7 prompt overhaul applied and syntax-verified in careerloop/council/graph.py
1005 " 🔴 Tailoring delta fixed: S7 now rewrites 9/9 sections with role-native language injection
1006 3:39a 🟣 S3 Grounded Synthesis — Hallucination Inhibition in company_intel.py
1007 " 🟣 S7 Per-Section Timing Debug + New Diagnostic Artifacts (09_s7_debug.json, 12_humanized_resume.md)
1008 " ⚖️ Company Intel MECE First-Principles Design — New Sprint Direction
S412 Implement all company intel phases (P1+P2+P3) with superpowers/sub-agents — full MECE multi-source research engine upgrade to company_intel.py (May 20 at 3:39 AM)
1009 12:10p 🔵 company_intel.py Architecture Map — Current 3-Layer Design with DuckDuckGo + Playwright
1010 12:11p 🔵 company_intel.py Grounding Status System + S7 Context Generation Architecture
S410 Company Intel MECE first-principles design — audit current S3 engine, map all functional limitations, and produce phased implementation plan for 8-source structured intelligence system (May 20 at 12:11 PM)
S411 Implement all company intel phases (P1+P2+P3) — multi-source research engine with targeted DDG queries, company website scraping, Reddit/Glassdoor/Twitter signals, people layer, and show final s7_rewrite_context output (May 20 at 12:11 PM)
1011 12:27p 🔵 company_intel.py Full Code Audit Before Phase 1-3 Implementation
1012 " 🟣 CompanyIntelligenceResult Schema Extended — Phase 2 People + Culture + Source Tracking Fields
1013 12:28p 🟣 _gather_web_sources() Replaced with MECE 5-Query Parallel Engine + Company Website Scraper
1022 11:11p 🔵 Critical S7 schema mismatch: prompt returns tailored_bullets but code reads rewritten_text
1023 " 🟣 candidate_graph.py: new structured dataclass for canonical candidate identity
1024 " 🔵 S3 company intelligence grounding upgraded to PARTIAL with 4 real sources for Nicobar run
1025 " 🔵 S7 section rewrite quality audit: profile similarity 0.217, Emote experience similarity 0.999 (no actual rewrite)
1026 " 🔵 Humanizer changed 77 lines, 2 slop flags detected, zero slop terms in final output
1027 " 🔵 LinkedIn URL renders as href="#" in 8 of 10 templates — placeholder not resolved
1028 11:13p ⚖️ Product-lead alignment audit agent dispatched to assess S7/S3/rendering work against PRD
1029 " 🔵 CareerLoop PRD canonical vision — 16-part product structure confirmed
1030 " 🔵 CareerLoop system offline at v1.8.0 — core config files all present
1031 11:14p 🔵 CareerLoop product-lead alignment audit — current system status and open blockers
1032 " 🔵 Uncommitted S7 schema migration: rewritten_text → tailored_bullets array in graph.py and schemas.py
1033 " 🟣 CandidateGraph dataclass created as new untracked file — canonical structured identity for Resume Council
1034 " 🔵 PRD-to-code alignment verdict: current S7/company-intel/rendering work is ALIGNED, with one structural risk
1035 11:16p 🔵 S7 section rewrites node uses ThreadPoolExecutor with 3 workers — parallel execution architecture confirmed
1036 " 🔵 Last 10 commits added 39,522 lines — company_intel.py rebuilt from scratch at 1,419 new lines
1037 " 🔵 render_all_templates.py _derive_role_subtitle uses 4-level cascade — header title → recent job role → bolded profile term → profile first sentence

Access 1773k tokens of past work via get_observations([IDs]) or mem-search skill.
</claude-mem-context>