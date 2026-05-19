---
name: resume-design
description: >
  Design, edit, and render CareerLoop resume templates. When the user wants to
  change design (colors, fonts, layout, spacing, typography, sizing, CSS) on
  any resume template — edit the template, re-render, re-validate, and show
  the results with absolute paths. Also re-run the existing rendering pipeline
  to verify nothing is broken.
triggers:
  - Any request to change resume template design, styling, colors, fonts, layout
  - "make it look more like X", "fix the dark mode", "change the spacing"
  - "render the resume", "generate PDF", "show me the output"
platforms:
  - claude-code
---

# Resume Design Skill

You are the CareerLoop resume template designer. Your job: edit templates, re-render, validate, show absolute paths.

## TEMPLATES

| Path | Purpose |
|------|---------|
| `templates/design-brand-compact.html` | Nicobar — warm editorial |
| `templates/compact-sidebar-premium.html` | Enterprise — clean sidebar |
| `templates/cv-template-v2.html` | General — industrial editorial |
| `templates/cv-template.html` | Original Career-Ops |

## INPUT DATA

Always use this resume for rendering:
```
output/council/siddharth/nicobar-final/10_final_resume.md
```

## RENDER COMMAND

```bash
cd <project_root> && \
source .venv/bin/activate && \
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null && \
PYTHONPATH=. python3 fill-template.py \
  output/council/siddharth/nicobar-final/10_final_resume.md \
  templates/<TEMPLATE_FILE> \
  output/<OUTPUT_DIR>/<NAME>.html \
  --theme light
```

## PDF COMMAND

```bash
node generate-pdf.mjs \
  output/<OUTPUT_DIR>/<NAME>.html \
  output/<OUTPUT_DIR>/<NAME>.pdf \
  --format=a4
```

## VALIDATION COMMAND

```bash
cd <project_root> && \
source .venv/bin/activate && \
python3 -c "
from PyPDF2 import PdfReader
reader = PdfReader('output/<OUTPUT_DIR>/<NAME>.pdf')
text = ''
for page in reader.pages: text += page.extract_text() or ''
issues = []
if '**' in text: issues.append(f'**bold ({text.count(\"**\")}x)')
if chr(0x2014) in text: issues.append(f'em-dash')
if chr(0x2192) in text: issues.append(f'arrow')
print(f'Pages: {len(reader.pages)} | {\"❌ \" + \", \".join(issues) if issues else \"✅ CLEAN\"}')
"
```

## DESIGN WORKFLOW

When the user gives a design change:
1. Read the template HTML file
2. Make the CSS change they asked for
3. Save the template
4. Run: clear pycache → render → PDF → validate
5. Report: absolute paths, page count, validation status
6. If validation fails, fix and re-render

## OUTPUT DIRECTORIES

| Template | Output Dir |
|----------|-----------|
| design-brand-compact | `output/design-system/` |
| compact-sidebar-premium | `output/compact-sidebar/` |
| cv-template-v2 | `output/council/siddharth/nicobar-final/` |

## ABSOLUTE PATH REPORT

After every render, ALWAYS show the user:

```
HTML: <project_root>/output/<DIR>/<FILE>.html
PDF:  <project_root>/output/<DIR>/<FILE>.pdf
Status: ✅/❌ | Pages: N | Issues: <list or "none">
```
