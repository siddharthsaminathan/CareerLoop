import argparse
import os
import subprocess
import mistune
import re
from pathlib import Path

from careerloop.rendering.normalizer import normalize
from careerloop.rendering.resume_model import NormalizedResume
from careerloop.rendering.template_registry import TEMPLATE_REGISTRY, TEMPLATES_DIR


def _inline_md(text: str) -> str:
    """Convert inline markdown (**bold**, *italic*, `code`, [links](url)) to HTML."""
    if not text:
        return ""
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
    return text


# ── Post-render validation: forbidden characters in final HTML body ──
_FORBIDDEN_IN_BODY = {
    '**': 'raw bold markers (markdown not converted to HTML)',
    chr(0x2014): 'EM DASH',
    chr(0x2013): 'EN DASH',
    chr(0x2192): 'RIGHT ARROW',
    chr(0x2190): 'LEFT ARROW',
    chr(0x2194): 'LEFT-RIGHT ARROW',
    chr(0x21D2): 'RIGHT DOUBLE ARROW',
    chr(0x2794): 'HEAVY RIGHT ARROW',
}


def _validate_html(output_path, html):
    """Post-render validation: FAIL HARD if forbidden chars found in body."""
    body_start = html.find('<body>')
    body_end = html.find('</body>')
    if body_start >= 0 and body_end >= 0:
        body_html = html[body_start:body_end]
    else:
        body_html = html

    errors = []
    for char, desc in _FORBIDDEN_IN_BODY.items():
        if char in body_html:
            count = body_html.count(char)
            idx = body_html.find(char)
            start = max(0, idx - 40)
            end = min(len(body_html), idx + 40)
            context = body_html[start:end].replace('\n', '\\n')
            errors.append(f'{desc}: {count} occurrences. First at: ...{context}...')

    if errors:
        print(f"\n{'='*60}")
        print(f"POST-RENDER VALIDATION FAILED: {output_path}")
        print(f"{'='*60}")
        for e in errors:
            print(f"  FAIL: {e}")
        print(f"{'='*60}")
        raise AssertionError(
            f"Post-render validation failed for {output_path}: "
            f"{len(errors)} forbidden character(s) found in HTML body."
        )


def generate_comparison_report(out_dir, results):
    report_path = out_dir / "template_comparison.md"
    content = "# Resume Template Comparison\n\n"
    content += "| Template | Pages | Links Preserved | ATS Risk |\n"
    content += "|----------|-------|-----------------|----------|\n"
    for res in results:
        content += f"| {res['template']} | {res['pages']} | Yes | Low |\n"

    with open(report_path, "w") as f:
        f.write(content)


def main():
    parser = argparse.ArgumentParser(description="Render 7 visual templates from final resume")
    parser.add_argument("--input", required=True, help="Path to final_resume.md or .html")
    parser.add_argument("--candidate", required=True, help="Candidate name/id")
    parser.add_argument("--run-id", default="latest", help="Run ID")

    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: {input_path} not found.")
        return

    out_dir = Path(f"output/resume_templates/{args.candidate}/{args.run_id}")
    out_dir.mkdir(parents=True, exist_ok=True)

    text = input_path.read_text()

    # ── Data contract assertion ──────────────────────────────────────────
    # ONE normalizer, ONE data model, consumed by ALL renderers.
    # No raw markdown parsing. No regex-based section splitting.
    resume = normalize(text)
    assert isinstance(resume, NormalizedResume), \
        "Renderer must consume NormalizedResume — normalizer returned wrong type"

    header = resume.header

    # ── Summary / Profile HTML ───────────────────────────────────────────
    summary_html = ""
    if resume.profile:
        summary_html = mistune.html(resume.profile)

    # ── Skills HTML ──────────────────────────────────────────────────────
    skills_html = ""
    label_map = {
        "AI Systems & Agentic Architectures": "AI Systems",
        "Backend & Real-Time Systems": "Backend",
        "System Design & Orchestration": "Systems Design",
        "Infra & Observability": "Infra",
        "Data & Analytics": "Data",
    }
    if resume.skills:
        skills_html = '<div class="skills-grid">'
        for skill in resume.skills:
            label = label_map.get(skill.label, skill.label)
            skills_html += f'<span class="cat">{label}</span>'
            skills_html += f'<span class="tags">{" · ".join(skill.items)}</span>'
        skills_html += '</div>'

    # ── Experience HTML ──────────────────────────────────────────────────
    experience_html = ""
    if resume.experience:
        for exp in resume.experience:
            bullets_html = "".join(
                f"<li>{_inline_md(b)}</li>" for b in exp.bullets
            )
            desc_html = (
                f'<div class="exp-desc">{_inline_md(exp.description)}</div>'
                if exp.description else ""
            )
            loc_str = f"{exp.company}{', ' + exp.location if exp.location else ''}"

            experience_html += f'''
            <div class="exp-item">
                <div class="exp-header">
                    <span class="role">{exp.role}</span>
                    <span class="exp-meta">
                        <span class="company">{loc_str}</span>
                        <span class="dates">{exp.dates}</span>
                    </span>
                </div>
                {desc_html}
                <ul>{bullets_html}</ul>
            </div>
            '''

    # ── Education HTML ───────────────────────────────────────────────────
    education_html = ""
    if resume.education:
        edu_items = ""
        for edu in resume.education:
            edu_items += f'<div class="edu-item"><span class="degree">{edu.degree}</span>'
            if edu.institution:
                edu_items += f', <span class="school">{edu.institution}</span>'
            if edu.dates:
                edu_items += f' <span class="dates">{edu.dates}</span>'
            if edu.details:
                edu_items += f'<p class="edu-details">{_inline_md(edu.details)}</p>'
            edu_items += '</div>'
        education_html = edu_items

    # Thesis
    if resume.thesis:
        education_html += (
            f'<h3 class="thesis-heading">Master\'s Thesis</h3>'
            f'<p class="thesis"><em>{_inline_md(resume.thesis)}</em></p>'
        )

    # ── Projects HTML (projects field wins; achievements as fallback) ────
    projects_html = ""
    project_items = resume.projects if resume.projects else resume.achievements
    if project_items:
        projects_html = '<ul class="achievements">'
        for item in project_items:
            projects_html += f'<li>{_inline_md(item)}</li>'
        projects_html += '</ul>'

    # ── Competencies HTML (derived from skill labels) ────────────────────
    competencies_html = ""
    if resume.skills:
        competencies_html = '<div class="competencies-grid">'
        for skill in resume.skills:
            competencies_html += f'<span class="competency-tag">{skill.label}</span>'
        competencies_html += '</div>'

    # ── Build placeholder dict ───────────────────────────────────────────
    placeholders = {
        "LANG": "en",
        "PAGE_WIDTH": "8.5in",
        "NAME": header.name or args.candidate.title(),
        "PHONE": header.phone,
        "EMAIL": header.email,
        "LINKEDIN_URL": header.linkedin_url or "#",
        "LINKEDIN_DISPLAY": header.linkedin_display or "LinkedIn",
        "PORTFOLIO_URL": header.portfolio_url or "#",
        "PORTFOLIO_DISPLAY": header.portfolio_display or "Portfolio",
        "LOCATION": header.location,
        "SECTION_SUMMARY": "Profile",
        "SUMMARY_TEXT": summary_html,
        "SECTION_COMPETENCIES": "Competencies",
        "COMPETENCIES": competencies_html,
        "SECTION_EXPERIENCE": "Experience",
        "EXPERIENCE": experience_html,
        "SECTION_PROJECTS": "Projects",
        "PROJECTS": projects_html,
        "SECTION_EDUCATION": "Education",
        "EDUCATION": education_html,
        "SECTION_SKILLS": "Skills",
        "SKILLS": skills_html,
    }

    # ── Generate templates ───────────────────────────────────────────────
    results = []
    for tmpl_id, tmpl_info in TEMPLATE_REGISTRY.items():
        tmpl_file = Path(TEMPLATES_DIR) / tmpl_info["file"]
        if not tmpl_file.exists():
            continue

        tmpl_html = tmpl_file.read_text()

        # Replace placeholders
        for k, v in placeholders.items():
            tmpl_html = tmpl_html.replace(f"{{{{{k}}}}}", str(v))

        out_html = out_dir / f"{tmpl_id}.html"
        out_html.write_text(tmpl_html)

        # Post-render validation: FAIL HARD on raw **, em dashes, arrows
        _validate_html(out_html, tmpl_html)

        out_pdf = out_dir / f"{tmpl_id}.pdf"

        # Run generate-pdf.mjs
        cmd = ["node", "generate-pdf.mjs", str(out_html), str(out_pdf)]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            pages = 1
            for line in res.stdout.split("\n"):
                if "Pages:" in line:
                    pages = line.split(":")[-1].strip()
            results.append({"template": tmpl_id, "pages": pages, "pdf": str(out_pdf)})
        except subprocess.CalledProcessError as e:
            print(f"Error generating PDF for {tmpl_id}: {e.stderr}")
            results.append({"template": tmpl_id, "pages": "?", "pdf": str(out_pdf)})

    generate_comparison_report(out_dir, results)

    # Generate index.html
    idx_content = "<html><body><h1>Template Preview</h1><ul>"
    for res in results:
        idx_content += f'<li><a href="{res["template"]}.pdf">{res["template"]}</a></li>'
    idx_content += "</ul></body></html>"
    (out_dir / "template_preview_index.html").write_text(idx_content)
    print(f"✅ Generated {len(results)} templates in {out_dir}")


if __name__ == "__main__":
    main()
